from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap, QRadialGradient
from pathlib import Path

from .backend_bridge import SessionRequest
from .controller import RealtimeController
from .dialogs import ask_confirmation, show_error
from .floating_windows import FloatingToolbar, FloatingTranscriptionWindow
from .settings_store import load_settings, save_settings
from .settings_window import SettingsWindow


APP_VERSION = "0.2.1"


def _assets_path() -> Path:
    """Resolve a pasta de assets tanto no workspace quanto no PyInstaller."""
    import sys
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "frontend" / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def _build_logo_fallback(size: int = 96) -> QIcon:
    """Logo de fallback caso o PNG não esteja disponível."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)

    center = size / 2.0
    radius = size * 0.42
    gradient = QRadialGradient(center, center * 0.7, center, center, radius)
    gradient.setColorAt(0.0, QColor("#6366F1"))
    gradient.setColorAt(0.6, QColor("#4F46E5"))
    gradient.setColorAt(1.0, QColor("#3730A3"))

    painter.setBrush(gradient)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    painter.setBrush(QColor("#F8FAFC"))
    bar_width = size * 0.055
    bar_spacing = size * 0.075
    heights = [0.28, 0.52, 0.68, 0.44, 0.32]
    total_width = (len(heights) - 1) * bar_spacing
    start_x = center - total_width / 2.0
    for index, height_ratio in enumerate(heights):
        bar_height = size * height_ratio
        x = start_x + index * bar_spacing - bar_width / 2.0
        y = center - bar_height / 2.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, bar_width, bar_height), bar_width / 2.0, bar_width / 2.0)
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


def _load_logo_icon(size: int = 96) -> QIcon:
    """Carrega o logo da pasta assets, com fallback para o desenho programático."""
    logo_path = _assets_path() / "globalvoice.png"
    if logo_path.is_file():
        return QIcon(str(logo_path))
    return _build_logo_fallback(size)


def _build_play_icon(size: int = 18, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(size * 0.32, size * 0.20)
    path.lineTo(size * 0.78, size * 0.50)
    path.lineTo(size * 0.32, size * 0.80)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _build_gear_icon(size: int = 18, color: str = "#CBD5E1") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    center = size / 2.0
    outer_r = size * 0.38
    inner_r = size * 0.18
    tooth_w = size * 0.18
    tooth_h = size * 0.12
    gear_path = QPainterPath()
    for i in range(8):
        painter.save()
        painter.translate(center, center)
        painter.rotate(i * 45)
        tooth_path = QPainterPath()
        tooth_path.addRoundedRect(-tooth_w / 2.0, -(outer_r + tooth_h), tooth_w, tooth_h, 1.5, 1.5)
        gear_path.addPath(painter.transform().map(tooth_path))
        painter.restore()
    ring_path = QPainterPath()
    ring_path.addEllipse(center - outer_r, center - outer_r, outer_r * 2, outer_r * 2)
    ring_path.addEllipse(center - inner_r, center - inner_r, inner_r * 2, inner_r * 2)
    ring_path.setFillRule(Qt.OddEvenFill)
    gear_path.addPath(ring_path)
    painter.setBrush(QColor(color))
    painter.drawPath(gear_path)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """Tela inicial que orquestra as janelas da aplicacao."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Global Voice")
        self.resize(720, 520)
        self.setMinimumSize(560, 420)

        self.controller = RealtimeController()
        self.settings_window = SettingsWindow(
            controller=self.controller,
            show_controller_errors=False,
        )
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
        root.setObjectName("homeRoot")
        self.setCentralWidget(root)

        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(40, 40, 40, 32)
        outer_layout.setSpacing(0)
        outer_layout.setAlignment(Qt.AlignCenter)

        container = QWidget()
        container.setObjectName("homeContainer")
        container.setMaximumWidth(720)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignCenter)

        # Hero
        hero = QWidget()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 34)
        hero_layout.setSpacing(16)
        hero_layout.setAlignment(Qt.AlignCenter)

        logo_label = QLabel()
        logo_label.setPixmap(_load_logo_icon(96).pixmap(96, 96))
        logo_label.setAlignment(Qt.AlignCenter)

        title = QLabel("Global Voice")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignCenter)

        slogan = QLabel("Tradução simultânea para reuniões online")
        slogan.setObjectName("heroSlogan")
        slogan.setAlignment(Qt.AlignCenter)

        hero_layout.addWidget(logo_label, 0, Qt.AlignCenter)
        hero_layout.addWidget(title)
        hero_layout.addWidget(slogan)

        # Botões
        button_row = QHBoxLayout()
        button_row.setSpacing(14)
        button_row.setAlignment(Qt.AlignCenter)

        self.start_button = QPushButton("  Iniciar")
        self.start_button.setObjectName("startButton")
        self.start_button.setIcon(_build_play_icon(18))
        self.start_button.setFixedHeight(46)
        self.start_button.setMinimumWidth(170)
        self.start_button.setCursor(Qt.PointingHandCursor)

        self.settings_button = QPushButton("  Configurações")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setIcon(_build_gear_icon(18))
        self.settings_button.setFixedHeight(46)
        self.settings_button.setMinimumWidth(190)
        self.settings_button.setCursor(Qt.PointingHandCursor)

        start_shadow = QGraphicsDropShadowEffect(self.start_button)
        start_shadow.setBlurRadius(28)
        start_shadow.setColor(QColor(79, 70, 229, 140))
        start_shadow.setOffset(0, 6)
        self.start_button.setGraphicsEffect(start_shadow)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.settings_button)

        # Rodapé
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(8, 0, 8, 0)
        footer_row.setSpacing(8)

        version_label = QLabel(f"Versão {APP_VERSION}")
        version_label.setObjectName("footerText")

        github_link = QLabel(
            '<a href="https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop" '
            'style="color: #818CF8; text-decoration: none;">Ver no GitHub</a>'
        )
        github_link.setObjectName("footerLink")
        github_link.setOpenExternalLinks(True)

        footer_row.addWidget(version_label)
        footer_row.addStretch(1)
        footer_row.addWidget(github_link)

        container_layout.addWidget(hero)
        container_layout.addLayout(button_row)
        container_layout.addSpacing(48)
        container_layout.addLayout(footer_row)

        outer_layout.addWidget(container)

        self.setStyleSheet(
            """
            QWidget#homeRoot {
                background: qradialgradient(
                    cx:0.5, cy:0.42, radius:0.95,
                    fx:0.5, fy:0.42,
                    stop:0 #131B33,
                    stop:0.55 #0B1224,
                    stop:1 #070B16
                );
                color: #F8FAFC;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Bahnschrift';
            }
            QLabel#heroTitle {
                font-size: 42px;
                font-weight: 700;
                color: #FFFFFF;
                letter-spacing: 0.5px;
            }
            QLabel#heroSlogan {
                font-size: 15px;
                color: #94A3B8;
                letter-spacing: 0.2px;
            }
            QPushButton#startButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6366F1, stop:1 #4F46E5
                );
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 22px;
            }
            QPushButton#startButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #818CF8, stop:1 #6366F1
                );
            }
            QPushButton#startButton:pressed {
                background: #4338CA;
                padding-top: 2px;
            }
            QPushButton#settingsButton {
                background: rgba(30, 41, 59, 0.7);
                color: #E2E8F0;
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 12px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 22px;
            }
            QPushButton#settingsButton:hover {
                background: rgba(99, 102, 241, 0.25);
                border: 1px solid rgba(129, 140, 248, 0.7);
                color: #FFFFFF;
            }
            QPushButton#settingsButton:pressed {
                background: rgba(99, 102, 241, 0.35);
            }
            QLabel#footerText {
                font-size: 11px;
                color: #64748B;
            }
            QLabel#footerLink {
                font-size: 11px;
                color: #818CF8;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start_clicked)
        self.settings_button.clicked.connect(self._on_settings_clicked)

        self.toolbar.start_requested.connect(self._on_toolbar_start_clicked)
        self.toolbar.stop_requested.connect(self._on_toolbar_stop_clicked)
        self.toolbar.ptt_pressed.connect(self._on_ptt_pressed)
        self.toolbar.ptt_released.connect(self._on_ptt_released)
        self.toolbar.microphone_mute_changed.connect(
            self.controller.set_microphone_muted
        )
        self.toolbar.source_language_changed.connect(self._on_source_language_changed)
        self.toolbar.target_language_changed.connect(self._on_target_language_changed)
        self.settings_window.language_pair_changed.connect(
            self._on_settings_language_pair_changed
        )
        self.toolbar.toggle_chat_requested.connect(self._on_toggle_chat)
        self.toolbar.clear_btn.clicked.connect(self._on_toolbar_clear_clicked)
        self.toolbar.settings_requested.connect(self._on_settings_clicked)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.speech_started.connect(self.transcription_window.begin_speech)
        self.controller.voice_activity_changed.connect(self.toolbar.set_voice_activity)
        self.controller.status_changed.connect(self._set_status)
        self.controller.runtime_changed.connect(self.toolbar.set_runtime_status)
        self.controller.runtime_cleared.connect(self.toolbar.reset_runtime_status)
        self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

        self.transcription_window.closed.connect(self._on_transcription_closed)
        self.toolbar.closed.connect(self._on_toolbar_closed)

    def _position_floating_windows(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        values = load_settings()
        toolbar_x = int(values.get("ui_toolbar_x", -1))
        toolbar_y = int(values.get("ui_toolbar_y", -1))
        if toolbar_x >= 0 and toolbar_y >= 0:
            self.toolbar.move(toolbar_x, toolbar_y)
        else:
            self.toolbar.move(
                geo.left() + geo.width() // 2 - self.toolbar.width() // 2,
                geo.bottom() - self.toolbar.height() - 20,
            )
        saved_x = int(values.get("ui_transcription_window_x", -1))
        saved_y = int(values.get("ui_transcription_window_y", -1))
        if saved_x < 0 or saved_y < 0:
            self.transcription_window.move(
                geo.right() - self.transcription_window.width() - 20,
                geo.top() + 100,
            )

    def _show_floating_windows(self) -> None:
        if not self.toolbar.isVisible():
            self._position_floating_windows()
        self.toolbar.show()
        self.transcription_window.show()
        self.transcription_window.raise_()
        self.toolbar.raise_()

    def _hide_floating_windows(self) -> None:
        self.toolbar.hide()
        self.transcription_window.hide()

    def _apply_ui_settings(self) -> None:
        values = load_settings()
        font_size = int(values.get("ui_transcription_font_size", 14))
        self.transcription_window.apply_font_size(font_size)
        capture_mode = values.get("capture_mode", "automatic")
        if values.get("audio_source") == "loopback":
            capture_mode = "automatic"
        self.toolbar.set_capture_mode(capture_mode)
        self.toolbar.set_language_pair(
            values.get("user_language", values.get("language", "pt-br")),
            values.get("meeting_language", "en"),
        )

    def _restore_home(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_transcription_closed(self) -> None:
        self.transcription_window.hide()

    def _on_toolbar_closed(self) -> None:
        self.controller.set_talk_active(False)
        self.controller.set_microphone_muted(False)
        self.toolbar.reset_microphone_state()
        self.controller.stop_session()
        self._loading_session = False
        self.toolbar.set_idle()
        self.toolbar.set_buttons_state(False)
        self._hide_floating_windows()
        self._restore_home()

    def _on_toggle_chat(self) -> None:
        if self.transcription_window.isVisible():
            self.transcription_window.hide()
            return
        self.transcription_window.show()
        self.transcription_window.raise_()
        self.toolbar.raise_()

    def _build_request(self) -> SessionRequest:
        values = load_settings()
        max_duration = float(values["max_duration_s"])
        max_duration = max_duration if max_duration > 0 else None
        audio_source = values.get("audio_source", "microphone")
        capture_mode = values.get("capture_mode", "automatic")
        if audio_source == "loopback":
            capture_mode = "automatic"

        user_language = str(
            self.toolbar.source_combo.currentData()
            or values.get("user_language", "pt-br")
        )
        meeting_language = str(
            self.toolbar.target_combo.currentData()
            or values.get("meeting_language", "en")
        )
        recognition_language = (
            meeting_language if audio_source == "loopback" else user_language
        )

        return SessionRequest(
            model_size=values["model_size"],
            device=values["device"],
            language=recognition_language,
            target_language=user_language,
            display_mode=values.get("display_mode", "translation_only"),
            capture_mode=capture_mode,
            audio_source=audio_source,
            audio_device_id=values.get("audio_device_id") or None,
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
        if not self.settings_window.has_unsaved_changes():
            self.settings_window.refresh_from_storage()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _on_toolbar_start_clicked(self) -> None:
        self._show_floating_windows()
        values = load_settings()
        capture_mode = values.get("capture_mode", "automatic")
        if values.get("audio_source") == "loopback":
            capture_mode = "automatic"
        self.toolbar.set_capture_mode(capture_mode)
        self.toolbar.set_language_pair(
            values.get("user_language", values.get("language", "pt-br")),
            values.get("meeting_language", "en"),
        )
        source = (
            "áudio da reunião"
            if values.get("audio_source") == "loopback"
            else self.toolbar.source_combo.currentText()
        )
        self.controller.set_talk_active(False)
        self.controller.set_microphone_muted(False)
        self.toolbar.reset_microphone_state()
        self._loading_session = True
        self.toolbar.set_connecting()
        self.toolbar.set_runtime_pending()
        self.toolbar.set_buttons_state(True, allow_stop=False)
        self._set_status(f"Preparando transcrição em {source}...")
        request = self._build_request()
        self.controller.start_session(request)

    def _on_toolbar_stop_clicked(self) -> None:
        self.controller.set_talk_active(False)
        self.controller.stop_session()

    def _on_ptt_pressed(self) -> None:
        self.controller.set_talk_active(True)

    def _on_ptt_released(self) -> None:
        self.controller.set_talk_active(False)

    def _on_source_language_changed(self, language: str) -> None:
        meeting_language = str(self.toolbar.target_combo.currentData() or "en")
        self.settings_window.set_language_pair(
            language, meeting_language, mark_saved=True
        )
        save_settings(
            {
                "user_language": language,
                "meeting_language": meeting_language,
            }
        )

    def _on_target_language_changed(self, language: str) -> None:
        user_language = str(self.toolbar.source_combo.currentData() or "pt-br")
        self.settings_window.set_language_pair(
            user_language, language, mark_saved=True
        )
        save_settings(
            {
                "user_language": user_language,
                "meeting_language": language,
            }
        )

    def _on_settings_language_pair_changed(
        self, user_language: str, meeting_language: str
    ) -> None:
        self.toolbar.set_language_pair(user_language, meeting_language)

    def _on_toolbar_clear_clicked(self) -> None:
        self.transcription_window.clear()

    def _on_running_changed(self, is_running: bool) -> None:
        if not is_running:
            self._loading_session = False
            self.toolbar.set_idle()
        self.toolbar.set_buttons_state(is_running, allow_stop=not self._loading_session)

    def _on_transcript_chunk(self, chunk: object) -> None:
        self.transcription_window.append_chunk(chunk)

    def _on_session_finished(self, final_text: str) -> None:
        if final_text and not self.transcription_window.transcription_area.toPlainText().strip():
            self.transcription_window.append_text(final_text)

    def _on_error(self, message: str) -> None:
        self._loading_session = False
        self.toolbar.set_idle()
        self.toolbar.set_buttons_state(False)
        dialog_parent = self.settings_window if self.settings_window.isVisible() else self
        show_error(dialog_parent, "Não foi possível iniciar", message)

    def _set_status(self, message: str) -> None:
        normalized = message.lower()
        if "captura ativa" in normalized:
            self._loading_session = False
            self.toolbar.set_active(message)
            self.toolbar.set_buttons_state(True, allow_stop=True)
            return
        if any(token in normalized for token in ("carregando", "inicializando", "conectando", "vad ativo", "silero")):
            if self._loading_session:
                self.toolbar.set_connecting(message)
                self.toolbar.set_buttons_state(True, allow_stop=False)
            return
        if any(
            token in normalized
            for token in ("sessão finalizada", "sessão interrompida", "encerrando")
        ):
            self._loading_session = False
            self.toolbar.set_idle()
            self.toolbar.set_buttons_state(False)
            return

        self.toolbar.set_status_message(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        reasons = []
        if self.controller.is_running:
            reasons.append("uma transcrição está em andamento")
        if self.settings_window.has_unsaved_changes():
            reasons.append("existem configurações não salvas")
        if reasons:
            details = " e ".join(reasons)
            confirmed = ask_confirmation(
                self,
                "Encerrar o GlobalVoice?",
                f"No momento, {details}.\n"
                "Deseja encerrar o aplicativo mesmo assim?",
                confirm_text="Encerrar",
                cancel_text="Continuar usando",
            )
            if not confirmed:
                event.ignore()
                return
        self.controller.set_talk_active(False)
        self.controller.set_microphone_muted(False)
        self.controller.stop_session()
        self.settings_window.hide()
        self.toolbar.hide()
        self.transcription_window.hide()
        event.accept()
        application = QApplication.instance()
        if application is not None:
            application.quit()