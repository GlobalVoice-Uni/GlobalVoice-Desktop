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
        self.assertEqual(values["min_silence_window_s"], 0.55)

    def test_valid_saved_preferences_are_preserved(self):
        saved = FakeSettings({"device": "cpu", "vad_type": "energy"})

        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()

        self.assertEqual(values["device"], "cpu")
        self.assertEqual(values["vad_type"], "energy")

    def test_previous_default_silence_is_migrated_to_longer_grouping(self):
        saved = FakeSettings({"min_silence_window_s": 0.4})

        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()

        self.assertEqual(values["min_silence_window_s"], 0.55)

    def test_custom_silence_window_is_preserved_during_migration(self):
        saved = FakeSettings(
            {
                "settings_revision": 1,
                "min_silence_window_s": 0.7,
            }
        )

        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()

        self.assertEqual(values["min_silence_window_s"], 0.7)

if __name__ == "__main__":
    unittest.main()
