import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from backend.app.runtime_status import (
    ActiveDevice,
    DevicePreference,
    FallbackReason,
    RuntimeProvider,
    RuntimeStatus,
)
from frontend.src.transcription_window.floating_windows import FloatingToolbar
from frontend.src.transcription_window.controller import RealtimeController
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


if __name__ == "__main__":
    unittest.main()
