import unittest

import numpy as np

from backend.app.audio.devices import AudioDeviceCatalog, AudioDeviceInfo, AudioDeviceKind
from backend.app.audio.microphone_relay import MicrophoneRelay
from backend.app.audio.virtual_cable import find_vb_cable
from diagnostics.measure_virtual_cable_latency import CaptureBlock, estimate_added_latency_ms


class VirtualCableTests(unittest.TestCase):
    def test_ready_probe_opens_and_closes_both_endpoints_without_starting_audio(self):
        import sys
        from unittest.mock import MagicMock, patch
        from backend.app.audio.virtual_cable import _cable_endpoints_ready, VirtualCableRoute

        route = VirtualCableRoute(
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2),
        )
        sd = MagicMock()
        sd.query_devices.return_value = {"default_samplerate": 48000}
        with patch.dict(sys.modules, {"sounddevice": sd}):
            self.assertTrue(_cable_endpoints_ready(route))
        sd.RawOutputStream.assert_called_once_with(device=2, samplerate=48000, channels=2)
        sd.RawInputStream.assert_called_once_with(device=3, samplerate=48000, channels=2)
        sd.RawOutputStream.return_value.start.assert_not_called()
        sd.RawInputStream.return_value.start.assert_not_called()
        sd.RawOutputStream.return_value.close.assert_called_once()
        sd.RawInputStream.return_value.close.assert_called_once()

        sd.RawInputStream.side_effect = OSError("endpoint indisponível")
        with patch.dict(sys.modules, {"sounddevice": sd}):
            self.assertFalse(_cable_endpoints_ready(route))
        self.assertEqual(sd.RawOutputStream.return_value.close.call_count, 2)

    def test_detects_matching_cable_and_prefers_wasapi(self):
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("1", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="MME"),
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="MME"),
            AudioDeviceInfo("4", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="Windows WASAPI"),
        ))
        route = find_vb_cable(catalog)
        self.assertIsNotNone(route)
        self.assertEqual(route.render.id, "2")
        self.assertEqual(route.capture.id, "4")

    def test_incomplete_cable_is_not_offered(self):
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2),
        ))
        self.assertIsNone(find_vb_cable(catalog))

    def test_service_left_after_uninstall_does_not_count_as_device(self):
        import os
        from unittest.mock import patch
        from backend.app.audio.virtual_cable import _driver_device_present

        if os.name != "nt":
            self.skipTest("consulta ao registro do Windows")
        with patch("winreg.OpenKey") as open_key, patch("winreg.QueryValueEx", return_value=(0, 4)):
            self.assertFalse(_driver_device_present())
            self.assertIn("Enum", open_key.call_args.args[1])
        with patch("winreg.OpenKey"), patch("winreg.QueryValueEx", return_value=(1, 4)):
            self.assertTrue(_driver_device_present())

    def test_status_distinguishes_pending_reboot_from_missing_driver(self):
        from unittest.mock import patch
        from backend.app.audio.virtual_cable import vb_cable_status

        catalog = AudioDeviceCatalog(())
        with patch("backend.app.audio.virtual_cable._restart_pending", return_value=True):
            self.assertEqual(vb_cable_status(catalog), "restart_required")
            complete_catalog = AudioDeviceCatalog((
                AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2),
                AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2),
            ))
            with patch("backend.app.audio.virtual_cable._cable_endpoints_ready", return_value=False):
                self.assertEqual(vb_cable_status(complete_catalog), "restart_required")
            with patch("backend.app.audio.virtual_cable._cable_endpoints_ready", return_value=True):
                self.assertEqual(vb_cable_status(complete_catalog), "available")
        with (
            patch("backend.app.audio.virtual_cable._restart_pending", return_value=False),
            patch("backend.app.audio.virtual_cable._driver_device_present", return_value=False),
        ):
            self.assertEqual(vb_cable_status(catalog), "not_installed")


class FakeOutputStream:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.latency = 0.004

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class FakeSoundDevice:
    def query_devices(self, device, kind):
        return {"default_samplerate": 48000}

    def OutputStream(self, **kwargs):
        self.stream = FakeOutputStream(**kwargs)
        return self.stream


