# Trecho a atualizar em frontend/src/transcription_window/controller.py
from PySide6.QtCore import QObject, Signal
from .backend_bridge import LocalBackendBridge, SessionRequest, TranscriptionBridge, TranslationChunk

class RealtimeController(QObject):
    # Emite o chunk estruturado contendo canal, texto original e tradução
    transcript_chunk = Signal(object)  # TranslationChunk
    status_changed = Signal(str)
    error_raised = Signal(str)
    session_finished = Signal(str)
    running_changed = Signal(bool)

    # ... restante do init e métodos ...

    def _emit_chunk(self, chunk: TranslationChunk | str) -> None:
        """Repassa o trecho gerado para os ouvintes da UI."""
        if chunk:
            self.transcript_chunk.emit(chunk)