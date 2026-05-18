from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from backend.app.audio.audio_capture import MicrophoneAudioSource
from backend.app.sessions.realtime_session import RealtimeTranscriptionSession
from backend.app.detectors.speech_detectors import build_speech_detector
from backend.app.transcribers.local_faster_whisper import LocalFasterWhisperTranscriber


@dataclass
class SessionRequest:
    """Parametros de execucao da sessao realtime.

    Este objeto e o formato unico de entrada entre UI e camada de execucao.
    """

    model_size: str = "small"
    device: str = "cpu"
    language: str = "pt-br"
    context_window: int = 0
    max_duration_s: Optional[float] = None

    # Config de detector de fala.
    vad_type: str = "silero"
    speech_peak_threshold: float = 0.0018
    silero_threshold: float = 0.5
    silero_min_silence_ms: int = 120
    silero_speech_pad_ms: int = 30

    # Janelas e limites de segmentacao.
    min_speech_window_s: float = 0.2
    min_silence_window_s: float = 0.4
    max_utterance_s: float = 3.2
    min_utterance_s: float = 0.7

    # Regras de fronteira para cortes forcados.
    boundary_overlap_s: float = 0.45
    tail_guard_words: int = 4
    forced_split_policy: str = "protect_boundary"
    forced_split_extra_tail_words: int = 1


class TranscriptionBridge(Protocol):
    """Contrato da ponte entre frontend e backend.

    Hoje a ponte e local. Futuramente pode ser remota mantendo a mesma API.
    """

    def run(
        self,
        request: SessionRequest,
        on_text: Callable[[str], None],
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Starts a realtime session and returns the final transcript when done."""

    def stop(self) -> None:
        """Requests stop for the running session."""


class LocalBackendBridge:
    """Implementacao atual: roda captura+ASR no mesmo processo da aplicacao."""

    def __init__(self):
        self._session: Optional[RealtimeTranscriptionSession] = None

    def run(
        self,
        request: SessionRequest,
        on_text: Callable[[str], None],
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Monta dependencias locais e executa sessao realtime."""
        audio_source = MicrophoneAudioSource(step_duration_s=0.2, target_sample_rate=16000)
        transcriber = LocalFasterWhisperTranscriber(model_size=request.model_size, device=request.device)
        speech_detector, _ = build_speech_detector(
            vad_type=request.vad_type,
            energy_peak_threshold=request.speech_peak_threshold,
            silero_threshold=request.silero_threshold,
            silero_min_silence_ms=request.silero_min_silence_ms,
            silero_speech_pad_ms=request.silero_speech_pad_ms,
            on_status=on_status,
        )

        self._session = RealtimeTranscriptionSession(
            audio_source=audio_source,
            transcriber=transcriber,
            speech_detector=speech_detector,
            language=request.language,
            context_window=request.context_window,
            speech_peak_threshold=request.speech_peak_threshold,
            min_speech_window_s=request.min_speech_window_s,
            min_silence_window_s=request.min_silence_window_s,
            max_utterance_s=request.max_utterance_s,
            min_utterance_s=request.min_utterance_s,
            boundary_overlap_s=request.boundary_overlap_s,
            tail_guard_words=request.tail_guard_words,
            forced_split_policy=request.forced_split_policy,
            forced_split_extra_tail_words=request.forced_split_extra_tail_words,
        )

        return self._session.run(
            on_text=on_text,
            on_status=on_status,
            max_duration_s=request.max_duration_s,
        )

    def stop(self) -> None:
        """Encaminha pedido de parada para a sessao ativa."""
        if self._session is not None:
            self._session.stop()
