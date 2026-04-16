from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .backend_bridge import SessionRequest
from .controller import RealtimeController


class MainWindow(QMainWindow):
    """Janela principal da aplicacao de transcricao realtime."""

    def __init__(self):
        super().__init__()
        self.controller = RealtimeController()

        self.setWindowTitle("GlobalVoice - Realtime")
        self.resize(980, 620)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Constroi os controles visuais e estilo base da janela."""
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        title = QLabel("Transcricao Em Tempo Real")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setObjectName("titleLabel")

        subtitle = QLabel(
            "Aplicacao desktop com PySide6. Hoje local, preparada para trocar a ponte de execucao no futuro."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        self.model_combo.setCurrentText("small")

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "gpu"])
        self.device_combo.setCurrentText("gpu")

        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt-br", "en"])
        self.language_combo.setCurrentText("pt-br")

        self.context_spin = QSpinBox()
        self.context_spin.setRange(0, 20)
        self.context_spin.setValue(0)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.0, 600.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)
        self.duration_spin.setValue(0.0)
        self.duration_spin.setToolTip("0 = modo continuo ate clicar em Parar")

        form.addRow("Modelo", self.model_combo)
        form.addRow("Dispositivo", self.device_combo)
        form.addRow("Idioma", self.language_combo)
        form.addRow("Contexto", self.context_spin)
        form.addRow("Duracao maxima (s)", self.duration_spin)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Parar")
        self.clear_button = QPushButton("Limpar")

        self.stop_button.setEnabled(False)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("A transcricao aparecera aqui...")

        self.status_label = QLabel("Pronto para iniciar.")
        self.status_label.setObjectName("statusLabel")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(form)
        main_layout.addLayout(button_row)
        main_layout.addWidget(self.output, stretch=1)
        main_layout.addWidget(self.status_label)

        self.setStyleSheet(
            """
            QWidget {
                background: #F7F5F2;
                color: #1F1C18;
                font-family: 'Bahnschrift', 'Segoe UI';
                font-size: 14px;
            }
            QLabel#titleLabel {
                font-size: 30px;
                font-weight: 700;
                color: #0F3D3E;
            }
            QLabel#subtitleLabel {
                color: #4B4B4B;
            }
            QPushButton {
                border: 1px solid #0F3D3E;
                background: #FFFFFF;
                color: #0F3D3E;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #E8F0EF;
            }
            QPushButton:disabled {
                color: #888888;
                border-color: #BBBBBB;
                background: #F3F3F3;
            }
            QPlainTextEdit {
                border: 1px solid #CFC8BF;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 10px;
                selection-background-color: #A8DADC;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                border: 1px solid #CFC8BF;
                border-radius: 6px;
                padding: 6px;
                background: #FFFFFF;
                min-height: 28px;
            }
            QLabel#statusLabel {
                color: #2F2F2F;
                font-weight: 600;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Conecta botoes/sinais da UI aos handlers e ao controller."""
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.clear_button.clicked.connect(self.output.clear)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.status_changed.connect(self._set_status)
        self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

    def _build_request(self) -> SessionRequest:
        """Traduz os valores da UI para o objeto de requisicao da sessao."""
        duration_value = float(self.duration_spin.value())
        max_duration = duration_value if duration_value > 0 else None

        return SessionRequest(
            model_size=self.model_combo.currentText(),
            device=self.device_combo.currentText(),
            language=self.language_combo.currentText(),
            context_window=int(self.context_spin.value()),
            max_duration_s=max_duration,
        )

    def _on_start_clicked(self) -> None:
        """Inicia sessao com os parametros selecionados."""
        request = self._build_request()
        self.controller.start_session(request)

    def _on_stop_clicked(self) -> None:
        """Solicita parada da sessao ativa."""
        self.controller.stop_session()

    def _on_running_changed(self, is_running: bool) -> None:
        """Ajusta estado dos controles conforme sessao ativa/inativa."""
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)

        self.model_combo.setEnabled(not is_running)
        self.device_combo.setEnabled(not is_running)
        self.language_combo.setEnabled(not is_running)
        self.context_spin.setEnabled(not is_running)
        self.duration_spin.setEnabled(not is_running)

    def _on_transcript_chunk(self, chunk: str) -> None:
        """Acrescenta novos trechos ao fim do campo de transcricao."""
        if not chunk:
            return

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)

        content = self.output.toPlainText()
        if content and not content.endswith(" "):
            self.output.insertPlainText(" ")

        self.output.insertPlainText(chunk)
        self.output.ensureCursorVisible()

    def _on_session_finished(self, final_text: str) -> None:
        """Garante texto final em tela caso nenhum chunk incremental tenha sido exibido."""
        if final_text and not self.output.toPlainText().strip():
            self.output.setPlainText(final_text)

    def _on_error(self, message: str) -> None:
        """Exibe erro de execucao para o usuario."""
        QMessageBox.critical(self, "Erro na transcricao", message)

    def _set_status(self, message: str) -> None:
        """Atualiza mensagem de status na barra inferior."""
        self.status_label.setText(message)
