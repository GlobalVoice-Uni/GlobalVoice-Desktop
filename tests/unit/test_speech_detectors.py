import unittest
import warnings
from unittest.mock import patch

import numpy as np

from backend.app.detectors.speech_detectors import (
    EnergySpeechDetector,
    SileroSpeechDetector,
    build_speech_detector,
)


class EnergySpeechDetectorTests(unittest.TestCase):
    def test_silero_principal_loads_and_processes_a_frame(self):
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always")
            detector = SileroSpeechDetector()

        detected = detector.detect(np.zeros(512, dtype=np.float32), peak=0.0)

        self.assertFalse(detected)
        self.assertEqual(captured_warnings, [])

    def test_detect_uses_peak_threshold(self):
        detector = EnergySpeechDetector(peak_threshold=0.01)
        audio = np.zeros(3200, dtype=np.float32)

        self.assertFalse(detector.detect(audio, peak=0.009))
        self.assertTrue(detector.detect(audio, peak=0.01))

    def test_build_energy_detector_reports_active_fallback(self):
        statuses = []

        detector, detector_name = build_speech_detector(
            vad_type="energy",
            energy_peak_threshold=0.002,
            silero_threshold=0.5,
            silero_min_silence_ms=120,
            silero_speech_pad_ms=30,
            on_status=statuses.append,
        )

        self.assertIsInstance(detector, EnergySpeechDetector)
        self.assertEqual(detector_name, "energy")
        self.assertEqual(statuses, ["VAD ativo: energia (fallback)."])

    def test_silero_fallback_does_not_expose_internal_error(self):
        statuses = []

        with patch(
            "backend.app.detectors.speech_detectors.SileroSpeechDetector",
            side_effect=RuntimeError("detalhe tecnico interno"),
        ):
            detector, detector_name = build_speech_detector(
                vad_type="silero",
                energy_peak_threshold=0.002,
                silero_threshold=0.5,
                silero_min_silence_ms=120,
                silero_speech_pad_ms=30,
                on_status=statuses.append,
            )

        self.assertIsInstance(detector, EnergySpeechDetector)
        self.assertEqual(detector_name, "energy")
        self.assertNotIn("detalhe tecnico interno", " ".join(statuses))
        self.assertEqual(
            statuses,
            [
                "Silero indisponivel. Usando VAD por energia automaticamente.",
                "VAD ativo: energia (fallback).",
            ],
        )


if __name__ == "__main__":
    unittest.main()
