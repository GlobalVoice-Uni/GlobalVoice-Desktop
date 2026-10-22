import unittest

from backend.app.audio.devices import (
    AudioDeviceKind,
    enumerate_audio_devices,
    select_device,
)


class FakeSoundDevice:
    devices = [
        {"index": 0, "name": "Entrada sem canais", "max_input_channels": 0, "max_output_channels": 0},
        {"index": 4, "name": "Microfone USB", "max_input_channels": 2, "max_output_channels": 0},
        {"index": 8, "name": "Saída virtual", "max_input_channels": 0, "max_output_channels": 2},
    ]

    @classmethod
    def query_devices(cls, device=None, kind=None):
        del device
        if kind == "input":
            return {**cls.devices[1], "default_samplerate": 48000}
        if kind == "output":
            return {**cls.devices[2], "default_samplerate": 48000}
        return cls.devices


class FakeSpeaker:
    def __init__(self, identifier, name, channels=2):
        self.id = identifier
        self.name = name
        self.channels = channels


class FakeSoundCard:
    speakers = [
        FakeSpeaker("speaker-a", "Alto-falantes"),
        FakeSpeaker("speaker-b", "Headset"),
    ]

    @classmethod
    def default_speaker(cls):
        return cls.speakers[1]

    @classmethod
    def all_speakers(cls):
        return cls.speakers


class AudioDeviceCatalogTests(unittest.TestCase):
    def test_enumerates_inputs_outputs_and_loopbacks(self):
        catalog = enumerate_audio_devices(FakeSoundDevice, FakeSoundCard)

        self.assertEqual(len(catalog.of_kind(AudioDeviceKind.INPUT)), 1)
        self.assertEqual(len(catalog.of_kind(AudioDeviceKind.OUTPUT)), 1)
        self.assertEqual(len(catalog.of_kind(AudioDeviceKind.LOOPBACK)), 2)
        self.assertEqual(catalog.warnings, ())

        default_loopback = select_device(
            catalog,
            AudioDeviceKind.LOOPBACK,
            device_id=None,
        )
        self.assertEqual(default_loopback.id, "speaker-b")
        self.assertTrue(default_loopback.is_default)

    def test_preserves_inputs_when_wasapi_backend_is_missing(self):
        catalog = enumerate_audio_devices(FakeSoundDevice, soundcard_module=False)

        self.assertEqual(len(catalog.of_kind(AudioDeviceKind.INPUT)), 1)
        self.assertEqual(len(catalog.of_kind(AudioDeviceKind.OUTPUT)), 1)
        self.assertFalse(catalog.of_kind(AudioDeviceKind.LOOPBACK))
        self.assertTrue(catalog.warnings)


if __name__ == "__main__":
    unittest.main()
