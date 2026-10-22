import math
import queue
import sys
import time
from typing import Callable, Optional, Tuple, Union

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from .windows_com import windows_com_initialized


class AudioSourceError(RuntimeError):
    """Erro de captura com mensagem adequada para exibicao ao usuario."""


def _load_soundcard():
    try:
        import soundcard as sc
    except (ImportError, OSError) as exc:
        raise AudioSourceError(
            "A captura do áudio do sistema não está disponível nesta instalação."
        ) from exc
    return sc


def _to_mono(audio_data: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio_data, dtype=np.float32)
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1, dtype=np.float32)
    elif audio.ndim != 1:
        audio = audio.reshape(-1)
    return np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float32)


def _resample_fixed(
    audio_data: np.ndarray,
    input_sample_rate: int,
    target_sample_rate: int,
    target_samples: int,
) -> np.ndarray:
    """Converte um bloco para mono, taxa alvo e tamanho fixo."""

    mono = _to_mono(audio_data)
    if input_sample_rate == target_sample_rate:
        result = mono
    else:
        gcd = math.gcd(int(input_sample_rate), int(target_sample_rate))
        result = resample_poly(
            mono,
            int(target_sample_rate // gcd),
            int(input_sample_rate // gcd),
        ).astype(np.float32)

    if len(result) > target_samples:
        return result[:target_samples]
    if len(result) < target_samples:
        return np.pad(result, (0, target_samples - len(result)), mode="constant")
    return result.astype(np.float32, copy=False)


def _wasapi_alias_for_default_microphone(sounddevice_module=None) -> int | None:
    """Usa o mesmo microfone padrão do Windows pelo backend de menor latência."""

    sounddevice_module = sounddevice_module or sd
    default = sounddevice_module.query_devices(kind="input")
    name = str(default.get("name", "")).casefold()
    hostapis = sounddevice_module.query_hostapis()
    for index, device in enumerate(sounddevice_module.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        if str(device.get("name", "")).casefold() != name:
            continue
        hostapi = hostapis[int(device["hostapi"])]
        if "wasapi" in str(hostapi["name"]).casefold():
            return index
    return None


class MicrophoneAudioSource:
    """Fonte de audio do microfone em blocos fixos.

    A classe encapsula captura continua, fila de blocos do callback e
    conversao para o formato esperado pela ASR (mono, 16 kHz).
    """

    def __init__(
        self,
        step_duration_s: float = 0.2,
        target_sample_rate: int = 16000,
        input_device: Optional[Union[int, str]] = None,
        passthrough=None,
    ):
        # step_duration_s define a cadencia de leitura usada pela sessao realtime.
        self.step_duration_s = step_duration_s
        self.target_sample_rate = target_sample_rate
        self.target_step_samples = int(target_sample_rate * step_duration_s)
        self.input_device = input_device
        self.passthrough = passthrough

        self.input_sample_rate = target_sample_rate
        self.step_samples = self.target_step_samples
        self.display_name = "Microfone padrão"

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
            selected_device = (
                int(self.input_device) if self.input_device not in (None, "") else None
            )
            if selected_device is None and self.passthrough is not None:
                selected_device = _wasapi_alias_for_default_microphone()
            device_info = sd.query_devices(selected_device, kind="input")
            self.input_sample_rate = int(
                device_info.get("default_samplerate", self.target_sample_rate)
            )
            self.display_name = str(device_info.get("name", "Microfone padrão"))
        except Exception as exc:
            raise AudioSourceError(
                "O microfone selecionado não está disponível. Escolha outra entrada."
            ) from exc

        self.step_samples = int(self.input_sample_rate * self.step_duration_s)
        self._audio_queue = queue.Queue()
        self._audio_remainder = np.zeros(0, dtype=np.float32)

        try:
            if self.passthrough is not None:
                self.passthrough.start(self.input_sample_rate)
            self._stream = sd.InputStream(
                samplerate=self.input_sample_rate,
                channels=1,
                dtype="float32",
                latency="low" if self.passthrough is not None else "high",
                blocksize=0,
                callback=self._audio_callback,
                device=selected_device,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            if self.passthrough is not None:
                self.passthrough.stop()
            raise AudioSourceError(
                "Não foi possível iniciar o microfone ou a rota para o cabo virtual."
            ) from exc

    def close(self) -> None:
        """Encerra o stream de captura com seguranca."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self.passthrough is not None:
            self.passthrough.stop()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback do sounddevice: coloca o bloco bruto na fila."""
        del frames, time_info, status
        if self.passthrough is not None:
            self.passthrough.push(indata[:, 0])
        self._audio_queue.put(indata[:, 0].copy())

    def _resample_to_target(self, audio_data: np.ndarray) -> np.ndarray:
        """Converte o bloco capturado para a taxa alvo (16 kHz)."""
        return _resample_fixed(
            audio_data,
            input_sample_rate=int(self.input_sample_rate),
            target_sample_rate=self.target_sample_rate,
            target_samples=self.target_step_samples,
        )

    def read_step(self, timeout_s: float = 2.0) -> Tuple[np.ndarray, float]:
        """Le um passo de audio padronizado e retorna pico de energia.

        Returns:
            (audio_16k, peak)
            audio_16k: bloco em 16 kHz com tamanho fixo.
            peak: amplitude de pico no bloco valido (usada no VAD simples).
        """
        if self._stream is None:
            raise AudioSourceError("O microfone não foi iniciado corretamente.")

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


class WasapiLoopbackAudioSource:
    """Captura a mistura reproduzida por uma saida usando WASAPI loopback."""

    def __init__(
        self,
        step_duration_s: float = 0.2,
        target_sample_rate: int = 16000,
        output_device: Optional[str] = None,
        capture_sample_rate: int = 48000,
        soundcard_module=None,
        suppress_capture: Optional[Callable[[], bool]] = None,
    ):
        self.step_duration_s = step_duration_s
        self.target_sample_rate = target_sample_rate
        self.target_step_samples = int(target_sample_rate * step_duration_s)
        self.output_device = output_device
        self.input_sample_rate = capture_sample_rate
        self.step_samples = int(capture_sample_rate * step_duration_s)
        self.display_name = "Áudio do sistema"
        self._soundcard_module = soundcard_module
        self._suppress_capture = suppress_capture
        self._recorder_context = None
        self._recorder = None
        self._com_context = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def open(self) -> None:
        if sys.platform != "win32" and self._soundcard_module is None:
            raise AudioSourceError(
                "A captura do áudio do sistema está disponível somente no Windows."
            )

        try:
            com_context = windows_com_initialized()
            com_context.__enter__()
            self._com_context = com_context
            sc = self._soundcard_module or _load_soundcard()
            device_id = self.output_device
            if device_id in (None, ""):
                default_speaker = sc.default_speaker()
                if default_speaker is None:
                    raise AudioSourceError(
                        "Nenhuma saída de áudio padrão foi encontrada no Windows."
                    )
                device_id = str(default_speaker.id)

            loopback = sc.get_microphone(str(device_id), include_loopback=True)
            if not bool(getattr(loopback, "isloopback", False)):
                raise AudioSourceError(
                    "O dispositivo selecionado não oferece captura WASAPI loopback."
                )

            channel_count = max(1, int(getattr(loopback, "channels", 2)))
            # SoundCard documenta dados invalidos ao pedir somente um canal no
            # WASAPI. Capturamos ate dois canais e fazemos o downmix depois.
            channels = list(range(min(2, channel_count)))
            blocksize = max(2048, self.step_samples * 2)
            self._recorder_context = loopback.recorder(
                samplerate=self.input_sample_rate,
                channels=channels,
                blocksize=blocksize,
                exclusive_mode=False,
            )
            self._recorder = self._recorder_context.__enter__()
            self.display_name = f"Áudio do sistema — {loopback.name}"
        except AudioSourceError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise AudioSourceError(
                "Não foi possível iniciar a captura do áudio do sistema. "
                "Verifique a saída selecionada."
            ) from exc

    def close(self) -> None:
        recorder_context = self._recorder_context
        com_context = self._com_context
        self._recorder = None
        self._recorder_context = None
        self._com_context = None
        try:
            if recorder_context is not None:
                recorder_context.__exit__(None, None, None)
        finally:
            if com_context is not None:
                com_context.__exit__(None, None, None)

    def read_step(self, timeout_s: float = 2.0) -> Tuple[np.ndarray, float]:
        del timeout_s
        if self._recorder is None:
            raise AudioSourceError("A captura do áudio do sistema não foi iniciada.")

        try:
            captured = self._recorder.record(numframes=self.step_samples)
        except Exception as exc:
            raise AudioSourceError(
                "A saída de áudio foi desconectada ou ficou indisponível."
            ) from exc

        if self._suppress_capture and self._suppress_capture():
            return np.zeros(self.target_step_samples, dtype=np.float32), 0.0

        mono = _to_mono(captured)
        peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
        normalized = _resample_fixed(
            mono,
            input_sample_rate=self.input_sample_rate,
            target_sample_rate=self.target_sample_rate,
            target_samples=self.target_step_samples,
        )
        return normalized, peak


def create_audio_source(
    source: str,
    device_id: Optional[str] = None,
    step_duration_s: float = 0.2,
    target_sample_rate: int = 16000,
    suppress_capture: Optional[Callable[[], bool]] = None,
):
    """Constroi a fonte solicitada sem expor detalhes de backend para a UI."""

    if source == "loopback":
        return WasapiLoopbackAudioSource(
            step_duration_s=step_duration_s,
            target_sample_rate=target_sample_rate,
            output_device=device_id,
            suppress_capture=suppress_capture,
        )
    return MicrophoneAudioSource(
        step_duration_s=step_duration_s,
        target_sample_rate=target_sample_rate,
        input_device=device_id,
    )
