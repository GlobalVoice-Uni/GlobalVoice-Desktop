from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .backend_bridge import SessionRequest
from .controller import RealtimeController
from .floating_windows import FloatingToolbar, FloatingTranscriptionWindow
from .settings_store import load_settings, save_settings
from .settings_window import SettingsWindow


class MainWindow(QMainWindow):
    """Tela inicial que orquestra as janelas da aplicacao."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Global Voice")
        self.resize(560, 360)

        self.controller = RealtimeController()
        self.settings_window = SettingsWindow()
        self.transcription_window = FloatingTranscriptionWindow()
        self.toolbar = FloatingToolbar()
        self._loading_session = False

        self._build_ui()
        self._connect_signals()
        self._position_floating_windows()
        self._hide_floating_windows()
        self._apply_ui_settings()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("homeCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(16)
        card_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Global Voice")
        title.setObjectName("homeTitle")
        title.setAlignment(Qt.AlignCenter)

        self.start_button = QPushButton("Iniciar")
        self.settings_button = QPushButton("Opcoes")

        self.start_button.setProperty("kind", "primary")
        self.settings_button.setProperty("kind", "secondary")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.setCursor(Qt.PointingHandCursor)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.settings_button)

        card_layout.addWidget(title)
        card_layout.addLayout(button_row)
        layout.addWidget(card)

        self.setStyleSheet(
            """
            QWidget {
                background: #0F1E2D;
                color: #FFFFFF;
                font-family: 'Bahnschrift', 'Segoe UI';
            }
            QFrame#homeCard {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 18px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
            QLabel#homeTitle {
                font-size: 32px;
                font-weight: 700;
                color: #FFFFFF;
            }
            QPushButton {
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton[kind="primary"] {
                background: rgba(52, 56, 214, 0.95);
                color: #FFFFFF;
                border: none;
            }
            QPushButton[kind="secondary"] {
                background: rgba(4, 0, 58, 0.55);
                color: #FFFFFF;
                border: 1px solid rgba(70, 73, 251, 0.5);
            }
            QPushButton[kind="primary"]:hover {
                background: rgba(70, 73, 251, 1);
            }
            QPushButton[kind="secondary"]:hover {
                background: rgba(70, 73, 251, 0.55);
            }
            QPushButton:pressed {
                background: rgba(70, 73, 251, 0.7);
                padding-top: 11px;
                padding-bottom: 9px;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start_clicked)
        self.settings_button.clicked.connect(self._on_settings_clicked)

        self.toolbar.start_btn.clicked.connect(self._on_toolbar_start_clicked)
        self.toolbar.stop_btn.clicked.connect(self._on_toolbar_stop_clicked)
        self.toolbar.clear_btn.clicked.connect(self._on_toolbar_clear_clicked)
        self.toolbar.settings_requested.connect(self._on_settings_clicked)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.status_changed.connect(self._set_status)
        self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

        self.transcription_window.closed.connect(self._on_floating_closed)
        self.toolbar.closed.connect(self._on_floating_closed)

    def _position_floating_windows(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        geo = screen.availableGeometry()
        self.toolbar.move(geo.width() // 2 - self.toolbar.width() // 2, geo.height() - 80)
        self.transcription_window.move(geo.width() - self.transcription_window.width() - 20, 100)

    def _show_floating_windows(self) -> None:
        self._position_floating_windows()
        self.toolbar.show()
        self.transcription_window.show()
        self.toolbar.raise_()
        self.transcription_window.raise_()

    def _hide_floating_windows(self) -> None:
        self.toolbar.hide()
        self.transcription_window.hide()

    def _apply_ui_settings(self) -> None:
        values = load_settings()
        font_size = int(values.get("ui_transcription_font_size", 14))
        self.transcription_window.apply_font_size(font_size)

    def _restore_home(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_floating_closed(self) -> None:
        self.controller.stop_session()
        self._loading_session = False
        self.toolbar.set_idle()
        self.toolbar.set_buttons_state(False)
        self._hide_floating_windows()
        self._restore_home()

    def _build_request(self) -> SessionRequest:
        values = load_settings()
        max_duration = float(values["max_duration_s"])
        max_duration = max_duration if max_duration > 0 else None

        return SessionRequest(
            model_size=values["model_size"],
            device=values["device"],
            language=self.toolbar.get_language_code(self.toolbar.source_combo.currentText()),
            context_window=int(values["context_window"]),
            max_duration_s=max_duration,
            vad_type=values["vad_type"],
            speech_peak_threshold=float(values["speech_peak_threshold"]),
            silero_threshold=float(values["silero_threshold"]),
            silero_min_silence_ms=int(values["silero_min_silence_ms"]),
            silero_speech_pad_ms=int(values["silero_speech_pad_ms"]),
            min_speech_window_s=float(values["min_speech_window_s"]),
            min_silence_window_s=float(values["min_silence_window_s"]),
            max_utterance_s=float(values["max_utterance_s"]),
            min_utterance_s=float(values["min_utterance_s"]),
            boundary_overlap_s=float(values["boundary_overlap_s"]),
            tail_guard_words=int(values["tail_guard_words"]),
            forced_split_policy=values["forced_split_policy"],
            forced_split_extra_tail_words=int(values["forced_split_extra_tail_words"]),
        )

    def _on_start_clicked(self) -> None:
        self._show_floating_windows()
        self.showMinimized()

    def _on_settings_clicked(self) -> None:
        self.settings_window.refresh_from_storage()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _on_toolbar_start_clicked(self) -> None:
        self._show_floating_windows()
        source = self.toolbar.source_combo.currentText()
        target = self.toolbar.target_combo.currentText()
        self._loading_session = True
        self.toolbar.set_connecting()
        self.toolbar.set_buttons_state(True, allow_stop=False)
        self._set_status(f"Conectando ({source} -> {target})...")
        request = self._build_request()
        self.controller.start_session(request)

    def _on_toolbar_stop_clicked(self) -> None:
        self.controller.stop_session()

    def _on_toolbar_clear_clicked(self) -> None:
        self.transcription_window.clear()


    def _on_running_changed(self, is_running: bool) -> None:
        if not is_running:
            self._loading_session = False
            self.toolbar.set_idle()
        self.toolbar.set_buttons_state(is_running, allow_stop=not self._loading_session)

    def _on_transcript_chunk(self, chunk: str) -> None:
        self.transcription_window.append_text(chunk)

    def _on_session_finished(self, final_text: str) -> None:
        if final_text and not self.transcription_window.transcription_area.toPlainText().strip():
            self.transcription_window.append_text(final_text)

    def _on_error(self, message: str) -> None:
        self._loading_session = False
        self.toolbar.set_idle()
        self.toolbar.set_buttons_state(False)
        QMessageBox.critical(self, "Erro na transcricao", message)

    def _set_status(self, message: str) -> None:
        normalized = message.lower()
        if "microfone ativo" in normalized:
            self._loading_session = False
            self.toolbar.set_active(message)
            self.toolbar.set_buttons_state(True, allow_stop=True)
            return
        if any(token in normalized for token in ("carregando", "inicializando", "conectando", "vad ativo", "silero")):
            if self._loading_session:
                self.toolbar.set_connecting(message)
                self.toolbar.set_buttons_state(True, allow_stop=False)
            return
        if any(token in normalized for token in ("sessao finalizada", "sessao interrompida", "encerrando")):
            self._loading_session = False
            self.toolbar.set_idle()
            self.toolbar.set_buttons_state(False)
            return

        self.toolbar.set_status_message(message)
