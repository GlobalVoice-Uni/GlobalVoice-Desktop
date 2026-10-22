import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QPushButton, QWidget
from PySide6.QtTest import QTest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QMouseEvent, QWheelEvent

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
from frontend.src.transcription_window.dialogs import ConfirmationDialog, ErrorDialog, UnsavedSettingsDialog, show_error
from frontend.src.transcription_window.controller import RealtimeController
from frontend.src.transcription_window.main_window import MainWindow
from frontend.src.transcription_window.settings_window import SettingsWindow
from frontend.src.transcription_window.settings_store import DEFAULT_SETTINGS
from frontend.src.transcription_window import settings_store


class RuntimeStatusUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        isolated_settings = tempfile.TemporaryDirectory()
        self.addCleanup(isolated_settings.cleanup)
        settings_path = Path(isolated_settings.name) / "settings.ini"
        settings_store_patch = patch(
            "frontend.src.transcription_window.settings_store.QSettings",
            side_effect=lambda *_args: QSettings(str(settings_path), QSettings.IniFormat),
        )
        settings_store_patch.start()
        self.addCleanup(settings_store_patch.stop)
        confirmation = patch(
            "frontend.src.transcription_window.settings_window.ask_confirmation",
            return_value=True,
        )
        confirmation.start()
        self.addCleanup(confirmation.stop)
        unsaved = patch(
            "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
            return_value="discard",
        )
        unsaved.start()
        self.addCleanup(unsaved.stop)

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
        self.assertEqual(window.hardware_indicator.text(), "!")
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

        self.assertEqual(toolbar.runtime_badge.text(), "GPU")
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
        self.assertEqual(toolbar.runtime_badge.text(), "Pronto")
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

    def test_saving_settings_keeps_microphone_muted_during_a_session(self):
        with patch("frontend.src.transcription_window.main_window.load_settings", return_value={
            **DEFAULT_SETTINGS,
            "audio_source": "both",
            "meeting_voice_enabled": True,
        }):
            window = MainWindow()
            window.toolbar.set_buttons_state(True, allow_stop=True)
            window.toolbar.ptt_btn.click()
            self.assertEqual(window.toolbar.ptt_btn.property("muted"), "true")
            window._on_settings_language_pair_changed("pt-br", "en")
            self.assertEqual(window.toolbar.ptt_btn.property("muted"), "true")
            self.assertTrue(window.toolbar.audio_btn.isEnabled())
            window.close()

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
        toolbar.show()
        toolbar.set_buttons_state(True, allow_stop=False)
        self.app.processEvents()
        self.assertEqual(toolbar.action_btn.width(), initial_width)
        self.assertLess(
            toolbar.action_btn.geometry().right(), toolbar.ptt_btn.geometry().left()
        )
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
        self.assertTrue(all(
            button.width() == popup.width() - 2
            for button in toolbar.source_combo._popup_buttons
        ))
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

    def test_language_selector_clears_hover_after_popup_closes_outside(self):
        toolbar = FloatingToolbar()
        toolbar.show()
        self.app.processEvents()

        combo = toolbar.source_combo
        combo._set_hovered(True)
        combo.showPopup()
        combo._language_popup.hide()
        QTest.qWait(180)

        self.assertFalse(combo._popup_open)
        self.assertFalse(combo.property("hovered"))
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
        defaults = dict(DEFAULT_SETTINGS)
        with (
            patch("frontend.src.transcription_window.main_window.load_settings", return_value=defaults),
            patch("frontend.src.transcription_window.settings_window.load_settings", return_value=defaults),
        ):
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

    def test_settings_build_bidirectional_voice_request(self):
        window = SettingsWindow()
        window.audio_source_combo.setCurrentIndex(window.audio_source_combo.findData("both"))
        window.voice_output_checkbox.setChecked(True)
        window.meeting_voice_checkbox.setChecked(True)
        request = window._build_request()
        self.assertEqual(request.audio_source, "both")
        self.assertEqual(request.user_language, window.user_language_combo.currentData())
        self.assertEqual(request.meeting_language, window.meeting_language_combo.currentData())
        self.assertTrue(request.voice_output_enabled)
        self.assertTrue(request.meeting_voice_enabled)
        self.assertIsNone(request.audio_device_id)
        self.assertIsNone(request.meeting_device_id)
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

    def test_installer_pack_is_shown_without_remove_action(self):
        class FakeLanguageManager:
            @staticmethod
            def language_packs():
                from backend.app.translators.argos_local import ArgosModelManager
                return ArgosModelManager.language_packs()

            @staticmethod
            def is_installed(code):
                return code == "en"

            @staticmethod
            def is_system_installed(code):
                return code == "en"

        window = SettingsWindow(language_manager_factory=FakeLanguageManager)
        window._start_language_pack_task("status")
        deadline = time.time() + 1.0
        while window._language_pack_busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertEqual(window.language_pack_buttons["en"].text(), "Na instalação")
        self.assertFalse(window.language_pack_buttons["en"].isEnabled())
        window.close()

    def test_language_tab_filters_direct_pairs_when_base_changes(self):
        window = SettingsWindow()
        window.base_language_combo.setCurrentIndex(
            window.base_language_combo.findData("en")
        )
        self.assertEqual(window.user_language_combo.currentData(), "en")
        self.assertFalse(window.language_pack_cards["en"].isHidden())
        self.assertTrue(window.language_pack_cards["es"].isHidden())
        self.assertFalse(window.language_pack_cards["en-es"].isHidden())
        self.assertEqual(window.language_pack_title_labels["en"].text(), "Português ↔ Inglês")
        self.assertEqual(window.language_pack_title_labels["en-es"].text(), "Espanhol ↔ Inglês")

        window.base_language_combo.setCurrentIndex(
            window.base_language_combo.findData("es")
        )
        self.assertTrue(window.language_pack_cards["en"].isHidden())
        self.assertFalse(window.language_pack_cards["es"].isHidden())
        self.assertFalse(window.language_pack_cards["en-es"].isHidden())
        self.assertEqual(window.language_pack_title_labels["es"].text(), "Português ↔ Espanhol")
        self.assertEqual(window.language_pack_title_labels["en-es"].text(), "Inglês ↔ Espanhol")
        window.close()

    def test_base_language_explains_when_a_pair_needs_installation(self):
        window = SettingsWindow()
        window._on_language_pack_result(
            {"success": True, "states": {"en": True, "es": False, "en-es": False}}
        )
        window.base_language_combo.setCurrentIndex(
            window.base_language_combo.findData("es")
        )
        self.assertIn("Nenhum par instalado", window.base_language_status_label.text())
        window.base_language_combo.setCurrentIndex(
            window.base_language_combo.findData("en")
        )
        self.assertTrue(window.base_language_status_label.isHidden())
        window.close()

    def test_language_download_bar_uses_reported_bytes(self):
        window = SettingsWindow()
        window._on_language_pack_progress(
            {"pack_code": "en-es", "current": 1, "count": 2,
             "received": 50, "total": 100}
        )
        self.assertEqual(window.language_pack_progress_bars["en-es"].value(), 50)
        self.assertEqual(
            window.language_pack_status_labels["en-es"].text(), "Baixando 1/2"
        )
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

        self.assertEqual(
            [window.tabs.tabText(i) for i in range(window.tabs.count())],
            ["Básico", "Voz", "Idiomas", "Avançado"],
        )
        self.assertTrue(window.tabs.widget(1).isAncestorOf(window.capture_mode_combo))
        self.assertTrue(window.advanced_tab.isAncestorOf(window.active_device_label))

        for width in (1500, 700):
            window.resize(width, 680)
            self.app.processEvents()
            self.assertLessEqual(window.model_combo.width(), 560)
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

        self.assertEqual(window.hardware_indicator.text(), "✓")
        for index, heading in enumerate(("Configurações básicas", "Configurações de voz", "Configurações de idiomas", "Configurações avançadas")):
            window.tabs.setCurrentIndex(index)
            self.assertEqual(window.header_title.text(), heading)

        self.assertEqual(window.model_combo.currentData(), DEFAULT_SETTINGS["model_size"])
        self.assertEqual(window.vad_combo.currentData(), DEFAULT_SETTINGS["vad_type"])

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

    def test_error_popup_does_not_block_other_windows(self):
        parent = QWidget()
        other_window = QWidget()
        parent.show()
        other_window.show()
        show_error(parent, "Falha de teste", "Confira a configuração.")
        self.app.processEvents()

        dialogs = parent.findChildren(ErrorDialog)
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(dialogs[0].windowModality(), Qt.NonModal)
        self.assertTrue(dialogs[0].isVisible())
        self.assertTrue(other_window.close())
        self.assertFalse(other_window.isVisible())
        dialogs[0].close()
        parent.close()
        self.app.processEvents()

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
        self.assertIn("#0F172A", popup.findChild(QFrame, "settingsComboPopupPanel").styleSheet())
        QTest.mouseClick(window.model_combo, Qt.LeftButton)
        self.app.processEvents()
        self.assertIsNone(window.model_combo._settings_popup)
        QTest.mouseClick(window.model_combo, Qt.LeftButton)
        self.app.processEvents()
        self.assertIsNotNone(window.model_combo._settings_popup)
        self.assertTrue(window.model_combo._settings_popup.isVisible())
        window.model_combo.hidePopup()
        window.close()

    def test_settings_dropdown_scrolls_when_many_outputs_are_listed(self):
        from PySide6.QtWidgets import QScrollArea
        from frontend.src.transcription_window.settings_window import ModernComboBox

        combo = ModernComboBox()
        for index in range(16):
            combo.addItem(f"Saída {index}", str(index))
        combo.resize(300, 30)
        combo.show()
        self.app.processEvents()
        combo.showPopup()
        self.app.processEvents()
        popup = combo._settings_popup
        scroll_area = popup.findChild(QScrollArea)
        self.assertLessEqual(popup.height(), 360)
        self.assertGreater(scroll_area.verticalScrollBar().maximum(), 0)
        combo.hidePopup()
        combo.close()

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
        with patch(
            "frontend.src.transcription_window.settings_window.ask_confirmation"
        ) as confirmation:
            window.close()
        confirmation.assert_not_called()

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
            with patch(
                "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
                return_value="discard",
            ) as confirmation:
                window.close()
            self.app.processEvents()

        confirmation.assert_called_once()
        self.assertIs(confirmation.call_args.args[0], window)
        self.assertEqual(window.model_combo.currentIndex(), saved_index)
        self.assertFalse(window.has_unsaved_changes())
        window.show()
        self.assertEqual(window.model_combo.currentIndex(), saved_index)
        window.close()

    def test_closing_settings_can_keep_unsaved_changes_for_editing(self):
        window = SettingsWindow()
        window.show()
        saved_index = window.model_combo.currentIndex()
        changed_index = (saved_index + 1) % window.model_combo.count()
        window.model_combo.setCurrentIndex(changed_index)

        with patch(
            "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
            return_value="cancel",
        ) as confirmation:
            window.close()

        confirmation.assert_called_once()
        self.assertTrue(window.isVisible())
        self.assertTrue(window.has_unsaved_changes())
        self.assertEqual(window.model_combo.currentIndex(), changed_index)
        window.close()

    def test_unsaved_settings_dialog_has_line_break_and_cancelable_close(self):
        dialog = UnsavedSettingsDialog(None)
        self.assertEqual(
            dialog.message_label.text(),
            "Há alterações não salvas nas configurações.\nDeseja descartá-las?",
        )
        self.assertEqual(dialog.save_button.text(), "Salvar e fechar")
        self.assertEqual(dialog.discard_button.text(), "Descartar")
        dialog.close()
        self.assertEqual(dialog.result(), QDialog.Rejected)

    def test_closing_settings_can_save_and_close_in_one_click(self):
        window = SettingsWindow()
        window.show()
        saved_index = window.model_combo.currentIndex()
        changed_index = (saved_index + 1) % window.model_combo.count()
        window.model_combo.setCurrentIndex(changed_index)
        self.assertTrue(window.has_unsaved_changes())

        with (
            patch("frontend.src.transcription_window.settings_window.ask_unsaved_settings", return_value="save"),
            patch("frontend.src.transcription_window.settings_window.save_settings") as save,
        ):
            window.close()

        save.assert_called_once()
        self.assertFalse(window.isVisible())
        self.assertFalse(window.has_unsaved_changes())
        self.assertEqual(window.model_combo.currentIndex(), changed_index)

    def test_save_clears_dotted_keyboard_focus_from_button(self):
        window = SettingsWindow()
        window.show()
        window.save_button.setFocus()
        self.app.processEvents()
        self.assertTrue(window.save_button.hasFocus())

        with patch("frontend.src.transcription_window.settings_window.save_settings"):
            window._on_save_clicked()

        self.assertFalse(window.save_button.hasFocus())
        window.hide()

    def test_opening_minimized_settings_restores_the_window(self):
        window = MainWindow()
        window.settings_window.showMinimized()
        self.app.processEvents()

        window._on_settings_clicked()

        self.assertFalse(window.settings_window.isMinimized())
        window.hide()
        window.settings_window.hide()
        window.toolbar.hide()
        window.transcription_window.hide()

    def test_home_returns_only_after_toolbar_and_settings_are_closed(self):
        window = MainWindow()
        window.show()
        window._on_start_clicked()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        self.assertTrue(window.toolbar.isVisible())
        self.assertTrue(window.transcription_window.isVisible())

        window._on_settings_clicked()
        self.app.processEvents()
        window.toolbar.close()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        self.assertTrue(window.settings_window.isVisible())
        self.assertFalse(window.transcription_window.isVisible())

        window.settings_window.close()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        window.hide()

    def test_settings_opened_from_home_restore_it_after_saving_and_closing(self):
        window = MainWindow()
        window.show()
        window._on_settings_clicked()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        model = window.settings_window.model_combo
        model.setCurrentIndex((model.currentIndex() + 1) % model.count())

        with (
            patch(
                "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
                return_value="save",
            ),
            patch("frontend.src.transcription_window.settings_window.save_settings") as save,
        ):
            window.settings_window.close()
        self.app.processEvents()
        save.assert_called_once()
        self.assertTrue(window.isVisible())
        window.hide()

    def test_toolbar_close_can_be_cancelled_when_settings_are_unsaved(self):
        window = MainWindow()
        window.show()
        window._on_start_clicked()
        window._on_settings_clicked()
        model = window.settings_window.model_combo
        model.setCurrentIndex((model.currentIndex() + 1) % model.count())

        with patch(
            "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
            return_value="cancel",
        ):
            window.toolbar.close()
        self.assertTrue(window.toolbar.isVisible())
        self.assertFalse(window.isVisible())

        with patch(
            "frontend.src.transcription_window.settings_window.ask_unsaved_settings",
            return_value="discard",
        ):
            window.toolbar.close()
        self.assertFalse(window.toolbar.isVisible())
        self.assertTrue(window.settings_window.isVisible())
        self.assertFalse(window.isVisible())
        window.settings_window.close()
        window.hide()

    def test_toolbar_represents_chat_in_the_taskbar(self):
        window = MainWindow()
        self.assertEqual(window.toolbar.windowType(), Qt.Window)
        self.assertEqual(window.transcription_window.windowType(), Qt.Tool)
        self.assertIs(window.transcription_window.parent(), window.toolbar)
        window.hide()

    def test_opening_home_keeps_saved_language_pair(self):
        settings_store.save_settings({"user_language": "pt-br", "meeting_language": "en"})
        window = MainWindow()
        self.assertEqual(window.toolbar.source_combo.currentData(), "pt-br")
        self.assertEqual(window.toolbar.target_combo.currentData(), "en")
        self.assertEqual(settings_store.load_settings()["user_language"], "pt-br")
        self.assertEqual(settings_store.load_settings()["meeting_language"], "en")
        window.hide()

    def test_home_logo_and_cards_fit_at_minimum_window_size(self):
        window = MainWindow()
        window.resize(700, 500)
        window.show()
        self.app.processEvents()
        root = window.centralWidget()
        logo = root.findChild(QLabel, "heroLogo")
        title = root.findChild(QLabel, "heroTitle")
        logo_top = logo.mapTo(root, logo.rect().topLeft()).y()
        title_top = title.mapTo(root, title.rect().topLeft()).y()
        self.assertGreaterEqual(logo_top, 0)
        self.assertLessEqual(logo_top + logo.height(), title_top)
        for card in root.findChildren(QFrame, "featureCard"):
            card_top = card.mapTo(root, card.rect().topLeft()).y()
            self.assertLessEqual(card_top + card.height(), root.height())
        window.hide()

    def test_home_cards_keep_space_below_buttons_when_window_grows(self):
        window = MainWindow()
        window.resize(700, 500)
        window.show()
        self.app.processEvents()
        root = window.centralWidget()
        logo = root.findChild(QLabel, "heroLogo")
        slogan = root.findChild(QLabel, "heroSlogan")
        footer = root.findChild(QLabel, "footerText")
        card = root.findChildren(QFrame, "featureCard")[0]

        def positions():
            footer_bottom = footer.mapTo(root, footer.rect().bottomLeft()).y()
            card_top = card.mapTo(root, card.rect().topLeft()).y()
            card_bottom = card.mapTo(root, card.rect().bottomLeft()).y()
            button_top = window.start_button.mapTo(
                root, window.start_button.rect().topLeft()
            ).y()
            slogan_bottom = slogan.mapTo(root, slogan.rect().bottomLeft()).y()
            logo_top = logo.mapTo(root, logo.rect().topLeft()).y()
            return (
                root.height() - footer_bottom,
                root.height() - card_bottom,
                button_top,
                logo_top,
                button_top - slogan_bottom,
                card_top - (button_top + window.start_button.height()),
            )

        small = positions()
        window.resize(1000, 700)
        self.app.processEvents()
        large = positions()
        self.assertGreater(large[0], small[0])
        self.assertGreater(large[1], small[1])
        self.assertGreater(large[2], small[2])
        self.assertGreaterEqual(small[3], 24)
        self.assertGreater(large[3], small[3])
        self.assertEqual(small[4], large[4])
        self.assertGreaterEqual(small[0], 30)
        self.assertGreaterEqual(small[5], 30)
        self.assertGreater(large[5], small[5])
        self.assertEqual(window.start_button.focusPolicy(), Qt.NoFocus)
        self.assertEqual(window.settings_button.focusPolicy(), Qt.NoFocus)
        window.hide()

    def test_hardware_indicator_precedes_aligned_selector(self):
        window = SettingsWindow()
        window.show()
        self.app.processEvents()
        form = window.tabs.widget(0).layout()
        indicator_right = window.hardware_indicator.mapTo(
            window.tabs.widget(0), window.hardware_indicator.rect().topRight()
        ).x()
        self.assertEqual(window.device_combo.x(), window.model_combo.x())
        self.assertGreater(indicator_right, form.labelForField(window.model_combo).geometry().right())
        self.assertLessEqual(
            abs(window.device_combo.x() - indicator_right - form.horizontalSpacing()), 1
        )
        window.close()

    def test_advanced_wheel_scrolls_page_without_changing_values(self):
        window = SettingsWindow()
        window.show()
        window.tabs.setCurrentWidget(window.advanced_tab)
        self.app.processEvents()
        window.context_spin.setValue(5)
        window.vad_combo.setCurrentIndex(0)
        bar = window._advanced_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        for widget in (window.context_spin, window.vad_combo):
            event = QWheelEvent(
                QPointF(10, 10), QPointF(10, 10), QPoint(0, 0),
                QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
                Qt.ScrollUpdate, False,
            )
            QApplication.sendEvent(widget, event)
        self.assertEqual(window.context_spin.value(), 5)
        self.assertEqual(window.vad_combo.currentIndex(), 0)
        self.assertGreater(bar.value(), 0)
        window.close()

    def test_chat_resizes_from_left_border_without_corner_grip(self):
        chat = FloatingTranscriptionWindow()
        chat.setGeometry(100, 100, 500, 300)
        chat.show()
        self.app.processEvents()
        start = chat.mapToGlobal(chat.rect().topLeft())
        start_pos = QPointF(start.x() + 3, start.y() + 100)
        end_pos = QPointF(start_pos.x() + 40, start_pos.y())
        press = QMouseEvent(
            QEvent.MouseButtonPress, QPointF(3, 100), start_pos,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        move = QMouseEvent(
            QEvent.MouseMove, QPointF(43, 100), end_pos,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        )
        release = QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(43, 100), end_pos,
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
        )
        with patch("frontend.src.transcription_window.floating_windows.save_settings"):
            self.assertTrue(chat._handle_border_mouse(press))
            self.assertTrue(chat._handle_border_mouse(move))
            self.assertTrue(chat._handle_border_mouse(release))
        self.assertEqual(chat.x(), 140)
        self.assertEqual(chat.width(), 460)
        chat.close()

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
