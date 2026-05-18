import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def _ensure_root_on_path() -> None:
    """Garante imports absolutos de frontend/back dentro do workspace."""
    repo_root = Path(__file__).resolve().parents[2]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def main() -> int:
    """Ponto de entrada da aplicacao desktop."""
    _ensure_root_on_path()

    from frontend.src.transcription_window.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("GlobalVoice")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
