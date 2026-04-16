import math
import queue
import time
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly


class MicrophoneAudioSource:
    """Fonte de audio do microfone em blocos fixos.

    A classe encapsula captura continua, fila de blocos do callback e
    conversao para o formato esperado pela ASR (mono, 16 kHz).
    """

    def __init__(
        self,
        step_duration_s: float = 0.2,
        target_sample_rate: int = 16000,
        input_device: Optional[int] = None,
    ):
        # step_duration_s define a cadencia de leitura usada pela sessao realtime.
        self.step_duration_s = step_duration_s
        self.target_sample_rate = target_sample_rate
        self.target_step_samples = int(target_sample_rate * step_duration_s)
        self.input_device = input_device

        self.input_sample_rate = target_sample_rate
        self.step_samples = self.target_step_samples

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._audio_remainder = np.zeros(0, dtype=np.float32)
        self._stream: Optional[sd.InputStream] = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def open(self) -> None:
        """Abre o stream de microfone e prepara taxas de captura."""
        try:
            default_input = sd.query_devices(kind="input")
            self.input_sample_rate = int(default_input.get("default_samplerate", self.target_sample_rate))
        except Exception:
            self.input_sample_rate = self.target_sample_rate

        self.step_samples = int(self.input_sample_rate * self.step_duration_s)

        self._stream = sd.InputStream(
            samplerate=self.input_sample_rate,
            channels=1,
            dtype="float32",
            latency="high",
            blocksize=0,
            callback=self._audio_callback,
            device=self.input_device,
        )
        self._stream.start()

    def close(self) -> None:
        """Encerra o stream de captura com seguranca."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback do sounddevice: coloca o bloco bruto na fila."""
        del frames, time_info, status
        self._audio_queue.put(indata[:, 0].copy())

    def _resample_to_target(self, audio_data: np.ndarray) -> np.ndarray:
        """Converte o bloco capturado para a taxa alvo (16 kHz)."""
        if int(self.input_sample_rate) == self.target_sample_rate:
            result = audio_data.astype(np.float32)
        else:
            g = math.gcd(int(self.input_sample_rate), int(self.target_sample_rate))
            up = int(self.target_sample_rate // g)
            down = int(self.input_sample_rate // g)
            result = resample_poly(audio_data, up, down).astype(np.float32)

        if len(result) > self.target_step_samples:
            return result[: self.target_step_samples]
        if len(result) < self.target_step_samples:
            return np.pad(result, (0, self.target_step_samples - len(result)), mode="constant")
        return result

    def read_step(self, timeout_s: float = 2.0) -> Tuple[np.ndarray, float]:
        """Le um passo de audio padronizado e retorna pico de energia.

        Returns:
            (audio_16k, peak)
            audio_16k: bloco em 16 kHz com tamanho fixo.
            peak: amplitude de pico no bloco valido (usada no VAD simples).
        """
        if self._stream is None:
            raise RuntimeError("Audio source is not open.")

        parts = []
        total = 0

        if len(self._audio_remainder) > 0:
            # Reaproveita sobra do ciclo anterior para nao perder amostras.
            parts.append(self._audio_remainder)
            total += len(self._audio_remainder)
            self._audio_remainder = np.zeros(0, dtype=np.float32)

        deadline = time.time() + timeout_s
        while total < self.step_samples and time.time() < deadline:
            read_timeout = max(0.05, deadline - time.time())
            try:
                chunk = self._audio_queue.get(timeout=read_timeout)
            except queue.Empty:
                break

            parts.append(chunk)
            total += len(chunk)

        if total == 0:
            return np.zeros(self.target_step_samples, dtype=np.float32), 0.0

        merged = np.concatenate(parts).astype(np.float32)
        valid_len = min(len(merged), self.step_samples)

        if len(merged) >= self.step_samples:
            input_step = merged[: self.step_samples]
            self._audio_remainder = merged[self.step_samples :]
        else:
            input_step = np.pad(merged, (0, self.step_samples - len(merged)), mode="constant")

        valid = input_step[:valid_len]
        # O pico e calculado antes do padding para refletir somente audio real.
        peak = float(np.max(np.abs(valid))) if len(valid) else 0.0

        audio_16k = self._resample_to_target(input_step)
        return audio_16k, peak
