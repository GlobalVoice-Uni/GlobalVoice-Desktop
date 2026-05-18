import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from .backend_bridge import LocalBackendBridge, SessionRequest, TranscriptionBridge


class RealtimeController(QObject):
    """Controla o ciclo de vida da transcricao sem bloquear a UI.

    A execucao da sessao acontece em thread separada e os resultados voltam
    para a janela por sinais Qt.
    """

    transcript_chunk = Signal(str)
    status_changed = Signal(str)
    error_raised = Signal(str)
    session_finished = Signal(str)
    running_changed = Signal(bool)

    def __init__(
        self,
        bridge_factory: Optional[Callable[[], TranscriptionBridge]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._bridge_factory = bridge_factory or LocalBackendBridge
        self._active_bridge: Optional[TranscriptionBridge] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start_session(self, request: SessionRequest) -> None:
        """Inicia uma nova sessao realtime em thread de fundo."""
        if self._running:
            return

        self._running = True
        self.running_changed.emit(True)
        self.status_changed.emit("Carregando backend de transcrição...")

        self._worker_thread = threading.Thread(
            target=self._run_worker,
            args=(request,),
            daemon=True,
        )
        self._worker_thread.start()

    def stop_session(self) -> None:
        """Solicita parada da sessao em execucao."""
        if not self._running:
            return

        self.status_changed.emit("Encerrando sessao...")
        if self._active_bridge is not None:
            self._active_bridge.stop()

    def _run_worker(self, request: SessionRequest) -> None:
        """Executa sessao e publica eventos de sucesso/erro para a UI."""
        bridge = self._bridge_factory()
        self._active_bridge = bridge

        try:
            final_text = bridge.run(
                request=request,
                on_text=self._emit_chunk,
                on_status=self.status_changed.emit,
            )
            self.session_finished.emit(final_text)
            self.status_changed.emit("Sessao finalizada.")
        except Exception as exc:
            self.error_raised.emit(str(exc))
            self.status_changed.emit("Sessao interrompida por erro.")
        finally:
            self._active_bridge = None
            self._running = False
            self.running_changed.emit(False)

    def _emit_chunk(self, chunk: str) -> None:
        """Repassa trecho transcrito para consumo da janela."""
        if chunk:
            self.transcript_chunk.emit(chunk)
