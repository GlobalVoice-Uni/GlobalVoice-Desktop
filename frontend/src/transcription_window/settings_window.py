import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from backend.app.audio.devices import AudioDeviceKind
from backend.app.audio.virtual_cable import (
    VB_CABLE_LICENSE, VB_CABLE_PAGE, find_vb_cable,
    install_bundled_vb_cable, is_vb_cable_render_device, vb_cable_status,
)
from backend.app.runtime_status import ActiveDevice, RuntimeStatus
from backend.app.translators.argos_local import ArgosModelManager

from .backend_bridge import SessionRequest, get_audio_device_catalog
from .controller import RealtimeController
from .dialogs import ask_confirmation, ask_unsaved_settings, show_error
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
                border: 1px solid rgba(148, 163, 184, 0.4);
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
        scroll_area = QScrollArea(popup)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setWidget(frame)
        popup_layout.addWidget(scroll_area)

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
        popup_height = min((self.count() * 36) + 4, 360)
        popup_position = self.mapToGlobal(QPoint(0, self.height() + 2))
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            below = max(0, available.bottom() - popup_position.y())
            above_position = self.mapToGlobal(QPoint(0, 0)).y()
            above = max(0, above_position - available.top())
            if below < popup_height and above > below:
                popup_height = min(popup_height, above)
                popup_position = self.mapToGlobal(QPoint(0, -popup_height - 2))
            else:
                popup_height = min(popup_height, below)
        popup.setFixedSize(popup_width, max(60, popup_height))
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


class ImmediateTooltipLabel(QLabel):
    """Mostra a explicação assim que o ponteiro entra no ícone."""

    def enterEvent(self, event) -> None:
        if self.toolTip():
            QToolTip.showText(
                self.mapToGlobal(QPoint(self.width() + 4, self.height())),
                self.toolTip(), self,
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)


