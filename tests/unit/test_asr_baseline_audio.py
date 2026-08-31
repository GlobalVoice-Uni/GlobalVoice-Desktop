import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from experiments.asr_baseline.audio import load_wav


class AudioLoadingTests(unittest.TestCase):
    def test_converts_stereo_pcm_and_resamples_to_16khz(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "stereo.wav"
            sample_rate = 8_000
            channel = np.array([0, 8_000, -8_000, 0], dtype=np.int16)
            wavfile.write(path, sample_rate, np.column_stack((channel, channel)))

            loaded = load_wav(path)

            self.assertEqual(loaded.original_sample_rate, sample_rate)
            self.assertEqual(loaded.target_sample_rate, 16_000)
            self.assertEqual(loaded.samples.dtype, np.float32)
            self.assertEqual(loaded.samples.ndim, 1)
            self.assertEqual(len(loaded.samples), 8)
            self.assertAlmostEqual(loaded.duration_seconds, 0.0005)

    def test_rejects_empty_wav(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "empty.wav"
            wavfile.write(path, 16_000, np.array([], dtype=np.int16))

            with self.assertRaisesRegex(ValueError, "vazio"):
                load_wav(path)


if __name__ == "__main__":
    unittest.main()

