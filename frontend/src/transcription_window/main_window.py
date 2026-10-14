<<<<<<< Updated upstream
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .backend_bridge import SessionRequest
from .controller import RealtimeController
from .floating_windows import FloatingToolbar, FloatingTranscriptionWindow
from .settings_store import load_settings, save_settings
from .settings_window import SettingsWindow


APP_VERSION = "0.1.0"


def _build_logo_icon(size: int = 96) -> QIcon:
    """Desenha o logo do GlobalVoice: onda de voz em um círculo com gradiente."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    center = size / 2.0
    radius = size * 0.42
    gradient = QRadialGradient(center, center * 0.7, center, center, radius)
    gradient.setColorAt(0.0, QColor("#6366F1"))
    gradient.setColorAt(0.6, QColor("#4F46E5"))
    gradient.setColorAt(1.0, QColor("#3730A3"))

    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    highlight = QRadialGradient(center, center * 0.5, center * 0.5, center * 1.6, radius * 1.2)
    highlight.setColorAt(0.0, QColor(255, 255, 255, 60))
    highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(highlight)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    painter.setBrush(QColor("#F8FAFC"))
    painter.setPen(Qt.NoPen)

    bar_count = 5
    bar_width = size * 0.055
    bar_spacing = size * 0.075
    total_width = (bar_count - 1) * bar_spacing
    start_x = center - total_width / 2.0
    heights = [0.28, 0.52, 0.68, 0.44, 0.32]

    for index, height_ratio in enumerate(heights):
        bar_height = size * height_ratio
        x = start_x + index * bar_spacing - bar_width / 2.0
        y = center - bar_height / 2.0
        rect = QRectF(x, y, bar_width, bar_height)
        path = QPainterPath()
        path.addRoundedRect(rect, bar_width / 2.0, bar_width / 2.0)
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


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


def _build_mic_icon(size: int = 20, color: str = "#818CF8") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(1.4, size * 0.10))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawRoundedRect(
        int(size * 0.34), int(size * 0.08), int(size * 0.32), int(size * 0.52),
        int(size * 0.16), int(size * 0.16),
    )
    path = QPainterPath()
    path.moveTo(size * 0.20, size * 0.45)
    path.cubicTo(size * 0.20, size * 0.76, size * 0.80, size * 0.76, size * 0.80, size * 0.45)
    painter.drawPath(path)
    painter.drawLine(QPointF(size * 0.50, size * 0.72), QPointF(size * 0.50, size * 0.90))
    painter.drawLine(QPointF(size * 0.34, size * 0.90), QPointF(size * 0.66, size * 0.90))
    painter.end()
    return QIcon(pixmap)


def _build_lock_icon(size: int = 20, color: str = "#34D399") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    body = QRectF(size * 0.22, size * 0.45, size * 0.56, size * 0.45)
    painter.drawRoundedRect(body, 2.5, 2.5)
    pen = QPen(QColor(color), max(1.5, size * 0.11))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    arc_rect = QRectF(size * 0.32, size * 0.18, size * 0.36, size * 0.42)
    painter.drawArc(arc_rect, 0, 180 * 16)
    painter.end()
    return QIcon(pixmap)


def _build_bolt_icon(size: int = 20, color: str = "#FBBF24") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.moveTo(size * 0.58, size * 0.05)
    path.lineTo(size * 0.20, size * 0.55)
    path.lineTo(size * 0.46, size * 0.55)
    path.lineTo(size * 0.40, size * 0.95)
    path.lineTo(size * 0.80, size * 0.42)
    path.lineTo(size * 0.54, size * 0.42)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class FeatureCard(QFrame):
    """Mini-card que descreve uma característica do produto."""

    def __init__(self, icon: QIcon, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("featureCard")
        # Largura mínima para igualar todos os cards
        self.setMinimumWidth(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(22, 22))
        icon_label.setFixedHeight(26)

        title_label = QLabel(title)
        title_label.setObjectName("featureTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("featureSubtitle")
        subtitle_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


class MainWindow(QMainWindow):
    """Tela inicial que orquestra as janelas da aplicacao."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Global Voice")
        self.resize(720, 520)
        self.setMinimumSize(560, 420)

        self.controller = RealtimeController()
        self.settings_window = SettingsWindow(controller=self.controller)
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
        hero_layout.setContentsMargins(0, 0, 0, 34)  # aumentei um pouco
        hero_layout.setSpacing(16)  # aumentei de 14 → 16
        hero_layout.setAlignment(Qt.AlignCenter)

        logo_label = QLabel()
        logo_label.setPixmap(_build_logo_icon(96).pixmap(96, 96))
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

        # Features (com stretch para igualar larguras)
        features_row = QHBoxLayout()
        features_row.setSpacing(12)
        features_row.setAlignment(Qt.AlignCenter)

        features = [
            (_build_mic_icon(22), "Captura local", "Áudio processado na sua máquina"),
            (_build_lock_icon(22), "100% offline", "Privacidade garantida"),
            (_build_bolt_icon(22), "GPU / CPU", "Aceleração automática"),
        ]
        for icon, title_text, subtitle_text in features:
            card = FeatureCard(icon, title_text, subtitle_text)
            features_row.addWidget(card, 1)  # stretch 1 para todos

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
        container_layout.addSpacing(36)  # aumentei de 34 → 36
        container_layout.addLayout(features_row)
        container_layout.addSpacing(28)
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
            QFrame#featureCard {
                background: rgba(30, 41, 59, 0.45);
                border: 1px solid rgba(148, 163, 184, 0.12);
                border-radius: 12px;
            }
            QFrame#featureCard:hover {
                background: rgba(30, 41, 59, 0.65);
                border: 1px solid rgba(99, 102, 241, 0.35);
            }
            QLabel#featureTitle {
                font-size: 13px;
                font-weight: 700;
                color: #F1F5F9;
            }
            QLabel#featureSubtitle {
                font-size: 11px;
                color: #94A3B8;
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

    # ------------------------------------------------------------------
    # O restante permanece igual ao arquivo anterior
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start_clicked)
        self.settings_button.clicked.connect(self._on_settings_clicked)

        self.toolbar.start_requested.connect(self._on_toolbar_start_clicked)
        self.toolbar.stop_requested.connect(self._on_toolbar_stop_clicked)
        self.toolbar.ptt_pressed.connect(self._on_ptt_pressed)
        self.toolbar.ptt_released.connect(self._on_ptt_released)
        self.toolbar.microphone_mute_changed.connect(self.controller.set_microphone_muted)
        self.toolbar.source_language_changed.connect(self._on_source_language_changed)
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

        # Conectar estado de running ao header da janela de transcrição
        self.controller.running_changed.connect(self.transcription_window.set_session_running)

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
        self.toolbar.set_capture_mode(values.get("capture_mode", "automatic"))
        self.toolbar.set_source_language(values.get("language", "pt-br"))

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

        return SessionRequest(
            model_size=values["model_size"],
            device=values["device"],
            language=str(self.toolbar.source_combo.currentData() or values["language"]),
            capture_mode=values.get("capture_mode", "automatic"),
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
        values = load_settings()
        self.toolbar.set_capture_mode(values.get("capture_mode", "automatic"))
        self.toolbar.set_source_language(values.get("language", "pt-br"))
        source = self.toolbar.source_combo.currentText()
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
        save_settings({"language": language})

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
        QMessageBox.critical(self, "Erro na transcrição", message)

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
=======
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDesktopServices,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .backend_bridge import SessionRequest
from .controller import RealtimeController
from .dialogs import ask_confirmation, show_error
from .floating_windows import FloatingToolbar, FloatingTranscriptionWindow
from .settings_store import load_settings, save_settings
from .settings_window import SettingsWindow


def _build_logo_pixmap(size: int = 100) -> QPixmap:
    """Carrega o novo símbolo (Globo + Microfone + Órbita) dos assets ou desenha vetorialmente."""

    # 1. Tenta carregar imagem salva na pasta assets
    bundle_root = getattr(sys, "_MEIPASS", None)
    possible_paths = [
        Path(__file__).resolve().parents[1] / "assets" / "global_voice_icon.png",
        Path(__file__).resolve().parents[1] / "assets" / "global_voice_icon.jpeg",
        Path(__file__).resolve().parents[1] / "assets" / "globalvoice.png",
    ]
    if bundle_root:
        possible_paths.insert(0, Path(bundle_root) / "frontend" / "assets" / "global_voice_icon.png")

    for path in possible_paths:
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                return pix.scaled(
                    size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

    # 2. Desenho Vetorial com QPainter (gradiente Ciano -> Azul -> Roxo)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#00D2FF"))  # Ciano vívido
    gradient.setColorAt(0.45, QColor("#3B82F6")) # Azul
    gradient.setColorAt(1.0, QColor("#7C3AED"))  # Roxo / Índigo

    stroke_w = max(2.5, size * 0.055)

    pen = QPen()
    pen.setBrush(gradient)
    pen.setWidthF(stroke_w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)

    # 1. Contorno Externo do Globo
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    margin = size * 0.12
    globe_rect = QRectF(margin, margin, size - (margin * 2), size - (margin * 2))
    painter.drawEllipse(globe_rect)

    # 2. Continentes estilizados
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)

    path_west = QPainterPath()
    path_west.moveTo(size * 0.26, size * 0.24)
    path_west.cubicTo(size * 0.40, size * 0.25, size * 0.42, size * 0.32, size * 0.30, size * 0.38)
    path_west.cubicTo(size * 0.22, size * 0.44, size * 0.20, size * 0.52, size * 0.28, size * 0.60)
    path_west.cubicTo(size * 0.32, size * 0.68, size * 0.25, size * 0.74, size * 0.20, size * 0.62)
    path_west.cubicTo(size * 0.15, size * 0.50, size * 0.16, size * 0.32, size * 0.26, size * 0.24)
    path_west.closeSubpath()
    painter.drawPath(path_west)

    path_east = QPainterPath()
    path_east.moveTo(size * 0.64, size * 0.25)
    path_east.cubicTo(size * 0.74, size * 0.30, size * 0.80, size * 0.38, size * 0.72, size * 0.48)
    path_east.cubicTo(size * 0.65, size * 0.56, size * 0.78, size * 0.62, size * 0.72, size * 0.70)
    path_east.cubicTo(size * 0.62, size * 0.64, size * 0.58, size * 0.42, size * 0.64, size * 0.25)
    path_east.closeSubpath()
    painter.drawPath(path_east)

    # 3. Microfone Central (Cápsula)
    capsule_w = size * 0.16
    capsule_h = size * 0.28
    capsule_x = (size - capsule_w) / 2.0
    capsule_y = size * 0.32
    painter.drawRoundedRect(
        QRectF(capsule_x, capsule_y, capsule_w, capsule_h),
        capsule_w / 2.0,
        capsule_w / 2.0,
    )

    # Suporte em U do microfone
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    u_path = QPainterPath()
    u_path.moveTo(size * 0.36, size * 0.46)
    u_path.cubicTo(size * 0.36, size * 0.64, size * 0.64, size * 0.64, size * 0.64, size * 0.46)
    painter.drawPath(u_path)

    # Haste e Base
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    stem_w = stroke_w
    stem_h = size * 0.08
    painter.drawRect(QRectF((size - stem_w) / 2.0, size * 0.61, stem_w, stem_h))
    base_w = size * 0.22
    base_h = stroke_w
    painter.drawRoundedRect(
        QRectF((size - base_w) / 2.0, size * 0.68, base_w, base_h),
        base_h / 2.0,
        base_h / 2.0,
    )

    # 4. Anel Orbital (Swoosh curvo inferior)
    orbit_path = QPainterPath()
    orbit_path.moveTo(size * 0.22, size * 0.70)
    orbit_path.cubicTo(
        size * 0.28, size * 0.85,
        size * 0.80, size * 0.88,
        size * 0.92, size * 0.42
    )
    orbit_path.cubicTo(
        size * 0.82, size * 0.76,
        size * 0.38, size * 0.79,
        size * 0.22, size * 0.70
    )
    orbit_path.closeSubpath()
    painter.drawPath(orbit_path)

    painter.end()
    return pixmap


def _build_play_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    """Ícone vetorial de Play para o botão Iniciar."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.moveTo(size * 0.30, size * 0.18)
    path.lineTo(size * 0.78, size * 0.50)
    path.lineTo(size * 0.30, size * 0.82)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _build_gear_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    """Ícone vetorial de engrenagem para o botão Configurações."""
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
        tooth_path.addRoundedRect(
            -tooth_w / 2.0,
            -(outer_r + tooth_h),
            tooth_w,
            tooth_h,
            1.5,
            1.5,
        )
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
        self.resize(760, 520)
        self.setMinimumSize(600, 420)

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
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(48, 36, 48, 28)
        main_layout.setSpacing(0)

        # Seção Central (Logo, Título, Subtítulo, Botões)
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)
        center_layout.setAlignment(Qt.AlignCenter)

        logo_label = QLabel()
        logo_label.setPixmap(_build_logo_pixmap(110))
        logo_label.setAlignment(Qt.AlignCenter)

        title = QLabel("Global Voice")
        title.setObjectName("homeTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Tradução simultânea para reuniões online")
        subtitle.setObjectName("homeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        button_row = QHBoxLayout()
        button_row.setSpacing(16)
        button_row.setAlignment(Qt.AlignCenter)

        self.start_button = QPushButton("  Iniciar")
        self.start_button.setObjectName("primaryStartBtn")
        self.start_button.setIcon(_build_play_icon(16, "#FFFFFF"))
        self.start_button.setFixedSize(160, 48)
        self.start_button.setCursor(Qt.PointingHandCursor)

        self.settings_button = QPushButton("  Configurações")
        self.settings_button.setObjectName("secondarySettingsBtn")
        self.settings_button.setIcon(_build_gear_icon(16, "#FFFFFF"))
        self.settings_button.setFixedSize(180, 48)
        self.settings_button.setCursor(Qt.PointingHandCursor)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.settings_button)

        center_layout.addWidget(logo_label)
        center_layout.addSpacing(4)
        center_layout.addWidget(title)
        center_layout.addWidget(subtitle)
        center_layout.addSpacing(16)
        center_layout.addLayout(button_row)

        main_layout.addStretch(1)
        main_layout.addWidget(center_container)
        main_layout.addStretch(1)

        # Rodapé
        footer_layout = QHBoxLayout()

        version_label = QLabel("Versão 0.1.0")
        version_label.setObjectName("footerVersion")

        github_button = QPushButton("Ver no GitHub")
        github_button.setObjectName("footerGithub")
        github_button.setCursor(Qt.PointingHandCursor)
        github_button.clicked.connect(self._open_github)

        footer_layout.addWidget(version_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(github_button)

        main_layout.addLayout(footer_layout)

        # Estilização
        self.setStyleSheet(
            """
            QWidget {
                background-color: #0A0F1D;
                color: #FFFFFF;
                font-family: 'Bahnschrift', 'Segoe UI', sans-serif;
            }
            QLabel#homeTitle {
                font-size: 36px;
                font-weight: 700;
                color: #FFFFFF;
                background: transparent;
            }
            QLabel#homeSubtitle {
                font-size: 15px;
                color: #94A3B8;
                background: transparent;
            }
            QPushButton#primaryStartBtn {
                background-color: #5B51D8;
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 600;
                padding: 0px 24px;
            }
            QPushButton#primaryStartBtn:hover {
                background-color: #4F46E5;
            }
            QPushButton#primaryStartBtn:pressed {
                background-color: #4338CA;
            }
            QPushButton#secondarySettingsBtn {
                background-color: rgba(30, 41, 59, 0.6);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                font-size: 15px;
                font-weight: 600;
                padding: 0px 24px;
            }
            QPushButton#secondarySettingsBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.25);
            }
            QPushButton#secondarySettingsBtn:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QLabel#footerVersion {
                font-size: 12px;
                color: #64748B;
                background: transparent;
            }
            QPushButton#footerGithub {
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: 600;
                color: #818CF8;
                text-align: right;
            }
            QPushButton#footerGithub:hover {
                color: #A5B4FC;
                text-decoration: underline;
            }
            """
        )

    def _open_github(self) -> None:
        """Abre o repositório do GitHub no navegador padrão do usuário."""
        QDesktopServices.openUrl(
            QUrl("https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop")
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
        try:
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
            if saved_x >= 0 and saved_y >= 0:
                self.transcription_window.move(saved_x, saved_y)
            else:
                self.transcription_window.move(
                    geo.right() - self.transcription_window.width() - 20,
                    geo.top() + 100,
                )
        except Exception as err:
            print(f"Aviso ao posicionar janelas flutuantes: {err}")

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

        # 1. Interrompe conexões e áudio em background
        self.controller.set_talk_active(False)
        self.controller.set_microphone_muted(False)
        self.controller.stop_session()

        # 2. Fecha e agenda a destruição dos objetos no Qt
        for window in (self.settings_window, self.toolbar, self.transcription_window):
            try:
                window.close()
                window.deleteLater()
            except Exception:
                pass

        event.accept()
        application = QApplication.instance()
        if application is not None:
            application.quit()
>>>>>>> Stashed changes
