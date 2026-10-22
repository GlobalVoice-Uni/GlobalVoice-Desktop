import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from backend.app.audio.speech_output import (
    PiperSpeechSynthesizer,
    SoundDeviceAudioSink,
    SpeechOutputQueue,
)


class SpeechOutputTests(unittest.TestCase):
    def test_piper_synthesizes_actual_voices_without_audio_device(self):
        model_dir = Path(__file__).resolve().parents[2] / ".build/tts-voices"
        if not (model_dir / "pt_BR-cadu-medium.onnx").exists():
            self.skipTest("Modelos de voz ainda não preparados")
        synth = PiperSpeechSynthesizer(model_dir)
        for language, text in (("pt-br", "Bom dia."), ("en", "Good morning."), ("es", "Buenos días.")):
            with self.subTest(language=language):
                samples, sample_rate = synth.synthesize(text, language)
                self.assertEqual(samples.ndim, 1)
                self.assertGreater(len(samples), sample_rate // 4)
                self.assertTrue(np.isfinite(samples).all())

    def test_english_voice_selection_and_language_validation(self):
        model_dir = Path(__file__).resolve().parents[2] / ".build/tts-voices"
        if not (model_dir / "en_US-joe-medium.onnx").exists():
            self.skipTest("Voz Joe ainda não preparada")
        synth = PiperSpeechSynthesizer(model_dir)
        samples, sample_rate = synth.synthesize("Good morning.", "en", "en-joe")
        self.assertGreater(len(samples), sample_rate // 4)
        self.assertEqual(set(synth._voices), {"en_US-joe-medium"})
        with self.assertRaises(ValueError):
            synth.synthesize("Bom dia.", "pt-br", "en-joe")

    def test_sink_plays_in_blocks_and_honors_stop(self):
        stream = MagicMock()
        writer = stream.__enter__.return_value
        event = threading.Event()
        writer.write.side_effect = lambda _: event.set()
        with (
            patch("sounddevice.query_devices", return_value={"default_samplerate": 1000}) as query,
            patch("sounddevice.OutputStream", return_value=stream) as output_stream,
        ):
            sink = SoundDeviceAudioSink("25")
            sink.play(np.ones(2400, dtype=np.float32), 1000, event)
        query.assert_called_once_with(25, kind="output")
        self.assertEqual(output_stream.call_args.kwargs["device"], 25)
        writer.write.assert_called_once()
        self.assertEqual(writer.write.call_args.args[0].shape, (200, 1))

    def test_sink_resamples_to_selected_device_rate(self):
        stream = MagicMock()
        event = threading.Event()
        with (
            patch("sounddevice.query_devices", return_value={"default_samplerate": 44100}),
            patch("sounddevice.OutputStream", return_value=stream) as output_stream,
        ):
            sink = SoundDeviceAudioSink("25")
            sink.play(np.ones(2205, dtype=np.float32), 22050, event)
        self.assertEqual(output_stream.call_args.kwargs["samplerate"], 44100)
        written = sum(call.args[0].shape[0] for call in stream.__enter__.return_value.write.call_args_list)
        self.assertEqual(written, 4410)

    def test_virtual_microphone_writes_stereo_with_headroom(self):
        stream = MagicMock()
        with (
            patch("sounddevice.query_devices", return_value={
                "default_samplerate": 48000, "max_output_channels": 2,
            }),
            patch("sounddevice.OutputStream", return_value=stream) as output_stream,
        ):
            sink = SoundDeviceAudioSink("14", virtual_microphone=True)
            sink.play(np.array([-1.0, 0.5, 1.0], dtype=np.float32), 48000, threading.Event())
        self.assertEqual(output_stream.call_args.kwargs["channels"], 2)
        np.testing.assert_array_equal(
            stream.__enter__.return_value.write.call_args.args[0],
            np.array([[-0.5, -0.5], [0.25, 0.25], [0.5, 0.5]], dtype=np.float32),
        )

    def test_queue_does_not_block_capture_and_cancels_pending_audio(self):
        started = threading.Event()
        release = threading.Event()
        synth = MagicMock()
        def slow_synthesis(text, language):
            started.set()
            release.wait(2)
            return np.ones(100, dtype=np.float32), 1000
        synth.synthesize.side_effect = slow_synthesis
        sink = MagicMock()
        output = SpeechOutputQueue(synth, sink, "en")
        output.start()
        begin = time.perf_counter()
        output.enqueue("first")
        output.enqueue("second")
        self.assertLess(time.perf_counter() - begin, 0.1)
        self.assertTrue(started.wait(1))
        output.stop()
        release.set()
        output._worker.join(2)
        sink.play.assert_not_called()
        self.assertEqual(synth.synthesize.call_count, 1)

    def test_queue_keeps_only_latest_pending_phrase(self):
        playing = threading.Event()
        release = threading.Event()
        second_played = threading.Event()
        synth = MagicMock()
        synth.synthesize.return_value = np.ones(100, dtype=np.float32), 1000
        sink = MagicMock()

        def play(_audio, _rate, _stop):
            if not playing.is_set():
                playing.set()
                release.wait(timeout=2)
            else:
                second_played.set()

        sink.play.side_effect = play
        notices = []
        output = SpeechOutputQueue(synth, sink, "en", on_notice=notices.append)
        output.start()
        output.enqueue("primeira")
        self.assertTrue(playing.wait(1))
        output.enqueue("segunda")
        output.enqueue("terceira")
        output.enqueue("mais recente")
        release.set()
        self.assertTrue(second_played.wait(1))
        output.stop()

        self.assertEqual(
            [call.args[0] for call in synth.synthesize.call_args_list],
            ["primeira", "mais recente"],
        )
        self.assertEqual(len(notices), 1)
        self.assertIn("voz traduzida atrasou", notices[0])

    def test_muting_meeting_voice_skips_synthesis_and_stops_current_audio(self):
        playing = threading.Event()
        stopped = threading.Event()
        synth = MagicMock()
        synth.synthesize.return_value = np.ones(200, dtype=np.float32), 1000
        sink = MagicMock()

        def play(_audio, _rate, stop_signal):
            playing.set()
            while not stop_signal.is_set():
                time.sleep(0.01)
            stopped.set()

        sink.play.side_effect = play
        output = SpeechOutputQueue(synth, sink, "en")
        output.start()
        try:
            output.enqueue("primeira")
            self.assertTrue(playing.wait(1))
            output.set_muted(True)
            self.assertTrue(stopped.wait(1))
            output.enqueue("segunda")
            time.sleep(0.05)
            self.assertEqual(synth.synthesize.call_count, 1)
        finally:
            output.stop()


if __name__ == "__main__":
    unittest.main()
