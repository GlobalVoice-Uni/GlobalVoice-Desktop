import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from backend.app.audio.audio_capture import WasapiLoopbackAudioSource
from backend.app.audio.devices import AudioDeviceCatalog, AudioDeviceInfo, AudioDeviceKind
from backend.app.audio.speech_output import SpeechOutputQueue
from frontend.src.transcription_window.backend_bridge import LoopbackPlaybackGate
from frontend.src.transcription_window.settings_window import SettingsWindow
from tests.unit.test_audio_capture import FakeSoundCard, FakeLoopback


class LoopbackFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_gate_mutes_local_playback_and_short_tail(self):
        FakeSoundCard.loopback = FakeLoopback()
        gate = LoopbackPlaybackGate(tail_s=0.01)
        source = WasapiLoopbackAudioSource(
            soundcard_module=FakeSoundCard,
            suppress_capture=gate.is_suppressed,
        )
        with source:
            gate.set_active(True)
            muted, peak = source.read_step()
            gate.set_active(False)
            self.assertTrue(gate.is_suppressed())
            time.sleep(0.02)
            audible, next_peak = source.read_step()
        self.assertEqual(peak, 0.0)
        self.assertFalse(np.any(muted))
        self.assertGreater(next_peak, 0.0)
        self.assertTrue(np.any(audible))

    def test_playback_gate_is_released_when_audio_output_fails(self):
        synthesizer = MagicMock()
        synthesizer.synthesize.return_value = (np.ones(10, dtype=np.float32), 1000)
        sink = MagicMock()
        sink.play.side_effect = RuntimeError("output unavailable")
        finished = threading.Event()
        states = []

        def report(active):
            states.append(active)
            if not active:
                finished.set()

        output = SpeechOutputQueue(
            synthesizer, sink, "en", on_playback_state=report,
        )
        output.start()
        output.enqueue("hello")
        self.assertTrue(finished.wait(1))
        output.stop()
        self.assertEqual(states, [True, False])
    def test_voice_tab_selects_default_headset_instead_of_cable(self):
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("4", "HeadSet", AudioDeviceKind.OUTPUT, 2, True, "MME"),
            AudioDeviceInfo("19", "HeadSet", AudioDeviceKind.OUTPUT, 2, False, "Windows WASAPI"),
            AudioDeviceInfo("16", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.OUTPUT, 2),
            AudioDeviceInfo("headset-guid", "HeadSet", AudioDeviceKind.LOOPBACK, 2, True),
            AudioDeviceInfo("cable-guid", "CABLE Input (VB-Audio Virtual Cable)", AudioDeviceKind.LOOPBACK, 2),
        ))
        with patch("frontend.src.transcription_window.settings_window.get_audio_device_catalog", return_value=catalog):
            window = SettingsWindow()
        self.addCleanup(window.close)
        self.assertEqual(window.meeting_voice_combo.currentData(), "19")
        self.assertEqual(window.meeting_voice_combo.count(), 1)
        self.assertIn("(padrão)", window.meeting_voice_combo.currentText())
        self.assertEqual(
            window.virtual_cable_note.text(),
            'No aplicativo de chamada, escolha "CABLE Output" como microfone.',
        )


if __name__ == "__main__":
    unittest.main()
