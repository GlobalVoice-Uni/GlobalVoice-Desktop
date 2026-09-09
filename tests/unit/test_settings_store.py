import unittest
from unittest.mock import patch

from frontend.src.transcription_window import settings_store


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def value(self, key, default):
        return self.values.get(key, default)


class SettingsStoreTests(unittest.TestCase):
    def test_clean_profile_prefers_gpu_and_silero(self):
        with patch.object(settings_store, "QSettings", return_value=FakeSettings()):
            values = settings_store.load_settings()

        self.assertEqual(values["device"], "gpu")
        self.assertEqual(values["vad_type"], "silero")
        self.assertEqual(values["capture_mode"], "automatic")
        self.assertEqual(values["ui_toolbar_x"], -1)
        self.assertEqual(values["ui_toolbar_y"], -1)

    def test_valid_saved_preferences_are_preserved(self):
        saved = FakeSettings({"device": "cpu", "vad_type": "energy"})

        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()

        self.assertEqual(values["device"], "cpu")
        self.assertEqual(values["vad_type"], "energy")


if __name__ == "__main__":
    unittest.main()
