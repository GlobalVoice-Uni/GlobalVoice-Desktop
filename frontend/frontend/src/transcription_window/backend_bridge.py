from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from backend.app.audio.audio_capture import MicrophoneAudioSource
from backend.app.sessions.realtime_session import RealtimeTranscriptionSession
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

        self._session = RealtimeTranscriptionSession(
            audio_source=audio_source,
            transcriber=transcriber,
            language=request.language,
            context_window=request.context_window,
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
