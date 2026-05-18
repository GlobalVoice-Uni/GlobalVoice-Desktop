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
from .settings_store import DEFAULT_SETTINGS, load_settings, save_settings


class SettingsWindow(QMainWindow):
    """Janela de configuracao e testes da transcricao realtime."""

    def __init__(self):
        super().__init__()
        self.controller = RealtimeController()

        self.setWindowTitle("GlobalVoice - Configuracoes")
        self.resize(980, 620)

        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def refresh_from_storage(self) -> None:
        self._load_settings()

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

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "gpu"])

        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt-br", "en"])

        self.context_spin = QSpinBox()
        self.context_spin.setRange(0, 20)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.0, 600.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)
        self.duration_spin.setToolTip("0 = modo continuo ate clicar em Parar")

        self.vad_combo = QComboBox()
        self.vad_combo.addItems(["silero", "energy"])

        self.speech_peak_spin = QDoubleSpinBox()
        self.speech_peak_spin.setRange(0.0001, 0.02)
        self.speech_peak_spin.setDecimals(4)
        self.speech_peak_spin.setSingleStep(0.0001)
        self.speech_peak_spin.setToolTip("Usado no VAD por energia e como fallback")

        self.silero_threshold_spin = QDoubleSpinBox()
        self.silero_threshold_spin.setRange(0.10, 0.95)
        self.silero_threshold_spin.setDecimals(2)
        self.silero_threshold_spin.setSingleStep(0.05)

        self.silero_min_silence_spin = QSpinBox()
        self.silero_min_silence_spin.setRange(50, 1200)
        self.silero_min_silence_spin.setSingleStep(10)

        self.silero_pad_spin = QSpinBox()
        self.silero_pad_spin.setRange(0, 300)
        self.silero_pad_spin.setSingleStep(10)

        self.min_speech_window_spin = QDoubleSpinBox()
        self.min_speech_window_spin.setRange(0.0, 1.5)
        self.min_speech_window_spin.setDecimals(2)
        self.min_speech_window_spin.setSingleStep(0.05)

        self.min_silence_window_spin = QDoubleSpinBox()
        self.min_silence_window_spin.setRange(0.1, 2.5)
        self.min_silence_window_spin.setDecimals(2)
        self.min_silence_window_spin.setSingleStep(0.05)

        self.max_utterance_spin = QDoubleSpinBox()
        self.max_utterance_spin.setRange(0.8, 12.0)
        self.max_utterance_spin.setDecimals(1)
        self.max_utterance_spin.setSingleStep(0.2)

        self.min_utterance_spin = QDoubleSpinBox()
        self.min_utterance_spin.setRange(0.2, 3.0)
        self.min_utterance_spin.setDecimals(1)
        self.min_utterance_spin.setSingleStep(0.1)

        self.forced_policy_combo = QComboBox()
        self.forced_policy_combo.addItems(["protect_boundary", "hard_cut"])

        self.boundary_overlap_spin = QDoubleSpinBox()
        self.boundary_overlap_spin.setRange(0.0, 1.2)
        self.boundary_overlap_spin.setDecimals(2)
        self.boundary_overlap_spin.setSingleStep(0.05)

        self.tail_guard_words_spin = QSpinBox()
        self.tail_guard_words_spin.setRange(0, 12)

        self.forced_extra_tail_spin = QSpinBox()
        self.forced_extra_tail_spin.setRange(0, 8)

        form.addRow("Modelo", self.model_combo)
        form.addRow("Dispositivo", self.device_combo)
        form.addRow("Idioma", self.language_combo)
        form.addRow("Contexto", self.context_spin)
        form.addRow("Duracao maxima (s)", self.duration_spin)
        form.addRow("VAD ativo", self.vad_combo)
        form.addRow("Limiar pico energia", self.speech_peak_spin)
        form.addRow("Limiar Silero", self.silero_threshold_spin)
        form.addRow("Silero min silencio (ms)", self.silero_min_silence_spin)
        form.addRow("Silero speech pad (ms)", self.silero_pad_spin)
        form.addRow("Janela minima fala (s)", self.min_speech_window_spin)
        form.addRow("Janela minima silencio (s)", self.min_silence_window_spin)
        form.addRow("Enunciado maximo (s)", self.max_utterance_spin)
        form.addRow("Enunciado minimo (s)", self.min_utterance_spin)
        form.addRow("Politica forced split", self.forced_policy_combo)
        form.addRow("Overlap fronteira (s)", self.boundary_overlap_spin)
        form.addRow("Tail guard (palavras)", self.tail_guard_words_spin)
        form.addRow("Tail extra forced", self.forced_extra_tail_spin)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Parar")
        self.clear_button = QPushButton("Limpar")
        self.save_button = QPushButton("Salvar")
        self.reset_button = QPushButton("Reverter")

        self.stop_button.setEnabled(False)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.reset_button)
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
        self.save_button.clicked.connect(self._on_save_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.vad_combo.currentTextChanged.connect(self._on_vad_type_changed)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.status_changed.connect(self._set_status)
        self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

    def _set_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(fallback)

    def _collect_settings(self) -> dict:
        duration_value = float(self.duration_spin.value())

        return {
            "model_size": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "language": self.language_combo.currentText(),
            "context_window": int(self.context_spin.value()),
            "max_duration_s": duration_value,
            "vad_type": self.vad_combo.currentText(),
            "speech_peak_threshold": float(self.speech_peak_spin.value()),
            "silero_threshold": float(self.silero_threshold_spin.value()),
            "silero_min_silence_ms": int(self.silero_min_silence_spin.value()),
            "silero_speech_pad_ms": int(self.silero_pad_spin.value()),
            "min_speech_window_s": float(self.min_speech_window_spin.value()),
            "min_silence_window_s": float(self.min_silence_window_spin.value()),
            "max_utterance_s": float(self.max_utterance_spin.value()),
            "min_utterance_s": float(self.min_utterance_spin.value()),
            "boundary_overlap_s": float(self.boundary_overlap_spin.value()),
            "tail_guard_words": int(self.tail_guard_words_spin.value()),
            "forced_split_policy": self.forced_policy_combo.currentText(),
            "forced_split_extra_tail_words": int(self.forced_extra_tail_spin.value()),
        }

    def _apply_settings(self, values: dict) -> None:
        self._set_combo_value(self.model_combo, values["model_size"], DEFAULT_SETTINGS["model_size"])
        self._set_combo_value(self.device_combo, values["device"], DEFAULT_SETTINGS["device"])
        self._set_combo_value(self.language_combo, values["language"], DEFAULT_SETTINGS["language"])
        self.context_spin.setValue(int(values["context_window"]))
        self.duration_spin.setValue(float(values["max_duration_s"]))
        self._set_combo_value(self.vad_combo, values["vad_type"], DEFAULT_SETTINGS["vad_type"])
        self.speech_peak_spin.setValue(float(values["speech_peak_threshold"]))
        self.silero_threshold_spin.setValue(float(values["silero_threshold"]))
        self.silero_min_silence_spin.setValue(int(values["silero_min_silence_ms"]))
        self.silero_pad_spin.setValue(int(values["silero_speech_pad_ms"]))
        self.min_speech_window_spin.setValue(float(values["min_speech_window_s"]))
        self.min_silence_window_spin.setValue(float(values["min_silence_window_s"]))
        self.max_utterance_spin.setValue(float(values["max_utterance_s"]))
        self.min_utterance_spin.setValue(float(values["min_utterance_s"]))
        self._set_combo_value(
            self.forced_policy_combo,
            values["forced_split_policy"],
            DEFAULT_SETTINGS["forced_split_policy"],
        )
        self.boundary_overlap_spin.setValue(float(values["boundary_overlap_s"]))
        self.tail_guard_words_spin.setValue(int(values["tail_guard_words"]))
        self.forced_extra_tail_spin.setValue(int(values["forced_split_extra_tail_words"]))

        self._on_vad_type_changed(self.vad_combo.currentText())

    def _load_settings(self) -> None:
        values = load_settings()
        self._apply_settings(values)

    def _on_save_clicked(self) -> None:
        values = self._collect_settings()
        save_settings(values)
        self._set_status("Configuracoes salvas.")

    def _on_reset_clicked(self) -> None:
        self._apply_settings(DEFAULT_SETTINGS)
        save_settings(DEFAULT_SETTINGS)
        self._set_status("Configuracoes restauradas.")

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
            vad_type=self.vad_combo.currentText(),
            speech_peak_threshold=float(self.speech_peak_spin.value()),
            silero_threshold=float(self.silero_threshold_spin.value()),
            silero_min_silence_ms=int(self.silero_min_silence_spin.value()),
            silero_speech_pad_ms=int(self.silero_pad_spin.value()),
            min_speech_window_s=float(self.min_speech_window_spin.value()),
            min_silence_window_s=float(self.min_silence_window_spin.value()),
            max_utterance_s=float(self.max_utterance_spin.value()),
            min_utterance_s=float(self.min_utterance_spin.value()),
            boundary_overlap_s=float(self.boundary_overlap_spin.value()),
            tail_guard_words=int(self.tail_guard_words_spin.value()),
            forced_split_policy=self.forced_policy_combo.currentText(),
            forced_split_extra_tail_words=int(self.forced_extra_tail_spin.value()),
        )

    def _on_vad_type_changed(self, vad_type: str) -> None:
        """Habilita ajustes especificos do Silero apenas quando necessario."""
        use_silero = vad_type == "silero"
        self.silero_threshold_spin.setEnabled(use_silero)
        self.silero_min_silence_spin.setEnabled(use_silero)
        self.silero_pad_spin.setEnabled(use_silero)

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
        self.vad_combo.setEnabled(not is_running)
        self.speech_peak_spin.setEnabled(not is_running)
        self.silero_threshold_spin.setEnabled(not is_running and self.vad_combo.currentText() == "silero")
        self.silero_min_silence_spin.setEnabled(not is_running and self.vad_combo.currentText() == "silero")
        self.silero_pad_spin.setEnabled(not is_running and self.vad_combo.currentText() == "silero")
        self.min_speech_window_spin.setEnabled(not is_running)
        self.min_silence_window_spin.setEnabled(not is_running)
        self.max_utterance_spin.setEnabled(not is_running)
        self.min_utterance_spin.setEnabled(not is_running)
        self.forced_policy_combo.setEnabled(not is_running)
        self.boundary_overlap_spin.setEnabled(not is_running)
        self.tail_guard_words_spin.setEnabled(not is_running)
        self.forced_extra_tail_spin.setEnabled(not is_running)
        self.save_button.setEnabled(not is_running)
        self.reset_button.setEnabled(not is_running)

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
