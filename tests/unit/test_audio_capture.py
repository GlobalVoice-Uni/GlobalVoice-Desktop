import unittest
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np

from backend.app.audio.audio_capture import (
    AudioSourceError,
    MicrophoneAudioSource,
    WasapiLoopbackAudioSource,
    create_audio_source,
)


class FakeRecorder:
    def record(self, numframes):
        left = np.full(numframes, 0.25, dtype=np.float32)
        right = np.full(numframes, 0.75, dtype=np.float32)
        return np.column_stack((left, right))


class FakeRecorderContext:
    def __init__(self):
        self.recorder = FakeRecorder()
        self.closed = False

    def __enter__(self):
        return self.recorder

    def __exit__(self, exc_type, exc, tb):
        self.closed = True


class FakeLoopback:
    id = "speaker-id"
    name = "Saida de teste"
    channels = 2
    isloopback = True

    def __init__(self):
        self.context = FakeRecorderContext()
        self.recorder_arguments = None

    def recorder(self, **kwargs):
        self.recorder_arguments = kwargs
        return self.context


class FakeSoundCard:
    loopback = FakeLoopback()

    @classmethod
    def default_speaker(cls):
        return cls.loopback

    @classmethod
    def get_microphone(cls, identifier, include_loopback=False):
        if identifier != "speaker-id" or not include_loopback:
            raise IndexError(identifier)
        return cls.loopback


class LoopbackAudioSourceTests(unittest.TestCase):
    def setUp(self):
        FakeSoundCard.loopback = FakeLoopback()

    def test_captures_stereo_and_returns_fixed_mono_block(self):
        source = WasapiLoopbackAudioSource(
            step_duration_s=0.2,
            target_sample_rate=16000,
            capture_sample_rate=48000,
            soundcard_module=FakeSoundCard,
        )

        with source:
            audio, peak = source.read_step()

        self.assertEqual(audio.shape, (3200,))
        self.assertEqual(audio.dtype, np.float32)
        self.assertAlmostEqual(float(np.mean(audio)), 0.5, places=3)
        self.assertAlmostEqual(peak, 0.5, places=3)
        self.assertEqual(
            FakeSoundCard.loopback.recorder_arguments["channels"],
            [0, 1],
        )
        self.assertTrue(FakeSoundCard.loopback.context.closed)

    def test_invalid_loopback_is_reported_with_user_message(self):
        class BrokenSoundCard(FakeSoundCard):
            @classmethod
            def get_microphone(cls, identifier, include_loopback=False):
                raise IndexError(identifier)

        source = WasapiLoopbackAudioSource(
            output_device="missing",
            soundcard_module=BrokenSoundCard,
        )

        with self.assertRaisesRegex(AudioSourceError, "Não foi possível iniciar"):
            source.open()

    def test_wasapi_keeps_com_initialized_until_capture_closes(self):
        active = False

        @contextmanager
        def com_context():
            nonlocal active
            active = True
            try:
                yield
            finally:
                active = False

        class GuardedSoundCard(FakeSoundCard):
            @classmethod
            def get_microphone(cls, identifier, include_loopback=False):
                self.assertTrue(active)
                return super().get_microphone(identifier, include_loopback)

        source = WasapiLoopbackAudioSource(soundcard_module=GuardedSoundCard)
        with patch("backend.app.audio.audio_capture.windows_com_initialized", com_context):
            with source:
                self.assertTrue(active)
                source.read_step()
        self.assertFalse(active)

    def test_factory_keeps_microphone_as_default(self):
        self.assertIsInstance(create_audio_source("microphone"), MicrophoneAudioSource)
        self.assertIsInstance(create_audio_source("loopback"), WasapiLoopbackAudioSource)


if __name__ == "__main__":
    unittest.main()
