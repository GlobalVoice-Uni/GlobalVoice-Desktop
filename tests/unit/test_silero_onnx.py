import unittest

import numpy as np

from backend.app.detectors.silero_onnx import (
    FRAME_SAMPLES,
    SileroOnnxStreamingModel,
)


class SileroOnnxStreamingModelTests(unittest.TestCase):
    def test_silence_remains_inactive(self):
        detector = SileroOnnxStreamingModel()

        result = detector.process(np.zeros(FRAME_SAMPLES, dtype=np.float32))

        self.assertFalse(result.active)
        self.assertIsNone(result.event)
        self.assertGreaterEqual(result.probability, 0.0)
        self.assertLessEqual(result.probability, 1.0)

    def test_rejects_non_streaming_frame_size(self):
        detector = SileroOnnxStreamingModel()

        with self.assertRaisesRegex(ValueError, "512"):
            detector.process(np.zeros(320, dtype=np.float32))

    def test_reset_restores_initial_model_state(self):
        detector = SileroOnnxStreamingModel()
        frame = np.full(FRAME_SAMPLES, 0.01, dtype=np.float32)

        first = detector.process(frame)
        detector.process(frame)
        detector.reset()
        after_reset = detector.process(frame)

        self.assertAlmostEqual(first.probability, after_reset.probability, places=7)
        self.assertEqual(first.active, after_reset.active)
        self.assertEqual(first.event, after_reset.event)


if __name__ == "__main__":
    unittest.main()
