<<<<<<< Updated upstream
from __future__ import annotations

import html
from typing import Union

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTextCursor,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
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

from backend.app.runtime_status import RuntimeStatus

from .settings_store import load_settings, save_settings


# ======================================================================
# WIDGETS AUXILIARES
# ======================================================================


class TranscriptionTextEdit(QTextEdit):
    """Area de texto com zoom previsivel, inclusive enquanto esta vazia."""

    font_size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_font_size = 14
        self._empty_state_label = QLabel(self.viewport())
        self._empty_state_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._empty_state_label.setStyleSheet(
            "background: transparent; color: rgba(248, 250, 252, 0.40); border: none;"
        )
        self.textChanged.connect(self._sync_empty_state)

    def set_empty_state_text(self, text: str) -> None:
        self._empty_state_label.setText(text)
        self._sync_empty_state()

    @property
    def display_font_size(self) -> int:
        return self._display_font_size

    def set_display_font_size(self, size: int) -> None:
        self._display_font_size = max(10, min(int(size), 28))
        font = self.font()
        font.setPointSize(self._display_font_size)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self._empty_state_label.setFont(font)
        self._layout_empty_state()
        self.viewport().update()

    def adjust_font_size(self, steps: int) -> None:
        new_size = max(10, min(self._display_font_size + int(steps), 28))
        if new_size == self._display_font_size:
            return
        self.set_display_font_size(new_size)
        self.font_size_changed.emit(new_size)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.adjust_font_size(1 if delta > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_empty_state()

    def _layout_empty_state(self) -> None:
        margin = 10
        self._empty_state_label.setGeometry(
            margin,
            margin,
            max(0, self.viewport().width() - (margin * 2)),
            max(0, self.viewport().height() - (margin * 2)),
        )

    def _sync_empty_state(self) -> None:
        self._empty_state_label.setVisible(self.document().isEmpty())
        self._empty_state_label.raise_()


class LanguageComboBox(QComboBox):
    """Seletor compacto com popup proprio, alinhado e transparente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)
            line_edit.setAlignment(Qt.AlignCenter)
            line_edit.setFocusPolicy(Qt.NoFocus)
            line_edit.setTextMargins(0, 0, 0, 4)
            line_edit.installEventFilter(self)
        self.currentIndexChanged.connect(self._sync_compact_text)
        self._language_popup: QWidget | None = None
        self._popup_buttons: list[QToolButton] = []

    def add_language(self, abbreviation: str, name: str, code: str) -> None:
        self.addItem(abbreviation, code)
        index = self.count() - 1
        self.setItemData(index, name, Qt.ToolTipRole)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.lineEdit():
            if event.type() == QEvent.MouseButtonPress:
                return True
            if event.type() == QEvent.MouseButtonRelease:
                if self.isEnabled():
                    QTimer.singleShot(0, self.showPopup)
                return True
        return super().eventFilter(watched, event)

    def showPopup(self) -> None:
        self._build_language_popup()
        if self._language_popup is None:
            return
        self._language_popup.setFixedWidth(self.width())
        self._refresh_popup_selection()
        popup_position = self.mapToGlobal(QPoint(0, self.height() + 2))
        self._language_popup.move(popup_position)
        self._language_popup.show()
        self._language_popup.raise_()

    def hidePopup(self) -> None:
        if self._language_popup is not None:
            self._language_popup.hide()

    def _build_language_popup(self) -> None:
        if self._language_popup is not None:
            return

        popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground)
        popup.setObjectName("languagePopup")

        frame = QFrame(popup)
        frame.setObjectName("languagePopupPanel")
        frame.setStyleSheet(
            """
            QFrame#languagePopupPanel {
                background: #0F172A;
                border: 1px solid rgba(99, 102, 241, 0.55);
                border-radius: 12px;
            }
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 700;
                padding: 0px;
            }
            QToolButton:hover {
                background: rgba(99, 102, 241, 0.45);
            }
            QToolButton[selected="true"] {
                background: rgba(99, 102, 241, 0.85);
            }
            """
        )

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(frame)

        option_layout = QVBoxLayout(frame)
        option_layout.setContentsMargins(1, 1, 1, 1)
        option_layout.setSpacing(1)

        self._popup_buttons = []
        for index in range(self.count()):
            option = QToolButton(frame)
            option.setText(self.itemText(index))
            option.setToolTip(str(self.itemData(index, Qt.ToolTipRole) or ""))
            option.setFixedHeight(26)
            option.setCursor(Qt.PointingHandCursor)
            option.clicked.connect(
                lambda checked=False, selected=index: self._select_popup_language(
                    selected
                )
            )
            option_layout.addWidget(option)
            self._popup_buttons.append(option)

        popup.setFixedSize(self.width(), (self.count() * 27) + 3)
        self._language_popup = popup

    def _select_popup_language(self, index: int) -> None:
        self.setCurrentIndex(index)
        self._sync_compact_text()
        self.hidePopup()

    def _refresh_popup_selection(self) -> None:
        for index, option in enumerate(self._popup_buttons):
            option.setProperty("selected", str(index == self.currentIndex()).lower())
            option.style().unpolish(option)
            option.style().polish(option)

    def _sync_compact_text(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setText(self.itemText(self.currentIndex()) or "PT")


# ======================================================================
# ÍCONES VETORIAIS
# ======================================================================


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
        tooth_path.addRoundedRect(-tooth_w / 2.0, -(outer_r + tooth_h), tooth_w, tooth_h, 1.5, 1.5)
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


def _build_play_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(size * 0.30, size * 0.18)
    path.lineTo(size * 0.78, size * 0.50)
    path.lineTo(size * 0.30, size * 0.82)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _build_stop_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(int(size * 0.25), int(size * 0.25), int(size * 0.50), int(size * 0.50), 2, 2)
    painter.end()
    return QIcon(pixmap)


def _build_microphone_icon(size: int = 16, color: str = "#64748B", muted: bool = False) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(1.4, size * 0.10))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(
        int(size * 0.34), int(size * 0.08), int(size * 0.32), int(size * 0.52),
        int(size * 0.16), int(size * 0.16),
    )
    path = QPainterPath()
    path.moveTo(size * 0.20, size * 0.45)
    path.cubicTo(size * 0.20, size * 0.76, size * 0.80, size * 0.76, size * 0.80, size * 0.45)
    painter.drawPath(path)
    painter.drawLine(QPointF(size * 0.50, size * 0.72), QPointF(size * 0.50, size * 0.90))
    painter.drawLine(QPointF(size * 0.34, size * 0.90), QPointF(size * 0.66, size * 0.90))
    if muted:
        slash_pen = QPen(QColor(color), max(1.8, size * 0.13))
        slash_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(QPointF(size * 0.18, size * 0.16), QPointF(size * 0.82, size * 0.84))
    painter.end()
    return QIcon(pixmap)


def _build_swap_icon(size: int = 16, color: str = "#94A3B8") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(1.2, size * 0.09))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    upper = QPainterPath()
    upper.moveTo(size * 0.18, size * 0.34)
    upper.lineTo(size * 0.76, size * 0.34)
    upper.moveTo(size * 0.62, size * 0.20)
    upper.lineTo(size * 0.78, size * 0.34)
    upper.lineTo(size * 0.62, size * 0.48)
    painter.drawPath(upper)
    lower = QPainterPath()
    lower.moveTo(size * 0.82, size * 0.66)
    lower.lineTo(size * 0.24, size * 0.66)
    lower.moveTo(size * 0.38, size * 0.52)
    lower.lineTo(size * 0.22, size * 0.66)
    lower.lineTo(size * 0.38, size * 0.80)
    painter.drawPath(lower)
    painter.end()
    return QIcon(pixmap)


# ======================================================================
# JANELA DE TRANSCRIÇÃO
# ======================================================================


class FloatingTranscriptionWindow(QWidget):
    """Janela flutuante (overlay) para exibicao em baloes de chat."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(360, 240)

        self.drag_position = QPoint()
        self._new_speech_pending = True
        self._session_running = False
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
                background: rgba(15, 23, 42, 0.96);
                border-radius: 18px;
                border: 1px solid rgba(99, 102, 241, 0.35);
            }
            """
        )

        shadow = QGraphicsDropShadowEffect(main_widget)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 8)
        main_widget.setGraphicsEffect(shadow)

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # ---- HEADER ----
        header = QFrame()
        header.setObjectName("transcriptionHeader")
        header.setStyleSheet(
            """
            #transcriptionHeader {
                background: rgba(30, 41, 59, 0.85);
                border-radius: 12px;
                border: 1px solid rgba(148, 163, 184, 0.12);
            }
            """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)
        header_layout.setSpacing(10)

        # Logo pequeno no header
        logo_label = QLabel()
        logo_label.setPixmap(_build_transcription_logo(22).pixmap(22, 22))
        logo_label.setFixedSize(22, 22)

        # Bolinha de status (verde = ativo, cinza = inativo)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet(
            "background: #64748B; border: none; border-radius: 4px;"
        )

        title = QLabel("Global Voice")
        title.setObjectName("transcriptionTitle")
        title.setStyleSheet(
            "color: #F8FAFC; font-weight: 700; font-size: 13px; "
            "letter-spacing: 0.4px; background: transparent;"
        )

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.status_dot)
        header_layout.addStretch()

        close_btn = QToolButton()
        close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setToolTip("Ocultar transcrição")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            """
            QToolButton {
                background: rgba(255, 255, 255, 0.06);
                border-radius: 9px;
                border: 1px solid rgba(99, 102, 241, 0.20);
            }
            QToolButton:hover {
                background: rgba(220, 38, 38, 0.9);
                border-color: rgba(220, 38, 38, 0.9);
                color: white;
            }
            QToolButton:pressed {
                background: rgba(185, 28, 28, 1);
            }
            """
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # ---- ÁREA DE TRANSCRIÇÃO ----
        self.transcription_area = TranscriptionTextEdit()
        self.transcription_area.setReadOnly(True)
        self.transcription_area.set_empty_state_text(
            "Aguardando áudio...\n\n"
            "A transcrição aparecerá aqui durante a sessão."
        )
        self.transcription_area.setStyleSheet(
            """
            QTextEdit {
                background: rgba(10, 15, 29, 0.9);
                border: 1px solid rgba(148, 163, 184, 0.10);
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
                background: rgba(99, 102, 241, 0.5);
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(129, 140, 248, 0.9);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )
        self.transcription_area.font_size_changed.connect(
            lambda size: save_settings({"ui_transcription_font_size": size})
        )
        layout.addWidget(self.transcription_area)

        # ---- FOOTER (legenda de canais + grip) ----
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(4, 0, 0, 0)
        footer_row.setSpacing(12)

        legend_meeting = self._build_legend_item("#818CF8", "Reunião")
        legend_user = self._build_legend_item("#25D366", "Você")

        footer_row.addWidget(legend_meeting)
        footer_row.addWidget(legend_user)
        footer_row.addStretch(1)

        self.size_grip = QSizeGrip(main_widget)
        self.size_grip.setFixedSize(16, 16)
        footer_row.addWidget(self.size_grip)

        layout.addLayout(footer_row)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)

    def _build_legend_item(self, color: str, label: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background: {color}; border: none; border-radius: 3px;")

        text = QLabel(label)
        text.setStyleSheet(
            "color: #94A3B8; font-size: 10px; font-weight: 600; background: transparent;"
        )

        layout.addWidget(dot)
        layout.addWidget(text)
        return widget

    # ---- Interação com o mouse ----

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

    # ---- Estado da sessão ----

    def set_session_running(self, running: bool) -> None:
        """Muda a bolinha do header: verde quando ativo, cinza quando inativo."""
        self._session_running = bool(running)
        if self._session_running:
            self.status_dot.setStyleSheet(
                "background: #10B981; border: none; border-radius: 4px;"
            )
        else:
            self.status_dot.setStyleSheet(
                "background: #64748B; border: none; border-radius: 4px;"
            )

    # ---- Conteúdo ----

    def append_chunk(self, chunk: Union[object, str]) -> None:
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
            escaped_text = html.escape(str(chunk).strip())
            if self._new_speech_pending:
                if self.transcription_area.toPlainText().strip():
                    self.transcription_area.insertHtml("<br><br>")
                self.transcription_area.insertHtml(
                    '<span style="font-size: 10px; font-weight: bold; '
                    'color: #818CF8;">TRANSCRIÇÃO</span><br>'
                )
                self._new_speech_pending = False
            elif (
                self.transcription_area.toPlainText()
                and not self.transcription_area.toPlainText().endswith((" ", "\n"))
            ):
                self.transcription_area.insertPlainText(" ")
            self.transcription_area.insertHtml(escaped_text)

        self.transcription_area.ensureCursorVisible()

    def append_text(self, text: str) -> None:
        self.append_chunk(text)

    def begin_speech(self) -> None:
        self._new_speech_pending = True

    def clear(self) -> None:
        self.transcription_area.clear()
        self._new_speech_pending = True

    def apply_font_size(self, size: int) -> None:
        self.transcription_area.set_display_font_size(size)


def _build_transcription_logo(size: int = 22) -> QIcon:
    """Logo pequeno de onda de voz para o header da janela de transcrição."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)

    center = size / 2.0
    radius = size * 0.46

    gradient = QRadialGradient(center, center * 0.7, center, center, radius)
    gradient.setColorAt(0.0, QColor("#6366F1"))
    gradient.setColorAt(1.0, QColor("#4F46E5"))
    painter.setBrush(gradient)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    painter.setBrush(QColor("#F8FAFC"))
    bar_width = size * 0.10
    bar_spacing = size * 0.15
    heights = [0.28, 0.52, 0.68, 0.44, 0.32]
    total_width = (len(heights) - 1) * bar_spacing
    start_x = center - total_width / 2.0
    for index, height_ratio in enumerate(heights):
        bar_height = size * height_ratio * 0.8
        x = start_x + index * bar_spacing - bar_width / 2.0
        y = center - bar_height / 2.0
        rect = QRectF(x, y, bar_width, bar_height)
        path = QPainterPath()
        path.addRoundedRect(rect, bar_width / 2.0, bar_width / 2.0)
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


# ======================================================================
# TOOLBAR FLUTUANTE
# ======================================================================


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante tipo capsule pill."""

    closed = Signal()
    settings_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    ptt_pressed = Signal()
    ptt_released = Signal()
    microphone_mute_changed = Signal(bool)
    source_language_changed = Signal(str)
    toggle_chat_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(58)
        self.setMinimumWidth(620)

        self.drag_position = QPoint()
        self._is_active = False
        self._allow_stop = False
        self._capture_mode = "automatic"
        self._microphone_muted = False
        self._voice_active = False
        self._updating_languages = False

        self._build_ui()
        self.set_idle()

    def _create_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setFixedWidth(1)
        sep.setStyleSheet(
            "background: rgba(148, 163, 184, 0.18); "
            "border: none; "
            "margin-top: 10px; margin-bottom: 10px;"
        )
        return sep

    def _build_ui(self) -> None:
        main_widget = QFrame()
        main_widget.setObjectName("toolbarFrame")
        main_widget.setStyleSheet(
            """
            #toolbarFrame {
                background: rgba(15, 23, 42, 0.96);
                border-radius: 18px;
                border: 1px solid rgba(99, 102, 241, 0.35);
            }
            #toolbarFrame QPushButton#actionBtn {
                border-radius: 12px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 13px;
                color: #FFFFFF;
                border: none;
            }
            #toolbarFrame QPushButton#actionBtn[active="false"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #4F46E5);
                padding-left: 10px;
            }
            #toolbarFrame QPushButton#actionBtn[active="false"]:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #818CF8, stop:1 #6366F1);
            }
            #toolbarFrame QPushButton#actionBtn[active="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #DC2626);
                padding-left: 10px;
            }
            #toolbarFrame QPushButton#actionBtn[active="true"]:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F87171, stop:1 #EF4444);
            }
            #toolbarFrame QPushButton#actionBtn[active="true"]:disabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: rgba(255, 255, 255, 0.9);
            }
            #toolbarFrame QPushButton#pttBtn {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 12px;
                color: #CBD5E1;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 12px;
            }
            #toolbarFrame QPushButton#pttBtn:hover {
                background: rgba(99, 102, 241, 0.30);
                border-color: rgba(129, 140, 248, 0.6);
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn:pressed {
                background: #059669;
                border-color: #10B981;
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn[voiceActive="true"] {
                background: rgba(16, 185, 129, 0.9);
                border-color: #34D399;
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn[muted="true"] {
                background: rgba(51, 65, 85, 0.7);
                border-color: rgba(100, 116, 139, 0.5);
                color: #CBD5E1;
            }
            #toolbarFrame QPushButton#pttBtn:disabled {
                background: rgba(30, 41, 59, 0.3);
                border-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.40);
            }
            #toolbarFrame QToolButton {
                background: rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                border: 1px solid rgba(99, 102, 241, 0.20);
                padding: 4px;
            }
            #toolbarFrame QToolButton:hover {
                background: rgba(99, 102, 241, 0.45);
                border-color: rgba(129, 140, 248, 0.55);
            }
            #toolbarFrame QToolButton:pressed {
                background: rgba(99, 102, 241, 0.65);
            }
            #toolbarFrame QToolButton#closeToolbarButton:hover {
                background: rgba(220, 38, 38, 0.9);
                border-color: rgba(220, 38, 38, 0.9);
            }
            #toolbarFrame QToolButton#closeToolbarButton:pressed {
                background: rgba(185, 28, 28, 1);
            }
            QFrame#languageGroup {
                background: rgba(30, 41, 59, 0.55);
                border: 1px solid rgba(99, 102, 241, 0.30);
                border-radius: 12px;
            }
            QFrame#languageGroup QComboBox {
                background: transparent;
                color: #F8FAFC;
                font-weight: 700;
                font-size: 12px;
                border: none;
                padding: 0px;
                border-radius: 12px;
            }
            QFrame#languageGroup QComboBox:hover {
                background: rgba(255, 255, 255, 0.06);
            }
            QFrame#languageGroup QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QFrame#languageGroup QToolButton#swapLangBtn {
                background: rgba(255, 255, 255, 0.04);
                border: none;
                color: #94A3B8;
                border-radius: 10px;
            }
            QFrame#languageGroup QToolButton#swapLangBtn:hover {
                background: rgba(99, 102, 241, 0.45);
                color: #FFFFFF;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect(main_widget)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 6)
        main_widget.setGraphicsEffect(shadow)

        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(10)

        # 1. Configurações
        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("settingsToolbarButton")
        self.settings_btn.setIcon(_build_gear_icon(18))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setToolTip("Opções")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setAutoRaise(True)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        layout.addWidget(self._create_separator())

        # 2. Idiomas
        lang_group = QFrame()
        lang_group.setObjectName("languageGroup")
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.setContentsMargins(2, 2, 2, 2)
        lang_layout.setSpacing(4)
        lang_group.setFixedHeight(32)
        self.language_group = lang_group

        self.source_combo = LanguageComboBox()
        self.source_combo.add_language("PT", "Português", "pt-br")
        self.source_combo.add_language("EN", "Inglês", "en")
        self.source_combo.add_language("ES", "Espanhol", "es")
        self._configure_language_combo(self.source_combo)

        self.swap_btn = QToolButton()
        self.swap_btn.setObjectName("swapLangBtn")
        self.swap_btn.setIcon(_build_swap_icon(16))
        self.swap_btn.setIconSize(QSize(16, 16))
        self.swap_btn.setFixedSize(28, 28)
        self.swap_btn.setToolTip("Inverter idiomas")
        self.swap_btn.setCursor(Qt.PointingHandCursor)
        self.swap_btn.clicked.connect(self._swap_languages)

        self.target_combo = LanguageComboBox()
        self.target_combo.add_language("EN", "Inglês", "en")
        self.target_combo.add_language("PT", "Português", "pt-br")
        self.target_combo.add_language("ES", "Espanhol", "es")
        self._configure_language_combo(self.target_combo)

        self.source_combo.setToolTip("Idioma do usuário")
        self.target_combo.setToolTip("Idioma da chamada")
        self.source_combo.currentIndexChanged.connect(self._on_source_language_changed)
        self.target_combo.currentIndexChanged.connect(self._on_target_language_changed)

        lang_layout.addWidget(self.source_combo)
        lang_layout.addWidget(self.swap_btn)
        lang_layout.addWidget(self.target_combo)
        lang_layout.setAlignment(self.swap_btn, Qt.AlignCenter)
        layout.addWidget(lang_group)

        layout.addWidget(self._create_separator())

        # 3. Ação + PTT
        self.action_btn = QPushButton("Iniciar")
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.setProperty("active", "false")
        self.action_btn.setToolTip("Iniciar transcrição")
        self.action_btn.setIcon(_build_play_icon(16))
        self.action_btn.setIconSize(QSize(16, 16))
        self.action_btn.setFixedSize(100, 32)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.ptt_btn = QPushButton("Falar")
        self.ptt_btn.setObjectName("pttBtn")
        self.ptt_btn.setIcon(_build_microphone_icon(17))
        self.ptt_btn.setIconSize(QSize(17, 17))
        self.ptt_btn.setToolTip(
            "Selecione 'Apertar para falar' nas configurações para usar este controle."
        )
        self.ptt_btn.setCursor(Qt.PointingHandCursor)
        self.ptt_btn.setEnabled(False)
        self.ptt_btn.setFixedSize(84, 32)
        self.ptt_btn.setProperty("voiceActive", "false")
        self.ptt_btn.setProperty("muted", "false")
        self.ptt_btn.pressed.connect(self._on_microphone_pressed)
        self.ptt_btn.released.connect(self._on_microphone_released)
        self.ptt_btn.clicked.connect(self._on_microphone_clicked)
        layout.addWidget(self.ptt_btn)

        layout.addWidget(self._create_separator())

        # 4. Utilitários
        self.toggle_chat_btn = QToolButton()
        self.toggle_chat_btn.setObjectName("toggleChatBtn")
        self.toggle_chat_btn.setIcon(_build_chat_icon(18))
        self.toggle_chat_btn.setIconSize(QSize(18, 18))
        self.toggle_chat_btn.setFixedSize(32, 32)
        self.toggle_chat_btn.setToolTip("Mostrar ou ocultar janela de mensagens")
        self.toggle_chat_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat_requested.emit)
        layout.addWidget(self.toggle_chat_btn)

        self.clear_btn = QToolButton()
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setIcon(_build_trash_icon(18))
        self.clear_btn.setIconSize(QSize(18, 18))
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setToolTip("Limpar mensagens em tela")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.clear_btn)

        layout.addWidget(self._create_separator())

        # 5. Indicador
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(10, 10)
        self.status_indicator.setStyleSheet(
            "background: #64748B; border: none; border-radius: 5px;"
        )

        self.runtime_group = QFrame()
        self.runtime_group.setObjectName("runtimeStatusGroup")
        status_layout = QHBoxLayout(self.runtime_group)
        status_layout.setContentsMargins(10, 3, 12, 3)
        status_layout.setSpacing(8)
        status_layout.addWidget(self.status_indicator)

        self.runtime_badge = QLabel("Esperando iniciar...")
        self.runtime_badge.setAlignment(Qt.AlignCenter)
        self.runtime_badge.setMinimumWidth(120)
        self.runtime_badge.setContentsMargins(0, 0, 0, 0)
        status_layout.addWidget(self.runtime_badge)
        self.runtime_group.setFixedHeight(32)
        layout.addWidget(self.runtime_group)
        self.reset_runtime_status()

        # 6. Fechar
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("closeToolbarButton")
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setToolTip("Fechar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setAutoRaise(True)
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)
        self.adjustSize()

    @staticmethod
    def _configure_language_combo(combo: QComboBox) -> None:
        combo.setFixedSize(30, 30)

    @staticmethod
    def _set_combo_language(combo: QComboBox, language: str) -> None:
        index = combo.findData(language)
        if index >= 0:
            combo.setCurrentIndex(index)
            if isinstance(combo, LanguageComboBox):
                combo._sync_compact_text()

    def set_source_language(self, language: str) -> None:
        normalized = language if language in {"pt-br", "en", "es"} else "pt-br"
        self._updating_languages = True
        try:
            self._set_combo_language(self.source_combo, normalized)
        finally:
            self._updating_languages = False

    def _emit_source_language(self) -> None:
        language = str(self.source_combo.currentData() or "pt-br")
        self.source_language_changed.emit(language)

    def _on_source_language_changed(self) -> None:
        if self._updating_languages:
            return
        self._emit_source_language()

    def _on_target_language_changed(self) -> None:
        return

    def _swap_languages(self) -> None:
        source = str(self.source_combo.currentData() or "pt-br")
        target = str(self.target_combo.currentData() or "en")
        self._updating_languages = True
        try:
            self._set_combo_language(self.source_combo, target)
            self._set_combo_language(self.target_combo, source)
        finally:
            self._updating_languages = False
        self._emit_source_language()

    def _on_action_clicked(self) -> None:
        if not self._is_active:
            self.start_requested.emit()
        elif self._allow_stop:
            self.stop_requested.emit()

    def set_capture_mode(self, mode: str) -> None:
        self._capture_mode = "push_to_talk" if mode == "push_to_talk" else "automatic"
        self._microphone_muted = False
        self._voice_active = False
        self._refresh_ptt_state()

    def _refresh_ptt_state(self) -> None:
        push_to_talk = self._capture_mode == "push_to_talk"
        self.ptt_btn.setEnabled(self._is_active and self._allow_stop)
        if push_to_talk:
            self.ptt_btn.setText("Falar")
            self.ptt_btn.setToolTip("Mantenha pressionado para captar sua fala.")
        else:
            self.ptt_btn.setText("Mudo" if self._microphone_muted else "Falar")
            self.ptt_btn.setToolTip(
                "Clique para reativar o microfone."
                if self._microphone_muted
                else "Clique para mutar o microfone; o verde indica voz detectada."
            )
        self.ptt_btn.setIcon(
            _build_microphone_icon(17, "#CBD5E1", muted=self._microphone_muted)
        )
        self._refresh_microphone_style()

    def _refresh_microphone_style(self) -> None:
        voice_active = (
            self._capture_mode == "automatic"
            and self._voice_active
            and not self._microphone_muted
        )
        self.ptt_btn.setProperty("voiceActive", str(voice_active).lower())
        self.ptt_btn.setProperty("muted", str(self._microphone_muted).lower())
        self.ptt_btn.style().unpolish(self.ptt_btn)
        self.ptt_btn.style().polish(self.ptt_btn)

    def set_voice_activity(self, active: bool) -> None:
        self._voice_active = bool(active)
        self._refresh_microphone_style()

    def reset_microphone_state(self) -> None:
        self._microphone_muted = False
        self._voice_active = False
        self._refresh_ptt_state()

    def _on_microphone_pressed(self) -> None:
        if self._capture_mode == "push_to_talk":
            self.ptt_pressed.emit()

    def _on_microphone_released(self) -> None:
        if self._capture_mode == "push_to_talk":
            self.ptt_released.emit()

    def _on_microphone_clicked(self) -> None:
        if self._capture_mode != "automatic" or not self._is_active:
            return
        self._microphone_muted = not self._microphone_muted
        if self._microphone_muted:
            self._voice_active = False
        self.microphone_mute_changed.emit(self._microphone_muted)
        self._refresh_ptt_state()

    def set_buttons_state(self, is_running: bool, allow_stop: bool = True) -> None:
        self._is_active = is_running
        self._allow_stop = allow_stop
        if is_running:
            self.action_btn.setText("Parar" if allow_stop else "Aguarde")
            self.action_btn.setIcon(_build_stop_icon(16))
            self.action_btn.setProperty("active", "true")
            self.action_btn.setEnabled(allow_stop)
            self.action_btn.setToolTip(
                "Parar transcrição" if allow_stop else "Aguarde o carregamento..."
            )
        else:
            self._microphone_muted = False
            self._voice_active = False
            self.action_btn.setText("Iniciar")
            self.action_btn.setIcon(_build_play_icon(16))
            self.action_btn.setProperty("active", "false")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip("Iniciar transcrição")

        self._refresh_ptt_state()
        self.source_combo.setEnabled(not is_running)
        self.target_combo.setEnabled(not is_running)
        self.swap_btn.setEnabled(not is_running)
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            pos = self.pos()
            save_settings(
                {
                    "ui_toolbar_x": pos.x(),
                    "ui_toolbar_y": pos.y(),
                }
            )
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closed.emit()
        event.accept()

    def set_status_message(self, message: str) -> None:
        self.status_indicator.setToolTip(message)
        self.runtime_group.setToolTip(message)

    def _set_runtime_visual_state(
        self,
        state: str,
        color: str,
        border: str,
        background: str,
    ) -> None:
        self.runtime_group.setProperty("state", state)
        self.status_indicator.setStyleSheet(
            f"background: {color}; border: none; border-radius: 5px;"
        )
        self.runtime_group.setStyleSheet(
            "QFrame#runtimeStatusGroup {"
            f"background: {background}; border: 1px solid {border}; "
            "border-radius: 12px; }"
            "QLabel { background: transparent; border: none; color: #F8FAFC; "
            "font-weight: 600; font-size: 11px; }"
        )

    def set_idle(self) -> None:
        self._set_runtime_visual_state(
            "idle", "#64748B", "rgba(148, 163, 184, 0.25)", "rgba(30, 41, 59, 0.55)"
        )
        self.set_status_message("Aguardando início")

    def set_active(self, message: str | None = None) -> None:
        self._set_runtime_visual_state(
            "active", "#10B981", "rgba(16, 185, 129, 0.55)", "rgba(16, 185, 129, 0.14)"
        )
        self.set_status_message(message or "Transcrição ativa")

    def set_connecting(self, message: str | None = None) -> None:
        self._set_runtime_visual_state(
            "loading", "#F59E0B", "rgba(245, 158, 11, 0.55)", "rgba(245, 158, 11, 0.14)"
        )
        self.set_status_message(message or "Carregando...")

    def set_runtime_pending(self) -> None:
        self.runtime_badge.setText("Verificando...")
        self.runtime_badge.setToolTip("Verificando o dispositivo solicitado.")
        self._set_runtime_visual_state(
            "loading", "#F59E0B", "rgba(245, 158, 11, 0.55)", "rgba(245, 158, 11, 0.14)"
        )

    def reset_runtime_status(self) -> None:
        self.runtime_badge.setText("Esperando iniciar...")
        self.runtime_badge.setToolTip("Dispositivo em uso durante a sessão.")
        self._set_runtime_visual_state(
            "idle", "#64748B", "rgba(148, 163, 184, 0.25)", "rgba(30, 41, 59, 0.55)"
        )

    def set_runtime_status(self, status: RuntimeStatus) -> None:
        self.runtime_badge.setText(status.display_label)
        self.runtime_badge.setToolTip(status.tooltip)
        if status.active_device.value == "gpu":
            color = "#10B981"
            border = "rgba(16, 185, 129, 0.55)"
            background = "rgba(16, 185, 129, 0.14)"
        elif status.is_fallback:
            color = "#F59E0B"
            border = "rgba(245, 158, 11, 0.55)"
            background = "rgba(245, 158, 11, 0.14)"
        else:
            color = "#64748B"
            border = "rgba(148, 163, 184, 0.25)"
            background = "rgba(30, 41, 59, 0.55)"
        self._set_runtime_visual_state("active", color, border, background)

    def get_language_code(self, combo_text: str) -> str:
        clean = combo_text.replace("▾", "").strip()
        mapping = {
            "PT": "pt-br", "EN": "en", "ES": "es",
            "Português (PT)": "pt-br", "Inglês (EN)": "en", "Espanhol (ES)": "es",
        }
=======
from __future__ import annotations

import html
from typing import Union

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QWheelEvent,
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

from backend.app.runtime_status import RuntimeStatus

from .settings_store import load_settings, save_settings


class TranscriptionTextEdit(QTextEdit):
    """Area de texto com zoom previsivel, inclusive enquanto esta vazia."""

    font_size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_font_size = 14
        self._empty_state_label = QLabel(self.viewport())
        self._empty_state_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._empty_state_label.setStyleSheet(
            "background: transparent; color: rgba(248, 250, 252, 0.45); border: none;"
        )
        self.textChanged.connect(self._sync_empty_state)

    def set_empty_state_text(self, text: str) -> None:
        self._empty_state_label.setText(text)
        self._sync_empty_state()

    @property
    def display_font_size(self) -> int:
        return self._display_font_size

    def set_display_font_size(self, size: int) -> None:
        self._display_font_size = max(10, min(int(size), 28))
        font = self.font()
        font.setPointSize(self._display_font_size)
        self.setFont(font)
        self.document().setDefaultFont(font)
        if not self.document().isEmpty():
            cursor = QTextCursor(self.document())
            cursor.select(QTextCursor.Document)
            text_format = QTextCharFormat()
            text_format.setFontPointSize(self._display_font_size)
            cursor.mergeCharFormat(text_format)
        self._empty_state_label.setFont(font)
        self._layout_empty_state()
        self.viewport().update()

    def adjust_font_size(self, steps: int) -> None:
        new_size = max(10, min(self._display_font_size + int(steps), 28))
        if new_size == self._display_font_size:
            return
        self.set_display_font_size(new_size)
        self.font_size_changed.emit(new_size)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.adjust_font_size(1 if delta > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_empty_state()

    def _layout_empty_state(self) -> None:
        margin = 10
        self._empty_state_label.setGeometry(
            margin,
            margin,
            max(0, self.viewport().width() - (margin * 2)),
            max(0, self.viewport().height() - (margin * 2)),
        )

    def _sync_empty_state(self) -> None:
        self._empty_state_label.setVisible(self.document().isEmpty())
        self._empty_state_label.raise_()


class LanguageComboBox(QComboBox):
    """Seletor compacto com popup próprio, alinhado e transparente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)
            line_edit.setAlignment(Qt.AlignCenter)
            line_edit.setFocusPolicy(Qt.NoFocus)
            line_edit.setTextMargins(0, 0, 0, 2)
            line_edit.installEventFilter(self)
        self.currentIndexChanged.connect(self._sync_compact_text)
        self._language_popup: QWidget | None = None
        self._popup_buttons: list[QToolButton] = []
        self._popup_open = False
        self._close_popup_on_release = False

    def add_language(self, abbreviation: str, name: str, code: str) -> None:
        self.addItem(abbreviation, code)
        index = self.count() - 1
        self.setItemData(index, name, Qt.ToolTipRole)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.lineEdit():
            if event.type() == QEvent.MouseButtonPress:
                self._close_popup_on_release = self._popup_open
                return True
            if event.type() == QEvent.MouseButtonRelease:
                if self._close_popup_on_release:
                    self._close_popup_on_release = False
                    self.hidePopup()
                elif self.isEnabled():
                    QTimer.singleShot(0, self.showPopup)
                return True
        if watched is self._language_popup and event.type() == QEvent.Hide:
            popup = watched
            QTimer.singleShot(150, lambda: self._release_auto_hidden_popup(popup))
        return super().eventFilter(watched, event)

    def showPopup(self) -> None:
        self._build_language_popup()
        if self._language_popup is None:
            return
        self._language_popup.setFixedWidth(self.width())
        self._refresh_popup_selection()
        popup_position = self.mapToGlobal(QPoint(0, self.height() + 2))
        self._language_popup.move(popup_position)
        self._popup_open = True
        self._language_popup.show()
        self._language_popup.raise_()

    def hidePopup(self) -> None:
        self._popup_open = False
        if self._language_popup is not None:
            self._language_popup.hide()

    def _build_language_popup(self) -> None:
        if self._language_popup is not None:
            return

        popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground)
        popup.setObjectName("languagePopup")

        frame = QFrame(popup)
        frame.setObjectName("languagePopupPanel")
        frame.setStyleSheet(
            """
            QFrame#languagePopupPanel {
                background: #0A0F1D;
                border: 1px solid rgba(99, 102, 241, 0.45);
                border-radius: 10px;
            }
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 700;
                padding: 0px;
            }
            QToolButton:hover {
                background: rgba(99, 102, 241, 0.45);
            }
            QToolButton[selected="true"] {
                background: rgba(99, 102, 241, 0.85);
            }
            """
        )

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(frame)

        option_layout = QVBoxLayout(frame)
        option_layout.setContentsMargins(1, 1, 1, 1)
        option_layout.setSpacing(1)

        self._popup_buttons = []
        for index in range(self.count()):
            option = QToolButton(frame)
            option.setText(self.itemText(index))
            option.setToolTip(str(self.itemData(index, Qt.ToolTipRole) or ""))
            option.setFixedHeight(24)
            option.setCursor(Qt.PointingHandCursor)
            option.clicked.connect(
                lambda checked=False, selected=index: self._select_popup_language(
                    selected
                )
            )
            option_layout.addWidget(option)
            self._popup_buttons.append(option)

        popup.setFixedSize(self.width(), (self.count() * 25) + 3)
        self._language_popup = popup
        popup.installEventFilter(self)

    def _release_auto_hidden_popup(self, popup: QWidget) -> None:
        if self._language_popup is not popup:
            return
        try:
            popup_visible = popup.isVisible()
        except RuntimeError:
            self._language_popup = None
            popup_visible = False
        if not popup_visible:
            self._popup_open = False

    def _select_popup_language(self, index: int) -> None:
        self.setCurrentIndex(index)
        self._sync_compact_text()
        self.hidePopup()

    def _refresh_popup_selection(self) -> None:
        for index, option in enumerate(self._popup_buttons):
            option.setProperty("selected", str(index == self.currentIndex()).lower())
            option.style().unpolish(option)
            option.style().polish(option)

    def _sync_compact_text(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setText(self.itemText(self.currentIndex()) or "PT")


class FloatingTranscriptionWindow(QWidget):
    """Janela flutuante para leitura continua das falas da sessao."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(360, 240)

        self.drag_position = QPoint()
        self._new_speech_pending = True
        self._active_channel: str | None = None
        self._group_chunk_count = 0
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
                background: rgba(10, 15, 29, 0.95);
                border-radius: 16px;
                border: 1px solid rgba(99, 102, 241, 0.35);
            }
            """
        )
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("transcriptionHeader")
        header.setStyleSheet(
            """
            #transcriptionHeader {
                background: rgba(30, 41, 59, 0.6);
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

        close_btn = QToolButton()
        close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setToolTip("Ocultar transcrição")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(
            """
            QToolButton {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                border: none;
            }
            QToolButton:hover {
                background: rgba(239, 68, 68, 0.9);
                color: white;
            }
            QToolButton:pressed {
                background: rgba(185, 28, 28, 1);
            }
            """
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        self.transcription_area = TranscriptionTextEdit()
        self.transcription_area.setReadOnly(True)
        self.transcription_area.set_empty_state_text(
            "Aguardando áudio...\n\n"
            "A transcrição aparecerá aqui durante a sessão."
        )
        self.transcription_area.setStyleSheet(
            """
            QTextEdit {
                background: rgba(15, 23, 42, 0.85);
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
                background: rgba(99, 102, 241, 0.4);
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(99, 102, 241, 0.8);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )
        self.transcription_area.font_size_changed.connect(
            lambda size: save_settings({"ui_transcription_font_size": size})
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

    def _insert_compact_pair_spacing(self) -> None:
        cursor = self.transcription_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock()
        block_format = cursor.blockFormat()
        block_format.setTopMargin(5.0)
        cursor.setBlockFormat(block_format)
        self.transcription_area.setTextCursor(cursor)

    def append_chunk(self, chunk: Union[object, str]) -> None:
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

            starts_new_group = (
                not self.transcription_area.toPlainText().strip()
                or self._new_speech_pending
                or self._active_channel != channel_name
            )
            if starts_new_group:
                if self.transcription_area.toPlainText().strip():
                    self.transcription_area.insertHtml("<br><br>")
                sender_label = "VOCÊ" if channel_name == "user" else "REUNIÃO"
                sender_color = "#34D399" if channel_name == "user" else "#818CF8"
                self.transcription_area.insertHtml(
                    f'<span style="font-weight: 700; color: {sender_color};">'
                    f"{sender_label}</span><br>"
                )
                self._group_chunk_count = 0
            elif self._group_chunk_count:
                if display_mode == "both":
                    self._insert_compact_pair_spacing()
                else:
                    self.transcription_area.insertHtml("<br>")

            content_parts = []
            if display_mode in ("transcript_only", "both") and orig:
                original_color = "#94A3B8" if display_mode == "both" else "#F8FAFC"
                content_parts.append(
                    f'<span style="color: {original_color};">{orig}</span>'
                )
            if display_mode in ("translation_only", "both") and trad:
                if content_parts:
                    content_parts.append("<br>")
                content_parts.append(
                    f'<span style="font-weight: 600; color: #F8FAFC;">{trad}</span>'
                )
            if not content_parts:
                content_parts.append(
                    f'<span style="color: #F8FAFC;">{orig or trad}</span>'
                )

            self.transcription_area.insertHtml("".join(content_parts))
            self._new_speech_pending = False
            self._active_channel = channel_name
            self._group_chunk_count += 1
        else:
            escaped_text = html.escape(str(chunk).strip())
            if self._new_speech_pending:
                if self.transcription_area.toPlainText().strip():
                    self.transcription_area.insertHtml("<br><br>")
                self.transcription_area.insertHtml(
                    '<span style="font-size: 10px; font-weight: bold; '
                    'color: #818CF8;">TRANSCRIÇÃO</span><br>'
                )
                self._new_speech_pending = False
            elif (
                self.transcription_area.toPlainText()
                and not self.transcription_area.toPlainText().endswith((" ", "\n"))
            ):
                self.transcription_area.insertPlainText(" ")
            self.transcription_area.insertHtml(escaped_text)

        self.transcription_area.ensureCursorVisible()

    def append_text(self, text: str) -> None:
        self.append_chunk(text)

    def begin_speech(self) -> None:
        self._new_speech_pending = True

    def clear(self) -> None:
        self.transcription_area.clear()
        self._new_speech_pending = True
        self._active_channel = None
        self._group_chunk_count = 0

    def apply_font_size(self, size: int) -> None:
        self.transcription_area.set_display_font_size(size)


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


def _build_play_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.moveTo(size * 0.30, size * 0.18)
    path.lineTo(size * 0.78, size * 0.50)
    path.lineTo(size * 0.30, size * 0.82)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _build_stop_icon(size: int = 16, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(
        int(size * 0.25),
        int(size * 0.25),
        int(size * 0.50),
        int(size * 0.50),
        2,
        2,
    )
    painter.end()
    return QIcon(pixmap)


def _build_microphone_icon(
    size: int = 16,
    color: str = "#CBD5E1",
    muted: bool = False,
) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(1.4, size * 0.10))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawRoundedRect(
        int(size * 0.34),
        int(size * 0.08),
        int(size * 0.32),
        int(size * 0.52),
        int(size * 0.16),
        int(size * 0.16),
    )
    path = QPainterPath()
    path.moveTo(size * 0.20, size * 0.45)
    path.cubicTo(size * 0.20, size * 0.76, size * 0.80, size * 0.76, size * 0.80, size * 0.45)
    painter.drawPath(path)
    painter.drawLine(QPointF(size * 0.50, size * 0.72), QPointF(size * 0.50, size * 0.90))
    painter.drawLine(QPointF(size * 0.34, size * 0.90), QPointF(size * 0.66, size * 0.90))
    if muted:
        slash_pen = QPen(QColor(color), max(1.8, size * 0.13))
        slash_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(
            QPointF(size * 0.18, size * 0.16),
            QPointF(size * 0.82, size * 0.84),
        )
    painter.end()
    return QIcon(pixmap)


def _build_swap_icon(size: int = 14, color: str = "#94A3B8") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(1.2, size * 0.09))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    upper = QPainterPath()
    upper.moveTo(size * 0.18, size * 0.34)
    upper.lineTo(size * 0.76, size * 0.34)
    upper.moveTo(size * 0.62, size * 0.20)
    upper.lineTo(size * 0.78, size * 0.34)
    upper.lineTo(size * 0.62, size * 0.48)
    painter.drawPath(upper)

    lower = QPainterPath()
    lower.moveTo(size * 0.82, size * 0.66)
    lower.lineTo(size * 0.24, size * 0.66)
    lower.moveTo(size * 0.38, size * 0.52)
    lower.lineTo(size * 0.22, size * 0.66)
    lower.lineTo(size * 0.38, size * 0.80)
    painter.drawPath(lower)
    painter.end()
    return QIcon(pixmap)


class FloatingToolbar(QWidget):
    """Barra de ferramentas flutuante tipo capsule pill para controle da sessao."""

    closed = Signal()
    settings_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    ptt_pressed = Signal()
    ptt_released = Signal()
    microphone_mute_changed = Signal(bool)
    source_language_changed = Signal(str)
    target_language_changed = Signal(str)
    toggle_chat_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(54)
        self.setMinimumWidth(580)

        self.drag_position = QPoint()
        self._is_active = False
        self._allow_stop = False
        self._capture_mode = "automatic"
        self._microphone_muted = False
        self._voice_active = False
        self._updating_languages = False

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
                background: rgba(10, 15, 29, 0.95);
                border-radius: 16px;
                border: 1px solid rgba(99, 102, 241, 0.35);
            }
            #toolbarFrame QPushButton {
                border-radius: 10px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 13px;
                color: #FFFFFF;
                border: none;
            }
            #toolbarFrame QPushButton#actionBtn[active="false"] {
                background-color: #5B51D8;
                padding-left: 10px;
                padding-right: 14px;
            }
            #toolbarFrame QPushButton#actionBtn[active="false"]:hover {
                background-color: #4F46E5;
            }
            #toolbarFrame QPushButton#actionBtn[active="true"] {
                background-color: #DC2626;
                padding-left: 10px;
                padding-right: 14px;
            }
            #toolbarFrame QPushButton#actionBtn[active="true"]:hover {
                background-color: #B91C1C;
            }
            #toolbarFrame QPushButton#actionBtn[active="true"]:disabled {
                background-color: rgba(245, 158, 11, 0.85);
                color: rgba(255, 255, 255, 0.95);
            }
            #toolbarFrame QPushButton#pttBtn {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #CBD5E1;
            }
            #toolbarFrame QPushButton#pttBtn:hover {
                background: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn:pressed {
                background: #059669;
                border-color: #10B981;
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn[voiceActive="true"] {
                background: rgba(16, 185, 129, 0.9);
                border-color: #10B981;
                color: #FFFFFF;
            }
            #toolbarFrame QPushButton#pttBtn[muted="true"] {
                background: rgba(51, 65, 85, 0.6);
                border-color: rgba(100, 116, 139, 0.4);
                color: #94A3B8;
            }
            #toolbarFrame QPushButton#pttBtn:disabled {
                background: rgba(30, 41, 59, 0.3);
                border-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.25);
            }
            #toolbarFrame QToolButton {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                padding: 4px;
            }
            #toolbarFrame QToolButton:hover {
                background: rgba(255, 255, 255, 0.12);
                border-color: rgba(255, 255, 255, 0.18);
            }
            #toolbarFrame QToolButton#closeToolbarButton:hover {
                background: rgba(220, 38, 38, 0.9);
                border-color: rgba(220, 38, 38, 0.9);
            }
            """
        )
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        # 1. Opcoes / Configuracoes
        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("settingsToolbarButton")
        self.settings_btn.setIcon(_build_gear_icon(16, "#CBD5E1"))
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.setToolTip("Configurações")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setAutoRaise(True)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        layout.addWidget(self._create_separator())

        # 2. Seletor de Idiomas em Pilula com Setas e Inversao
        lang_group = QFrame()
        lang_group.setObjectName("languageGroup")
        lang_group.setStyleSheet(
            """
            QFrame#languageGroup {
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
            }
            QComboBox {
                background: transparent;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border: none;
                padding: 0px;
                border-radius: 10px;
            }
            QComboBox:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background: #0A0F1D;
                color: #FFFFFF;
                selection-background-color: #4338CA;
                selection-color: #FFFFFF;
                border: 1px solid rgba(99, 102, 241, 0.5);
                border-radius: 10px;
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
                border-radius: 10px;
            }
            QToolButton#swapLangBtn:hover {
                background: rgba(99, 102, 241, 0.45);
                color: #FFFFFF;
            }
            """
        )
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.setContentsMargins(2, 1, 2, 1)
        lang_layout.setSpacing(2)
        lang_group.setFixedHeight(30)
        self.language_group = lang_group

        self.source_combo = LanguageComboBox()
        self.source_combo.add_language("PT", "Português", "pt-br")
        self.source_combo.add_language("EN", "Inglês", "en")
        self.source_combo.add_language("ES", "Espanhol", "es")
        self._configure_language_combo(self.source_combo)

        self.swap_btn = QToolButton()
        self.swap_btn.setObjectName("swapLangBtn")
        self.swap_btn.setIcon(_build_swap_icon(14, "#94A3B8"))
        self.swap_btn.setIconSize(QSize(14, 14))
        self.swap_btn.setFixedSize(26, 26)
        self.swap_btn.setToolTip("Inverter idiomas")
        self.swap_btn.setCursor(Qt.PointingHandCursor)
        self.swap_btn.clicked.connect(self._swap_languages)

        self.target_combo = LanguageComboBox()
        self.target_combo.add_language("EN", "Inglês", "en")
        self.target_combo.add_language("PT", "Português", "pt-br")
        self.target_combo.add_language("ES", "Espanhol", "es")
        self._configure_language_combo(self.target_combo)
        self.source_combo.setToolTip("Você")
        self.target_combo.setToolTip("Chamada")
        self.source_combo.currentIndexChanged.connect(
            self._on_source_language_changed
        )
        self.target_combo.currentIndexChanged.connect(
            self._on_target_language_changed
        )

        lang_layout.addWidget(self.source_combo)
        lang_layout.addWidget(self.swap_btn)
        lang_layout.addWidget(self.target_combo)
        lang_layout.setAlignment(self.swap_btn, Qt.AlignCenter)
        layout.addWidget(lang_group)

        layout.addWidget(self._create_separator())

        # 3. Acoes Principais (Iniciar/Parar + PTT)
        self.action_btn = QPushButton("Iniciar")
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.setProperty("active", "false")
        self.action_btn.setIcon(_build_play_icon(15, "#FFFFFF"))
        self.action_btn.setIconSize(QSize(15, 15))
        self.action_btn.setFixedSize(96, 30)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.ptt_btn = QPushButton("Falar")
        self.ptt_btn.setObjectName("pttBtn")
        self.ptt_btn.setIcon(_build_microphone_icon(15, "#CBD5E1"))
        self.ptt_btn.setIconSize(QSize(15, 15))
        self.ptt_btn.setToolTip("Controle do microfone.")
        self.ptt_btn.setCursor(Qt.PointingHandCursor)
        self.ptt_btn.setEnabled(False)
        self.ptt_btn.setFixedSize(78, 30)
        self.ptt_btn.setProperty("voiceActive", "false")
        self.ptt_btn.setProperty("muted", "false")
        self.ptt_btn.pressed.connect(self._on_microphone_pressed)
        self.ptt_btn.released.connect(self._on_microphone_released)
        self.ptt_btn.clicked.connect(self._on_microphone_clicked)
        layout.addWidget(self.ptt_btn)

        layout.addWidget(self._create_separator())

        # 4. Utilitarios (Toggle Chat + Limpar)
        self.toggle_chat_btn = QToolButton()
        self.toggle_chat_btn.setObjectName("toggleChatBtn")
        self.toggle_chat_btn.setIcon(_build_chat_icon(16, "#CBD5E1"))
        self.toggle_chat_btn.setIconSize(QSize(16, 16))
        self.toggle_chat_btn.setFixedSize(30, 30)
        self.toggle_chat_btn.setToolTip("Mostrar ou ocultar janela de mensagens")
        self.toggle_chat_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat_requested.emit)
        layout.addWidget(self.toggle_chat_btn)

        self.clear_btn = QToolButton()
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setIcon(_build_trash_icon(16, "#CBD5E1"))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setFixedSize(30, 30)
        self.clear_btn.setToolTip("Limpar mensagens em tela")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.clear_btn)

        layout.addWidget(self._create_separator())

        # 5. Estado da sessao e dispositivo ativo
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(9, 9)

        self.runtime_group = QFrame()
        self.runtime_group.setObjectName("runtimeStatusGroup")
        status_layout = QHBoxLayout(self.runtime_group)
        status_layout.setContentsMargins(10, 3, 10, 3)
        status_layout.setSpacing(6)
        status_layout.addWidget(self.status_indicator)

        self.runtime_badge = QLabel("Esperando iniciar...")
        self.runtime_badge.setAlignment(Qt.AlignCenter)
        self.runtime_badge.setMinimumWidth(105)
        self.runtime_badge.setContentsMargins(0, 0, 8, 0)
        status_layout.addWidget(self.runtime_badge)
        self.runtime_group.setFixedHeight(30)
        layout.addWidget(self.runtime_group)
        self.reset_runtime_status()

        # 6. Fechar Toolbar
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("closeToolbarButton")
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setToolTip("Fechar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setAutoRaise(True)
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)
        self.adjustSize()

    @staticmethod
    def _configure_language_combo(combo: QComboBox) -> None:
        combo.setFixedSize(28, 28)

    @staticmethod
    def _set_combo_language(combo: QComboBox, language: str) -> None:
        index = combo.findData(language)
        if index >= 0:
            combo.setCurrentIndex(index)
            if isinstance(combo, LanguageComboBox):
                combo._sync_compact_text()

    def set_source_language(self, language: str) -> None:
        normalized = language if language in {"pt-br", "en", "es"} else "pt-br"
        self._updating_languages = True
        try:
            self._set_combo_language(self.source_combo, normalized)
        finally:
            self._updating_languages = False

    def set_target_language(self, language: str) -> None:
        normalized = language if language in {"pt-br", "en", "es"} else "en"
        self._updating_languages = True
        try:
            self._set_combo_language(self.target_combo, normalized)
        finally:
            self._updating_languages = False

    def set_language_pair(self, user_language: str, meeting_language: str) -> None:
        self._updating_languages = True
        try:
            self._set_combo_language(
                self.source_combo,
                user_language if user_language in {"pt-br", "en", "es"} else "pt-br",
            )
            self._set_combo_language(
                self.target_combo,
                meeting_language if meeting_language in {"pt-br", "en", "es"} else "en",
            )
        finally:
            self._updating_languages = False

    def _emit_source_language(self) -> None:
        language = str(self.source_combo.currentData() or "pt-br")
        self.source_language_changed.emit(language)

    def _on_source_language_changed(self) -> None:
        if self._updating_languages:
            return
        self._emit_source_language()

    def _on_target_language_changed(self) -> None:
        if self._updating_languages:
            return
        language = str(self.target_combo.currentData() or "en")
        self.target_language_changed.emit(language)

    def _swap_languages(self) -> None:
        source = str(self.source_combo.currentData() or "pt-br")
        target = str(self.target_combo.currentData() or "en")
        self._updating_languages = True
        try:
            self._set_combo_language(self.source_combo, target)
            self._set_combo_language(self.target_combo, source)
        finally:
            self._updating_languages = False
        self._emit_source_language()
        self.target_language_changed.emit(
            str(self.target_combo.currentData() or "en")
        )

    def _on_action_clicked(self) -> None:
        if not self._is_active:
            self.start_requested.emit()
        elif self._allow_stop:
            self.stop_requested.emit()

    def set_capture_mode(self, mode: str) -> None:
        self._capture_mode = (
            "push_to_talk" if mode == "push_to_talk" else "automatic"
        )
        self._microphone_muted = False
        self._voice_active = False
        self._refresh_ptt_state()

    def _refresh_ptt_state(self) -> None:
        push_to_talk = self._capture_mode == "push_to_talk"
        self.ptt_btn.setEnabled(self._is_active and self._allow_stop)
        if push_to_talk:
            self.ptt_btn.setText("Falar")
            self.ptt_btn.setToolTip("Mantenha pressionado para captar sua fala.")
        else:
            self.ptt_btn.setText("Mudo" if self._microphone_muted else "Falar")
            self.ptt_btn.setToolTip(
                "Clique para reativar o microfone."
                if self._microphone_muted
                else "Clique para mutar o microfone; o verde indica voz detectada."
            )
        self.ptt_btn.setIcon(
            _build_microphone_icon(15, "#CBD5E1", muted=self._microphone_muted)
        )
        self._refresh_microphone_style()

    def _refresh_microphone_style(self) -> None:
        voice_active = (
            self._capture_mode == "automatic"
            and self._voice_active
            and not self._microphone_muted
        )
        self.ptt_btn.setProperty("voiceActive", str(voice_active).lower())
        self.ptt_btn.setProperty("muted", str(self._microphone_muted).lower())
        self.ptt_btn.style().unpolish(self.ptt_btn)
        self.ptt_btn.style().polish(self.ptt_btn)

    def set_voice_activity(self, active: bool) -> None:
        self._voice_active = bool(active)
        self._refresh_microphone_style()

    def reset_microphone_state(self) -> None:
        self._microphone_muted = False
        self._voice_active = False
        self._refresh_ptt_state()

    def _on_microphone_pressed(self) -> None:
        if self._capture_mode == "push_to_talk":
            self.ptt_pressed.emit()

    def _on_microphone_released(self) -> None:
        if self._capture_mode == "push_to_talk":
            self.ptt_released.emit()

    def _on_microphone_clicked(self) -> None:
        if self._capture_mode != "automatic" or not self._is_active:
            return
        self._microphone_muted = not self._microphone_muted
        if self._microphone_muted:
            self._voice_active = False
        self.microphone_mute_changed.emit(self._microphone_muted)
        self._refresh_ptt_state()

    def set_buttons_state(self, is_running: bool, allow_stop: bool = True) -> None:
        self._is_active = is_running
        self._allow_stop = allow_stop
        if is_running:
            self.action_btn.setText("Parar" if allow_stop else "Aguarde")
            self.action_btn.setIcon(_build_stop_icon(15))
            self.action_btn.setProperty("active", "true")
            self.action_btn.setEnabled(allow_stop)
        else:
            self._microphone_muted = False
            self._voice_active = False
            self.action_btn.setText("Iniciar")
            self.action_btn.setIcon(_build_play_icon(15))
            self.action_btn.setProperty("active", "false")
            self.action_btn.setEnabled(True)

        self._refresh_ptt_state()
        self.source_combo.setEnabled(not is_running)
        self.target_combo.setEnabled(not is_running)
        self.swap_btn.setEnabled(not is_running)
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            pos = self.pos()
            save_settings(
                {
                    "ui_toolbar_x": pos.x(),
                    "ui_toolbar_y": pos.y(),
                }
            )
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closed.emit()
        event.accept()

    def set_status_message(self, message: str) -> None:
        self.status_indicator.setToolTip(message)
        self.runtime_group.setToolTip(message)

    def _set_runtime_visual_state(
        self,
        state: str,
        color: str,
        border: str,
        background: str,
    ) -> None:
        self.runtime_group.setProperty("state", state)
        self.status_indicator.setStyleSheet(
            f"background: {color}; border: 1px solid {border}; border-radius: 4px;"
        )
        self.runtime_group.setStyleSheet(
            "QFrame#runtimeStatusGroup {"
            f"background: {background}; border: 1px solid {border}; "
            "border-radius: 10px; }"
            "QLabel { background: transparent; border: none; color: white; "
            "font-weight: 700; font-size: 11px; }"
        )

    def set_idle(self) -> None:
        self._set_runtime_visual_state(
            "idle",
            "#64748B",
            "rgba(148, 163, 184, 0.35)",
            "rgba(30, 41, 59, 0.5)",
        )
        self.set_status_message("Aguardando início")

    def set_active(self, message: str | None = None) -> None:
        self._set_runtime_visual_state(
            "active",
            "#22C55E",
            "rgba(34, 197, 94, 0.75)",
            "rgba(34, 197, 94, 0.20)",
        )
        self.set_status_message(message or "Transcrição ativa")

    def set_connecting(self, message: str | None = None) -> None:
        self._set_runtime_visual_state(
            "loading",
            "#F59E0B",
            "rgba(245, 158, 11, 0.75)",
            "rgba(245, 158, 11, 0.20)",
        )
        self.set_status_message(message or "Carregando...")

    def set_runtime_pending(self) -> None:
        self.runtime_badge.setText("Verificando...")
        self.runtime_badge.setToolTip("Verificando o dispositivo solicitado.")
        self._set_runtime_visual_state(
            "loading",
            "#F59E0B",
            "rgba(245, 158, 11, 0.75)",
            "rgba(245, 158, 11, 0.20)",
        )

    def reset_runtime_status(self) -> None:
        self.runtime_badge.setText("Esperando iniciar...")
        self.runtime_badge.setToolTip("Dispositivo em uso durante a sessão.")
        self._set_runtime_visual_state(
            "idle",
            "#64748B",
            "rgba(148, 163, 184, 0.35)",
            "rgba(30, 41, 59, 0.5)",
        )

    def set_runtime_status(self, status: RuntimeStatus) -> None:
        self.runtime_badge.setText(status.display_label)
        self.runtime_badge.setToolTip(status.tooltip)
        self._set_runtime_visual_state(
            "active",
            "#22C55E",
            "rgba(34, 197, 94, 0.75)",
            "rgba(34, 197, 94, 0.20)",
        )

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
>>>>>>> Stashed changes
        return mapping.get(clean, "pt-br")