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

    def test_voice_options_saved_as_strings_keep_their_boolean_values(self):
        saved = FakeSettings({
            "voice_output_enabled": "false",
            "meeting_voice_enabled": "0",
        })
        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()
        self.assertFalse(values["voice_output_enabled"])
        self.assertFalse(values["meeting_voice_enabled"])

        saved.values.update({
            "voice_output_enabled": "true",
            "meeting_voice_enabled": "1",
        })
        with patch.object(settings_store, "QSettings", return_value=saved):
            values = settings_store.load_settings()
        self.assertTrue(values["voice_output_enabled"])
        self.assertTrue(values["meeting_voice_enabled"])

    def test_installer_language_initializes_only_new_profile(self):
        class WritableSettings(FakeSettings):
            def contains(self, key):
                return key in self.values

            def setValue(self, key, value):
                self.values[key] = value

            def sync(self):
                pass

        saved = WritableSettings()
        with patch.object(settings_store, "QSettings", return_value=saved):
            self.assertTrue(settings_store.set_initial_base_language("es"))
            self.assertEqual(saved.values["user_language"], "es")
            self.assertEqual(saved.values["meeting_language"], "pt-br")
            self.assertFalse(settings_store.set_initial_base_language("en"))
            self.assertEqual(saved.values["user_language"], "es")

    def test_installation_manifest_applies_selected_pair_once_per_installation(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = Path(temporary_directory) / "installation.ini"
            manifest.write_text(
                "[App]\nInstallId=first\n[Language]\nBase=pt-br\nPairs=es\n",
                encoding="utf-8",
            )
            self.assertEqual(
                settings_store._installation_language_selection(manifest),
                ("pt-br", "es", "first"),
            )
            manifest.write_text("[Language]\nBase=es\n", encoding="utf-8")
            self.assertEqual(settings_store._installation_base_language(manifest), "es")

        class WritableSettings(FakeSettings):
            def contains(self, key):
                return key in self.values

            def setValue(self, key, value):
                self.values[key] = value

            def sync(self):
                pass

        saved = WritableSettings()
        with (
            patch.object(settings_store, "QSettings", return_value=saved),
            patch.object(
                settings_store, "_installation_language_selection",
                side_effect=[("pt-br", "es", "first"), ("pt-br", "es", "first"),
                             ("en", "pt-br", "second")],
            ),
        ):
            self.assertEqual(settings_store.load_settings()["user_language"], "pt-br")
            self.assertEqual(saved.values["meeting_language"], "es")
            saved.values["user_language"] = "en"
            self.assertEqual(settings_store.load_settings()["user_language"], "en")
            self.assertEqual(settings_store.load_settings()["meeting_language"], "pt-br")
            self.assertEqual(saved.values["user_language"], "en")

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
