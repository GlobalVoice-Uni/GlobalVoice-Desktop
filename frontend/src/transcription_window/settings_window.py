import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backend.app.audio.devices import AudioDeviceKind
from backend.app.runtime_status import ActiveDevice, RuntimeStatus
from backend.app.translators.argos_local import ArgosModelManager

from .backend_bridge import SessionRequest, get_audio_device_catalog
from .controller import RealtimeController
from .dialogs import ask_confirmation, show_error
from .settings_store import DEFAULT_SETTINGS, load_settings, save_settings


class ModernComboBox(QComboBox):
    """Seletor com menu próprio para manter o mesmo visual da toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_popup: QWidget | None = None
        self._popup_open = False

    def showPopup(self) -> None:
        if not self.isEnabled() or self.count() == 0:
            return
        if self._popup_open:
            self.hidePopup()
            return

        popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground)
        popup.setObjectName("settingsComboPopup")

        frame = QFrame(popup)
        frame.setObjectName("settingsComboPopupPanel")
        frame.setStyleSheet(
            """
            QFrame#settingsComboPopupPanel {
                background: #0F172A;
                border: 1px solid rgba(70, 73, 251, 0.55);
                border-radius: 10px;
            }
            QPushButton {
                min-height: 34px;
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 0 10px;
                text-align: left;
                font-family: 'Bahnschrift', 'Segoe UI';
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(70, 73, 251, 0.45);
            }
            QPushButton[selected="true"] {
                background: rgba(70, 73, 251, 0.85);
            }
            """
        )

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(frame)

        option_layout = QVBoxLayout(frame)
        option_layout.setContentsMargins(2, 2, 2, 2)
        option_layout.setSpacing(2)
        for index in range(self.count()):
            option = QPushButton(self.itemText(index), frame)
            option.setProperty("selected", str(index == self.currentIndex()).lower())
            option.setToolTip(str(self.itemData(index, Qt.ToolTipRole) or ""))
            option.setCursor(Qt.PointingHandCursor)
            option.clicked.connect(
                lambda _checked=False, selected=index: self._select_popup_item(
                    selected
                )
            )
            option_layout.addWidget(option)

        popup_width = self.width()
        popup_height = (self.count() * 36) + 4
        popup.setFixedSize(popup_width, popup_height)
        popup_position = self.mapToGlobal(QPoint(0, self.height() + 2))
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            if popup_position.y() + popup_height > available.bottom():
                popup_position = self.mapToGlobal(QPoint(0, -popup_height - 2))
        popup.move(popup_position)
        self._settings_popup = popup
        self._popup_open = True
        popup.installEventFilter(self)
        popup.show()
        popup.raise_()

    def hidePopup(self) -> None:
        self._popup_open = False
        if self._settings_popup is None:
            return
        self._settings_popup.hide()
        self._settings_popup.deleteLater()
        self._settings_popup = None

    def _select_popup_item(self, index: int) -> None:
        self.setCurrentIndex(index)
        self.hidePopup()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._popup_open:
            self.hidePopup()
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._settings_popup and event.type() == QEvent.Hide:
            popup = watched
            # Qt.Popup fecha antes de repassar ao combo o clique feito sobre
            # ele. Adiar a limpeza permite que o mesmo clique apenas recolha
            # o menu, em vez de abri-lo novamente.
            QTimer.singleShot(150, lambda: self._release_hidden_popup(popup))
        return super().eventFilter(watched, event)

    def _release_hidden_popup(self, popup: QWidget) -> None:
        if self._settings_popup is not popup:
            return
        try:
            popup_visible = popup.isVisible()
        except RuntimeError:
            self._settings_popup = None
            popup_visible = False
        if not popup_visible:
            self._popup_open = False
            if self._settings_popup is popup:
                popup.deleteLater()
                self._settings_popup = None


class SettingsWindow(QMainWindow):
    """Janela de configuracao e testes da transcricao realtime."""

    language_pack_result = Signal(object)
    language_pair_changed = Signal(str, str)

    def __init__(
        self,
        controller: RealtimeController | None = None,
        language_manager_factory=ArgosModelManager,
        show_controller_errors: bool = True,
    ):
        super().__init__()
        self.controller = controller or RealtimeController()
        self._language_manager_factory = language_manager_factory
        self._show_controller_errors = show_controller_errors
        self._language_pack_busy = False
        self._language_pack_thread = None
        self._saved_settings_snapshot: dict = {}

        self.setWindowTitle("GlobalVoice - Configurações")
        self.resize(880, 680)
        self.setMinimumSize(720, 670)

        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def refresh_from_storage(self) -> None:
        self._load_settings()
        if self.tabs.currentWidget() is self.languages_tab:
            self._refresh_language_packs()

    def _build_form_tab(self, rows: list[tuple[str, QWidget]]) -> QWidget:
        container = QWidget()
        layout = QFormLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(7)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        for label, widget in rows:
            layout.addRow(label, widget)

        return container

    def _build_language_card(
        self,
        title: str,
        description: str,
        status: str | QLabel,
        button: QPushButton | None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("languageCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("languagePackTitle")
        description_label = QLabel(description)
        description_label.setObjectName("subtitleLabel")
        description_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        card_layout.addLayout(text_layout, stretch=1)

        status_label = status if isinstance(status, QLabel) else QLabel(status)
        status_label.setObjectName("languagePackStatus")
        card_layout.addWidget(status_label)
        if button is not None:
            card_layout.addWidget(button)
        return card

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

        title = QLabel("Configurações de transcrição")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setObjectName("titleLabel")

        subtitle = QLabel(
            "Ajuste o modelo, o controle do microfone, o VAD e a segmentação."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        self.model_combo = ModernComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])

        self.device_combo = ModernComboBox()
        self.device_combo.addItem("GPU (recomendado)", "gpu")
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.setToolTip(
            "A GPU é priorizada. A CPU é usada por escolha ou como alternativa automática."
        )

        self.active_device_label = QLabel("Esperando iniciar...")
        self.active_device_label.setObjectName("runtimeDeviceLabel")
        self.active_device_label.setToolTip("Dispositivo em uso durante a sessão.")

        self.audio_source_combo = ModernComboBox()
        self.audio_source_combo.addItem("Microfone", "microphone")
        self.audio_source_combo.addItem("Áudio da reunião (WASAPI)", "loopback")
        self.audio_source_combo.setToolTip(
            "Escolha se a sessão escuta o microfone ou o áudio reproduzido pelo Windows."
        )

        self.audio_device_combo = ModernComboBox()
        self.audio_device_combo.setToolTip("Dispositivo usado como origem da captura.")

        self.user_language_combo = ModernComboBox()
        self.user_language_combo.addItem("Português (Brasil)", "pt-br")
        self.user_language_combo.addItem("Inglês", "en")
        self.user_language_combo.addItem("Espanhol", "es")

        self.meeting_language_combo = ModernComboBox()
        self.meeting_language_combo.addItem("Português (Brasil)", "pt-br")
        self.meeting_language_combo.addItem("Inglês", "en")
        self.meeting_language_combo.addItem("Espanhol", "es")
        # Alias temporário para integrações que ainda consultam o campo antigo.
        self.language_combo = self.meeting_language_combo

        self.display_mode_combo = ModernComboBox()
        self.display_mode_combo.addItem("Somente tradução (padrão)", "translation_only")
        self.display_mode_combo.addItem("Somente transcrição original", "transcript_only")
        self.display_mode_combo.addItem("Transcrição e tradução", "both")

        self.capture_mode_combo = ModernComboBox()
        self.capture_mode_combo.addItem("Detecção automática", "automatic")
        self.capture_mode_combo.addItem("Apertar para falar", "push_to_talk")
        self.capture_mode_combo.setToolTip(
            "No modo automático, o VAD identifica a fala. No modo manual, "
            "o áudio só é processado enquanto o botão Falar estiver pressionado."
        )

        self.context_spin = QSpinBox()
        self.context_spin.setRange(0, 20)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.0, 600.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)
        self.duration_spin.setToolTip("Use 0 para manter a sessão ativa até clicar em Parar.")

        self.vad_combo = ModernComboBox()
        self.vad_combo.addItems(["silero", "energy"])

        self.speech_peak_spin = QDoubleSpinBox()
        self.speech_peak_spin.setRange(0.0001, 0.02)
        self.speech_peak_spin.setDecimals(4)
        self.speech_peak_spin.setSingleStep(0.0001)
        self.speech_peak_spin.setToolTip(
            "Sensibilidade usada pela detecção por energia."
        )

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

        self.forced_policy_combo = ModernComboBox()
        self.forced_policy_combo.addItem("Proteger fronteira", "protect_boundary")
        self.forced_policy_combo.addItem("Corte direto", "hard_cut")

        self.boundary_overlap_spin = QDoubleSpinBox()
        self.boundary_overlap_spin.setRange(0.0, 1.2)
        self.boundary_overlap_spin.setDecimals(2)
        self.boundary_overlap_spin.setSingleStep(0.05)

        self.tail_guard_words_spin = QSpinBox()
        self.tail_guard_words_spin.setRange(0, 12)

        self.forced_extra_tail_spin = QSpinBox()
        self.forced_extra_tail_spin.setRange(0, 8)

        field_widgets = [
            self.model_combo,
            self.device_combo,
            self.active_device_label,
            self.audio_source_combo,
            self.audio_device_combo,
            self.user_language_combo,
            self.meeting_language_combo,
            self.display_mode_combo,
            self.capture_mode_combo,
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
        ]
        for widget in field_widgets:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            widget.setMinimumWidth(280)
            widget.setMaximumWidth(560)
            widget.setFixedHeight(30)
            if isinstance(widget, QAbstractSpinBox):
                widget.setButtonSymbols(QAbstractSpinBox.NoButtons)

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
        self.output.setPlaceholderText("A transcrição aparecerá aqui...")
        self.output.setMinimumHeight(140)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.status_label = QLabel("Pronto para iniciar.")
        self.status_label.setObjectName("statusLabel")

        self.tabs = QTabWidget()
        self.tabs.setObjectName("configTabs")
        self.tabs.setDocumentMode(True)

        base_rows = [
            ("Modelo", self.model_combo),
            ("Preferência", self.device_combo),
            ("Dispositivo ativo", self.active_device_label),
            ("Fonte de áudio", self.audio_source_combo),
            ("Entrada/saída", self.audio_device_combo),
            ("Idioma do usuário", self.user_language_combo),
            ("Idioma da chamada", self.meeting_language_combo),
            ("Texto exibido", self.display_mode_combo),
            ("Controle do microfone", self.capture_mode_combo),
            ("Contexto anterior", self.context_spin),
            ("Duração máxima (s)", self.duration_spin),
        ]
        vad_rows = [
            ("VAD ativo", self.vad_combo),
            ("Limiar de pico (energia)", self.speech_peak_spin),
            ("Limiar Silero", self.silero_threshold_spin),
            ("Silêncio mínimo do Silero (ms)", self.silero_min_silence_spin),
            ("Margem de fala do Silero (ms)", self.silero_pad_spin),
        ]
        segment_rows = [
            ("Janela mínima de fala (s)", self.min_speech_window_spin),
            ("Janela mínima de silêncio (s)", self.min_silence_window_spin),
            ("Enunciado máximo (s)", self.max_utterance_spin),
            ("Enunciado mínimo (s)", self.min_utterance_spin),
            ("Política de corte forçado", self.forced_policy_combo),
            ("Sobreposição de fronteira (s)", self.boundary_overlap_spin),
            ("Proteção final (palavras)", self.tail_guard_words_spin),
            ("Palavras extras após corte", self.forced_extra_tail_spin),
        ]

        self.tabs.addTab(self._build_form_tab(base_rows), "Básico")
        self.tabs.addTab(self._build_form_tab(vad_rows), "VAD")
        self.tabs.addTab(self._build_form_tab(segment_rows), "Segmentação")

        self.languages_tab = QWidget()
        languages_layout = QVBoxLayout(self.languages_tab)
        languages_layout.setContentsMargins(16, 16, 16, 16)
        languages_layout.setSpacing(12)

        languages_intro = QLabel(
            "Gerencie os recursos de tradução local disponíveis neste computador."
        )
        languages_intro.setWordWrap(True)
        languages_intro.setObjectName("subtitleLabel")
        languages_layout.addWidget(languages_intro)

        base_card = self._build_language_card(
            "Português (Brasil)",
            "Idioma base do aplicativo",
            "Incluído",
            None,
        )
        languages_layout.addWidget(base_card)

        self.language_pack_status_labels = {}
        self.language_pack_buttons = {}
        for pack in ArgosModelManager.language_packs():
            status_label = QLabel("Aguardando verificação...")
            status_label.setObjectName("languagePackStatus")
            button = QPushButton("Verificar")
            button.setProperty("kind", "secondary")
            button.setCursor(Qt.PointingHandCursor)
            button.setEnabled(False)
            button.clicked.connect(
                lambda _checked=False, code=pack.code: self._on_language_pack_clicked(code)
            )
            card = self._build_language_card(
                pack.label,
                f"Download aproximado: {pack.download_size_mb:.2f} MB",
                status_label,
                button,
            )
            self.language_pack_status_labels[pack.code] = status_label
            self.language_pack_buttons[pack.code] = button
            languages_layout.addWidget(card)

        languages_layout.addStretch(1)
        self.tabs.addTab(self.languages_tab, "Idiomas")

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

        chevron_path = (
            Path(__file__).resolve().parents[2] / "assets" / "chevron-down.svg"
        ).as_posix()
        stylesheet = """
            QWidget {
                background: #0F1E2D;
                color: #FFFFFF;
                font-family: 'Bahnschrift', 'Segoe UI';
                font-size: 13px;
            }
            QLabel {
                background: transparent;
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
                border-radius: 12px;
                background: rgba(15, 30, 45, 0.85);
                padding: 6px;
            }
            QTabBar::tab {
                background: rgba(30, 41, 59, 0.9);
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
                background: rgba(70, 73, 251, 0.28);
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
                background: rgba(30, 41, 59, 0.86);
                border: 1px solid rgba(70, 73, 251, 0.25);
                border-radius: 10px;
                padding: 3px 10px;
                min-height: 20px;
            }
            QComboBox {
                padding-right: 38px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 34px;
                background: transparent;
                border: none;
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
            }
            QComboBox::down-arrow {
                image: url(__CHEVRON_PATH__);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background: #1E293B;
                color: #F8FAFC;
                border: 1px solid rgba(70, 73, 251, 0.55);
                border-radius: 10px;
                padding: 4px;
                outline: 0;
                selection-background-color: rgba(70, 73, 251, 0.78);
                selection-color: #FFFFFF;
            }
            QPlainTextEdit {
                padding: 10px;
                selection-background-color: rgba(70, 73, 251, 0.6);
            }
            QLabel#statusLabel {
                color: #AFC3FF;
                font-weight: 600;
            }
            QLabel#runtimeDeviceLabel {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 3px 10px;
                min-height: 20px;
                font-weight: 700;
            }
            QFrame#languageCard {
                background: rgba(30, 41, 59, 0.78);
                border: 1px solid rgba(70, 73, 251, 0.25);
                border-radius: 10px;
            }
            QLabel#languagePackTitle {
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#languagePackStatus {
                color: #AFC3FF;
                font-weight: 600;
            }
            QPushButton {
                border-radius: 10px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton[kind="primary"] {
                background: rgba(70, 73, 251, 0.95);
                color: #FFFFFF;
            }
            QPushButton[kind="secondary"] {
                background: rgba(30, 41, 59, 0.92);
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
        self.setStyleSheet(stylesheet.replace("__CHEVRON_PATH__", chevron_path))

    def _connect_signals(self) -> None:
        """Conecta botoes/sinais da UI aos handlers e ao controller."""
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.clear_button.clicked.connect(self.output.clear)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.close_button.clicked.connect(self.close)
        self.vad_combo.currentTextChanged.connect(self._on_vad_type_changed)
        self.audio_source_combo.currentIndexChanged.connect(
            self._on_audio_source_changed
        )
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.language_pack_result.connect(self._on_language_pack_result)

        self.controller.transcript_chunk.connect(self._on_transcript_chunk)
        self.controller.status_changed.connect(self._set_status)
        self.controller.runtime_changed.connect(self._on_runtime_changed)
        self.controller.runtime_cleared.connect(self._reset_runtime_status)
        if self._show_controller_errors:
            self.controller.error_raised.connect(self._on_error)
        self.controller.session_finished.connect(self._on_session_finished)
        self.controller.running_changed.connect(self._on_running_changed)

    def _set_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(fallback)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str, fallback: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(index, 0))

    @staticmethod
    def _combo_data(combo: QComboBox, fallback: str) -> str:
        return str(combo.currentData() or fallback)

    def language_pair(self) -> tuple[str, str]:
        return (
            self._combo_data(self.user_language_combo, "pt-br"),
            self._combo_data(self.meeting_language_combo, "en"),
        )

    def set_language_pair(
        self,
        user_language: str,
        meeting_language: str,
        *,
        mark_saved: bool = False,
    ) -> None:
        """Atualiza os seletores sem reenviar a alteracao para a toolbar."""
        self.user_language_combo.blockSignals(True)
        self.meeting_language_combo.blockSignals(True)
        try:
            self._set_combo_data(self.user_language_combo, user_language, "pt-br")
            self._set_combo_data(self.meeting_language_combo, meeting_language, "en")
        finally:
            self.user_language_combo.blockSignals(False)
            self.meeting_language_combo.blockSignals(False)
        if mark_saved and self._saved_settings_snapshot:
            self._saved_settings_snapshot["user_language"] = self._combo_data(
                self.user_language_combo, "pt-br"
            )
            self._saved_settings_snapshot["meeting_language"] = self._combo_data(
                self.meeting_language_combo, "en"
            )
            self._saved_settings_snapshot["language"] = self._saved_settings_snapshot[
                "meeting_language"
            ]

    def _device_preference(self) -> str:
        return str(self.device_combo.currentData() or "gpu")

    def _capture_mode(self) -> str:
        return str(self.capture_mode_combo.currentData() or "automatic")

    def _audio_source(self) -> str:
        return str(self.audio_source_combo.currentData() or "microphone")

    def _audio_device_id(self) -> str:
        return str(self.audio_device_combo.currentData() or "")

    def _set_device_preference(self, value: str) -> None:
        normalized = "cpu" if value == "cpu" else "gpu"
        index = self.device_combo.findData(normalized)
        self.device_combo.setCurrentIndex(max(index, 0))

    def _set_capture_mode(self, value: str) -> None:
        index = self.capture_mode_combo.findData(value)
        self.capture_mode_combo.setCurrentIndex(max(index, 0))

    def _set_audio_source(self, value: str) -> None:
        normalized = "loopback" if value == "loopback" else "microphone"
        index = self.audio_source_combo.findData(normalized)
        self.audio_source_combo.setCurrentIndex(max(index, 0))

    def _refresh_audio_devices(self, preferred_id: str = "") -> None:
        catalog = get_audio_device_catalog()
        kind = (
            AudioDeviceKind.LOOPBACK
            if self._audio_source() == "loopback"
            else AudioDeviceKind.INPUT
        )

        self.audio_device_combo.blockSignals(True)
        try:
            self.audio_device_combo.clear()
            for device in catalog.of_kind(kind):
                default_suffix = " (padrão)" if device.is_default else ""
                self.audio_device_combo.addItem(
                    f"{device.name}{default_suffix}",
                    device.id,
                )

            if self.audio_device_combo.count() == 0:
                self.audio_device_combo.addItem("Nenhum dispositivo compatível", "")
                self.audio_device_combo.setEnabled(False)
            else:
                self.audio_device_combo.setEnabled(not self.controller.is_running)
                selected_index = self.audio_device_combo.findData(str(preferred_id or ""))
                if selected_index >= 0:
                    self.audio_device_combo.setCurrentIndex(selected_index)
                else:
                    default_index = next(
                        (
                            index
                            for index, device in enumerate(catalog.of_kind(kind))
                            if device.is_default
                        ),
                        0,
                    )
                    self.audio_device_combo.setCurrentIndex(default_index)
        finally:
            self.audio_device_combo.blockSignals(False)

        self.audio_device_combo.setToolTip(
            "\n".join(catalog.warnings)
            if catalog.warnings
            else "Dispositivo usado como origem da captura."
        )

    def _on_audio_source_changed(self, _index: int = -1) -> None:
        self._refresh_audio_devices()

    def _on_tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.languages_tab:
            self._refresh_language_packs()

    def _refresh_language_packs(self) -> None:
        self._start_language_pack_task("status")

    def _on_language_pack_clicked(self, pack_code: str) -> None:
        pack = next(
            pack for pack in ArgosModelManager.language_packs() if pack.code == pack_code
        )
        installed = bool(self.language_pack_buttons[pack_code].property("installed"))
        if installed:
            confirmed = ask_confirmation(
                self,
                "Remover idioma",
                f"Deseja remover o pacote de {pack.label}?\n\n"
                "A transcrição continuará disponível, mas a tradução desse idioma não.",
            )
            if confirmed:
                self._start_language_pack_task("uninstall", pack_code)
            return

        confirmed = ask_confirmation(
            self,
            "Instalar idioma",
            f"Baixar e instalar o pacote de {pack.label}?\n\n"
            f"Download aproximado: {pack.download_size_mb:.2f} MB. "
            "O pacote permite tradução nos dois sentidos.",
            default_confirm=True,
        )
        if confirmed:
            self._start_language_pack_task("install", pack_code)

    def _start_language_pack_task(
        self,
        action: str,
        pack_code: str | None = None,
    ) -> None:
        if self._language_pack_busy:
            return

        self._language_pack_busy = True
        if action == "install":
            self._set_status("Instalando idioma... Aguarde alguns instantes...")
        elif action == "uninstall":
            self._set_status("Removendo idioma... Aguarde alguns instantes...")
        for code, button in self.language_pack_buttons.items():
            button.setEnabled(False)
            if code == pack_code:
                self.language_pack_status_labels[code].setText(
                    "Instalando..." if action == "install" else "Removendo..."
                )
            elif action == "status":
                self.language_pack_status_labels[code].setText("Verificando...")

        def worker() -> None:
            result = {"success": False, "action": action, "pack_code": pack_code}
            try:
                manager = self._language_manager_factory()
                if action == "install" and pack_code:
                    manager.install(pack_code)
                elif action == "uninstall" and pack_code:
                    manager.uninstall(pack_code)
                result["states"] = {
                    pack.code: manager.is_installed(pack.code)
                    for pack in manager.language_packs()
                }
                result["success"] = True
            except Exception as exc:
                result["error"] = str(exc)
            self.language_pack_result.emit(result)

        self._language_pack_thread = threading.Thread(
            target=worker,
            name="globalvoice-language-packs",
            daemon=True,
        )
        self._language_pack_thread.start()

    def _on_language_pack_result(self, result: dict) -> None:
        self._language_pack_busy = False
        if result.get("success"):
            states = result.get("states", {})
            for code, button in self.language_pack_buttons.items():
                installed = bool(states.get(code, False))
                button.setProperty("installed", installed)
                button.setText("Desinstalar" if installed else "Instalar")
                button.setEnabled(not self.controller.is_running)
                self.language_pack_status_labels[code].setText(
                    "Instalado" if installed else "Não instalado"
                )
            action = result.get("action")
            if action == "install":
                self._set_status("Pacote de idioma instalado.")
            elif action == "uninstall":
                self._set_status("Pacote de idioma removido.")
            return

        message = result.get("error") or "Não foi possível consultar os idiomas."
        for code, button in self.language_pack_buttons.items():
            button.setEnabled(not self.controller.is_running)
            if button.text() == "Verificar":
                button.setText("Tentar novamente")
            self.language_pack_status_labels[code].setText("Falha ao verificar")
        self._set_status(message)

    def _collect_settings(self) -> dict:
        duration_value = float(self.duration_spin.value())

        return {
            "model_size": self.model_combo.currentText(),
            "device": self._device_preference(),
            "language": self._combo_data(self.meeting_language_combo, "en"),
            "user_language": self._combo_data(self.user_language_combo, "pt-br"),
            "meeting_language": self._combo_data(self.meeting_language_combo, "en"),
            "display_mode": self._combo_data(
                self.display_mode_combo, "translation_only"
            ),
            "capture_mode": self._capture_mode(),
            "audio_source": self._audio_source(),
            "audio_device_id": self._audio_device_id(),
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
            "forced_split_policy": self._combo_data(
                self.forced_policy_combo, "protect_boundary"
            ),
            "forced_split_extra_tail_words": int(self.forced_extra_tail_spin.value()),
        }

    def _apply_settings(self, values: dict) -> None:
        self._set_combo_value(self.model_combo, values["model_size"], DEFAULT_SETTINGS["model_size"])
        self._set_device_preference(values["device"])
        self.set_language_pair(
            values.get("user_language", values.get("language", "pt-br")),
            values.get("meeting_language", "en"),
        )
        self._set_combo_data(
            self.display_mode_combo,
            values.get("display_mode", "translation_only"),
            "translation_only",
        )
        self._set_capture_mode(values["capture_mode"])
        self._set_audio_source(values.get("audio_source", "microphone"))
        self._refresh_audio_devices(values.get("audio_device_id", ""))
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
        self._set_combo_data(
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
        self._saved_settings_snapshot = self._collect_settings()

    def has_unsaved_changes(self) -> bool:
        """Informa se algum controle difere da última configuração salva."""
        return bool(self._saved_settings_snapshot) and (
            self._collect_settings() != self._saved_settings_snapshot
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.has_unsaved_changes():
            self._load_settings()
        event.accept()

    def _on_save_clicked(self) -> None:
        values = self._collect_settings()
        save_settings(values)
        self._saved_settings_snapshot = dict(values)
        self.language_pair_changed.emit(
            values["user_language"], values["meeting_language"]
        )
        runtime_status = self.controller.runtime_status
        if runtime_status and runtime_status.preference.value != values["device"]:
            self.controller.reset_runtime_status()
        self._set_status("Configurações salvas.")

    def _on_reset_clicked(self) -> None:
        self._apply_settings(DEFAULT_SETTINGS)
        save_settings(DEFAULT_SETTINGS)
        self._saved_settings_snapshot = self._collect_settings()
        self.language_pair_changed.emit(
            DEFAULT_SETTINGS["user_language"],
            DEFAULT_SETTINGS["meeting_language"],
        )
        self._set_status("Configurações restauradas.")

    def _build_request(self) -> SessionRequest:
        """Traduz os valores da UI para o objeto de requisicao da sessao."""
        duration_value = float(self.duration_spin.value())
        max_duration = duration_value if duration_value > 0 else None

        user_language = self._combo_data(self.user_language_combo, "pt-br")
        meeting_language = self._combo_data(self.meeting_language_combo, "en")
        audio_source = self._audio_source()
        return SessionRequest(
            model_size=self.model_combo.currentText(),
            device=self._device_preference(),
            language=(meeting_language if audio_source == "loopback" else user_language),
            target_language=user_language,
            display_mode=self._combo_data(
                self.display_mode_combo, "translation_only"
            ),
            # O diagnostico desta janela nao possui o botao de PTT; usa VAD.
            capture_mode="automatic",
            audio_source=audio_source,
            audio_device_id=self._audio_device_id() or None,
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
            forced_split_policy=self._combo_data(
                self.forced_policy_combo, "protect_boundary"
            ),
            forced_split_extra_tail_words=int(self.forced_extra_tail_spin.value()),
        )

    def _on_vad_type_changed(self, vad_type: str) -> None:
        """Habilita ajustes especificos do Silero apenas quando necessario."""
        use_silero = vad_type == "silero"
        self.silero_threshold_spin.setEnabled(use_silero)
        self.silero_min_silence_spin.setEnabled(use_silero)
        self.silero_pad_spin.setEnabled(use_silero)

    def _on_start_clicked(self) -> None:
        """Inicia a sessão de diagnóstico com os parâmetros já salvos."""
        self._load_settings()
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
        self.user_language_combo.setEnabled(not is_running)
        self.meeting_language_combo.setEnabled(not is_running)
        self.display_mode_combo.setEnabled(not is_running)
        self.capture_mode_combo.setEnabled(not is_running)
        self.audio_source_combo.setEnabled(not is_running)
        self.audio_device_combo.setEnabled(
            not is_running and bool(self._audio_device_id())
        )
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
        for button in self.language_pack_buttons.values():
            button.setEnabled(not is_running and not self._language_pack_busy)

    def _on_transcript_chunk(self, chunk: object) -> None:
        """Acrescenta novos trechos ao fim do campo de transcricao."""
        if not chunk:
            return

        display_text = (
            chunk.format_for_display()
            if hasattr(chunk, "format_for_display")
            else str(chunk)
        )
        if not display_text:
            return

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)

        content = self.output.toPlainText()
        if content and not content.endswith(" "):
            self.output.insertPlainText(" ")

        self.output.insertPlainText(display_text)
        self.output.ensureCursorVisible()

    def _on_session_finished(self, final_text: str) -> None:
        """Garante texto final em tela caso nenhum chunk incremental tenha sido exibido."""
        if final_text and not self.output.toPlainText().strip():
            self.output.setPlainText(final_text)

    def _on_error(self, message: str) -> None:
        """Exibe erro de execucao para o usuario."""
        show_error(self, "Não foi possível iniciar", message)

    def _on_runtime_changed(self, status: RuntimeStatus) -> None:
        """Mostra o dispositivo efetivo sem alterar a preferencia salva."""
        self.active_device_label.setText(status.display_label)
        self.active_device_label.setToolTip(status.tooltip)
        self.device_combo.setToolTip(status.tooltip)

        if status.active_device == ActiveDevice.GPU:
            color = "rgba(34, 197, 94, 0.28)"
            border = "rgba(34, 197, 94, 0.75)"
        elif status.is_fallback:
            color = "rgba(245, 158, 11, 0.24)"
            border = "rgba(245, 158, 11, 0.75)"
        else:
            color = "rgba(70, 73, 251, 0.24)"
            border = "rgba(70, 73, 251, 0.75)"

        self.active_device_label.setStyleSheet(
            f"background: {color}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 3px 10px; font-weight: 700;"
        )

    def _reset_runtime_status(self) -> None:
        self.active_device_label.setText("Esperando iniciar...")
        self.active_device_label.setToolTip("Dispositivo em uso durante a sessão.")
        self.active_device_label.setStyleSheet("")
        self.device_combo.setToolTip(
            "A GPU é priorizada. A CPU é usada por escolha ou como alternativa automática."
        )

    def _set_status(self, message: str) -> None:
        """Atualiza mensagem de status na barra inferior."""
        self.status_label.setText(message)