class SettingsWindow(QMainWindow):
    """Janela de configuracao e testes da transcricao realtime."""

    closed = Signal()
    language_pack_result = Signal(object)
    language_pack_progress = Signal(object)
    language_pair_changed = Signal(str, str)
    cable_install_result = Signal(object)

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
        self._language_pack_status_loaded = False
        self._language_pack_thread = None
        self._cable_installing = False
        self._cable_install_thread = None
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._align_hardware_indicator)

    def _align_hardware_indicator(self) -> None:
        form = self.tabs.widget(0).layout()
        label = form.labelForField(self.device_combo)
        if label is not None:
            width = self.device_combo.x() - form.horizontalSpacing() - label.x()
            if width > label.width():
                label.setFixedWidth(width)

    def _build_form_tab(
        self, rows: list[tuple[str | QWidget, QWidget]], *, advanced: bool = False,
    ) -> QWidget:
        container = QWidget()
        layout = QFormLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(8 if advanced else 12)
        layout.setVerticalSpacing(9 if advanced else 14)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        label_width = max(
            (
                QLabel(label).sizeHint().width()
                if isinstance(label, str) else label.sizeHint().width()
            )
            for label, _ in rows if label
        )
        for label, widget in rows:
            if label:
                if isinstance(label, QWidget):
                    label.setFixedWidth(label_width)
                layout.addRow(label, widget)
            else:
                layout.addRow(widget)

        return container

    @staticmethod
    def _help_label(title: str, explanation: str) -> QWidget:
        label = QWidget()
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row = QHBoxLayout(label)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        row.addWidget(QLabel(title))
        row.addStretch(1)
        help_icon = ImmediateTooltipLabel("?")
        help_icon.setObjectName("helpIcon")
        help_icon.setToolTip(explanation)
        help_icon.setFixedWidth(18)
        help_icon.setAlignment(Qt.AlignCenter)
        row.addWidget(help_icon)
        return label

    def _build_advanced_tab(self, sections: list[tuple[str, list[tuple[str, QWidget, str]]]]) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._advanced_scroll = scroll
        self._advanced_wheel_fields = set()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        for heading, fields in sections:
            section_title = QLabel(heading)
            section_title.setObjectName("advancedSectionTitle")
            content_layout.addWidget(section_title)
            content_layout.addWidget(self._build_form_tab([
                (self._help_label(title, explanation), widget)
                for title, widget, explanation in fields
            ], advanced=True))
            for _, widget, _ in fields:
                if isinstance(widget, (QComboBox, QAbstractSpinBox)):
                    widget.installEventFilter(self)
                    self._advanced_wheel_fields.add(widget)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        return tab

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == QEvent.Wheel
            and watched in getattr(self, "_advanced_wheel_fields", ())
        ):
            bar = self._advanced_scroll.verticalScrollBar()
            delta = event.pixelDelta().y() or event.angleDelta().y()
            bar.setValue(bar.value() - delta)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _build_language_card(
        self,
        title: str,
        description: str,
        status: str | QLabel,
        button: QPushButton | None,
        progress_bar: QProgressBar | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("languageCard")
        card.setMaximumWidth(560)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("languagePackTitle")
        description_label = QLabel(description)
        description_label.setObjectName("languagePackDescription")
        description_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        if progress_bar is not None:
            text_layout.addWidget(progress_bar)
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

        self.header_title = QLabel("Configurações básicas")
        self.header_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.header_title.setObjectName("titleLabel")

        self.header_subtitle = QLabel("Escolha o modelo, o hardware, os idiomas e o texto exibido.")
        self.header_subtitle.setWordWrap(True)
        self.header_subtitle.setObjectName("subtitleLabel")

        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_subtitle)

        self.model_combo = ModernComboBox()
        for model in ("tiny", "base", "small", "medium", "large"):
            self.model_combo.addItem(model.capitalize(), model)

        self.device_combo = ModernComboBox()
        self.device_combo.addItem("GPU (recomendado)", "gpu")
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.setToolTip(
            "A GPU é priorizada. A CPU é usada por escolha ou como alternativa automática."
        )
        self.hardware_indicator = ImmediateTooltipLabel("")
        self.hardware_indicator.setObjectName("hardwareIndicator")
        self.hardware_indicator.setFixedWidth(18)
        self.hardware_indicator.setAlignment(Qt.AlignCenter)
        hardware_label = QWidget()
        hardware_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hardware_layout = QHBoxLayout(hardware_label)
        hardware_layout.setContentsMargins(0, 0, 0, 0)
        hardware_layout.setSpacing(0)
        hardware_layout.addWidget(QLabel("Hardware"))
        hardware_layout.addStretch(1)
        hardware_layout.addWidget(self.hardware_indicator)

        self.active_device_label = QLabel("Esperando iniciar...")
        self.active_device_label.setObjectName("runtimeDeviceLabel")
        self.active_device_label.setToolTip("Dispositivo em uso durante a sessão.")

        self.audio_source_combo = ModernComboBox()
        self.audio_source_combo.addItem("Microfone", "microphone")
        self.audio_source_combo.addItem("Áudio da reunião", "loopback")
        self.audio_source_combo.addItem("Microfone e reunião", "both")
        self.audio_source_combo.setToolTip(
            "Escolha se a sessão escuta o microfone ou o áudio reproduzido pelo Windows."
        )

        self.voice_output_checkbox = QCheckBox("Enviar voz traduzida à chamada")
        self.virtual_cable_label = QLabel("VB-CABLE não encontrado")
        self.virtual_cable_label.setObjectName("voiceDeviceLabel")
        self.virtual_cable_label.setWordWrap(True)
        self.virtual_cable_install_button = QPushButton("Instalar")
        self.virtual_cable_install_button.setProperty("kind", "secondary")
        self.virtual_cable_install_button.setCursor(Qt.PointingHandCursor)
        self.virtual_cable_install_button.hide()
        self.virtual_cable_status_widget = QWidget()
        cable_status_layout = QHBoxLayout(self.virtual_cable_status_widget)
        cable_status_layout.setContentsMargins(0, 0, 0, 0)
        cable_status_layout.setSpacing(10)
        cable_status_layout.addWidget(self.virtual_cable_label, 1)
        cable_status_layout.addWidget(self.virtual_cable_install_button)
        self.virtual_cable_note = QLabel(
            'No aplicativo de chamada, escolha "CABLE Output" como microfone.'
        )
        self.virtual_cable_note.setWordWrap(True)
        self.virtual_cable_note.setToolTip(
            "VB-CABLE da VB-Audio é donationware; contribuições são bem-vindas.\n"
            f"Página oficial: {VB_CABLE_PAGE}\nLicenciamento: {VB_CABLE_LICENSE}"
        )
        self.meeting_capture_label = QLabel("Verificando a saída padrão do Windows...")
        self.meeting_capture_label.setWordWrap(True)
        self.meeting_capture_label.setObjectName("voiceDeviceLabel")
        self.meeting_voice_checkbox = QCheckBox("Ouvir tradução da reunião")
        self.meeting_voice_combo = ModernComboBox()
        self.meeting_voice_combo.setToolTip("Escolha a saída para ouvir a tradução recebida.")
        self.english_voice_combo = ModernComboBox()
        self.english_voice_combo.addItem("LJ Speech (feminina)", "en-ljspeech")
        self.english_voice_combo.addItem("Joe (masculina)", "en-joe")
        self.english_voice_combo.setToolTip("Voz usada sempre que o idioma da fala traduzida for inglês.")

        self.user_language_combo = ModernComboBox()
        self.user_language_combo.addItem("Português", "pt-br")
        self.user_language_combo.addItem("Inglês", "en")
        self.user_language_combo.addItem("Espanhol", "es")

        self.meeting_language_combo = ModernComboBox()
        self.meeting_language_combo.addItem("Português", "pt-br")
        self.meeting_language_combo.addItem("Inglês", "en")
        self.meeting_language_combo.addItem("Espanhol", "es")
        # Alias temporário para integrações que ainda consultam o campo antigo.
        self.language_combo = self.meeting_language_combo

        self.display_mode_combo = ModernComboBox()
        self.display_mode_combo.addItem("Somente Tradução (padrão)", "translation_only")
        self.display_mode_combo.addItem("Somente Transcrição Original", "transcript_only")
        self.display_mode_combo.addItem("Transcrição e Tradução", "both")

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
        self.vad_combo.addItem("Silero (padrão)", "silero")
        self.vad_combo.addItem("Energy", "energy")

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
            self.meeting_voice_combo,
            self.english_voice_combo,
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
        advanced_fields = {
            self.active_device_label, self.context_spin, self.duration_spin,
            self.vad_combo, self.speech_peak_spin, self.silero_threshold_spin,
            self.silero_min_silence_spin, self.silero_pad_spin,
            self.min_speech_window_spin, self.min_silence_window_spin,
            self.max_utterance_spin, self.min_utterance_spin,
            self.forced_policy_combo, self.boundary_overlap_spin,
            self.tail_guard_words_spin, self.forced_extra_tail_spin,
        }
        for widget in field_widgets:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            widget.setMinimumWidth(280)
            widget.setMaximumWidth(560)
            widget.setFixedHeight(30 if widget in advanced_fields else 34)
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
        self.tabs.tabBar().setDrawBase(False)

        base_rows = [
            ("Modelo", self.model_combo),
            (hardware_label, self.device_combo),
            ("Fonte de áudio", self.audio_source_combo),
            ("Idioma do Usuário", self.user_language_combo),
            ("Idioma da Chamada", self.meeting_language_combo),
            ("Texto exibido", self.display_mode_combo),
        ]

        self.tabs.addTab(self._build_form_tab(base_rows), "Básico")
        voice_rows = [
            ("", self.voice_output_checkbox),
            ("Microfone da chamada", self.virtual_cable_status_widget),
            ("Uso na chamada", self.virtual_cable_note),
            ("Áudio da reunião", self.meeting_capture_label),
            ("", self.meeting_voice_checkbox),
            ("Saída de Áudio", self.meeting_voice_combo),
            ("Voz em inglês", self.english_voice_combo),
            ("Controle do Microfone", self.capture_mode_combo),
        ]
        self.tabs.addTab(self._build_form_tab(voice_rows), "Voz")

        self.languages_tab = QWidget()
        languages_layout = QVBoxLayout(self.languages_tab)
        languages_layout.setContentsMargins(16, 16, 16, 16)
        languages_layout.setSpacing(12)

        languages_layout.addWidget(QLabel("Idioma Principal"))
        self.base_language_combo = ModernComboBox()
        self.base_language_combo.addItem("Português (Brasil)", "pt-br")
        self.base_language_combo.addItem("Inglês", "en")
        self.base_language_combo.addItem("Espanhol", "es")
        self.base_language_combo.setFixedHeight(34)
        self.base_language_combo.setMinimumWidth(280)
        self.base_language_combo.setMaximumWidth(560)
        languages_layout.addWidget(self.base_language_combo)
        self.base_language_status_label = QLabel("Verificando os pares instalados...")
        self.base_language_status_label.setObjectName("subtitleLabel")
        self.base_language_status_label.setWordWrap(True)
        languages_layout.addWidget(self.base_language_status_label)

        self.language_pack_status_labels = {}
        self.language_pack_buttons = {}
        self.language_pack_cards = {}
        self.language_pack_title_labels = {}
        self.language_pack_progress_bars = {}
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
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setTextVisible(False)
            progress_bar.hide()
            card = self._build_language_card(
                pack.label,
                f"Download aproximado: {pack.download_size_mb:.2f} MiB",
                status_label,
                button,
                progress_bar,
            )
            self.language_pack_status_labels[pack.code] = status_label
            self.language_pack_buttons[pack.code] = button
            self.language_pack_cards[pack.code] = card
            self.language_pack_title_labels[pack.code] = card.findChild(
                QLabel, "languagePackTitle"
            )
            self.language_pack_progress_bars[pack.code] = progress_bar
            languages_layout.addWidget(card)

        languages_layout.addStretch(1)
        self.tabs.addTab(self.languages_tab, "Idiomas")

        self.advanced_tab = self._build_advanced_tab([
            ("Sessão", [
                ("Contexto de fala", self.context_spin, "Número de trechos anteriores usados para ajudar a transcrição a manter o contexto."),
                ("Limite da sessão (s)", self.duration_spin, "Encerra a sessão após este tempo; zero deixa a sessão ativa até você parar."),
                ("Hardware em uso", self.active_device_label, "Mostra o dispositivo realmente usado na sessão, inclusive quando houve troca automática para CPU."),
            ]),
            ("Detecção de fala (VAD)", [
                ("Detector", self.vad_combo, "Silero detecta fala com um modelo local. Energy usa o volume do áudio como critério."),
                ("Limiar de pico", self.speech_peak_spin, "Sensibilidade do detector Energy; valores menores aceitam sons mais baixos."),
                ("Limiar Silero", self.silero_threshold_spin, "Confiança mínima para o Silero considerar um trecho como fala."),
                ("Silêncio Silero (ms)", self.silero_min_silence_spin, "Tempo de silêncio necessário para fechar um trecho de fala."),
                ("Margem Silero (ms)", self.silero_pad_spin, "Áudio extra mantido antes e depois de cada trecho detectado."),
            ]),
            ("Segmentação", [
                ("Fala mínima (s)", self.min_speech_window_spin, "Tempo mínimo de fala para enviar um trecho à transcrição."),
                ("Silêncio mínimo (s)", self.min_silence_window_spin, "Pausa usada para separar uma fala da próxima."),
                ("Fala máxima (s)", self.max_utterance_spin, "Duração máxima de um trecho antes de um corte forçado."),
                ("Enunciado mínimo (s)", self.min_utterance_spin, "Descarta trechos de áudio curtos demais."),
                ("Corte forçado", self.forced_policy_combo, "Escolhe como preservar o limite entre trechos longos."),
                ("Sobreposição (s)", self.boundary_overlap_spin, "Repete um pequeno intervalo no início do trecho seguinte para evitar perda de palavras."),
                ("Proteção final", self.tail_guard_words_spin, "Número de palavras finais preservadas ao juntar trechos."),
                ("Palavras extras", self.forced_extra_tail_spin, "Palavras adicionais consideradas após um corte forçado."),
            ]),
        ])
        self.tabs.addTab(self.advanced_tab, "Avançado")

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
        check_path = (
            Path(__file__).resolve().parents[2] / "assets" / "checkmark.svg"
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
                border: 1px solid rgba(148, 163, 184, 0.22);
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
                border: none;
                border-radius: 12px;
                background: rgba(15, 30, 45, 0.85);
                padding: 6px;
            }
            QTabBar::base { border: none; }
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
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-radius: 10px;
                padding: 3px 10px;
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
                border: 1px solid rgba(148, 163, 184, 0.45);
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
            QScrollBar:vertical {
                width: 10px;
                margin: 4px 2px;
                background: #27364B;
                border: none;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                min-height: 24px;
                background: #66758E;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #929FB4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
                background: transparent;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QCheckBox {
                spacing: 10px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid rgba(175, 195, 255, 0.65);
                border-radius: 5px;
                background: #1E293B;
            }
            QCheckBox::indicator:hover {
                border-color: #AFC3FF;
            }
            QCheckBox::indicator:checked {
                border-color: #4649FB;
                background: #4649FB;
                image: url(__CHECK_PATH__);
            }
            QCheckBox::indicator:disabled {
                border-color: rgba(175, 195, 255, 0.3);
                background: rgba(30, 41, 59, 0.55);
            }
            QCheckBox::indicator:checked:disabled {
                background: rgba(70, 73, 251, 0.5);
            }
            QLabel#statusLabel {
                color: #AFC3FF;
                font-weight: 600;
            }
            QLabel#helpIcon {
                color: #94A3B8;
                font-size: 14px;
            }
            QLabel#advancedSectionTitle {
                color: #E2E8F0;
                font-size: 14px;
                font-weight: 700;
                padding: 12px 16px 0 16px;
            }
            QLabel#hardwareIndicator {
                background: transparent;
            }
            QLabel#runtimeDeviceLabel {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 3px 10px;
                min-height: 20px;
                font-weight: 700;
            }
            QLabel#voiceDeviceLabel {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 3px 10px;
                min-height: 26px;
                font-weight: 700;
            }
            QFrame#languageCard {
                background: rgba(30, 41, 59, 0.78);
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-radius: 10px;
            }
            QLabel#languagePackTitle {
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#languagePackDescription {
                color: rgba(255, 255, 255, 0.7);
                font-size: 11px;
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
                border: 1px solid rgba(148, 163, 184, 0.32);
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
        self.setStyleSheet(
            stylesheet.replace("__CHEVRON_PATH__", chevron_path)
            .replace("__CHECK_PATH__", check_path)
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
        self.audio_source_combo.currentIndexChanged.connect(
            self._on_audio_source_changed
        )
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.user_language_combo.currentIndexChanged.connect(
            self._on_user_language_changed
        )
        self.base_language_combo.currentIndexChanged.connect(
            self._on_base_language_changed
        )
        self.language_pack_result.connect(self._on_language_pack_result)
        self.language_pack_progress.connect(self._on_language_pack_progress)
        self.virtual_cable_install_button.clicked.connect(self._install_virtual_cable)
        self.cable_install_result.connect(self._on_cable_install_result)

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
        self._sync_language_pack_cards()
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

    def _set_device_preference(self, value: str) -> None:
        normalized = "cpu" if value == "cpu" else "gpu"
        index = self.device_combo.findData(normalized)
        self.device_combo.setCurrentIndex(max(index, 0))

    def _set_capture_mode(self, value: str) -> None:
        index = self.capture_mode_combo.findData(value)
        self.capture_mode_combo.setCurrentIndex(max(index, 0))

    def _set_audio_source(self, value: str) -> None:
        normalized = value if value in {"microphone", "loopback", "both"} else "microphone"
        index = self.audio_source_combo.findData(normalized)
        self.audio_source_combo.setCurrentIndex(max(index, 0))

    def _on_audio_source_changed(self, _index: int = -1) -> None:
        self._refresh_voice_devices()

    def _refresh_voice_devices(self, values: dict | None = None) -> None:
        values = values or {}
        catalog = get_audio_device_catalog()
        cable = find_vb_cable(catalog)
        cable_state = vb_cable_status(catalog)
        cable_messages = {
            "available": "CABLE Output disponível",
            "restart_required": "Reinicie o PC para ativar o VB-CABLE",
            "incomplete": "VB-CABLE indisponível",
            "not_installed": "VB-CABLE não instalado",
        }
        self.virtual_cable_label.setText(cable_messages[cable_state])
        self.virtual_cable_label.setToolTip(
            "O driver foi detectado, mas a entrada ou a saída virtual não apareceu. Reinicie o PC; se persistir, use Reparar."
            if cable_state == "incomplete" else ""
        )
        self.virtual_cable_label.setStyleSheet(
            "color: #FCA5A5;" if cable_state in {"not_installed", "incomplete"} else ""
        )
        self.virtual_cable_install_button.setText(
            "Reparar" if cable_state == "incomplete" else "Instalar"
        )
        self.virtual_cable_install_button.setVisible(
            cable_state in {"not_installed", "incomplete"}
        )
        self.virtual_cable_install_button.setEnabled(
            not self._cable_installing and not self.controller.is_running
        )
        outputs = catalog.of_kind(AudioDeviceKind.OUTPUT)
        speakers = catalog.of_kind(AudioDeviceKind.LOOPBACK)
        meeting_output = next(
            (device for device in speakers if device.is_default),
            speakers[0] if speakers else None,
        )
        if self._audio_source() == "microphone":
            meeting_text = "Não usado no modo Microfone"
        elif meeting_output is None:
            meeting_text = "Nenhuma saída padrão encontrada no Windows"
        elif is_vb_cable_render_device(meeting_output):
            meeting_text = "CABLE Input é a saída padrão do Windows. Mude para seu headset ou alto-falante."
        else:
            meeting_text = f"Padrão do Windows: {meeting_output.name}"
        self.meeting_capture_label.setText(meeting_text)
        self.meeting_capture_label.setStyleSheet(
            "color: #FCA5A5;"
            if self._audio_source() != "microphone" and is_vb_cable_render_device(meeting_output)
            else ""
        )
        speaker_names = {device.name.casefold() for device in speakers}
        default_speaker = next((device.name.casefold() for device in speakers if device.is_default), "")
        # PortAudio repete a mesma saída por backend. WASAPI usa o endpoint
        # real e evita selecionar aliases MME/DirectSound com nomes truncados.
        ranked_outputs = sorted(
            outputs,
            key=lambda device: (
                device.name.casefold() != default_speaker,
                device.backend != "Windows WASAPI",
                device.name.casefold(),
            ),
        )
        return_outputs = tuple(
            device for device in ranked_outputs
            if device.name.casefold() in speaker_names
            and "VB-Audio Virtual Cable" not in device.name
        )
        for combo, key, candidates, unavailable_text in (
            (
                self.meeting_voice_combo, "meeting_voice_device_id", return_outputs,
                "Nenhuma saída de áudio disponível",
            ),
        ):
            preferred = str(values.get(key, combo.currentData() or ""))
            combo.clear()
            seen_names = set()
            for device in candidates:
                if device.name.casefold() in seen_names:
                    continue
                seen_names.add(device.name.casefold())
                is_default = device.name.casefold() == default_speaker
                combo.addItem(device.name + (" (padrão)" if is_default else ""), device.id)
            if combo.count() == 0:
                combo.addItem(unavailable_text, "")
            selected = combo.findData(preferred)
            if selected < 0:
                selected = next(
                    (i for i in range(combo.count()) if combo.itemText(i).endswith(" (padrão)")),
                    0,
                )
            combo.setCurrentIndex(selected)
        active = not self.controller.is_running
        if cable_state != "available":
            self.voice_output_checkbox.setChecked(False)
        self.voice_output_checkbox.setEnabled(active and cable_state == "available" and self._audio_source() != "loopback")
        can_return = bool(return_outputs) and self._audio_source() != "microphone"
        if not return_outputs:
            self.meeting_voice_checkbox.setChecked(False)
        self.meeting_voice_checkbox.setEnabled(active and can_return)
        self.meeting_voice_combo.setEnabled(active and can_return)
        self.meeting_voice_checkbox.setToolTip(
            "Ao usar a saída capturada da reunião, a captura pausa durante a voz sintetizada."
            if return_outputs else "Conecte uma saída de áudio ao Windows para ouvir a tradução."
        )

    def _install_virtual_cable(self) -> None:
        if self._cable_installing or self.controller.is_running:
            return
        self._cable_installing = True
        self.virtual_cable_install_button.setEnabled(False)
        self.virtual_cable_label.setText("Instalando VB-CABLE... Autorize a instalação na janela do Windows.")

        def worker() -> None:
            try:
                install_bundled_vb_cable()
                self.cable_install_result.emit({"success": True})
            except Exception as exc:
                self.cable_install_result.emit({"success": False, "error": str(exc)})

        self._cable_install_thread = threading.Thread(target=worker, daemon=True)
        self._cable_install_thread.start()

    def _on_cable_install_result(self, result: dict) -> None:
        self._cable_installing = False
        self._refresh_voice_devices()
        if result.get("success"):
            self._set_status("VB-CABLE instalado. Reinicie o computador para ativá-lo.")
        else:
            show_error(self, "Instalação do microfone virtual", result.get("error", "Falha ao instalar VB-CABLE."))

    def _on_tab_changed(self, _index: int) -> None:
        headers = {
            "Básico": ("Configurações básicas", "Escolha o modelo, o hardware, os idiomas e o texto exibido."),
            "Voz": ("Configurações de voz", "Defina a voz enviada à chamada, a tradução que você ouve e o controle do microfone."),
            "Idiomas": ("Configurações de idiomas", "Gerencie os recursos de tradução local disponíveis neste computador."),
            "Avançado": ("Configurações avançadas", "Ajuste a detecção de fala, a duração da sessão e a segmentação do áudio."),
        }
        title, subtitle = headers.get(self.tabs.tabText(self.tabs.currentIndex()), headers["Básico"])
        self.header_title.setText(title)
        self.header_subtitle.setText(subtitle)
        if self.tabs.currentWidget() is self.languages_tab:
            self._refresh_language_packs()

    def _sync_language_pack_cards(self) -> None:
        base = self._combo_data(self.user_language_combo, "pt-br")
        self.base_language_combo.blockSignals(True)
        try:
            self._set_combo_data(self.base_language_combo, base, "pt-br")
        finally:
            self.base_language_combo.blockSignals(False)
        visible = {
            pack.code for pack in ArgosModelManager.language_packs(base)
        }
        for code, card in self.language_pack_cards.items():
            card.setVisible(code in visible)
        for pack in ArgosModelManager.language_packs(base):
            self.language_pack_title_labels[pack.code].setText(pack.label_for_base(base))
        self._update_base_language_status()

    def _update_base_language_status(self) -> None:
        if getattr(self, "_language_pack_status_loaded", False) is None:
            self.base_language_status_label.show()
            self.base_language_status_label.setText("Não foi possível verificar os pares instalados.")
            self.base_language_status_label.setStyleSheet("color: #FACC77;")
            return
        if not getattr(self, "_language_pack_status_loaded", False):
            self.base_language_status_label.show()
            self.base_language_status_label.setText("Verificando os pares instalados...")
            self.base_language_status_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
            return
        base = self._combo_data(self.base_language_combo, "pt-br")
        visible = ArgosModelManager.language_packs(base)
        installed = sum(
            bool(self.language_pack_buttons[pack.code].property("installed"))
            for pack in visible
        )
        if installed == 0:
            self.base_language_status_label.show()
            self.base_language_status_label.setText(
                "O idioma principal não exige pacote próprio. Nenhum par instalado para traduzir; instale um dos pares abaixo."
            )
            self.base_language_status_label.setStyleSheet("color: #FACC77;")
        else:
            self.base_language_status_label.hide()

    def _on_user_language_changed(self, _index: int) -> None:
        self._sync_language_pack_cards()
        if self.user_language_combo.currentData() == self.meeting_language_combo.currentData():
            fallback = "en" if self.user_language_combo.currentData() == "pt-br" else "pt-br"
            self._set_combo_data(self.meeting_language_combo, fallback, "en")

    def _on_base_language_changed(self, _index: int) -> None:
        self._set_combo_data(
            self.user_language_combo,
            self._combo_data(self.base_language_combo, "pt-br"),
            "pt-br",
        )

    def _refresh_language_packs(self) -> None:
        self._start_language_pack_task("status")

    def _on_language_pack_clicked(self, pack_code: str) -> None:
        pack = next(
            pack for pack in ArgosModelManager.language_packs() if pack.code == pack_code
        )
        base = self._combo_data(self.base_language_combo, "pt-br")
        label = pack.label_for_base(base)
        installed = bool(self.language_pack_buttons[pack_code].property("installed"))
        if installed:
            if self.language_pack_buttons[pack_code].property("system_installed"):
                return
            confirmed = ask_confirmation(
                self,
                "Remover idioma",
                f"Deseja remover o pacote de {label}?\n\n"
                "A transcrição continuará disponível, mas a tradução desse idioma não.",
            )
            if confirmed:
                self._start_language_pack_task("uninstall", pack_code)
            return

        confirmed = ask_confirmation(
            self,
            "Instalar idioma",
            f"Baixar e instalar o pacote de {label}?\n\n"
            f"Download aproximado: {pack.download_size_mb:.2f} MiB. "
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
        self.base_language_combo.setEnabled(False)
        if action == "status":
            self._language_pack_status_loaded = False
            self._update_base_language_status()
        if action == "install":
            self._set_status("Baixando e instalando idioma...")
            if pack_code:
                progress_bar = self.language_pack_progress_bars[pack_code]
                progress_bar.setRange(0, 0)
                progress_bar.show()
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
                    manager.install(
                        pack_code,
                        progress_callback=lambda current, count, received, total: (
                            self.language_pack_progress.emit(
                                {"pack_code": pack_code, "current": current,
                                 "count": count, "received": received, "total": total}
                            )
                        ),
                    )
                elif action == "uninstall" and pack_code:
                    manager.uninstall(pack_code)
                result["states"] = {
                    pack.code: manager.is_installed(pack.code)
                    for pack in manager.language_packs()
                }
                result["system_states"] = {
                    pack.code: getattr(manager, "is_system_installed", lambda code: False)(pack.code)
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

    def _on_language_pack_progress(self, progress: dict) -> None:
        code = progress["pack_code"]
        bar = self.language_pack_progress_bars[code]
        total = progress["total"]
        if total:
            bar.setRange(0, 100)
            bar.setValue(min(100, int(progress["received"] * 100 / total)))
        else:
            bar.setRange(0, 0)
        self.language_pack_status_labels[code].setText(
            f"Baixando {progress['current']}/{progress['count']}"
        )

    def _on_language_pack_result(self, result: dict) -> None:
        self._language_pack_busy = False
        self.base_language_combo.setEnabled(not self.controller.is_running)
        code = result.get("pack_code")
        if code and code in self.language_pack_progress_bars:
            self.language_pack_progress_bars[code].hide()
        if result.get("success"):
            self._language_pack_status_loaded = True
            states = result.get("states", {})
            system_states = result.get("system_states", {})
            for code, button in self.language_pack_buttons.items():
                installed = bool(states.get(code, False))
                system_installed = bool(system_states.get(code, False))
                button.setProperty("installed", installed)
                button.setProperty("system_installed", system_installed)
                button.setText(
                    "Na instalação" if system_installed else
                    ("Desinstalar" if installed else "Instalar")
                )
                button.setEnabled(not self.controller.is_running and not system_installed)
                self.language_pack_status_labels[code].setText(
                    "Instalado" if installed else "Não instalado"
                )
            self._update_base_language_status()
            action = result.get("action")
            if action == "install":
                self._set_status("Pacote de idioma instalado.")
            elif action == "uninstall":
                self._set_status("Pacote de idioma removido.")
            return

        message = result.get("error") or "Não foi possível consultar os idiomas."
        self._language_pack_status_loaded = None
        self.base_language_status_label.setText("Não foi possível verificar os pares instalados.")
        self.base_language_status_label.setStyleSheet("color: #FACC77;")
        for code, button in self.language_pack_buttons.items():
            button.setEnabled(
                not self.controller.is_running
                and not bool(button.property("system_installed"))
            )
            if button.text() == "Verificar":
                button.setText("Tentar novamente")
            self.language_pack_status_labels[code].setText("Falha ao verificar")
        self._set_status(message)

    def _collect_settings(self) -> dict:
        duration_value = float(self.duration_spin.value())

        return {
            "model_size": self._combo_data(self.model_combo, "small"),
            "device": self._device_preference(),
            "language": self._combo_data(self.meeting_language_combo, "en"),
            "user_language": self._combo_data(self.user_language_combo, "pt-br"),
            "meeting_language": self._combo_data(self.meeting_language_combo, "en"),
            "display_mode": self._combo_data(
                self.display_mode_combo, "translation_only"
            ),
            "capture_mode": self._capture_mode(),
            "audio_source": self._audio_source(),
            "audio_device_id": "",
            "meeting_device_id": "",
            "voice_output_enabled": self.voice_output_checkbox.isChecked(),
            "voice_output_device_id": "",
            "meeting_voice_enabled": self.meeting_voice_checkbox.isChecked(),
            "meeting_voice_device_id": str(self.meeting_voice_combo.currentData() or ""),
            "english_voice": self._combo_data(self.english_voice_combo, "en-ljspeech"),
            "context_window": int(self.context_spin.value()),
            "max_duration_s": duration_value,
            "vad_type": self._combo_data(self.vad_combo, "silero"),
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
        self._set_combo_data(self.model_combo, values["model_size"], DEFAULT_SETTINGS["model_size"])
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
        self.voice_output_checkbox.setChecked(bool(values.get("voice_output_enabled", False)))
        self.meeting_voice_checkbox.setChecked(bool(values.get("meeting_voice_enabled", False)))
        self._set_combo_data(self.english_voice_combo, values.get("english_voice", "en-ljspeech"), "en-ljspeech")
        self._refresh_voice_devices(values)
        self.context_spin.setValue(int(values["context_window"]))
        self.duration_spin.setValue(float(values["max_duration_s"]))
        self._set_combo_data(self.vad_combo, values["vad_type"], DEFAULT_SETTINGS["vad_type"])
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

        self._on_vad_type_changed(self._combo_data(self.vad_combo, "silero"))

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
        if not self.resolve_unsaved_changes():
            event.ignore()
            return
        event.accept()
        self.closed.emit()

    def resolve_unsaved_changes(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        choice = ask_unsaved_settings(self)
        if choice == "save":
            try:
                self._on_save_clicked()
            except Exception as exc:
                show_error(self, "Não foi possível salvar", str(exc))
                return False
            return True
        if choice == "discard":
            self._load_settings()
            return True
        return False

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
        self.save_button.clearFocus()

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
            model_size=self._combo_data(self.model_combo, "small"),
            device=self._device_preference(),
            language=(meeting_language if audio_source == "loopback" else user_language),
            target_language=(user_language if audio_source == "loopback" else meeting_language),
            user_language=user_language,
            meeting_language=meeting_language,
            display_mode=self._combo_data(
                self.display_mode_combo, "translation_only"
            ),
            # O diagnostico desta janela nao possui o botao de PTT; usa VAD.
            capture_mode="automatic",
            audio_source=audio_source,
            audio_device_id=None,
            meeting_device_id=None,
            voice_output_enabled=self.voice_output_checkbox.isChecked() and audio_source != "loopback",
            voice_output_device_id=None,
            meeting_voice_enabled=self.meeting_voice_checkbox.isChecked() and audio_source != "microphone",
            meeting_voice_device_id=str(self.meeting_voice_combo.currentData() or "") or None,
            english_voice=self._combo_data(self.english_voice_combo, "en-ljspeech"),
            context_window=int(self.context_spin.value()),
            max_duration_s=max_duration,
            vad_type=self._combo_data(self.vad_combo, "silero"),
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
        use_silero = self._combo_data(self.vad_combo, "silero") == "silero"
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
        self.base_language_combo.setEnabled(not is_running)
        self.meeting_language_combo.setEnabled(not is_running)
        self.display_mode_combo.setEnabled(not is_running)
        self.capture_mode_combo.setEnabled(not is_running)
        self.audio_source_combo.setEnabled(not is_running)
        cable_available = vb_cable_status(get_audio_device_catalog()) == "available"
        self.virtual_cable_install_button.setEnabled(not is_running and not self._cable_installing)
        self.voice_output_checkbox.setEnabled(
            not is_running and cable_available and self._audio_source() != "loopback"
        )
        self.meeting_voice_checkbox.setEnabled(not is_running and self._audio_source() != "microphone")
        self.meeting_voice_combo.setEnabled(not is_running and self._audio_source() != "microphone" and bool(self.meeting_voice_combo.currentData()))
        self.english_voice_combo.setEnabled(not is_running)
        self.context_spin.setEnabled(not is_running)
        self.duration_spin.setEnabled(not is_running)
        self.vad_combo.setEnabled(not is_running)
        self.speech_peak_spin.setEnabled(not is_running)
        self.silero_threshold_spin.setEnabled(not is_running and self._combo_data(self.vad_combo, "silero") == "silero")
        self.silero_min_silence_spin.setEnabled(not is_running and self._combo_data(self.vad_combo, "silero") == "silero")
        self.silero_pad_spin.setEnabled(not is_running and self._combo_data(self.vad_combo, "silero") == "silero")
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
            button.setEnabled(
                not is_running and not self._language_pack_busy
                and not bool(button.property("system_installed"))
            )

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
        preferred = self._device_preference()
        if status.is_fallback or status.active_device.value != preferred:
            self.hardware_indicator.setText("!")
            self.hardware_indicator.setStyleSheet("color: #FBBF24; font-weight: 800; font-size: 17px;")
        else:
            self.hardware_indicator.setText("✓")
            self.hardware_indicator.setStyleSheet("color: #34D399; font-weight: 800; font-size: 17px;")
        self.hardware_indicator.setToolTip(status.tooltip)

        if status.active_device == ActiveDevice.GPU:
            color = "rgba(34, 197, 94, 0.28)"
            border = "rgba(34, 197, 94, 0.75)"
        elif status.is_fallback:
            color = "rgba(245, 158, 11, 0.24)"
            border = "rgba(245, 158, 11, 0.75)"
        else:
            color = "rgba(70, 73, 251, 0.24)"
            border = "rgba(148, 163, 184, 0.45)"

        self.active_device_label.setStyleSheet(
            f"background: {color}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 3px 10px; font-weight: 700;"
        )

    def _reset_runtime_status(self) -> None:
        self.active_device_label.setText("Esperando iniciar...")
        self.active_device_label.setToolTip("Dispositivo em uso durante a sessão.")
        self.active_device_label.setStyleSheet("")
        self.hardware_indicator.setText("")
        self.hardware_indicator.setToolTip("")
        self.device_combo.setToolTip(
            "A GPU é priorizada. A CPU é usada por escolha ou como alternativa automática."
        )

    def _set_status(self, message: str) -> None:
        """Atualiza mensagem de status na barra inferior."""
        self.status_label.setText(message)
