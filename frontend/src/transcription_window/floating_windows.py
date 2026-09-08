from __future__ import annotations

import html
from typing import TYPE_CHECKING, Union

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .settings_store import load_settings, save_settings

if TYPE_CHECKING:
    from .backend_bridge import TranslationChunk


class FloatingTranscriptionWindow(QWidget):
    """Janela flutuante (overlay) para exibicao em baloes de chat (estilo WhatsApp)."""

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
        width = int(values.get("ui_transcription_window_width", 520))
        height = int(values.get("ui_transcription_window_height", 420))
        self.resize(width, height)

        saved_x = int(values.get("ui_transcription_window_x", -1))
        saved_y = int(values.get("ui_transcription_window_y", -1))
        if saved_x >= 0 and saved_y >= 0:
            self.move(saved_x, saved_y)

        self.apply_font_size(int(values.get("ui_transcription_font_size", 14)))

    def _build_ui(self) -> None:
        main_widget = QFrame()
        main_widget.setObjectName("transcriptionFrame")
        main_widget.setStyleSheet(
            """
            #transcriptionFrame {
                background: rgba(15, 23, 42, 0.94);
                border-radius: 16px;
                border: 1px solid rgba(70, 73, 251, 0.4);
            }
            """
        )
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Cabecalho da janela de chat
        header = QFrame()
        header.setObjectName("transcriptionHeader")
        header.setStyleSheet(
            """
            #transcriptionHeader {
                background: rgba(30, 41, 59, 0.85);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 10, 6)

        title = QLabel("Global Voice")
        title.setObjectName("transcriptionTitle")
        title.setStyleSheet("color: #E2E8F0; font-weight: 700; font-size: 13px; letter-spacing: 0.5px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #CBD5E1;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.9);
                color: white;
            }
            QPushButton:pressed {
                background: rgba(185, 28, 28, 1);
            }
            """
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # Area de exibicao em baloes de mensagens
        self.transcription_area = QTextEdit()
        self.transcription_area.setReadOnly(True)
        self.transcription_area.setPlaceholderText(
            "Aguardando áudio...\n\n"
            "• Reunião: falas capturadas da chamada (balão à esquerda).\n"
            "• Você: falas capturadas do seu microfone (balão à direita)."
        )
        self.transcription_area.setStyleSheet(
            """
            QTextEdit {
                background: rgba(10, 15, 29, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                color: #F8FAFC;
                padding: 10px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 0 4px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(70, 73, 251, 0.4);
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(70, 73, 251, 0.8);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )
        layout.addWidget(self.transcription_area)

        # Grip para redimensionamento
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

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = self.pos()
            save_settings(
                {
                    "ui_transcription_window_x": pos.x(),
                    "ui_transcription_window_y": pos.y(),
                }
            )
        super().mouseReleaseEvent(event)

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

    def append_chunk(self, chunk: Union[TranslationChunk, str]) -> None:
        """Renderiza as falas como baloes de conversa (estilo WhatsApp)."""
        if not chunk:
            return

        cursor = self.transcription_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.transcription_area.setTextCursor(cursor)

        if hasattr(chunk, "format_for_display"):
            channel_name = getattr(chunk, "channel", "meeting")
            orig = html.escape(getattr(chunk, "original_text", "")).strip()
            trad = html.escape(getattr(chunk, "translated_text", "")).strip()
            display_mode = getattr(chunk, "display_mode", "translation_only")

            if channel_name == "user":
                align = "right"
                bubble_bg = "#075E54"
                border_color = "#128C7E"
                sender_label = "Você"
                badge_color = "#25D366"
            else:
                align = "left"
                bubble_bg = "#1E293B"
                border_color = "#334155"
                sender_label = "Reunião"
                badge_color = "#818CF8"

            content_parts = []
            if display_mode in ("transcript_only", "both") and orig:
                content_parts.append(
                    f'<div style="font-size: 11px; color: #94A3B8; margin-bottom: 2px;">{orig}</div>'
                )
            if display_mode in ("translation_only", "both") and trad:
                content_parts.append(
                    f'<div style="font-size: 13px; font-weight: 600; color: #F8FAFC;">{trad}</div>'
                )

            if not content_parts:
                content_parts.append(f'<div style="font-size: 13px; color: #F8FAFC;">{orig or trad}</div>')

            inner_content = "".join(content_parts)

            bubble_html = (
                f'<div align="{align}" style="margin-top: 6px; margin-bottom: 6px;">'
                f'<div style="display: inline-block; max-width: 82%; background-color: {bubble_bg}; '
                f'border: 1px solid {border_color}; border-radius: 12px; padding: 8px 12px; text-align: left;">'
                f'<div style="font-size: 10px; font-weight: bold; color: {badge_color}; '
                f'text-transform: uppercase; margin-bottom: 3px;">{sender_label}</div>'
                f'{inner_content}'
                f'</div></div>'
            )
            self.transcription_area.insertHtml(bubble_html)
        else:
            escaped_text = html.escape(str(chunk))
            self.transcription_area.insertPlainText(f" {escaped_text}")

        self.transcription_area.ensureCursorVisible()

    def append_text(self, text: str) -> None:
        self.append_chunk(text)

    def clear(self) -> None:
        self.transcription_area.clear()

    def apply_font_size(self, size: int) -> None:
        size = max(10, min(size, 28))
        font = self.transcription_area.font()
        font.setPointSize(size)
        self.transcription_area.setFont(font)


def _build_gear_icon(size: int = 16, color: str = "#CBD5E1") -> QIcon:
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


def _build_chat_icon(size: int = 16, color: str = "#CBD5E1") -> QIcon:
    """Desenha um icone vetorial de balao de chat."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.addRoundedRect(1, 1, size - 2, size - 5, 3.5, 3.5)

    tail = QPainterPath()
    tail.moveTo(3, size - 4)
    tail.lineTo(3, size - 1)
    tail.lineTo(7, size - 4)
    tail.closeSubpath()
    path.addPath(tail)

    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _build_trash_icon(size: int = 16, color: str = "#CBD5E1") -> QIcon:
    """Desenha um icone vetorial de lixeira."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.addRoundedRect(2, 2, size - 4, 2, 1, 1)
    path.addRoundedRect(size / 2 - 2, 0.5, 4, 2, 0.5, 0.5)
    path.addRoundedRect(3, 5, size - 6, size - 6, 1.5, 1.5)

    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante tipo capsule pill para controle da sessao."""

    closed = Signal()
    settings_requested = Signal()
    action_toggled = Signal(bool)
    ptt_pressed = Signal()
    ptt_released = Signal()
    toggle_chat_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(52)
        self.setMinimumWidth(430)

        self.drag_position = QPoint()
        self._is_active = False

        # Instanciados aqui para garantir compatibilidade com as conexoes da MainWindow
        self.start_btn = QPushButton()
        self.stop_btn = QPushButton()

        self._build_ui()
        self.set_idle()

    def _create_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.12); margin-top: 6px; margin-bottom: 6px;")
        return sep

    def _build_ui(self) -> None:
        main_widget = QFrame()
        main_widget.setObjectName("toolbarFrame")
        main_widget.setStyleSheet(
            """
            #toolbarFrame {
                background: rgba(15, 23, 42, 0.94);
                border-radius: 26px;
                border: 1px solid rgba(70, 73, 251, 0.35);
            }
            #toolbarFrame QPushButton {
                border-radius: 12px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
                color: #FFFFFF;
                border: none;
            }
            #toolbarFrame QPushButton#actionBtn[active="false"] {
                background: rgba(70, 73, 251, 0.95);
            }
            #toolbarFrame QPushButton#actionBtn[active="false"]:hover {
                background: rgba(70, 73, 251, 1);
            }
            #toolbarFrame QPushButton#actionBtn[active="true"] {
                background: rgba(220, 38, 38, 0.95);
            }
            #toolbarFrame QPushButton#actionBtn[active="true"]:hover {
                background: rgba(220, 38, 38, 1);
            }
            #toolbarFrame QPushButton#pttBtn {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid rgba(70, 73, 251, 0.4);
                color: #CBD5E1;
            }
            #toolbarFrame QPushButton#pttBtn:hover {
                background: rgba(70, 73, 251, 0.3);
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn:pressed {
                background: #059669;
                border-color: #10B981;
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn:disabled {
                background: rgba(30, 41, 59, 0.3);
                border-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.25);
            }
            #toolbarFrame QToolButton {
                background: rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                border: 1px solid rgba(70, 73, 251, 0.25);
                padding: 4px;
            }
            #toolbarFrame QToolButton:hover {
                background: rgba(70, 73, 251, 0.5);
            }
            #toolbarFrame QToolButton#closeToolbarButton:hover {
                background: rgba(220, 38, 38, 0.9);
                border-color: rgba(220, 38, 38, 0.9);
            }
            """
        )
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(8)

        # 1. Opcoes / Configuracoes
        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("settingsToolbarButton")
        self.settings_btn.setIcon(_build_gear_icon(16))
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Opções")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setAutoRaise(True)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        layout.addWidget(self._create_separator())

        # 2. Seletor de Idiomas em Pilula com Setas e Inversao
        lang_group = QFrame()
        lang_group.setStyleSheet(
            """
            QFrame {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(70, 73, 251, 0.35);
                border-radius: 14px;
            }
            QComboBox {
                background: transparent;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border: none;
                padding: 3px 6px;
                min-width: 44px;
            }
            QComboBox:hover {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 6px;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background: #0F172A;
                color: #FFFFFF;
                selection-background-color: #4338CA;
                selection-color: #FFFFFF;
                border: 1px solid rgba(70, 73, 251, 0.5);
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QToolButton#swapLangBtn {
                background: transparent;
                border: none;
                color: #94A3B8;
                font-size: 12px;
                font-weight: bold;
                padding: 1px 3px;
                border-radius: 6px;
            }
            QToolButton#swapLangBtn:hover {
                background: rgba(70, 73, 251, 0.5);
                color: #FFFFFF;
            }
            """
        )
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.setContentsMargins(4, 2, 4, 2)
        lang_layout.setSpacing(1)

        self.source_combo = QComboBox()
        self.source_combo.addItem("PT ▾", "pt-br")
        self.source_combo.addItem("EN ▾", "en")
        self.source_combo.addItem("ES ▾", "es")

        self.swap_btn = QToolButton()
        self.swap_btn.setObjectName("swapLangBtn")
        self.swap_btn.setText("⇄")
        self.swap_btn.setToolTip("Inverter idiomas")
        self.swap_btn.setCursor(Qt.PointingHandCursor)
        self.swap_btn.clicked.connect(self._swap_languages)

        self.target_combo = QComboBox()
        self.target_combo.addItem("EN ▾", "en")
        self.target_combo.addItem("PT ▾", "pt-br")
        self.target_combo.addItem("ES ▾", "es")

        lang_layout.addWidget(self.source_combo)
        lang_layout.addWidget(self.swap_btn)
        lang_layout.addWidget(self.target_combo)
        layout.addWidget(lang_group)

        layout.addWidget(self._create_separator())

        # 3. Acoes Principais (Iniciar/Parar + PTT)
        self.action_btn = QPushButton("▶ Iniciar")
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.setProperty("active", "false")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.ptt_btn = QPushButton("🎤 Falar")
        self.ptt_btn.setObjectName("pttBtn")
        self.ptt_btn.setToolTip("Mantenha pressionado para falar na chamada")
        self.ptt_btn.setCursor(Qt.PointingHandCursor)
        self.ptt_btn.setEnabled(False)
        self.ptt_btn.pressed.connect(self.ptt_pressed.emit)
        self.ptt_btn.released.connect(self.ptt_released.emit)
        layout.addWidget(self.ptt_btn)

        layout.addWidget(self._create_separator())

        # 4. Utilitarios (Toggle Chat + Limpar)
        self.toggle_chat_btn = QToolButton()
        self.toggle_chat_btn.setObjectName("toggleChatBtn")
        self.toggle_chat_btn.setIcon(_build_chat_icon(16))
        self.toggle_chat_btn.setIconSize(QSize(16, 16))
        self.toggle_chat_btn.setFixedSize(28, 28)
        self.toggle_chat_btn.setToolTip("Mostrar ou ocultar janela de mensagens")
        self.toggle_chat_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat_requested.emit)
        layout.addWidget(self.toggle_chat_btn)

        self.clear_btn = QToolButton()
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setIcon(_build_trash_icon(16))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setToolTip("Limpar mensagens em tela")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.clear_btn)

        layout.addWidget(self._create_separator())

        # 5. Indicador de Status
        self.status_indicator = QLabel("⚪")
        self.status_indicator.setStyleSheet("font-size: 11px;")
        self.status_text = QLabel("")
        self.status_text.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        self.status_text.setFixedWidth(58)
        self.status_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        status_group = QFrame()
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_text)
        layout.addWidget(status_group)

        # 6. Fechar Toolbar
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("closeToolbarButton")
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setToolTip("Fechar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setAutoRaise(True)
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)
        self.adjustSize()

    def _swap_languages(self) -> None:
        src_idx = self.source_combo.currentIndex()
        tgt_idx = self.target_combo.currentIndex()
        src_data = self.source_combo.itemData(src_idx)
        tgt_data = self.target_combo.itemData(tgt_idx)

        new_src = self.source_combo.findData(tgt_data)
        new_tgt = self.target_combo.findData(src_data)

        if new_src >= 0:
            self.source_combo.setCurrentIndex(new_src)
        if new_tgt >= 0:
            self.target_combo.setCurrentIndex(new_tgt)

    def _on_action_clicked(self) -> None:
        if not self._is_active:
            self.start_btn.click()
        else:
            self.stop_btn.click()

    def set_buttons_state(self, is_running: bool, allow_stop: bool = True) -> None:
        self._is_active = is_running
        if is_running:
            self.action_btn.setText("⏹ Parar")
            self.action_btn.setProperty("active", "true")
            self.action_btn.setEnabled(allow_stop)
            self.ptt_btn.setEnabled(True)
        else:
            self.action_btn.setText("▶ Iniciar")
            self.action_btn.setProperty("active", "false")
            self.action_btn.setEnabled(True)
            self.ptt_btn.setEnabled(False)

        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)
        self.clear_btn.setEnabled(True)

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
        self.set_status_message("Aguardando início")

    def set_active(self, message: str | None = None) -> None:
        self.status_indicator.setText("🟢")
        self.status_text.setText("Ativa")
        self.set_status_message(message or "Tradução ativa")

    def set_connecting(self, message: str | None = None) -> None:
        self.status_indicator.setText("🟡")
        self.status_text.setText("Carregando")
        self.set_status_message(message or "Carregando...")

    def get_language_code(self, combo_text: str) -> str:
        clean = combo_text.replace("▾", "").strip()
        mapping = {
            "PT": "pt-br",
            "EN": "en",
            "ES": "es",
            "Português (PT)": "pt-br",
            "Inglês (EN)": "en",
            "Espanhol (ES)": "es",
        }
        return mapping.get(clean, "pt-br")