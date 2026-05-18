import sys
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QTextCursor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from .backend_bridge import SessionRequest
from .controller import RealtimeController


class FloatingTranscriptionWindow(QWidget):
    """Janela fantasma (floating overlay) para transcrição em tempo real."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(400, 300)
        self.resize(500, 400)

        self.drag_position = QPoint()
        self._build_ui()

    def _build_ui(self):
        """Constrói a interface da janela de transcrição."""
        main_widget = QFrame()
        main_widget.setObjectName("transcriptionFrame")
        main_widget.setStyleSheet("""
            #transcriptionFrame {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 16px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
        """)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Cabeçalho (arrastável)
        header = QFrame()
        header.setObjectName("transcriptionHeader")
        header.setStyleSheet("""
            #transcriptionHeader {
                background: rgba(0, 4, 255, 0.2);
                border-radius: 12px;
                padding: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("🎤 Transcrição em Tempo Real")
        title.setObjectName("transcriptionTitle")
        title.setStyleSheet("color: white; font-weight: 600; font-size: 14px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(220, 53, 69, 0.8);
            }
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # Área de transcrição (destaque)
        self.transcription_area = QPlainTextEdit()
        self.transcription_area.setReadOnly(True)
        self.transcription_area.setPlaceholderText(
            "Clique em 'Iniciar' na barra de ferramentas e comece a falar...\n\n"
            "A transcrição aparecerá aqui em tempo real."
        )
        self.transcription_area.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(4, 0, 58, 0.8);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 14px;
                padding: 12px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.transcription_area)

        # Layout principal
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

    def append_text(self, text: str):
        """Adiciona texto à área de transcrição."""
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

    def clear(self):
        """Limpa a área de transcrição."""
        self.transcription_area.clear()


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante para controle da transcrição."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(60)
        self.setMinimumWidth(380)

        self.drag_position = QPoint()
        self._build_ui()

    def _build_ui(self):
        main_widget = QFrame()
        main_widget.setObjectName("toolbarFrame")
        main_widget.setStyleSheet("""
            #toolbarFrame {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 30px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
        """)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(12)

        # Ícone de arraste
        drag_icon = QLabel("⋮⋮")
        drag_icon.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(drag_icon)

        # Seletores de idioma
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Português (PT)", "Inglês (EN)", "Espanhol (ES)"])
        self.source_combo.setCurrentText("Português (PT)")
        self.source_combo.setStyleSheet("""
            QComboBox {
                background: rgba(4, 0, 58, 0.8);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 6px 12px;
                min-width: 120px;
            }
        """)

        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("color: white; font-weight: bold;")

        self.target_combo = QComboBox()
        self.target_combo.addItems(["Inglês (EN)", "Português (PT)", "Espanhol (ES)"])
        self.target_combo.setCurrentText("Inglês (EN)")
        self.target_combo.setStyleSheet("""
            QComboBox {
                background: rgba(4, 0, 58, 0.8);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 6px 12px;
                min-width: 120px;
            }
        """)

        layout.addWidget(self.source_combo)
        layout.addWidget(arrow_label)
        layout.addWidget(self.target_combo)

        # Botões
        self.start_btn = QPushButton("▶ Iniciar")
        self.stop_btn = QPushButton("⏹ Parar")
        self.clear_btn = QPushButton("🗑 Limpar")
        self.stop_btn.setEnabled(False)

        btn_style = """
            QPushButton {
                background: rgba(0, 4, 255, 0.8);
                color: white;
                border: none;
                border-radius: 20px;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(70, 73, 251, 0.9);
            }
            QPushButton:disabled {
                background: rgba(100, 100, 100, 0.6);
            }
        """
        self.start_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)
        self.clear_btn.setStyleSheet(btn_style)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.clear_btn)

        # Indicador de status
        self.status_indicator = QLabel("⚪")
        self.status_indicator.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.status_indicator)

        # Layout final
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

    def set_status(self, is_running: bool):
        if is_running:
            self.status_indicator.setText("🟢")
            self.status_indicator.setToolTip("Transcrição ativa")
        else:
            self.status_indicator.setText("⚪")
            self.status_indicator.setToolTip("Transcrição inativa")

    def set_buttons_state(self, is_running: bool):
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        # Clear sempre habilitado
        self.clear_btn.setEnabled(True)

    def get_language_code(self, combo_text: str) -> str:
        mapping = {
            "Português (PT)": "pt",
            "Inglês (EN)": "en",
            "Espanhol (ES)": "es",
        }
        return mapping.get(combo_text, "pt")


class MainWindow(QMainWindow):
    """Janela principal que orquestra as janelas flutuantes."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GlobalVoice")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setVisible(False)

        self.controller = RealtimeController()

        # Cria as janelas flutuantes
        self.transcription_window = FloatingTranscriptionWindow()
        self.toolbar = FloatingToolbar()

        # Posiciona as janelas na tela
        screen = QApplication.primaryScreen().availableGeometry()
        self.toolbar.move(screen.width() // 2 - self.toolbar.width() // 2, screen.height() - 80)
        self.transcription_window.move(screen.width() - self.transcription_window.width() - 20, 100)

        # Conecta sinais
        self._connect_signals()

        # Mostra as janelas
        self.toolbar.show()
        self.transcription_window.show()

    def _connect_signals(self):
        self.toolbar.start_btn.clicked.connect(self._on_start_clicked)
        self.toolbar.stop_btn.clicked.connect(self._on_stop_clicked)
        self.toolbar.clear_btn.clicked.connect(self._on_clear_clicked)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.status_changed.connect(self._set_status)
        self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

    def _build_request(self) -> SessionRequest:
        return SessionRequest(
            model_size="small",
            device="cpu",
            language=self.toolbar.get_language_code(self.toolbar.source_combo.currentText()),
            context_window=0,
            max_duration_s=None,
        )

    def _on_start_clicked(self):
        source = self.toolbar.source_combo.currentText()
        target = self.toolbar.target_combo.currentText()
        self._set_status(f"Iniciando transcrição ({source} → {target})...")
        request = self._build_request()
        self.controller.start_session(request)

    def _on_stop_clicked(self):
        self.controller.stop_session()

    def _on_clear_clicked(self):
        self.transcription_window.clear()

    def _on_running_changed(self, is_running: bool):
        self.toolbar.set_buttons_state(is_running)
        self.toolbar.set_status(is_running)
        self._set_status("Transcrição ativa" if is_running else "Pronto")

    def _on_transcript_chunk(self, chunk: str):
        self.transcription_window.append_text(chunk)

    def _on_session_finished(self, final_text: str):
        if final_text and not self.transcription_window.transcription_area.toPlainText().strip():
            self.transcription_window.append_text(final_text)

    def _on_error(self, message: str):
        QMessageBox.critical(None, "Erro na transcrição", message)

    def _set_status(self, message: str):
        self.toolbar.status_indicator.setToolTip(message)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()