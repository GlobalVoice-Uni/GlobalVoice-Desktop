from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
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
    """Janela de configuracao e testes da aplicacao."""

    def __init__(self):
        super().__init__()
        self.controller = RealtimeController()

        self.setWindowTitle("GlobalVoice - Configurações")
        self.resize(900, 700)
        self.setMinimumSize(680, 540)

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
        layout.setVerticalSpacing(12)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignTop)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        for label, widget in rows:
            layout.addRow(label, widget)

        return container

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Cabeçalho
        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        title = QLabel("Configurações do Global Voice")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setObjectName("titleLabel")

        subtitle = QLabel(
            "Configure os canais de áudio, preferências de tradução e hiperparâmetros de transcrição e segmentação."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        # ----------------- Controles de Uso Comum -----------------
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["Português (PT)", "Inglês (EN)", "Espanhol (ES)"])

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["Inglês (EN)", "Português (PT)", "Espanhol (ES)"])

        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItems(["Somente Tradução", "Somente Transcrição", "Ambos"])

        self.input_device_combo = QComboBox()
        self.input_device_combo.addItems(["Padrão do Sistema"])

        self.loopback_device_combo = QComboBox()
        self.loopback_device_combo.addItems(["Padrão do Sistema"])

        self.virtual_device_combo = QComboBox()
        self.virtual_device_combo.addItems(["Padrão do Sistema", "CABLE Input (VB-Audio Virtual Cable)"])

        self.translation_provider_combo = QComboBox()
        self.translation_provider_combo.addItems(["Local (CTranslate2/MarianMT)", "Remoto (API)"])

        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItems(["Local (Piper TTS)", "Remoto (Edge-TTS)", "Desabilitado"])

        # ----------------- Controles Técnicos / Avançados -----------------
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])

        self.device_combo = QComboBox()
        self.device_combo.addItems(["gpu", "cpu"])

        self.context_spin = QSpinBox()
        self.context_spin.setRange(0, 20)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.0, 600.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)

        self.vad_combo = QComboBox()
        self.vad_combo.addItems(["silero", "energy"])

        self.speech_peak_spin = QDoubleSpinBox()
        self.speech_peak_spin.setRange(0.0001, 0.02)
        self.speech_peak_spin.setDecimals(4)
        self.speech_peak_spin.setSingleStep(0.0001)

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

        # Política de expansão para todos os controles
        all_widgets = [
            self.source_lang_combo, self.target_lang_combo, self.display_mode_combo,
            self.input_device_combo, self.loopback_device_combo, self.virtual_device_combo,
            self.translation_provider_combo, self.tts_engine_combo,
            self.model_combo, self.device_combo, self.context_spin, self.duration_spin,
            self.vad_combo, self.speech_peak_spin, self.silero_threshold_spin,
            self.silero_min_silence_spin, self.silero_pad_spin, self.min_speech_window_spin,
            self.min_silence_window_spin, self.max_utterance_spin, self.min_utterance_spin,
            self.forced_policy_combo, self.boundary_overlap_spin, self.tail_guard_words_spin,
            self.forced_extra_tail_spin,
        ]
        for w in all_widgets:
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Botões de Ação
        self.start_button = QPushButton("Iniciar Teste")
        self.stop_button = QPushButton("Parar")
        self.clear_button = QPushButton("Limpar")
        self.save_button = QPushButton("Salvar Configurações")
        self.reset_button = QPushButton("Restaurar Padrões")
        self.close_button = QPushButton("Fechar")

        self.stop_button.setEnabled(False)

        self.start_button.setProperty("kind", "primary")
        self.stop_button.setProperty("kind", "danger")
        self.clear_button.setProperty("kind", "ghost")
        self.save_button.setProperty("kind", "primary")
        self.reset_button.setProperty("kind", "secondary")
        self.close_button.setProperty("kind", "ghost")

        for button in (
            self.start_button, self.stop_button, self.clear_button,
            self.save_button, self.reset_button, self.close_button,
        ):
            button.setCursor(Qt.PointingHandCursor)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("A transcrição/tradução de teste aparecerá aqui...")
        self.output.setMinimumHeight(140)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.status_label = QLabel("Pronto.")
        self.status_label.setObjectName("statusLabel")

        # Organização das Abas
        self.tabs = QTabWidget()
        self.tabs.setObjectName("configTabs")
        self.tabs.setDocumentMode(True)

        # 1. Aba Geral / Uso Comum
        general_rows = [
            ("Idioma de Origem (Você)", self.source_lang_combo),
            ("Idioma Alvo (Reunião)", self.target_lang_combo),
            ("Modo de Exibição Padrão", self.display_mode_combo),
            ("Provedor de Tradução", self.translation_provider_combo),
            ("Motor de Voz (TTS)", self.tts_engine_combo),
        ]
        # 2. Aba Dispositivos de Áudio
        devices_rows = [
            ("Microfone (Entrada)", self.input_device_combo),
            ("Áudio da Reunião (Loopback)", self.loopback_device_combo),
            ("Microfone Virtual (Envio)", self.virtual_device_combo),
        ]
        # 3. Aba Modelo ASR
        asr_rows = [
            ("Tamanho do Modelo Whisper", self.model_combo),
            ("Dispositivo de Processamento", self.device_combo),
            ("Janela de Contexto", self.context_spin),
            ("Duração Máxima (s)", self.duration_spin),
        ]
        # 4. Aba VAD & Segmentação Avançada
        vad_rows = [
            ("Tipo de VAD", self.vad_combo),
            ("Limiar Pico Energia", self.speech_peak_spin),
            ("Limiar Silero", self.silero_threshold_spin),
            ("Silero Silêncio Mínimo (ms)", self.silero_min_silence_spin),
            ("Silero Speech Pad (ms)", self.silero_pad_spin),
            ("Janela Mínima Fala (s)", self.min_speech_window_spin),
            ("Janela Mínima Silêncio (s)", self.min_silence_window_spin),
            ("Enunciado Máximo (s)", self.max_utterance_spin),
            ("Enunciado Mínimo (s)", self.min_utterance_spin),
            ("Política Forced Split", self.forced_policy_combo),
            ("Overlap Fronteira (s)", self.boundary_overlap_spin),
            ("Tail Guard (palavras)", self.tail_guard_words_spin),
            ("Tail Extra Forced", self.forced_extra_tail_spin),
        ]

        self.tabs.addTab(self._build_form_tab(general_rows), "Geral")
        self.tabs.addTab(self._build_form_tab(devices_rows), "Dispositivos")
        self.tabs.addTab(self._build_form_tab(asr_rows), "Modelo ASR")
        self.tabs.addTab(self._build_form_tab(vad_rows), "VAD & Segmentação")

        # Aba de Teste
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
        self.tabs.addTab(test_tab, "Diagnóstico / Teste")

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
        return {
            "source_language": self.source_lang_combo.currentText(),
            "target_language": self.target_lang_combo.currentText(),
            "display_mode": self.display_mode_combo.currentText(),
            "audio_input_device": self.input_device_combo.currentText(),
            "audio_loopback_device": self.loopback_device_combo.currentText(),
            "audio_virtual_device": self.virtual_device_combo.currentText(),
            "translation_provider": self.translation_provider_combo.currentText(),
            "tts_engine": self.tts_engine_combo.currentText(),
            "model_size": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "context_window": int(self.context_spin.value()),
            "max_duration_s": float(self.duration_spin.value()),
            "vad_type": self.vad_combo.currentText(),
            "speech_peak_threshold": float(self.speech_peak_spin.value()),
            "silero_threshold": float(self.silero_threshold_spin.value()),
            "silero_min_silence_ms": int(self.silero_min_silence_spin.value()),
            "silero_speech_pad_ms": int(self.silero_pad_spin.value()),
            "min_speech_window_s": float(self.min_speech_window_spin.value()),
            "min_silence_window_s": float(self.min_silence_window_spin.value()),
            "max_utterance_s": float(self.max_utterance_spin.value()),
            "min_utterance_s": float(self.min_utterance_spin.value()),
            "forced_split_policy": self.forced_policy_combo.currentText(),
            "boundary_overlap_s": float(self.boundary_overlap_spin.value()),
            "tail_guard_words": int(self.tail_guard_words_spin.value()),
            "forced_split_extra_tail_words": int(self.forced_extra_tail_spin.value()),
        }

    def _apply_settings(self, values: dict) -> None:
        self._set_combo_value(self.source_lang_combo, values.get("source_language", DEFAULT_SETTINGS["source_language"]), DEFAULT_SETTINGS["source_language"])
        self._set_combo_value(self.target_lang_combo, values.get("target_language", DEFAULT_SETTINGS["target_language"]), DEFAULT_SETTINGS["target_language"])
        self._set_combo_value(self.display_mode_combo, values.get("display_mode", DEFAULT_SETTINGS["display_mode"]), DEFAULT_SETTINGS["display_mode"])
        self._set_combo_value(self.input_device_combo, values.get("audio_input_device", DEFAULT_SETTINGS["audio_input_device"]), DEFAULT_SETTINGS["audio_input_device"])
        self._set_combo_value(self.loopback_device_combo, values.get("audio_loopback_device", DEFAULT_SETTINGS["audio_loopback_device"]), DEFAULT_SETTINGS["audio_loopback_device"])
        self._set_combo_value(self.virtual_device_combo, values.get("audio_virtual_device", DEFAULT_SETTINGS["audio_virtual_device"]), DEFAULT_SETTINGS["audio_virtual_device"])
        self._set_combo_value(self.translation_provider_combo, values.get("translation_provider", DEFAULT_SETTINGS["translation_provider"]), DEFAULT_SETTINGS["translation_provider"])
        self._set_combo_value(self.tts_engine_combo, values.get("tts_engine", DEFAULT_SETTINGS["tts_engine"]), DEFAULT_SETTINGS["tts_engine"])

        self._set_combo_value(self.model_combo, values.get("model_size", DEFAULT_SETTINGS["model_size"]), DEFAULT_SETTINGS["model_size"])
        self._set_combo_value(self.device_combo, values.get("device", DEFAULT_SETTINGS["device"]), DEFAULT_SETTINGS["device"])
        self.context_spin.setValue(int(values.get("context_window", DEFAULT_SETTINGS["context_window"])))
        self.duration_spin.setValue(float(values.get("max_duration_s", DEFAULT_SETTINGS["max_duration_s"])))
        self._set_combo_value(self.vad_combo, values.get("vad_type", DEFAULT_SETTINGS["vad_type"]), DEFAULT_SETTINGS["vad_type"])
        self.speech_peak_spin.setValue(float(values.get("speech_peak_threshold", DEFAULT_SETTINGS["speech_peak_threshold"])))
        self.silero_threshold_spin.setValue(float(values.get("silero_threshold", DEFAULT_SETTINGS["silero_threshold"])))
        self.silero_min_silence_spin.setValue(int(values.get("silero_min_silence_ms", DEFAULT_SETTINGS["silero_min_silence_ms"])))
        self.silero_pad_spin.setValue(int(values.get("silero_speech_pad_ms", DEFAULT_SETTINGS["silero_speech_pad_ms"])))
        self.min_speech_window_spin.setValue(float(values.get("min_speech_window_s", DEFAULT_SETTINGS["min_speech_window_s"])))
        self.min_silence_window_spin.setValue(float(values.get("min_silence_window_s", DEFAULT_SETTINGS["min_silence_window_s"])))
        self.max_utterance_spin.setValue(float(values.get("max_utterance_s", DEFAULT_SETTINGS["max_utterance_s"])))
        self.min_utterance_spin.setValue(float(values.get("min_utterance_s", DEFAULT_SETTINGS["min_utterance_s"])))
        self._set_combo_value(self.forced_policy_combo, values.get("forced_split_policy", DEFAULT_SETTINGS["forced_split_policy"]), DEFAULT_SETTINGS["forced_split_policy"])
        self.boundary_overlap_spin.setValue(float(values.get("boundary_overlap_s", DEFAULT_SETTINGS["boundary_overlap_s"])))
        self.tail_guard_words_spin.setValue(int(values.get("tail_guard_words", DEFAULT_SETTINGS["tail_guard_words"])))
        self.forced_extra_tail_spin.setValue(int(values.get("forced_split_extra_tail_words", DEFAULT_SETTINGS["forced_split_extra_tail_words"])))

        self._on_vad_type_changed(self.vad_combo.currentText())

    def _load_settings(self) -> None:
        values = load_settings()
        self._apply_settings(values)

    def _on_save_clicked(self) -> None:
        values = self._collect_settings()
        save_settings(values)
        self._set_status("Configurações salvas.")

    def _on_reset_clicked(self) -> None:
        self._apply_settings(DEFAULT_SETTINGS)
        save_settings(DEFAULT_SETTINGS)
        self._set_status("Configurações restauradas.")

    def _build_request(self) -> SessionRequest:
        duration_value = float(self.duration_spin.value())
        max_duration = duration_value if duration_value > 0 else None

        # Mapeamento do idioma de origem para o backend
        source_map = {"Português (PT)": "pt-br", "Inglês (EN)": "en", "Espanhol (ES)": "es"}
        target_map = {"Português (PT)": "pt", "Inglês (EN)": "en", "Espanhol (ES)": "es"}
        display_map = {
            "Somente Tradução": "translation_only",
            "Somente Transcrição": "transcript_only",
            "Ambos": "both",
        }

        return SessionRequest(
            source_language=source_map.get(self.source_lang_combo.currentText(), "pt-br"),
            target_language=target_map.get(self.target_lang_combo.currentText(), "en"),
            display_mode=display_map.get(self.display_mode_combo.currentText(), "translation_only"),
            input_device=self.input_device_combo.currentText(),
            loopback_device=self.loopback_device_combo.currentText(),
            virtual_device=self.virtual_device_combo.currentText(),
            model_size=self.model_combo.currentText(),
            device=self.device_combo.currentText(),
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
        use_silero = vad_type == "silero"
        self.silero_threshold_spin.setEnabled(use_silero)
        self.silero_min_silence_spin.setEnabled(use_silero)
        self.silero_pad_spin.setEnabled(use_silero)

    def _on_start_clicked(self) -> None:
        request = self._build_request()
        self.controller.start_session(request)

    def _on_stop_clicked(self) -> None:
        self.controller.stop_session()

    def _on_running_changed(self, is_running: bool) -> None:
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
        self.tabs.setEnabled(not is_running or self.tabs.currentIndex() == 4)  # Permite ver a aba de teste
        self.save_button.setEnabled(not is_running)
        self.reset_button.setEnabled(not is_running)

    def _on_transcript_chunk(self, chunk) -> None:
        if not chunk:
            return

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)

        if hasattr(chunk, "format_for_display"):
            text = f"\n{chunk.format_for_display()}"
        else:
            prefix = " " if self.output.toPlainText() and not self.output.toPlainText().endswith((" ", "\n")) else ""
            text = f"{prefix}{chunk}"

        self.output.insertPlainText(text)
        self.output.ensureCursorVisible()

    def _on_session_finished(self, final_text: str) -> None:
        if final_text and not self.output.toPlainText().strip():
            self.output.setPlainText(final_text)

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Erro na execução", message)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)