"""Síntese local e reprodução em um endpoint de saída escolhido."""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
from math import gcd
from scipy.signal import resample_poly


VOICE_MODELS = {
    "pt-br": "pt_BR-cadu-medium",
    "en": "en_US-ljspeech-medium",
    "es": "es_ES-davefx-medium",
}
ENGLISH_VOICES = {
    "en-ljspeech": "en_US-ljspeech-medium",
    "en-joe": "en_US-joe-medium",
}


def voice_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "backend/assets/tts"
    return Path(__file__).resolve().parents[3] / ".build/tts-voices"


class PiperSpeechSynthesizer:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir is not None else voice_directory()
        self._voices = {}

    def preload(self, language: str, voice_id: str | None = None) -> None:
        self._load_voice(language, voice_id)

    def _load_voice(self, language: str, voice_id: str | None = None):
        try:
            model_name = VOICE_MODELS[language]
        except KeyError as exc:
            raise ValueError(f"Não há voz local para o idioma {language}.") from exc
        if voice_id is not None:
            if language != "en" or voice_id not in ENGLISH_VOICES:
                raise ValueError("A voz selecionada não corresponde ao idioma de saída.")
            model_name = ENGLISH_VOICES[voice_id]
        model_path = self.model_dir / f"{model_name}.onnx"
        if not model_path.is_file() or not Path(f"{model_path}.json").is_file():
            raise FileNotFoundError(f"Voz local não encontrada: {model_name}.")
        voice = self._voices.get(model_name)
        if voice is None:
            from piper.voice import PiperVoice

            voice = PiperVoice.load(model_path)
            self._voices[model_name] = voice
        return voice

    def synthesize(self, text: str, language: str, voice_id: str | None = None) -> tuple[np.ndarray, int]:
        voice = self._load_voice(language, voice_id)
        chunks = list(voice.synthesize(text))
        if not chunks:
            return np.empty(0, dtype=np.float32), voice.config.sample_rate
        sample_rate = chunks[0].sample_rate
        return np.concatenate([chunk.audio_float_array for chunk in chunks]), sample_rate


class SoundDeviceAudioSink:
    def __init__(self, device_id: str, *, virtual_microphone: bool = False) -> None:
        if not device_id:
            raise ValueError("Selecione uma saída de áudio para a voz traduzida.")
        self._device_index = int(device_id)
        device = sd.query_devices(self._device_index, kind="output")
        self._sample_rate = int(device["default_samplerate"])
        self._virtual_microphone = virtual_microphone
        self._channels = 2 if virtual_microphone else 1
        if virtual_microphone and int(device.get("max_output_channels", 0)) < 2:
            raise ValueError("O microfone virtual precisa de saída estéreo.")
        if self._sample_rate <= 0:
            raise ValueError("A saída de áudio selecionada não tem frequência válida.")

    def play(self, audio: np.ndarray, sample_rate: int, stop_event: threading.Event) -> None:
        if audio.size == 0 or stop_event.is_set():
            return
        if sample_rate != self._sample_rate:
            divisor = gcd(sample_rate, self._sample_rate)
            audio = resample_poly(
                audio, self._sample_rate // divisor, sample_rate // divisor,
            ).astype(np.float32)
        if self._virtual_microphone:
            # O VB-CABLE usa estéreo por padrão. Duplicar o mono preserva a
            # voz nos dois canais; a margem de 6 dB evita saturar a captura.
            audio = np.clip(audio * 0.5, -1.0, 1.0)
        block = max(1, self._sample_rate // 5)
        with sd.OutputStream(
            samplerate=self._sample_rate, channels=self._channels, dtype="float32",
            device=self._device_index,
        ) as stream:
            for offset in range(0, len(audio), block):
                if stop_event.is_set():
                    break
                samples = audio[offset : offset + block].reshape(-1, 1)
                stream.write(np.repeat(samples, self._channels, axis=1))


class SpeechOutputQueue:
    """Fila limitada para TTS/reprodução sem bloquear o callback de STT."""

    def __init__(
        self,
        synthesizer,
        sink,
        language: str,
        voice_id: str | None = None,
        on_error: Callable[[str], None] | None = None,
        on_playback_state: Callable[[bool], None] | None = None,
        on_notice: Callable[[str], None] | None = None,
    ) -> None:
        self.synthesizer = synthesizer
        self.sink = sink
        self.language = language
        self.voice_id = voice_id
        self.on_error = on_error
        self.on_playback_state = on_playback_state
        self.on_notice = on_notice
        self._last_notice_at = 0.0
        # Uma fala sintetizada pode durar mais que o intervalo entre chunks.
        # Guardar varias frases cria atraso crescente mesmo com STT rapido.
        self._pending: queue.Queue[tuple[str, float]] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._muted = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._worker.start()

    def enqueue(self, text: str) -> None:
        if not text.strip() or self._stop_event.is_set() or self._muted.is_set():
            return
        try:
            self._pending.put_nowait((text, time.monotonic()))
        except queue.Full:
            # Frases antigas já perderam o contexto da chamada.
            self._report_lag()
            try:
                self._pending.get_nowait()
            except queue.Empty:
                pass
            try:
                self._pending.put_nowait((text, time.monotonic()))
            except queue.Full:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        while True:
            try:
                self._pending.get_nowait()
            except queue.Empty:
                break
        if self._worker.is_alive():
            self._worker.join(timeout=2)

    def set_muted(self, muted: bool) -> None:
        if muted:
            self._muted.set()
            while True:
                try:
                    self._pending.get_nowait()
                except queue.Empty:
                    break
        else:
            self._muted.clear()

    def _report_lag(self) -> None:
        if self.on_notice is None:
            return
        now = time.monotonic()
        if now - self._last_notice_at < 5.0:
            return
        self._last_notice_at = now
        self.on_notice("A voz traduzida atrasou; um trecho antigo foi ignorado para acompanhar a chamada.")

    def _run(self) -> None:
        preload = getattr(self.synthesizer, "preload", None)
        if callable(preload):
            try:
                if self.voice_id is None:
                    preload(self.language)
                else:
                    preload(self.language, self.voice_id)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"Falha ao preparar a voz traduzida: {exc}")
        while not self._stop_event.is_set():
            try:
                text, queued_at = self._pending.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                # Se a reproducao anterior ocupou a saida por muito tempo,
                # o texto ainda aparece na transcricao, mas a voz ja seria
                # antiga demais para uma conversa em andamento.
                if self._muted.is_set():
                    continue
                if time.monotonic() - queued_at > 4.0:
                    self._report_lag()
                    continue
                if self.voice_id is None:
                    audio, sample_rate = self.synthesizer.synthesize(text, self.language)
                else:
                    audio, sample_rate = self.synthesizer.synthesize(
                        text, self.language, self.voice_id,
                    )
                if time.monotonic() - queued_at > 4.0 and not self._pending.empty():
                    self._report_lag()
                    continue
                if not self._stop_event.is_set() and not self._muted.is_set():
                    if self.on_playback_state:
                        self.on_playback_state(True)
                    try:
                        self.sink.play(audio, sample_rate, self._playback_stop_signal())
                    finally:
                        if self.on_playback_state:
                            self.on_playback_state(False)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"Falha na voz traduzida: {exc}")

    def _playback_stop_signal(self):
        class StopSignal:
            def is_set(inner_self) -> bool:
                return self._stop_event.is_set() or self._muted.is_set()

        return StopSignal()
