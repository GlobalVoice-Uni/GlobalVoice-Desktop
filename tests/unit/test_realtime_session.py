import unittest

import numpy as np

from backend.app.sessions.realtime_session import RealtimeTranscriptionSession


class StubAudioSource:
    step_duration_s = 0.2
    target_sample_rate = 16000


class ControlledAudioSource:
    step_duration_s = 0.2
    target_sample_rate = 16000
    input_sample_rate = 48000

    def __init__(self, talk_states):
        self.talk_states = list(talk_states)
        self.index = 0
        self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read_step(self):
        if self.index >= len(self.talk_states):
            self.session.stop()
            return np.zeros(3200, dtype=np.float32), 0.0

        self.session.set_talk_active(self.talk_states[self.index])
        self.index += 1
        return np.ones(3200, dtype=np.float32), 0.5


class RejectingSpeechDetector:
    def reset(self):
        pass

    def detect(self, audio, peak):
        raise AssertionError("O VAD nao deve decidir a captura no modo PTT")


class PeakSpeechDetector:
    def reset(self):
        pass

    def detect(self, audio, peak):
        return peak > 0.1


class SequencedAudioSource:
    step_duration_s = 0.2
    target_sample_rate = 16000
    input_sample_rate = 48000

    def __init__(self, speech_states):
        self.speech_states = list(speech_states)
        self.index = 0
        self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read_step(self):
        if self.index >= len(self.speech_states):
            self.session.stop()
            return np.zeros(3200, dtype=np.float32), 0.0

        has_speech = self.speech_states[self.index]
        self.index += 1
        audio = (
            np.ones(3200, dtype=np.float32)
            if has_speech
            else np.zeros(3200, dtype=np.float32)
        )
        return audio, 0.5 if has_speech else 0.0


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

    def test_push_to_talk_processes_only_frames_while_pressed(self):
        source = ControlledAudioSource([False, True, True, False])
        transcriber = SpyTranscriber(result="fala manual")
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=RejectingSpeechDetector(),
            capture_mode="push_to_talk",
        )
        source.session = session
        emitted = []
        speech_starts = []

        result = session.run(
            on_text=emitted.append,
            on_speech_start=lambda: speech_starts.append(True),
        )

        self.assertEqual(result, "fala manual")
        self.assertEqual(emitted, ["fala manual"])
        self.assertEqual(len(transcriber.calls), 1)
        self.assertEqual(len(transcriber.calls[0]["audio"]), 6400)
        self.assertEqual(speech_starts, [True])

    def test_short_chunk_pause_stays_in_the_same_visual_speech(self):
        source = SequencedAudioSource(
            [
                True,
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                True,
                False,
                False,
            ]
        )
        transcriber = SpyTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_silence_window_s=0.4,
            new_speech_silence_s=1.2,
            min_utterance_s=0.2,
        )
        source.session = session
        speech_starts = []
        voice_activity = []

        session.run(
            on_text=lambda _text: None,
            on_speech_start=lambda: speech_starts.append(True),
            on_voice_activity=voice_activity.append,
        )

        self.assertEqual(len(transcriber.calls), 3)
        self.assertEqual(len(speech_starts), 2)
        self.assertEqual(voice_activity[0], True)
        self.assertEqual(voice_activity[-1], False)

    def test_muted_automatic_capture_discards_audio(self):
        source = SequencedAudioSource([True, True, True])
        transcriber = SpyTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_utterance_s=0.2,
        )
        source.session = session
        session.set_microphone_muted(True)
        voice_activity = []

        session.run(
            on_text=lambda _text: None,
            on_voice_activity=voice_activity.append,
        )

        self.assertEqual(transcriber.calls, [])
        self.assertEqual(voice_activity, [])


if __name__ == "__main__":
    unittest.main()