class MicrophoneRelayTests(unittest.TestCase):
    def test_forwards_recent_audio_and_mutes_immediately(self):
        fake = FakeSoundDevice()
        enabled = [True]
        relay = MicrophoneRelay("4", lambda: enabled[0], sounddevice_module=fake)
        relay.start(48000)
        relay.push(np.full(480, 0.4, dtype=np.float32))
        output = np.zeros((480, 1), dtype=np.float32)
        fake.stream.callback(output, 480, None, None)
        np.testing.assert_allclose(output[:, 0], 0.4)
        relay.push(np.full(480, 0.4, dtype=np.float32))
        enabled[0] = False
        fake.stream.callback(output, 480, None, None)
        np.testing.assert_array_equal(output, 0)
        relay.stop()

    def test_drops_old_audio_instead_of_building_delay(self):
        fake = FakeSoundDevice()
        relay = MicrophoneRelay("4", lambda: True, sounddevice_module=fake, max_buffer_ms=20)
        relay.start(48000)
        for number in range(5):
            relay.push(np.full(480, number + 1, dtype=np.float32))
        output = np.zeros((480, 1), dtype=np.float32)
        fake.stream.callback(output, 480, None, None)
        np.testing.assert_allclose(output[:, 0], 4)
        relay.stop()

    def test_measurement_recovers_known_added_delay(self):
        rate = 48000
        direct = np.zeros(rate, dtype=np.float32)
        delayed = np.zeros(rate, dtype=np.float32)
        direct[rate // 4] = 1
        delayed[rate // 4 + int(rate * 0.018)] = 1
        latency, correlation = estimate_added_latency_ms(
            [CaptureBlock(100.0, rate, direct)],
            [CaptureBlock(100.0, rate, delayed)],
        )
        self.assertAlmostEqual(latency, 18.0, places=1)
        self.assertGreater(correlation, 0.9)


if __name__ == "__main__":
    unittest.main()

class VendorSetupTests(unittest.TestCase):
    def test_downloads_only_sha_verified_official_archive(self):
        import hashlib
        from pathlib import Path
        import tempfile
        from zipfile import ZipFile
        from backend.app.audio.virtual_cable import prepare_vb_cable_setup

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendor = root / "vendor.zip"
            with ZipFile(vendor, "w") as package:
                package.writestr("VBCABLE_Setup_x64.exe", b"test setup")
            sha = hashlib.sha256(vendor.read_bytes()).hexdigest()
            setup = prepare_vb_cable_setup(
                root / "install", url=vendor.as_uri(), expected_sha256=sha
            )
            self.assertEqual(setup.read_bytes(), b"test setup")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                prepare_vb_cable_setup(
                    root / "changed", url=vendor.as_uri(), expected_sha256="0" * 64
                )

    def test_rejects_archive_path_traversal(self):
        import hashlib
        from pathlib import Path
        import tempfile
        from zipfile import ZipFile
        from backend.app.audio.virtual_cable import prepare_vb_cable_setup

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendor = root / "vendor.zip"
            with ZipFile(vendor, "w") as package:
                package.writestr("VBCABLE_Setup_x64.exe", b"test setup")
                package.writestr("../outside.txt", b"malicious")
            sha = hashlib.sha256(vendor.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "caminho inesperado"):
                prepare_vb_cable_setup(root / "install", url=vendor.as_uri(), expected_sha256=sha)
            self.assertFalse((root / "outside.txt").exists())


class WasapiMicrophoneTests(unittest.TestCase):
    def test_uses_wasapi_alias_of_windows_default(self):
        from backend.app.audio.audio_capture import _wasapi_alias_for_default_microphone

        class FakeSoundDevice:
            @staticmethod
            def query_devices(device=None, kind=None):
                if kind == "input":
                    return {"name": "Physical Mic"}
                return (
                    {"name": "Physical Mic", "max_input_channels": 1, "hostapi": 0},
                    {"name": "Other Mic", "max_input_channels": 1, "hostapi": 1},
                    {"name": "Physical Mic", "max_input_channels": 1, "hostapi": 1},
                )

            @staticmethod
            def query_hostapis():
                return ({"name": "MME"}, {"name": "Windows WASAPI"})

        self.assertEqual(_wasapi_alias_for_default_microphone(FakeSoundDevice), 2)

class CableUiTests(unittest.TestCase):
    def test_settings_offer_install_only_when_reboot_is_not_pending(self):
        import os
        from unittest.mock import patch
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from frontend.src.transcription_window.settings_window import SettingsWindow

        app = QApplication.instance() or QApplication([])
        with (
            patch("frontend.src.transcription_window.settings_window.get_audio_device_catalog", return_value=AudioDeviceCatalog(())),
            patch("backend.app.audio.virtual_cable._driver_device_present", return_value=False),
            patch("backend.app.audio.virtual_cable._restart_pending", return_value=False) as restart_pending,
        ):
            window = SettingsWindow()
            self.assertIn("não instalado", window.virtual_cable_label.text())
            self.assertFalse(window.virtual_cable_install_button.isHidden())
            restart_pending.return_value = True
            window._refresh_voice_devices()
            self.assertIn("Reinicie", window.virtual_cable_label.text())
            self.assertTrue(window.virtual_cable_install_button.isHidden())
            window._saved_settings_snapshot = window._collect_settings()
            window.close()
        app.processEvents()

    def test_settings_use_fixed_call_microphone(self):
        import os
        from unittest.mock import patch
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from frontend.src.transcription_window.settings_window import SettingsWindow

        app = QApplication.instance() or QApplication([])
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("1", "Physical Mic", AudioDeviceKind.INPUT, 1, is_default=True),
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("speaker", "Headphones", AudioDeviceKind.LOOPBACK, 2, is_default=True),
        ))
        with patch(
            "frontend.src.transcription_window.settings_window.get_audio_device_catalog",
            return_value=catalog,
        ), patch("backend.app.audio.virtual_cable._restart_pending", return_value=False) as restart_pending, patch(
            "backend.app.audio.virtual_cable._cable_endpoints_ready", return_value=False
        ) as endpoints_ready:
            window = SettingsWindow()
            window.audio_source_combo.setCurrentIndex(window.audio_source_combo.findData("both"))
            window.voice_output_checkbox.setChecked(True)
            request = window._build_request()
            self.assertTrue(request.voice_output_enabled)
            self.assertIsNone(request.voice_output_device_id)
            self.assertFalse(hasattr(window, "voice_output_combo"))
            self.assertIn("CABLE Output", window.virtual_cable_label.text())
            restart_pending.return_value = True
            window._refresh_voice_devices()
            self.assertIn("Reinicie", window.virtual_cable_label.text())
            self.assertTrue(window.virtual_cable_install_button.isHidden())
            endpoints_ready.return_value = True
            window._refresh_voice_devices()
            self.assertIn("CABLE Output disponível", window.virtual_cable_label.text())
            window._saved_settings_snapshot = window._collect_settings()
            window.close()
        app.processEvents()

