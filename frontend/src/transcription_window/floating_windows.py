from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QMouseEvent, QPainter, QPainterPath, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .settings_store import load_settings, save_settings


class FloatingTranscriptionWindow(QWidget):
    """Janela fantasma (floating overlay) para transcricao em tempo real."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(360, 240)

        self.drag_position = QPoint()
        self._build_ui()
        self._apply_saved_ui()

    def _apply_saved_ui(self) -> None:
        values = load_settings()
        width = int(values.get("ui_transcription_window_width", 500))
        height = int(values.get("ui_transcription_window_height", 400))
        self.resize(width, height)
        self.apply_font_size(int(values.get("ui_transcription_font_size", 14)))

    def _build_ui(self) -> None:
        """Constroi a interface da janela de transcricao."""
        main_widget = QFrame()
        main_widget.setObjectName("transcriptionFrame")
        main_widget.setStyleSheet(
            """
            #transcriptionFrame {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 16px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
            """
        )
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("transcriptionHeader")
        header.setStyleSheet(
            """
            #transcriptionHeader {
                background: rgba(0, 4, 255, 0.2);
                border-radius: 12px;
                padding: 8px;
            }
            """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("🎤 Transcricao em Tempo Real")
        title.setObjectName("transcriptionTitle")
        title.setStyleSheet("color: white; font-weight: 600; font-size: 14px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border-radius: 12px;
                font-size: 14px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:hover {
                background: rgba(220, 53, 69, 0.9);
            }
            QPushButton:pressed {
                background: rgba(220, 53, 69, 1);
            }
            """
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        self.transcription_area = QPlainTextEdit()
        self.transcription_area.setReadOnly(True)
        self.transcription_area.setPlaceholderText(
            "Clique em 'Iniciar' na barra de ferramentas e comece a falar...\n\n"
            "A transcricao aparecera aqui em tempo real."
        )
        self.transcription_area.setStyleSheet(
            """
            QPlainTextEdit {
                background: rgba(4, 0, 58, 0.8);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 14px;
                padding: 12px;
                line-height: 1.5;
            }
            """
        )
        layout.addWidget(self.transcription_area)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        self.size_grip = QSizeGrip(main_widget)
        self.size_grip.setFixedSize(16, 16)
        grip_row.addWidget(self.size_grip)
        layout.addLayout(grip_row)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closed.emit()
        event.accept()

    def resizeEvent(self, event) -> None:
        size = self.size()
        save_settings(
            {
                "ui_transcription_window_width": size.width(),
                "ui_transcription_window_height": size.height(),
            }
        )
        super().resizeEvent(event)

    def append_text(self, text: str) -> None:
        """Adiciona texto a area de transcricao."""
        if not text:
            return

        cursor = self.transcription_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.transcription_area.setTextCursor(cursor)

        content = self.transcription_area.toPlainText()
        if content and not content.endswith(" "):
            self.transcription_area.insertPlainText(" ")

        self.transcription_area.insertPlainText(text)
        self.transcription_area.ensureCursorVisible()

    def clear(self) -> None:
        """Limpa a area de transcricao."""
        self.transcription_area.clear()

    def apply_font_size(self, size: int) -> None:
        size = max(10, min(size, 28))
        font = self.transcription_area.font()
        font.setPointSize(size)
        self.transcription_area.setFont(font)


