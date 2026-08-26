import unittest

import numpy as np

from backend.app.sessions.realtime_session import RealtimeTranscriptionSession


class StubAudioSource:
    step_duration_s = 0.2
    target_sample_rate = 16000


class SpyTranscriber:
    def __init__(self, result="texto confirmado"):
        self.result = result
        self.calls = []

    def transcribe(self, audio_16k, language, context_prompt=None):
        self.calls.append(
            {
                "audio": audio_16k,
                "language": language,
                "context_prompt": context_prompt,
            }
        )
        return self.result


class RealtimeTranscriptionSessionTests(unittest.TestCase):
    def build_session(self, transcriber=None, **overrides):
        values = {
            "audio_source": StubAudioSource(),
            "transcriber": transcriber or SpyTranscriber(),
            "language": "pt-br",
            "context_window": 0,
        }
        values.update(overrides)
        return RealtimeTranscriptionSession(**values)

    def test_normalizes_portuguese_language_code(self):
        session = self.build_session()

        self.assertEqual(session.language, "pt")

    def test_short_utterance_is_not_transcribed(self):
        transcriber = SpyTranscriber()
        session = self.build_session(transcriber=transcriber)
        emitted = []

        session._process_utterance(
            utter=np.zeros(99, dtype=np.float32),
            min_utt_samples=100,
            forced_split=False,
            on_text=emitted.append,
        )

        self.assertEqual(transcriber.calls, [])
        self.assertEqual(emitted, [])

    def test_processes_valid_utterance_and_emits_text(self):
        transcriber = SpyTranscriber(result="fala válida")
        session = self.build_session(transcriber=transcriber)
        emitted = []

        session._process_utterance(
            utter=np.zeros(100, dtype=np.float32),
            min_utt_samples=100,
            forced_split=False,
            on_text=emitted.append,
        )

        self.assertEqual(emitted, ["fala válida"])
        self.assertEqual(transcriber.calls[0]["language"], "pt")
        self.assertIsNone(transcriber.calls[0]["context_prompt"])

    def test_reconciles_tail_after_forced_split(self):
        session = self.build_session(
            tail_guard_words=2,
            forced_split_extra_tail_words=0,
        )
        emitted = []

        session._commit_transcribed_text(
            "um dois três quatro",
            forced_split=True,
            on_text=emitted.append,
        )
        session._commit_transcribed_text(
            "três quatro cinco",
            forced_split=False,
            on_text=emitted.append,
        )

        self.assertEqual(emitted, ["um dois", "três quatro cinco"])
        self.assertEqual(session.get_full_transcript(), "um dois três quatro cinco")

    def test_blocks_pathological_word_loop(self):
        session = self.build_session()

        self.assertTrue(session._looks_like_loop(["eco"] * 30))


if __name__ == "__main__":
    unittest.main()
