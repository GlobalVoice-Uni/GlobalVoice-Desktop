import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from experiments.asr_baseline.audio import LoadedAudio
from experiments.asr_baseline.benchmark import run_baseline


class FakeTranscriber:
    device = "cpu"

    def transcribe(self, audio_16k, language, context_prompt=None):
        return "ola mundo"


class BaselineRunnerTests(unittest.TestCase):
    def test_builds_report_without_loading_a_real_model(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            audio_path = Path(temporary_directory) / "sample.wav"
            audio_path.write_bytes(b"fixed-audio-content")
            audio = LoadedAudio(
                samples=np.zeros(16_000, dtype=np.float32),
                original_sample_rate=16_000,
                target_sample_rate=16_000,
                duration_seconds=1.0,
            )

            with patch(
                "experiments.asr_baseline.benchmark.collect_environment",
                return_value={"python": "test"},
            ):
                report = run_baseline(
                    audio_path=audio_path,
                    audio=audio,
                    reference="ola mundo",
                    reference_path=None,
                    language="pt",
                    model_size="small",
                    requested_device="cpu",
                    runs=2,
                    transcriber_factory=lambda model, device: FakeTranscriber(),
                    project_root=Path(temporary_directory),
                )

            self.assertEqual(report["configuration"]["engine"], "faster-whisper")
            self.assertEqual(report["configuration"]["resolved_device"], "cpu")
            self.assertEqual(len(report["runs"]), 2)
            self.assertEqual(report["summary"]["word_error_rate_median"], 0.0)
            self.assertEqual(report["runs"][0]["transcript"], "ola mundo")


if __name__ == "__main__":
    unittest.main()