def _build_gear_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
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


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante para controle da transcricao."""

    closed = Signal()
    settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(60)
        self.setMinimumWidth(520)

        self.drag_position = QPoint()
        self._build_ui()
        self.set_idle()

    def _build_ui(self) -> None:
        main_widget = QFrame()
        main_widget.setObjectName("toolbarFrame")
        main_widget.setStyleSheet(
            """
            #toolbarFrame {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 30px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
            #toolbarFrame QPushButton {
                border-radius: 12px;
                padding: 6px 14px;
                font-weight: 600;
                color: #FFFFFF;
                background: rgba(70, 73, 251, 0.9);
                border: none;
            }
            #toolbarFrame QPushButton[kind="secondary"] {
                background: rgba(4, 0, 58, 0.55);
                border: 1px solid rgba(70, 73, 251, 0.5);
            }
            #toolbarFrame QPushButton[kind="danger"] {
                background: rgba(220, 53, 69, 0.9);
            }
            #toolbarFrame QPushButton[kind="ghost"] {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            #toolbarFrame QPushButton:hover {
                background: rgba(70, 73, 251, 1);
            }
            #toolbarFrame QPushButton[kind="secondary"]:hover {
                background: rgba(70, 73, 251, 0.55);
            }
            #toolbarFrame QPushButton[kind="danger"]:hover {
                background: rgba(220, 53, 69, 1);
            }
            #toolbarFrame QPushButton[kind="ghost"]:hover {
                background: rgba(255, 255, 255, 0.18);
            }
            #toolbarFrame QPushButton:pressed {
                background: rgba(70, 73, 251, 0.7);
                padding-top: 7px;
                padding-bottom: 5px;
            }
            #toolbarFrame QPushButton:disabled {
                background: rgba(100, 100, 100, 0.6);
                color: rgba(255, 255, 255, 0.5);
            }
            #toolbarFrame QToolButton {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                border: 1px solid rgba(70, 73, 251, 0.3);
                padding: 4px;
            }
            #toolbarFrame QToolButton:hover {
                background: rgba(70, 73, 251, 0.55);
            }
            #toolbarFrame QToolButton#closeToolbarButton:hover {
                background: rgba(220, 53, 69, 0.9);
            }
            #toolbarFrame QToolButton:pressed {
                background: rgba(70, 73, 251, 0.75);
            }
            """
        )
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(12)

        drag_icon_left = QLabel("⋮⋮")
        drag_icon_left.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(drag_icon_left)

        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("settingsToolbarButton")
        self.settings_btn.setIcon(_build_gear_icon(18))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Opcoes")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setAutoRaise(True)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Português (PT)", "Inglês (EN)", "Espanhol (ES)"])
        self.source_combo.setCurrentText("Português (PT)")
        self.source_combo.setStyleSheet(
            """
            QComboBox {
                background: rgba(4, 0, 58, 0.8);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 6px 12px;
                min-width: 120px;
            }
            """
        )

        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("color: white; font-weight: bold;")

        self.target_combo = QComboBox()
        self.target_combo.addItems(["Inglês (EN)", "Português (PT)", "Espanhol (ES)"])
        self.target_combo.setCurrentText("Inglês (EN)")
        self.target_combo.setStyleSheet(
            """
            QComboBox {
                background: rgba(4, 0, 58, 0.8);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 6px 12px;
                min-width: 120px;
            }
            """
        )


        layout.addWidget(self.source_combo)
        layout.addWidget(arrow_label)
        layout.addWidget(self.target_combo)

        self.start_btn = QPushButton("▶ Iniciar")
        self.stop_btn = QPushButton("⏹ Parar")
        self.clear_btn = QPushButton("🗑 Limpar")
        self.stop_btn.setEnabled(False)

        self.start_btn.setProperty("kind", "primary")
        self.stop_btn.setProperty("kind", "danger")
        self.clear_btn.setProperty("kind", "ghost")

        for button in (self.start_btn, self.stop_btn, self.clear_btn):
            button.setCursor(Qt.PointingHandCursor)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.clear_btn)

        self.status_indicator = QLabel("⚪")
        self.status_indicator.setStyleSheet("font-size: 14px;")
        self.status_text = QLabel("")
        self.status_text.setStyleSheet("color: rgba(255, 255, 255, 0.75); font-size: 12px;")
        self.status_text.setFixedWidth(70)
        self.status_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        status_group = QFrame()
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_text)

        layout.addStretch(1)
        layout.addWidget(status_group)


        self.close_btn = QToolButton()
        self.close_btn.setObjectName("closeToolbarButton")
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setToolTip("Fechar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setAutoRaise(True)
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        drag_icon_right = QLabel("⋮⋮")
        drag_icon_right.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(drag_icon_right)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)

        self.adjustSize()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closed.emit()
        event.accept()

    def set_status_message(self, message: str) -> None:
        self.status_indicator.setToolTip(message)
        self.status_text.setToolTip(message)

    def set_idle(self) -> None:
        self.status_indicator.setText("⚪")
        self.status_text.setText("")
        self.set_status_message("Aguardando inicio")

    def set_active(self, message: str | None = None) -> None:
        self.status_indicator.setText("🟢")
        self.status_text.setText("Ativa")
        self.set_status_message(message or "Transcricao ativa")

    def set_connecting(self, message: str | None = None) -> None:
        self.status_indicator.setText("🟡")
        self.status_text.setText("Carregando")
        self.set_status_message(message or "Carregando...")

    def set_buttons_state(self, is_running: bool, allow_stop: bool = True) -> None:
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running and allow_stop)
        self.clear_btn.setEnabled(True)


    def get_language_code(self, combo_text: str) -> str:
        mapping = {
            "Português (PT)": "pt-br",
            "Inglês (EN)": "en",
            "Espanhol (ES)": "es",
        }
        return mapping.get(combo_text, "pt-br")
