from typing import Callable, Optional, Tuple

import numpy as np

from ..ports import SpeechDetectorPort


class EnergySpeechDetector:
    """Detector de fallback baseado em pico de energia."""

    def __init__(self, peak_threshold: float = 0.0018):
        self.peak_threshold = peak_threshold

    def reset(self) -> None:
        """Sem estado interno para resetar."""

    def detect(self, audio_16k: np.ndarray, peak: float) -> bool:
        del audio_16k
        return peak >= self.peak_threshold


class SileroSpeechDetector:
    """Detector principal de fala em streaming baseado em Silero VAD."""

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        min_silence_duration_ms: int = 120,
        speech_pad_ms: int = 30,
        use_onnx: bool = False,
    ):
        if sample_rate not in (8000, 16000):
            raise ValueError("SileroSpeechDetector suporta apenas 8000 Hz ou 16000 Hz.")

        try:
            from silero_vad import VADIterator, load_silero_vad  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError(
                "Dependencia silero-vad nao encontrada. Instale com: pip install silero-vad"
            ) from exc

        self.sample_rate = sample_rate
        self.frame_samples = 512 if sample_rate == 16000 else 256
        self._model = load_silero_vad(onnx=use_onnx)
        self._iterator = VADIterator(
            self._model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=speech_pad_ms,
        )
        self._speech_active = False

    def reset(self) -> None:
        self._iterator.reset_states()
        self._speech_active = False

    def detect(self, audio_16k: np.ndarray, peak: float) -> bool:
        del peak

        if audio_16k is None or len(audio_16k) == 0:
            return self._speech_active

        # O modelo Silero opera com frames fixos (512 em 16 kHz).
        chunk = np.asarray(audio_16k, dtype=np.float32)
        for start in range(0, len(chunk), self.frame_samples):
            frame = chunk[start : start + self.frame_samples]
            if len(frame) < self.frame_samples:
                frame = np.pad(frame, (0, self.frame_samples - len(frame)), mode="constant")

            event = self._iterator(frame, return_seconds=False)
            if isinstance(event, dict):
                if "start" in event:
                    self._speech_active = True
                if "end" in event:
                    self._speech_active = False

        return self._speech_active


def build_speech_detector(
    vad_type: str,
    energy_peak_threshold: float,
    silero_threshold: float,
    silero_min_silence_ms: int,
    silero_speech_pad_ms: int,
    on_status: Optional[Callable[[str], None]] = None,
) -> Tuple[SpeechDetectorPort, str]:
    """Cria detector conforme configuracao e aplica fallback seguro quando preciso."""
    normalized = (vad_type or "silero").strip().lower()

    if normalized == "silero":
        try:
            detector = SileroSpeechDetector(
                threshold=silero_threshold,
                sample_rate=16000,
                min_silence_duration_ms=silero_min_silence_ms,
                speech_pad_ms=silero_speech_pad_ms,
            )
            if on_status:
                on_status("VAD ativo: Silero.")
            return detector, "silero"
        except Exception as exc:
            if on_status:
                on_status(f"Silero indisponivel ({exc}). Fallback para VAD por energia.")

    detector = EnergySpeechDetector(peak_threshold=energy_peak_threshold)
    if on_status:
        on_status("VAD ativo: energia (fallback).")
    return detector, "energy"
