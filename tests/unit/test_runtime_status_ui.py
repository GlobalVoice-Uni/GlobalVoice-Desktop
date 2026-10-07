import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent

from backend.app.transcript import TranscriptChunk
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
from frontend.src.transcription_window.dialogs import ConfirmationDialog, ErrorDialog
from frontend.src.transcription_window.controller import RealtimeController
from frontend.src.transcription_window.main_window import MainWindow
from frontend.src.transcription_window.settings_window import SettingsWindow
from frontend.src.transcription_window.settings_store import DEFAULT_SETTINGS


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
        self.assertIn("não pôde ser inicializada", window.active_device_label.toolTip())
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

    def test_language_selector_closes_popup_on_second_click(self):
        toolbar = FloatingToolbar()
        toolbar.show()
        self.app.processEvents()

        QTest.mouseClick(toolbar.source_combo.lineEdit(), Qt.LeftButton)
        QTest.qWait(20)
        popup = toolbar.source_combo._language_popup
        self.assertIsNotNone(popup)
        self.assertTrue(popup.isVisible())

        QTest.mouseClick(toolbar.source_combo.lineEdit(), Qt.LeftButton)
        QTest.qWait(20)
        self.assertFalse(popup.isVisible())
        toolbar.close()

    def test_language_selector_does_not_reopen_after_native_popup_hide(self):
        toolbar = FloatingToolbar()
        toolbar.show()
        self.app.processEvents()

        QTest.mouseClick(toolbar.source_combo.lineEdit(), Qt.LeftButton)
        QTest.qWait(20)
        popup = toolbar.source_combo._language_popup
        popup.hide()

        QTest.mouseClick(toolbar.source_combo.lineEdit(), Qt.LeftButton)
        QTest.qWait(20)

        self.assertFalse(popup.isVisible())
        self.assertFalse(toolbar.source_combo._popup_open)
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

    def test_language_pair_stays_synchronized_between_settings_and_toolbar(self):
        values = dict(DEFAULT_SETTINGS)
        with (
            patch(
                "frontend.src.transcription_window.main_window.load_settings",
                return_value=values,
            ),
            patch(
                "frontend.src.transcription_window.settings_window.load_settings",
                return_value=values,
            ),
        ):
            window = MainWindow()

        with (
            patch("frontend.src.transcription_window.main_window.save_settings"),
            patch("frontend.src.transcription_window.settings_window.save_settings"),
        ):
            window.settings_window.user_language_combo.setCurrentIndex(
                window.settings_window.user_language_combo.findData("es")
            )
            window.settings_window.meeting_language_combo.setCurrentIndex(
                window.settings_window.meeting_language_combo.findData("pt-br")
            )

            self.assertEqual(window.toolbar.source_combo.currentData(), "pt-br")
            self.assertEqual(window.toolbar.target_combo.currentData(), "en")
            window.settings_window._on_save_clicked()

            self.assertEqual(window.toolbar.source_combo.currentData(), "es")
            self.assertEqual(window.toolbar.target_combo.currentData(), "pt-br")

            window.toolbar.source_combo.setCurrentIndex(
                window.toolbar.source_combo.findData("en")
            )
            window.toolbar.target_combo.setCurrentIndex(
                window.toolbar.target_combo.findData("es")
            )

        self.assertEqual(
            window.settings_window.user_language_combo.currentData(), "en"
        )
        self.assertEqual(
            window.settings_window.meeting_language_combo.currentData(), "es"
        )
        window.close()

    def test_settings_diagnostic_uses_only_saved_values(self):
        values = dict(DEFAULT_SETTINGS)
        window = SettingsWindow()
        window.user_language_combo.setCurrentIndex(
            window.user_language_combo.findData("es")
        )

        with (
            patch(
                "frontend.src.transcription_window.settings_window.load_settings",
                return_value=values,
            ),
            patch.object(window.controller, "start_session") as start_session,
        ):
            window._on_start_clicked()

        request = start_session.call_args.args[0]
        self.assertEqual(request.language, "pt-br")
        self.assertEqual(window.user_language_combo.currentData(), "pt-br")
        window.close()

    def test_toolbar_language_context_is_explained_only_by_tooltip(self):
        toolbar = FloatingToolbar()

        self.assertEqual(toolbar.source_combo.toolTip(), "Você")
        self.assertEqual(toolbar.target_combo.toolTip(), "Chamada")
        visible_labels = {child.text() for child in toolbar.findChildren(QLabel)}
        self.assertNotIn("Você", visible_labels)
        self.assertNotIn("Chamada", visible_labels)
        toolbar.close()

    def test_loopback_uses_meeting_language_and_translates_to_user_language(self):
        values = dict(DEFAULT_SETTINGS)
        values.update(
            audio_source="loopback",
            user_language="pt-br",
            meeting_language="en",
            display_mode="both",
        )
        with patch(
            "frontend.src.transcription_window.main_window.load_settings",
            return_value=values,
        ):
            window = MainWindow()
            request = window._build_request()

        self.assertEqual(request.language, "en")
        self.assertEqual(request.target_language, "pt-br")
        self.assertEqual(request.display_mode, "both")
        window.close()

    def test_language_pack_tab_reports_installed_and_optional_models(self):
        class FakeLanguageManager:
            @staticmethod
            def language_packs():
                from backend.app.translators.argos_local import ArgosModelManager

                return ArgosModelManager.language_packs()

            @staticmethod
            def is_installed(code):
                return code == "en"

        window = SettingsWindow(language_manager_factory=FakeLanguageManager)
        window._start_language_pack_task("status")
        deadline = time.time() + 1.0
        while window._language_pack_busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(window.language_pack_status_labels["en"].text(), "Instalado")
        self.assertEqual(window.language_pack_buttons["en"].text(), "Desinstalar")
        self.assertEqual(window.language_pack_status_labels["es"].text(), "Não instalado")
        self.assertEqual(window.language_pack_buttons["es"].text(), "Instalar")
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

    def test_font_size_changes_existing_transcription_text(self):
        transcription = FloatingTranscriptionWindow()
        transcription.append_chunk(
            TranscriptChunk("meeting", "Hello", "Olá", "both")
        )

        transcription.apply_font_size(19)

        translated_text = transcription.transcription_area.document().find("Olá")
        content = transcription.transcription_area.toPlainText()
        self.assertEqual(translated_text.charFormat().fontPointSize(), 19)
        self.assertEqual(content.count("REUNIÃO"), 1)
        transcription.close()

    def test_chat_groups_continuations_without_repeating_sender_or_blank_lines(self):
        transcription = FloatingTranscriptionWindow()
        transcription.append_chunk(
            TranscriptChunk("user", "primeiro", "first", "translation_only")
        )
        transcription.append_chunk(
            TranscriptChunk("user", "segundo", "second", "translation_only")
        )

        content = transcription.transcription_area.toPlainText()
        self.assertEqual(content, "VOCÊ\nfirst\nsecond")
        self.assertEqual(content.count("VOCÊ"), 1)

        transcription.begin_speech()
        transcription.append_chunk(
            TranscriptChunk("user", "terceiro", "third", "translation_only")
        )
        self.assertIn("second\n\nVOCÊ\nthird", transcription.transcription_area.toPlainText())
        transcription.close()

    def test_chat_separates_original_and_translation_without_background_bars(self):
        transcription = FloatingTranscriptionWindow()
        transcription.append_chunk(
            TranscriptChunk("meeting", "Hello", "Olá", "both")
        )
        transcription.append_chunk(
            TranscriptChunk("meeting", "How are you?", "Como você está?", "both")
        )

        content = transcription.transcription_area.toPlainText()
        html_content = transcription.transcription_area.toHtml()
        self.assertEqual(
            content,
            "REUNIÃO\nHello\nOlá\nHow are you?\nComo você está?",
        )
        self.assertNotIn("background-color:#075e54", html_content.lower())
        self.assertNotIn("background-color:#1e293b", html_content.lower())
        transcription.close()

    def test_settings_fields_remain_compact_on_wide_and_medium_windows(self):
        window = SettingsWindow()
        window.show()

        for width in (1500, 700):
            window.resize(width, 680)
            self.app.processEvents()
            self.assertLessEqual(window.model_combo.width(), 560)
            self.assertEqual(window.active_device_label.width(), window.model_combo.width())
            self.assertEqual(window.active_device_label.height(), window.model_combo.height())
            self.assertGreaterEqual(window.height(), 670)
            label = window.tabs.widget(0).layout().labelForField(window.model_combo)
            self.assertLess(label.geometry().right(), window.model_combo.geometry().left())

        window._on_runtime_changed(
            RuntimeStatus(
                preference=DevicePreference.GPU,
                active_device=ActiveDevice.GPU,
                engine="engine",
                provider=RuntimeProvider.CUDA,
            )
        )

        base_fields = [
            window.model_combo,
            window.device_combo,
            window.active_device_label,
            window.audio_source_combo,
            window.audio_device_combo,
            window.user_language_combo,
            window.meeting_language_combo,
            window.display_mode_combo,
            window.capture_mode_combo,
        ]
        gaps = [
            following.y() - (current.y() + current.height())
            for current, following in zip(base_fields, base_fields[1:])
        ]
        self.assertTrue(all(gap >= 7 for gap in gaps))
        self.assertEqual(window.active_device_label.height(), window.model_combo.height())

        window.close()

    def test_confirmation_dialog_is_compact_and_centered_without_icon(self):
        dialog = ConfirmationDialog(
            None,
            "Encerrar o GlobalVoice?",
            "Existem configurações não salvas. Deseja encerrar mesmo assim?",
            confirm_text="Encerrar",
            cancel_text="Continuar usando",
            default_confirm=False,
        )
        dialog.show()
        self.app.processEvents()

        self.assertEqual(dialog.width(), 380)
        self.assertEqual(dialog.message_label.alignment(), Qt.AlignCenter)
        self.assertEqual(len(dialog.findChildren(QLabel)), 1)
        self.assertEqual(len(dialog.findChildren(QPushButton)), 2)
        buttons_center = (
            dialog.confirm_button.x() + dialog.cancel_button.geometry().right()
        ) / 2
        self.assertAlmostEqual(buttons_center, dialog.width() / 2, delta=2)
        dialog.close()

    def test_error_dialog_matches_compact_centered_style_without_icon(self):
        dialog = ErrorDialog(
            None,
            "Não foi possível iniciar",
            "O par de idiomas selecionado não está instalado.",
        )
        dialog.show()
        self.app.processEvents()

        self.assertEqual(dialog.width(), 380)
        self.assertEqual(dialog.message_label.alignment(), Qt.AlignCenter)
        self.assertEqual(len(dialog.findChildren(QLabel)), 1)
        self.assertEqual(len(dialog.findChildren(QPushButton)), 1)
        button_center = (
            dialog.acknowledge_button.x()
            + (dialog.acknowledge_button.width() / 2)
        )
        self.assertAlmostEqual(button_center, dialog.width() / 2, delta=2)
        dialog.close()

    def test_error_dialog_closes_on_first_button_press(self):
        dialog = ErrorDialog(
            None,
            "Não foi possível iniciar",
            "Falha de teste.",
        )
        dialog.show()
        self.app.processEvents()

        QTest.mousePress(dialog.acknowledge_button, Qt.LeftButton)

        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertFalse(dialog.isVisible())

    def test_shared_controller_opens_only_one_error_dialog(self):
        with (
            patch(
                "frontend.src.transcription_window.main_window.show_error"
            ) as main_error,
            patch(
                "frontend.src.transcription_window.settings_window.show_error"
            ) as settings_error,
        ):
            window = MainWindow()
            window.settings_window.show()
            self.app.processEvents()
            window.controller.error_raised.emit("Falha de teste.")

            main_error.assert_called_once()
            settings_error.assert_not_called()
            self.assertIs(main_error.call_args.args[0], window.settings_window)
            window.close()


    def test_settings_dropdown_uses_custom_spaced_popup(self):
        window = SettingsWindow()
        window.show()
        self.app.processEvents()

        window.model_combo.showPopup()
        self.app.processEvents()

        popup = window.model_combo._settings_popup
        self.assertIsNotNone(popup)
        self.assertEqual(popup.width(), window.model_combo.width())
        options = popup.findChildren(QPushButton)
        self.assertEqual(len(options), window.model_combo.count())
        self.assertTrue(all(option.minimumHeight() >= 34 for option in options))
        self.assertIn("#0F172A", popup.findChild(QFrame).styleSheet())
        QTest.mouseClick(window.model_combo, Qt.LeftButton)
        self.app.processEvents()
        self.assertIsNone(window.model_combo._settings_popup)
        QTest.mouseClick(window.model_combo, Qt.LeftButton)
        self.app.processEvents()
        self.assertIsNotNone(window.model_combo._settings_popup)
        self.assertTrue(window.model_combo._settings_popup.isVisible())
        window.model_combo.hidePopup()
        window.close()

    def test_settings_dropdown_does_not_reopen_after_native_popup_hide(self):
        window = SettingsWindow()
        window.show()
        self.app.processEvents()

        window.model_combo.showPopup()
        popup = window.model_combo._settings_popup
        popup.hide()
        QTest.mouseClick(window.model_combo, Qt.LeftButton)
        QTest.qWait(20)

        self.assertIsNone(window.model_combo._settings_popup)
        self.assertFalse(window.model_combo._popup_open)
        window.close()


    def test_settings_track_unsaved_changes_until_save(self):
        window = SettingsWindow()
        original_index = window.model_combo.currentIndex()
        changed_index = (original_index + 1) % window.model_combo.count()

        window.model_combo.setCurrentIndex(changed_index)

        self.assertTrue(window.has_unsaved_changes())
        with patch("frontend.src.transcription_window.settings_window.save_settings"):
            window._on_save_clicked()
        self.assertFalse(window.has_unsaved_changes())
        window.close()

    def test_closing_settings_discards_unsaved_changes(self):
        values = dict(DEFAULT_SETTINGS)
        with patch(
            "frontend.src.transcription_window.settings_window.load_settings",
            return_value=values,
        ):
            window = SettingsWindow()
            saved_index = window.model_combo.currentIndex()
            changed_index = (saved_index + 1) % window.model_combo.count()
            window.show()
            window.model_combo.setCurrentIndex(changed_index)

            self.assertTrue(window.has_unsaved_changes())
            window.close()
            self.app.processEvents()

        self.assertEqual(window.model_combo.currentIndex(), saved_index)
        self.assertFalse(window.has_unsaved_changes())
        window.show()
        self.assertEqual(window.model_combo.currentIndex(), saved_index)
        window.close()

    def test_home_close_warns_and_can_cancel_when_work_would_be_lost(self):
        window = MainWindow()
        original_index = window.settings_window.model_combo.currentIndex()
        changed_index = (
            original_index + 1
        ) % window.settings_window.model_combo.count()
        window.settings_window.model_combo.setCurrentIndex(changed_index)
        window.controller._running = True
        event = QCloseEvent()

        with (
            patch(
                "frontend.src.transcription_window.main_window.ask_confirmation",
                return_value=False,
            ) as confirmation,
            patch.object(window.controller, "stop_session") as stop_session,
        ):
            window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        stop_session.assert_not_called()
        message = confirmation.call_args.args[2]
        self.assertIn("transcrição está em andamento", message)
        self.assertIn("configurações não salvas", message)
        self.assertIn(".\nDeseja encerrar", message)
        window.controller._running = False
        window.hide()
        window.settings_window.hide()
        window.toolbar.hide()
        window.transcription_window.hide()

    def test_home_close_stops_session_and_hides_auxiliary_windows_when_confirmed(self):
        window = MainWindow()
        window.controller._running = True
        event = QCloseEvent()

        with (
            patch(
                "frontend.src.transcription_window.main_window.ask_confirmation",
                return_value=True,
            ),
            patch.object(window.controller, "stop_session") as stop_session,
        ):
            window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        stop_session.assert_called_once_with()
        self.assertFalse(window.settings_window.isVisible())
        self.assertFalse(window.toolbar.isVisible())
        self.assertFalse(window.transcription_window.isVisible())

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
