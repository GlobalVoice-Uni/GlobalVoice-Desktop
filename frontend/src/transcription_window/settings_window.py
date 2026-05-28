from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
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
        self.resize(880, 680)
        self.setMinimumSize(640, 520)

        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def refresh_from_storage(self) -> None:
        self._load_settings()

    def _build_form_tab(self, rows: list[tuple[str, QWidget]]) -> QWidget:
        container = QWidget()
        layout = QFormLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignTop)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        for label, widget in rows:
            layout.addRow(label, widget)

        return container

    def _build_ui(self) -> None:
        """Constroi os controles visuais e estilo base da janela."""
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        title = QLabel("Configuracoes de Transcricao")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setObjectName("titleLabel")

        subtitle = QLabel(
            "Ajuste parametros de modelo, VAD e segmentacao. O modo teste usa os mesmos valores salvos."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "gpu"])

        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt-br", "en"])

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Ex: PC 1")
        self.display_name_input.setMaxLength(40)

        self.smooth_text_check = QCheckBox()
        self.smooth_text_check.setText("Ativar")

        self.smooth_interval_spin = QSpinBox()
        self.smooth_interval_spin.setRange(10, 140)
        self.smooth_interval_spin.setSingleStep(5)
        self.smooth_interval_spin.setToolTip("Intervalo entre palavras em ms")

        self.correction_check = QCheckBox()
        self.correction_check.setText("Ativar")

        self.reconcile_check = QCheckBox()
        self.reconcile_check.setText("Ativar")

        self.reconcile_tail_spin = QSpinBox()
        self.reconcile_tail_spin.setRange(4, 40)
        self.reconcile_tail_spin.setSingleStep(2)
        self.reconcile_tail_spin.setToolTip("Quantidade de palavras para reconciliação")

        self.silence_break_spin = QDoubleSpinBox()
        self.silence_break_spin.setRange(0.0, 6.0)
        self.silence_break_spin.setDecimals(1)
        self.silence_break_spin.setSingleStep(0.1)
        self.silence_break_spin.setToolTip("0 desativa quebra automatica")

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

        self.relay_mode_combo = QComboBox()
        self.relay_mode_combo.addItems(["off", "host", "cliente"])

        self.relay_host_input = QLineEdit()
        self.relay_host_input.setPlaceholderText("IP do host, ex: 192.168.0.10")
        self.relay_host_input.setMaxLength(120)

        self.relay_port_spin = QSpinBox()
        self.relay_port_spin.setRange(1024, 65535)

        field_widgets = [
            self.model_combo,
            self.device_combo,
            self.language_combo,
            self.display_name_input,
            self.smooth_text_check,
            self.smooth_interval_spin,
            self.silence_break_spin,
            self.correction_check,
            self.reconcile_check,
            self.reconcile_tail_spin,
            self.context_spin,
            self.duration_spin,
            self.vad_combo,
            self.speech_peak_spin,
            self.silero_threshold_spin,
            self.silero_min_silence_spin,
            self.silero_pad_spin,
            self.min_speech_window_spin,
            self.min_silence_window_spin,
            self.max_utterance_spin,
            self.min_utterance_spin,
            self.forced_policy_combo,
            self.boundary_overlap_spin,
            self.tail_guard_words_spin,
            self.forced_extra_tail_spin,
            self.relay_mode_combo,
            self.relay_host_input,
            self.relay_port_spin,
        ]
        for widget in field_widgets:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Parar")
        self.clear_button = QPushButton("Limpar")
        self.save_button = QPushButton("Salvar")
        self.reset_button = QPushButton("Restaurar")
        self.close_button = QPushButton("Fechar")

        self.stop_button.setEnabled(False)

        self.start_button.setProperty("kind", "primary")
        self.stop_button.setProperty("kind", "danger")
        self.clear_button.setProperty("kind", "ghost")
        self.save_button.setProperty("kind", "primary")
        self.reset_button.setProperty("kind", "secondary")
        self.close_button.setProperty("kind", "ghost")

        for button in (
            self.start_button,
            self.stop_button,
            self.clear_button,
            self.save_button,
            self.reset_button,
            self.close_button,
        ):
            button.setCursor(Qt.PointingHandCursor)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("A transcricao aparecera aqui...")
        self.output.setMinimumHeight(140)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.status_label = QLabel("Pronto para iniciar.")
        self.status_label.setObjectName("statusLabel")

        self.tabs = QTabWidget()
        self.tabs.setObjectName("configTabs")
        self.tabs.setDocumentMode(True)

        base_rows = [
            ("Modelo", self.model_combo),
            ("Dispositivo", self.device_combo),
            ("Idioma", self.language_combo),
            ("Contexto", self.context_spin),
            ("Duracao maxima (s)", self.duration_spin),
            ("Nome de exibicao", self.display_name_input),
            ("Suavizar exibicao", self.smooth_text_check),
            ("Tempo suavizacao (ms)", self.smooth_interval_spin),
            ("Quebra por silencio (s)", self.silence_break_spin),
            ("Correcao SymSpell", self.correction_check),
            ("Reconcilia chunks", self.reconcile_check),
            ("Cauda reconcilia (palavras)", self.reconcile_tail_spin),
        ]
        vad_rows = [
            ("VAD ativo", self.vad_combo),
            ("Limiar pico energia", self.speech_peak_spin),
            ("Limiar Silero", self.silero_threshold_spin),
            ("Silero min silencio (ms)", self.silero_min_silence_spin),
            ("Silero speech pad (ms)", self.silero_pad_spin),
        ]
        segment_rows = [
            ("Janela minima fala (s)", self.min_speech_window_spin),
            ("Janela minima silencio (s)", self.min_silence_window_spin),
            ("Enunciado maximo (s)", self.max_utterance_spin),
            ("Enunciado minimo (s)", self.min_utterance_spin),
            ("Politica forced split", self.forced_policy_combo),
            ("Overlap fronteira (s)", self.boundary_overlap_spin),
            ("Tail guard (palavras)", self.tail_guard_words_spin),
            ("Tail extra forced", self.forced_extra_tail_spin),
        ]

        network_rows = [
            ("Modo de rede", self.relay_mode_combo),
            ("Host do relay", self.relay_host_input),
            ("Porta", self.relay_port_spin),
        ]

        self.tabs.addTab(self._build_form_tab(base_rows), "Basico")
        self.tabs.addTab(self._build_form_tab(vad_rows), "VAD")
        self.tabs.addTab(self._build_form_tab(segment_rows), "Segmentacao")
        self.tabs.addTab(self._build_form_tab(network_rows), "Rede")

        test_tab = QWidget()
        test_layout = QVBoxLayout(test_tab)
        test_layout.setContentsMargins(16, 16, 16, 16)
        test_layout.setSpacing(12)

        test_buttons = QHBoxLayout()
        test_buttons.setSpacing(10)
        test_buttons.addWidget(self.start_button)
        test_buttons.addWidget(self.stop_button)
        test_buttons.addWidget(self.clear_button)
        test_buttons.addStretch(1)

        test_layout.addLayout(test_buttons)
        test_layout.addWidget(self.output, stretch=1)

        self.tabs.addTab(test_tab, "Teste")

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.status_label)
        action_row.addStretch(1)
        action_row.addWidget(self.reset_button)
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.close_button)

        main_layout.addWidget(header)
        main_layout.addWidget(self.tabs, stretch=1)
        main_layout.addLayout(action_row)

        self.setStyleSheet(
            """
            QWidget {
                background: #0F1E2D;
                color: #FFFFFF;
                font-family: 'Bahnschrift', 'Segoe UI';
                font-size: 13px;
            }
            QFrame#headerCard {
                background: rgba(15, 30, 45, 0.95);
                border-radius: 16px;
                border: 1px solid rgba(70, 73, 251, 0.3);
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
                color: #FFFFFF;
            }
            QLabel#subtitleLabel {
                color: rgba(255, 255, 255, 0.7);
            }
            QTabWidget::pane {
                border: 1px solid rgba(70, 73, 251, 0.3);
                border-radius: 14px;
                background: rgba(15, 30, 45, 0.85);
                padding: 6px;
            }
            QTabBar::tab {
                background: rgba(4, 0, 58, 0.55);
                color: rgba(255, 255, 255, 0.8);
                padding: 8px 14px;
                border-radius: 10px;
                margin: 4px 4px 0 4px;
            }
            QTabBar::tab:selected {
                background: rgba(70, 73, 251, 0.9);
                color: #FFFFFF;
            }
            QTabBar::tab:!selected:hover {
                background: rgba(70, 73, 251, 0.35);
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
                background: rgba(4, 0, 58, 0.7);
                border: 1px solid rgba(70, 73, 251, 0.25);
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 28px;
            }
            QPlainTextEdit {
                padding: 10px;
                selection-background-color: rgba(70, 73, 251, 0.6);
            }
            QLabel#statusLabel {
                color: #AFC3FF;
                font-weight: 600;
            }
            QPushButton {
                border-radius: 12px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton[kind="primary"] {
                background: rgba(70, 73, 251, 0.95);
                color: #FFFFFF;
            }
            QPushButton[kind="secondary"] {
                background: rgba(4, 0, 58, 0.55);
                color: #FFFFFF;
                border: 1px solid rgba(70, 73, 251, 0.5);
            }
            QPushButton[kind="danger"] {
                background: rgba(220, 53, 69, 0.9);
                color: #FFFFFF;
            }
            QPushButton[kind="ghost"] {
                background: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:hover {
                background: rgba(70, 73, 251, 0.85);
            }
            QPushButton[kind="secondary"]:hover {
                background: rgba(70, 73, 251, 0.55);
            }
            QPushButton[kind="danger"]:hover {
                background: rgba(220, 53, 69, 1);
            }
            QPushButton[kind="ghost"]:hover {
                background: rgba(255, 255, 255, 0.18);
            }
            QPushButton:pressed {
                background: rgba(70, 73, 251, 0.65);
                padding-top: 9px;
                padding-bottom: 7px;
            }
            QPushButton:disabled {
                background: rgba(100, 100, 100, 0.4);
                color: rgba(255, 255, 255, 0.4);
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
        self.close_button.clicked.connect(self.close)
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
            "user_display_name": self.display_name_input.text().strip(),
            "context_window": int(self.context_spin.value()),
            "max_duration_s": duration_value,
            "ui_smooth_text": bool(self.smooth_text_check.isChecked()),
            "ui_smooth_interval_ms": int(self.smooth_interval_spin.value()),
            "ui_balloon_silence_s": float(self.silence_break_spin.value()),
            "ui_text_correction_enabled": bool(self.correction_check.isChecked()),
            "ui_reconcile_enabled": bool(self.reconcile_check.isChecked()),
            "ui_reconcile_tail_words": int(self.reconcile_tail_spin.value()),
            "relay_mode": self.relay_mode_combo.currentText(),
            "relay_host": self.relay_host_input.text().strip(),
            "relay_port": int(self.relay_port_spin.value()),
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
        self.display_name_input.setText(str(values.get("user_display_name", "")))
        self.context_spin.setValue(int(values["context_window"]))
        self.duration_spin.setValue(float(values["max_duration_s"]))
        self.smooth_text_check.setChecked(bool(values.get("ui_smooth_text", False)))
        self.smooth_interval_spin.setValue(int(values.get("ui_smooth_interval_ms", 35)))
        self.silence_break_spin.setValue(float(values.get("ui_balloon_silence_s", 0.0)))
        self.correction_check.setChecked(bool(values.get("ui_text_correction_enabled", False)))
        self.reconcile_check.setChecked(bool(values.get("ui_reconcile_enabled", False)))
        self.reconcile_tail_spin.setValue(int(values.get("ui_reconcile_tail_words", 12)))
        self._set_combo_value(self.relay_mode_combo, values["relay_mode"], DEFAULT_SETTINGS["relay_mode"])
        self.relay_host_input.setText(str(values.get("relay_host", "")))
        self.relay_port_spin.setValue(int(values["relay_port"]))
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
        self.display_name_input.setEnabled(not is_running)
        self.smooth_text_check.setEnabled(not is_running)
        self.smooth_interval_spin.setEnabled(not is_running)
        self.silence_break_spin.setEnabled(not is_running)
        self.correction_check.setEnabled(not is_running)
        self.reconcile_check.setEnabled(not is_running)
        self.reconcile_tail_spin.setEnabled(not is_running)
        self.context_spin.setEnabled(not is_running)
        self.duration_spin.setEnabled(not is_running)
        self.relay_mode_combo.setEnabled(not is_running)
        self.relay_host_input.setEnabled(not is_running)
        self.relay_port_spin.setEnabled(not is_running)
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
