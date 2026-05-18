from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FloatingTranscriptionWindow(QWidget):
    """Janela fantasma (floating overlay) para transcricao em tempo real."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(400, 300)
        self.resize(500, 400)

        self.drag_position = QPoint()
        self._build_ui()

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
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(220, 53, 69, 0.8);
            }
            """
        )
        close_btn.clicked.connect(self.hide)
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


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante para controle da transcricao."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(60)
        self.setMinimumWidth(380)

        self.drag_position = QPoint()
        self._build_ui()

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
            """
        )
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(12)

        drag_icon = QLabel("⋮⋮")
        drag_icon.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(drag_icon)

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

        btn_style = (
            ""
            "QPushButton {"
            "    background: rgba(0, 4, 255, 0.8);"
            "    color: white;"
            "    border: none;"
            "    border-radius: 20px;"
            "    padding: 6px 16px;"
            "    font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "    background: rgba(70, 73, 251, 0.9);"
            "}"
            "QPushButton:disabled {"
            "    background: rgba(100, 100, 100, 0.6);"
            "}"
        )
        self.start_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)
        self.clear_btn.setStyleSheet(btn_style)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.clear_btn)

        self.status_indicator = QLabel("⚪")
        self.status_indicator.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.status_indicator)

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

    def set_status(self, is_running: bool) -> None:
        if is_running:
            self.status_indicator.setText("🟢")
            self.status_indicator.setToolTip("Transcricao ativa")
        else:
            self.status_indicator.setText("⚪")
            self.status_indicator.setToolTip("Transcricao inativa")

    def set_buttons_state(self, is_running: bool) -> None:
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        self.clear_btn.setEnabled(True)

    def get_language_code(self, combo_text: str) -> str:
        mapping = {
            "Português (PT)": "pt-br",
            "Inglês (EN)": "en",
            "Espanhol (ES)": "es",
        }
        return mapping.get(combo_text, "pt-br")
