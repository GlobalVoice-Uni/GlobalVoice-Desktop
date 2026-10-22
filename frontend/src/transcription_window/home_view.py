"""Home visual portada da branch front_eric, sem a lógica de sessão antiga."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .app_version import app_version


def _logo_path() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "frontend/assets/newicon.png"
    return Path(__file__).resolve().parents[2] / "assets/newicon.png"


def _build_logo_icon(size: int = 96) -> QIcon:
    """Desenha o logo do GlobalVoice: onda de voz em um círculo com gradiente."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    center = size / 2.0
    radius = size * 0.42
    gradient = QRadialGradient(center, center * 0.7, center, center, radius)
    gradient.setColorAt(0.0, QColor("#6366F1"))
    gradient.setColorAt(0.6, QColor("#4F46E5"))
    gradient.setColorAt(1.0, QColor("#3730A3"))

    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    highlight = QRadialGradient(center, center * 0.5, center * 0.5, center * 1.6, radius * 1.2)
    highlight.setColorAt(0.0, QColor(255, 255, 255, 60))
    highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(highlight)
    painter.drawEllipse(QPointF(center, center), radius, radius)

    painter.setBrush(QColor("#F8FAFC"))
    painter.setPen(Qt.NoPen)

    bar_count = 5
    bar_width = size * 0.055
    bar_spacing = size * 0.075
    total_width = (bar_count - 1) * bar_spacing
    start_x = center - total_width / 2.0
    heights = [0.28, 0.52, 0.68, 0.44, 0.32]

    for index, height_ratio in enumerate(heights):
        bar_height = size * height_ratio
        x = start_x + index * bar_spacing - bar_width / 2.0
        y = center - bar_height / 2.0
        rect = QRectF(x, y, bar_width, bar_height)
        path = QPainterPath()
        path.addRoundedRect(rect, bar_width / 2.0, bar_width / 2.0)
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)

def _build_play_icon(size: int = 18, color: str = "#FFFFFF") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.moveTo(size * 0.32, size * 0.20)
    path.lineTo(size * 0.78, size * 0.50)
    path.lineTo(size * 0.32, size * 0.80)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)

def _build_gear_icon(size: int = 18, color: str = "#CBD5E1") -> QIcon:
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

def _build_mic_icon(size: int = 20, color: str = "#818CF8") -> QIcon:
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
    painter.end()
    return QIcon(pixmap)

def _build_lock_icon(size: int = 20, color: str = "#34D399") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    body = QRectF(size * 0.22, size * 0.45, size * 0.56, size * 0.45)
    painter.drawRoundedRect(body, 2.5, 2.5)
    pen = QPen(QColor(color), max(1.5, size * 0.11))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    arc_rect = QRectF(size * 0.32, size * 0.18, size * 0.36, size * 0.42)
    painter.drawArc(arc_rect, 0, 180 * 16)
    painter.end()
    return QIcon(pixmap)

def _build_bolt_icon(size: int = 20, color: str = "#FBBF24") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    path = QPainterPath()
    path.moveTo(size * 0.58, size * 0.05)
    path.lineTo(size * 0.20, size * 0.55)
    path.lineTo(size * 0.46, size * 0.55)
    path.lineTo(size * 0.40, size * 0.95)
    path.lineTo(size * 0.80, size * 0.42)
    path.lineTo(size * 0.54, size * 0.42)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)

