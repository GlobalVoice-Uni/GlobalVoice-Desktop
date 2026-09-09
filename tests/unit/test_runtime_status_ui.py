import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from backend.app.runtime_status import (
    ActiveDevice,
    DevicePreference,
    FallbackReason,
    RuntimeProvider,
    RuntimeStatus,
)
from frontend.src.transcription_window.floating_windows import (
    FloatingToolbar,
    FloatingTranscriptionWindow,
)
from frontend.src.transcription_window.controller import RealtimeController
from frontend.src.transcription_window.main_window import MainWindow
from frontend.src.transcription_window.settings_window import SettingsWindow


class RuntimeStatusUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_keep_gpu_preference_while_showing_cpu_fallback(self):
        window = SettingsWindow()
        window._set_device_preference("gpu")
        status = RuntimeStatus(
            preference=DevicePreference.GPU,
            active_device=ActiveDevice.CPU,
            engine="engine",
            provider=RuntimeProvider.CPU,
            fallback_reason=FallbackReason.INITIALIZATION_FAILED,
        )

        window._on_runtime_changed(status)

        self.assertEqual(window.device_combo.currentData(), "gpu")
        self.assertEqual(window.active_device_label.text(), "CPU · fallback")
        self.assertIn("nao pode ser inicializada", window.active_device_label.toolTip())
        window.close()

    def test_toolbar_shows_the_provider_that_is_really_active(self):
        toolbar = FloatingToolbar()
        status = RuntimeStatus(
            preference=DevicePreference.GPU,
            active_device=ActiveDevice.GPU,
            engine="engine",
            provider=RuntimeProvider.DIRECTML,
            compute_type="float16",
        )

        toolbar.set_runtime_status(status)

        self.assertEqual(toolbar.runtime_badge.text(), "GPU · DIRECTML")
        self.assertIn("float16", toolbar.runtime_badge.toolTip())
        self.assertEqual(toolbar.runtime_group.property("state"), "active")
        toolbar.close()

    def test_saving_another_preference_clears_the_previous_active_device(self):
        controller = RealtimeController()
        window = SettingsWindow(controller=controller)
        toolbar = FloatingToolbar()
        controller.runtime_changed.connect(toolbar.set_runtime_status)
        controller.runtime_cleared.connect(toolbar.reset_runtime_status)
        active_gpu = RuntimeStatus(
            preference=DevicePreference.GPU,
            active_device=ActiveDevice.GPU,
            engine="engine",
            provider=RuntimeProvider.CUDA,
            compute_type="float32",
        )
        controller._publish_runtime_status(active_gpu)
        window._set_device_preference("cpu")

        with patch(
            "frontend.src.transcription_window.settings_window.save_settings"
        ):
            window._on_save_clicked()

        self.assertIsNone(controller.runtime_status)
        self.assertEqual(window.active_device_label.text(), "Esperando iniciar...")
        self.assertEqual(toolbar.runtime_badge.text(), "Esperando iniciar...")
        window.close()
        toolbar.close()

    def test_microphone_button_supports_auto_mute_and_push_to_talk(self):
        toolbar = FloatingToolbar()
        mute_states = []
        ptt_presses = []
        toolbar.microphone_mute_changed.connect(mute_states.append)
        toolbar.ptt_pressed.connect(lambda: ptt_presses.append(True))

        toolbar.set_buttons_state(True, allow_stop=True)
        self.assertTrue(toolbar.ptt_btn.isEnabled())
        normal_icon_key = toolbar.ptt_btn.icon().cacheKey()
        toolbar.set_voice_activity(True)
        self.assertEqual(toolbar.ptt_btn.property("voiceActive"), "true")
        toolbar.ptt_btn.click()
        self.assertEqual(mute_states, [True])
        self.assertEqual(toolbar.ptt_btn.property("muted"), "true")
        self.assertNotEqual(toolbar.ptt_btn.icon().cacheKey(), normal_icon_key)

        toolbar.set_capture_mode("push_to_talk")
        self.assertTrue(toolbar.ptt_btn.isEnabled())
        toolbar.ptt_btn.pressed.emit()
        self.assertEqual(ptt_presses, [True])

        toolbar.set_buttons_state(False)
        self.assertFalse(toolbar.ptt_btn.isEnabled())
        toolbar.close()

    def test_settings_store_push_to_talk_preference(self):
        window = SettingsWindow()

        window._set_capture_mode("push_to_talk")

        self.assertEqual(window._collect_settings()["capture_mode"], "push_to_talk")
        window.close()

    def test_single_action_button_emits_start_and_stop(self):
        toolbar = FloatingToolbar()
        initial_width = toolbar.action_btn.width()
        starts = []
        stops = []
        toolbar.start_requested.connect(lambda: starts.append(True))
        toolbar.stop_requested.connect(lambda: stops.append(True))

        toolbar.action_btn.click()
        toolbar.set_buttons_state(True, allow_stop=True)
        toolbar.action_btn.click()

        self.assertEqual(starts, [True])
        self.assertEqual(stops, [True])
        self.assertEqual(toolbar.action_btn.width(), initial_width)
        toolbar.close()

    def test_language_controls_have_fixed_square_dimensions(self):
        toolbar = FloatingToolbar()

        self.assertEqual(toolbar.source_combo.width(), toolbar.source_combo.height())
        self.assertEqual(toolbar.target_combo.width(), toolbar.target_combo.height())
        self.assertEqual(
            toolbar.source_combo.minimumSize(), toolbar.source_combo.maximumSize()
        )
        self.assertEqual(
            toolbar.target_combo.minimumSize(), toolbar.target_combo.maximumSize()
        )
        self.assertEqual(toolbar.swap_btn.minimumSize(), toolbar.swap_btn.maximumSize())
        self.assertEqual(toolbar.language_group.height(), toolbar.settings_btn.height())
        self.assertLess(toolbar.source_combo.height(), toolbar.language_group.height())
        reference_height = toolbar.settings_btn.height()
        for widget in (
            toolbar.action_btn,
            toolbar.ptt_btn,
            toolbar.toggle_chat_btn,
            toolbar.clear_btn,
            toolbar.runtime_group,
            toolbar.close_btn,
        ):
            self.assertEqual(widget.height(), reference_height)
        toolbar.close()

    def test_language_pair_controls_the_whisper_source_language(self):
        toolbar = FloatingToolbar()
        languages = []
        toolbar.source_language_changed.connect(languages.append)

        self.assertGreaterEqual(toolbar.source_combo.findData("es"), 0)
        self.assertGreaterEqual(toolbar.target_combo.findData("es"), 0)
        toolbar.set_source_language("pt-br")
        toolbar.source_combo.setCurrentIndex(toolbar.source_combo.findData("en"))

        self.assertEqual(toolbar.source_combo.currentData(), "en")
        self.assertEqual(toolbar.target_combo.currentData(), "en")
        toolbar.target_combo.setCurrentIndex(toolbar.target_combo.findData("pt-br"))
        toolbar._swap_languages()

        self.assertEqual(toolbar.source_combo.currentData(), "pt-br")
        self.assertEqual(toolbar.target_combo.currentData(), "en")
        self.assertEqual(languages, ["en", "pt-br"])
        toolbar.close()

    def test_language_selector_opens_popup_when_centered_text_is_clicked(self):
        toolbar = FloatingToolbar()
        toolbar.show()
        self.app.processEvents()

        QTest.mouseClick(toolbar.source_combo.lineEdit(), Qt.LeftButton)
        QTest.qWait(50)

        popup = toolbar.source_combo._language_popup
        self.assertIsNotNone(popup)
        self.assertTrue(popup.isVisible())
        self.assertEqual(popup.width(), toolbar.source_combo.width())
        self.assertEqual(toolbar.source_combo.itemText(0), "PT")
        self.assertEqual(toolbar.source_combo.itemText(1), "EN")
        self.assertEqual(toolbar.source_combo.itemText(2), "ES")
        self.assertEqual(
            toolbar.source_combo.itemData(0, Qt.ToolTipRole), "Português"
        )
        self.assertEqual(toolbar.source_combo.itemData(1, Qt.ToolTipRole), "Inglês")
        self.assertEqual(
            toolbar.source_combo.itemData(2, Qt.ToolTipRole), "Espanhol"
        )
        self.assertEqual(toolbar.source_combo.lineEdit().text(), "PT")
        self.assertEqual(
            [button.text() for button in toolbar.source_combo._popup_buttons],
            ["PT", "EN", "ES"],
        )
        self.assertEqual(
            [button.toolTip() for button in toolbar.source_combo._popup_buttons],
            ["Português", "Inglês", "Espanhol"],
        )
        QTest.mouseClick(toolbar.source_combo._popup_buttons[1], Qt.LeftButton)
        self.assertEqual(toolbar.source_combo.currentData(), "en")
        self.assertFalse(popup.isVisible())
        toolbar.close()

    def test_spanish_can_be_selected_as_whisper_source_language(self):
        toolbar = FloatingToolbar()
        languages = []
        toolbar.source_language_changed.connect(languages.append)

        toolbar.source_combo.setCurrentIndex(toolbar.source_combo.findData("es"))

        self.assertEqual(toolbar.source_combo.currentData(), "es")
        self.assertNotEqual(toolbar.target_combo.currentData(), "es")
        self.assertEqual(languages, ["es"])
        toolbar.close()

    def test_language_pair_allows_the_same_language_on_both_sides(self):
        toolbar = FloatingToolbar()

        toolbar.set_source_language("pt-br")
        toolbar.target_combo.setCurrentIndex(
            toolbar.target_combo.findData("pt-br")
        )

        self.assertEqual(toolbar.source_combo.currentData(), "pt-br")
        self.assertEqual(toolbar.target_combo.currentData(), "pt-br")
        toolbar.close()

    def test_session_request_uses_language_code_instead_of_visual_text(self):
        window = MainWindow()
        window.toolbar.source_combo.setCurrentIndex(
            window.toolbar.source_combo.findData("en")
        )

        request = window._build_request()

        self.assertEqual(request.language, "en")
        window.close()

    def test_runtime_indicator_uses_idle_loading_and_active_states(self):
        toolbar = FloatingToolbar()

        self.assertEqual(toolbar.runtime_group.property("state"), "idle")
        toolbar.set_connecting()
        self.assertEqual(toolbar.runtime_group.property("state"), "loading")
        toolbar.set_active()
        self.assertEqual(toolbar.runtime_group.property("state"), "active")
        toolbar.close()

    def test_font_size_changes_without_requiring_transcribed_content(self):
        transcription = FloatingTranscriptionWindow()
        transcription.apply_font_size(14)

        with patch("frontend.src.transcription_window.floating_windows.save_settings"):
            transcription.transcription_area.adjust_font_size(-1)

        self.assertTrue(transcription.transcription_area.document().isEmpty())
        self.assertEqual(transcription.transcription_area.display_font_size, 13)
        self.assertEqual(transcription.transcription_area.font().pointSize(), 13)
        self.assertEqual(transcription.transcription_area._empty_state_label.font().pointSize(), 13)
        self.assertFalse(transcription.transcription_area._empty_state_label.isHidden())
        transcription.close()

    def test_saved_toolbar_position_is_reused_when_windows_are_shown(self):
        window = MainWindow()
        values = {
            "ui_toolbar_x": 180,
            "ui_toolbar_y": 220,
            "ui_transcription_window_x": -1,
            "ui_transcription_window_y": -1,
        }

        with patch(
            "frontend.src.transcription_window.main_window.load_settings",
            return_value=values,
        ):
            window._position_floating_windows()

        self.assertEqual(window.toolbar.x(), 180)
        self.assertEqual(window.toolbar.y(), 220)
        window.close()

    def test_starting_session_does_not_reposition_visible_toolbar(self):
        window = MainWindow()
        window.toolbar.move(210, 240)
        window.toolbar.show()

        with patch.object(window, "_position_floating_windows") as reposition:
            window._show_floating_windows()

        reposition.assert_not_called()
        self.assertEqual(window.toolbar.x(), 210)
        self.assertEqual(window.toolbar.y(), 240)
        window.close()

    def test_toolbar_is_raised_after_chat_when_windows_are_shown(self):
        window = MainWindow()
        order = []

        with (
            patch.object(
                window.transcription_window,
                "raise_",
                side_effect=lambda: order.append("chat"),
            ),
            patch.object(
                window.toolbar,
                "raise_",
                side_effect=lambda: order.append("toolbar"),
            ),
        ):
            window._show_floating_windows()

        self.assertEqual(order[-2:], ["chat", "toolbar"])
        window.close()

    def test_closing_transcription_window_only_hides_chat(self):
        window = MainWindow()
        window.transcription_window.show()

        with patch.object(window.controller, "stop_session") as stop_session:
            window.transcription_window.closed.emit()

        self.assertFalse(window.transcription_window.isVisible())
        stop_session.assert_not_called()
        window.close()

    def test_transcription_label_only_appears_at_each_speech_start(self):
        transcription = FloatingTranscriptionWindow()

        transcription.begin_speech()
        transcription.append_text("primeiro trecho")
        transcription.append_text("continuação da mesma fala")
        transcription.begin_speech()
        transcription.append_text("nova fala")

        content = transcription.transcription_area.toPlainText()
        self.assertEqual(content.count("TRANSCRIÇÃO"), 2)
        self.assertIn("TRANSCRIÇÃO\nprimeiro trecho continuação", content)
        self.assertIn("\n\nTRANSCRIÇÃO\nnova fala", content)
        transcription.close()


if __name__ == "__main__":
    unittest.main()
