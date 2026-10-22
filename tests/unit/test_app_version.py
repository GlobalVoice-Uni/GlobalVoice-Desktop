import tempfile
import unittest
from pathlib import Path

from frontend.src.transcription_window.app_version import DEVELOPMENT_VERSION, app_version


class AppVersionTests(unittest.TestCase):
    def test_installer_version_is_shown_when_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            installation = Path(temporary) / "installation.ini"
            installation.write_text("[App]\nVersion=0.4.2\n", encoding="utf-8")
            self.assertEqual(app_version(installation), "0.4.2")

    def test_missing_version_uses_development_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(app_version(Path(temporary) / "missing.ini"), DEVELOPMENT_VERSION)


if __name__ == "__main__":
    unittest.main()