class FeatureCard(QFrame):
    """Mini-card que descreve uma característica do produto."""

    def __init__(self, icon: QIcon, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("featureCard")
        # Largura mínima para igualar todos os cards
        self.setMinimumWidth(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(22, 22))
        icon_label.setFixedHeight(26)

        title_label = QLabel(title)
        title_label.setObjectName("featureTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("featureSubtitle")
        subtitle_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


def build_home(self) -> None:
    root = QWidget()
    root.setObjectName("homeRoot")
    self.setCentralWidget(root)

    outer_layout = QVBoxLayout(root)
    outer_layout.setContentsMargins(32, 24, 32, 36)
    outer_layout.setSpacing(0)

    container = QWidget()
    container.setObjectName("homeContainer")
    container.setMaximumWidth(760)
    container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(0)

    # Hero
    hero = QWidget()
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(0, 0, 0, 16)
    hero_layout.setSpacing(7)
    hero_layout.setAlignment(Qt.AlignCenter)

    logo_label = QLabel()
    logo_label.setObjectName("heroLogo")
    logo_label.setPixmap(QIcon(str(_logo_path())).pixmap(104, 104))
    logo_label.setFixedSize(104, 104)
    logo_label.setAlignment(Qt.AlignCenter)

    title = QLabel("Global Voice")
    title.setObjectName("heroTitle")
    title.setAlignment(Qt.AlignCenter)

    slogan = QLabel("Tradução simultânea para reuniões online")
    slogan.setObjectName("heroSlogan")
    slogan.setAlignment(Qt.AlignCenter)

    hero_layout.addWidget(logo_label, 0, Qt.AlignCenter)
    hero_layout.addWidget(title)
    hero_layout.addWidget(slogan)

    # Botões
    button_row = QHBoxLayout()
    button_row.setSpacing(14)
    button_row.setAlignment(Qt.AlignCenter)

    self.start_button = QPushButton("  Iniciar")
    self.start_button.setObjectName("startButton")
    self.start_button.setIcon(_build_play_icon(18))
    self.start_button.setFixedHeight(46)
    self.start_button.setMinimumWidth(170)
    self.start_button.setCursor(Qt.PointingHandCursor)
    self.start_button.setFocusPolicy(Qt.NoFocus)

    self.settings_button = QPushButton("  Configurações")
    self.settings_button.setObjectName("settingsButton")
    self.settings_button.setIcon(_build_gear_icon(18))
    self.settings_button.setFixedHeight(46)
    self.settings_button.setMinimumWidth(190)
    self.settings_button.setCursor(Qt.PointingHandCursor)
    self.settings_button.setFocusPolicy(Qt.NoFocus)

    start_shadow = QGraphicsDropShadowEffect(self.start_button)
    start_shadow.setBlurRadius(28)
    start_shadow.setColor(QColor(79, 70, 229, 140))
    start_shadow.setOffset(0, 6)
    self.start_button.setGraphicsEffect(start_shadow)

    button_row.addWidget(self.start_button)
    button_row.addWidget(self.settings_button)

    # Cards com largura uniforme.
    features_widget = QWidget()
    features_row = QHBoxLayout(features_widget)
    features_row.setContentsMargins(0, 0, 0, 0)
    features_row.setSpacing(12)
    features_row.setAlignment(Qt.AlignCenter)

    features = [
        (_build_mic_icon(22), "Captura local", "Áudio processado na sua máquina"),
        (_build_lock_icon(22), "Uso local", "Áudio processado sem rede"),
        (_build_bolt_icon(22), "GPU / CPU", "Aceleração automática"),
    ]
    for icon, title_text, subtitle_text in features:
        card = FeatureCard(icon, title_text, subtitle_text)
        features_row.addWidget(card, 1)
    features_widget.setFixedHeight(features_widget.sizeHint().height())

    # Rodapé
    footer_row = QHBoxLayout()
    footer_row.setContentsMargins(8, 0, 8, 0)
    footer_row.setSpacing(8)

    version_label = QLabel(f"Versão {app_version()}")
    version_label.setObjectName("footerText")

    github_link = QLabel(
        '<a href="https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop" '
        'style="color: #818CF8; text-decoration: none;">Ver no GitHub</a>'
    )
    github_link.setObjectName("footerLink")
    github_link.setOpenExternalLinks(True)

    footer_row.addWidget(version_label)
    footer_row.addStretch(1)
    footer_row.addWidget(github_link)

    container_layout.addStretch(3)
    container_layout.addWidget(hero)
    container_layout.addSpacing(42)
    container_layout.addLayout(button_row)
    container_layout.addSpacing(30)
    container_layout.addStretch(2)
    container_layout.addWidget(features_widget)
    container_layout.addSpacing(12)
    container_layout.addLayout(footer_row)
    container_layout.addStretch(1)

    outer_layout.addWidget(container, 1, Qt.AlignHCenter)

    self.setStyleSheet(
        """
        QWidget#homeRoot {
            background: qradialgradient(
                cx:0.5, cy:0.42, radius:0.95,
                fx:0.5, fy:0.42,
                stop:0 #131B33,
                stop:0.55 #0B1224,
                stop:1 #070B16
            );
            color: #F8FAFC;
            font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Bahnschrift';
        }
        QLabel#heroTitle {
            font-size: 46px;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: 0.5px;
        }
        QLabel#heroSlogan {
            font-size: 14px;
            color: #94A3B8;
            letter-spacing: 0.2px;
        }
        QPushButton#startButton {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #6366F1, stop:1 #4F46E5
            );
            color: #FFFFFF;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            padding: 0 22px;
        }
        QPushButton#startButton:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #818CF8, stop:1 #6366F1
            );
        }
        QPushButton#startButton:pressed {
            background: #4338CA;
            padding-top: 2px;
        }
        QPushButton#settingsButton {
            background: rgba(30, 41, 59, 0.7);
            color: #E2E8F0;
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            padding: 0 22px;
        }
        QPushButton#settingsButton:hover {
            background: rgba(99, 102, 241, 0.25);
            border: 1px solid rgba(129, 140, 248, 0.7);
            color: #FFFFFF;
        }
        QPushButton#settingsButton:pressed {
            background: rgba(99, 102, 241, 0.35);
        }
        QFrame#featureCard {
            background: rgba(30, 41, 59, 0.45);
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 12px;
        }
        QFrame#featureCard:hover {
            background: rgba(30, 41, 59, 0.65);
            border: 1px solid rgba(99, 102, 241, 0.35);
        }
        QLabel#featureTitle {
            font-size: 13px;
            font-weight: 700;
            color: #F1F5F9;
        }
        QLabel#featureSubtitle {
            font-size: 11px;
            color: #94A3B8;
        }
        QLabel#footerText {
            font-size: 11px;
            color: #64748B;
        }
        QLabel#footerLink {
            font-size: 11px;
            color: #818CF8;
        }
        """
    )
