import sys
import ctypes
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


def _ensure_root_on_path() -> None:
    """Garante imports absolutos de frontend/back dentro do workspace."""
    repo_root = Path(__file__).resolve().parents[2]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _application_icon_path() -> Path:
    """Resolve o ícone no workspace e na distribuição do PyInstaller."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "frontend" / "assets" / "globalvoice.ico"
    return Path(__file__).resolve().parents[1] / "assets" / "globalvoice.ico"


def _configure_windows_identity() -> None:
    """Mantém o ícone correto e o agrupamento único na barra de tarefas."""

    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "GlobalVoice.Desktop"
        )
    except (AttributeError, OSError):
        pass


def main() -> int:
    """Ponto de entrada da aplicacao desktop."""
    _ensure_root_on_path()

    from frontend.src.transcription_window.main_window import MainWindow

    _configure_windows_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("GlobalVoice")
    icon_path = _application_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
