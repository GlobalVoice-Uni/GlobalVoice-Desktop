from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_BASE_DIALOG_STYLE = """
QDialog {
    background: #0F1E2D;
}
QLabel {
    background: transparent;
    color: #F8FAFC;
    font-family: 'Bahnschrift', 'Segoe UI';
    font-size: 13px;
    font-weight: 600;
}
QPushButton {
    min-height: 32px;
    background: rgba(30, 41, 59, 0.92);
    color: #FFFFFF;
    border: 1px solid rgba(70, 73, 251, 0.5);
    border-radius: 10px;
    padding: 1px 10px;
    font-family: 'Bahnschrift', 'Segoe UI';
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(70, 73, 251, 0.72);
}
QPushButton:pressed {
    background: rgba(70, 73, 251, 0.55);
}
"""


class ConfirmationDialog(QDialog):
    """Confirmação compacta, sem ícone e alinhada ao visual do aplicativo."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        confirm_text: str,
        cancel_text: str,
        default_confirm: bool,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.ApplicationModal)
        self.setModal(True)
        self.setFixedWidth(380)
        self.setStyleSheet(
            _BASE_DIALOG_STYLE
            + """
            QLabel#confirmationMessage {
                qproperty-alignment: AlignCenter;
            }
            QPushButton#confirmationPrimary {
                background: rgba(70, 73, 251, 0.9);
            }
            QPushButton#confirmationPrimary:hover {
                background: rgba(70, 73, 251, 1);
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(18)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("confirmationMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)

        self.confirm_button = QPushButton(confirm_text)
        self.confirm_button.setObjectName("confirmationPrimary")
        self.confirm_button.setFixedWidth(108)
        self.confirm_button.setCursor(Qt.PointingHandCursor)
        self.confirm_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton(cancel_text)
        self.cancel_button.setFixedWidth(140)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)

        button_row.addWidget(self.confirm_button)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        default_button = self.confirm_button if default_confirm else self.cancel_button
        default_button.setDefault(True)
        default_button.setFocus()
        self.adjustSize()


class ErrorDialog(QDialog):
    """Aviso de erro compacto, sem ícone e com conteúdo centralizado."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.ApplicationModal)
        self.setModal(True)
        self.setFixedWidth(380)
        self.setStyleSheet(_BASE_DIALOG_STYLE)
        self.details = details.strip() if details else ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(18)

        self.message_label = QLabel(
            message or "Não foi possível concluir a operação."
        )
        self.message_label.setObjectName("errorMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.acknowledge_button = QPushButton("Entendi")
        self.acknowledge_button.setFixedWidth(102)
        self.acknowledge_button.setCursor(Qt.PointingHandCursor)
        self.acknowledge_button.setDefault(True)
        # Um aviso informativo não deve exigir um segundo clique caso o
        # Windows ainda esteja transferindo o foco para a janela modal.
        self.acknowledge_button.pressed.connect(self.accept)
        button_row.addWidget(self.acknowledge_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.acknowledge_button.setFocus()
        self.adjustSize()


def ask_confirmation(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    confirm_text: str = "Sim",
    cancel_text: str = "Não",
    default_confirm: bool = False,
) -> bool:
    """Exibe uma confirmação coerente com o visual e o idioma da aplicação."""

    dialog = ConfirmationDialog(
        parent,
        title,
        message,
        confirm_text=confirm_text,
        cancel_text=cancel_text,
        default_confirm=default_confirm,
    )
    return dialog.exec() == QDialog.Accepted


def show_error(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    details: str | None = None,
) -> None:
    """Mostra uma falha em linguagem direta com o padrão visual da aplicação."""

    dialog = ErrorDialog(parent, title, message, details=details)
    dialog.exec()