class CableBridgeTests(unittest.TestCase):
    def test_cable_as_windows_default_output_explains_capture_conflict(self):
        from unittest.mock import patch
        from frontend.src.transcription_window import backend_bridge as bridge

        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI", is_default=True),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("4", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.LOOPBACK, 2, backend="Windows WASAPI", is_default=True),
            AudioDeviceInfo("5", "Headphones", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI"),
        ))
        with (
            patch.object(bridge, "enumerate_audio_devices", return_value=catalog),
            patch.object(bridge, "vb_cable_status", return_value="available"),
        ):
            with self.assertRaisesRegex(ValueError, "saída padrão do Windows"):
                bridge.LocalBackendBridge().run(
                    bridge.SessionRequest(audio_source="both", voice_output_enabled=True, meeting_voice_device_id="5"),
                    lambda chunk: None,
                )

    def test_translated_voice_uses_detected_cable_without_saved_output_id(self):
        from unittest.mock import MagicMock, patch
        from backend.app.runtime_status import ActiveDevice, DevicePreference, RuntimeProvider, RuntimeStatus
        from frontend.src.transcription_window import backend_bridge as bridge

        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="Windows WASAPI"),
        ))
        runtime = RuntimeStatus(
            preference=DevicePreference.CPU, active_device=ActiveDevice.CPU,
            engine="faster-whisper", provider=RuntimeProvider.CPU, compute_type="int8",
        )
        sink_factory = MagicMock()
        session = MagicMock()
        session.run.return_value = "done"
        with (
            patch.object(bridge, "enumerate_audio_devices", return_value=catalog),
            patch.object(bridge, "vb_cable_status", return_value="available"),
            patch.object(bridge, "LocalFasterWhisperTranscriber", return_value=MagicMock(runtime_status=runtime)),
            patch.object(bridge, "MicrophoneAudioSource", return_value=object()) as microphone,
            patch.object(bridge, "build_speech_detector", return_value=(object(), "energy")),
            patch.object(bridge, "RealtimeTranscriptionSession", return_value=session),
            patch.object(bridge, "SpeechOutputQueue", return_value=MagicMock()),
        ):
            bridge.LocalBackendBridge(
                translator_factory=lambda: MagicMock(),
                synthesizer_factory=lambda: object(),
                sink_factory=sink_factory,
            ).run(bridge.SessionRequest(voice_output_enabled=True), lambda chunk: None)
        sink_factory.assert_called_once_with("2", virtual_microphone=True)
        self.assertNotIn("passthrough", microphone.call_args.kwargs)

    def test_original_voice_gets_direct_relay_when_translation_off(self):
        from unittest.mock import MagicMock, patch
        from backend.app.runtime_status import ActiveDevice, DevicePreference, RuntimeProvider, RuntimeStatus
        from frontend.src.transcription_window import backend_bridge as bridge

        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("2", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2, backend="Windows WASAPI"),
            AudioDeviceInfo("3", "CABLE Output (VB-Audio Virtual Cable)", AudioDeviceKind.INPUT, 2, backend="Windows WASAPI"),
        ))
        runtime = RuntimeStatus(
            preference=DevicePreference.CPU, active_device=ActiveDevice.CPU,
            engine="faster-whisper", provider=RuntimeProvider.CPU, compute_type="int8",
        )
        session = MagicMock()
        session.run.return_value = "done"
        with (
            patch.object(bridge, "enumerate_audio_devices", return_value=catalog),
            patch.object(bridge, "vb_cable_status", return_value="available"),
            patch.object(bridge, "LocalFasterWhisperTranscriber", return_value=MagicMock(runtime_status=runtime)),
            patch.object(bridge, "MicrophoneAudioSource", return_value=object()) as microphone,
            patch.object(bridge, "MicrophoneRelay", return_value=object()) as relay,
            patch.object(bridge, "build_speech_detector", return_value=(object(), "energy")),
            patch.object(bridge, "RealtimeTranscriptionSession", return_value=session),
        ):
            bridge.LocalBackendBridge().run(bridge.SessionRequest(), lambda chunk: None)
        relay.assert_called_once()
        self.assertEqual(relay.call_args.args[0], "2")
        self.assertIn("passthrough", microphone.call_args.kwargs)
        microphone.reset_mock()
        with (
            patch.object(bridge, "enumerate_audio_devices", return_value=catalog),
            patch.object(bridge, "vb_cable_status", return_value="available"),
            patch.object(bridge, "LocalFasterWhisperTranscriber", return_value=MagicMock(runtime_status=runtime)),
            patch.object(bridge, "MicrophoneAudioSource", return_value=object()) as cable_source,
            patch.object(bridge, "build_speech_detector", return_value=(object(), "energy")),
            patch.object(bridge, "RealtimeTranscriptionSession", return_value=session),
        ):
            bridge.LocalBackendBridge().run(
                bridge.SessionRequest(audio_device_id="3"), lambda chunk: None,
            )
        self.assertNotIn("passthrough", cable_source.call_args.kwargs)
