import threading
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


class CaptureAwareTranscriber(SpyTranscriber):
    def __init__(self, capture_finished):
        super().__init__(result="captura continua")
        self.capture_finished = capture_finished
        self.capture_continued_during_stt = False

    def transcribe(self, audio_16k, language, context_prompt=None):
        self.capture_continued_during_stt = self.capture_finished.wait(timeout=0.5)
        return super().transcribe(audio_16k, language, context_prompt)


class CaptureAwareAudioSource(SequencedAudioSource):
    def __init__(self, speech_states, capture_finished):
        super().__init__(speech_states)
        self.capture_finished = capture_finished

    def read_step(self):
        if self.index >= len(self.speech_states):
            self.capture_finished.set()
        return super().read_step()


class WaitForTextAudioSource(SequencedAudioSource):
    def __init__(self, speech_states, text_ready):
        super().__init__(speech_states)
        self.text_ready = text_ready
        self.text_arrived_during_silence = False

    def read_step(self):
        if self.index == len(self.speech_states):
            self.text_arrived_during_silence = self.text_ready.wait(timeout=0.5)
        return super().read_step()


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

    def test_continuous_speech_ramps_up_without_slow_third_chunk(self):
        source = SequencedAudioSource([True] * 60)
        transcriber = SpyTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_utterance_s=0.2,
            boundary_overlap_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: None)

        durations = [len(call["audio"]) / 16000 for call in transcriber.calls]
        self.assertEqual(durations[:5], [1.8, 2.0, 2.2, 2.4, 2.4])

    def test_short_initial_chunks_restart_after_a_long_pause(self):
        source = SequencedAudioSource([True] * 10 + [False] * 6 + [True] * 10)
        transcriber = SpyTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_silence_window_s=0.4,
            new_speech_silence_s=0.8,
            min_utterance_s=0.2,
            boundary_overlap_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: None)

        durations = [len(call["audio"]) / 16000 for call in transcriber.calls]
        self.assertEqual(durations[0], 1.8)
        self.assertEqual(durations[2], 1.8)

    def test_first_forced_chunk_publishes_text_before_capture_stops(self):
        text_ready = threading.Event()
        source = WaitForTextAudioSource([True] * 9, text_ready)
        transcriber = SpyTranscriber(result="um dois três")
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_utterance_s=0.2,
            boundary_overlap_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: text_ready.set())

        self.assertTrue(source.text_arrived_during_silence)

    def test_initial_chunk_limit_also_applies_to_push_to_talk(self):
        source = ControlledAudioSource([True] * 60 + [False])
        transcriber = SpyTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=RejectingSpeechDetector(),
            capture_mode="push_to_talk",
            min_speech_window_s=0.2,
            min_utterance_s=0.2,
            boundary_overlap_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: None)

        durations = [len(call["audio"]) / 16000 for call in transcriber.calls]
        self.assertEqual(durations[:5], [1.8, 2.0, 2.2, 2.4, 2.4])

    def test_forced_split_tail_is_processed_after_silence_without_new_speech(self):
        source = SequencedAudioSource([True, True, True, True, False, False, False, False])

        class TailTranscriber(SpyTranscriber):
            def transcribe(self, audio_16k, language, context_prompt=None):
                result = "um dois três quatro cinco" if not self.calls else "cinco seis"
                self.result = result
                return super().transcribe(audio_16k, language, context_prompt)

        transcriber = TailTranscriber()
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_silence_window_s=0.4,
            min_utterance_s=0.2,
            max_utterance_s=0.8,
            boundary_overlap_s=0.4,
            tail_guard_words=2,
            forced_split_extra_tail_words=0,
        )
        source.session = session
        emitted = []

        session.run(on_text=emitted.append)

        self.assertEqual(len(transcriber.calls), 2)
        self.assertEqual(" ".join(emitted), "um dois três quatro cinco seis")

    def test_natural_pause_publishes_pending_text_before_session_stops(self):
        text_ready = threading.Event()
        source = WaitForTextAudioSource([True, True, False, False], text_ready)
        session = self.build_session(
            audio_source=source,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_silence_window_s=0.4,
            min_utterance_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: text_ready.set())

        self.assertTrue(source.text_arrived_during_silence)

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

    def test_capture_continues_while_stt_processes_previous_utterance(self):
        capture_finished = threading.Event()
        source = CaptureAwareAudioSource(
            [True, True, False, False, False],
            capture_finished,
        )
        transcriber = CaptureAwareTranscriber(capture_finished)
        session = self.build_session(
            audio_source=source,
            transcriber=transcriber,
            speech_detector=PeakSpeechDetector(),
            min_speech_window_s=0.2,
            min_silence_window_s=0.4,
            min_utterance_s=0.2,
        )
        source.session = session

        session.run(on_text=lambda _text: None)

        self.assertTrue(transcriber.capture_continued_during_stt)
        timing = session.get_last_transcription_timing()
        self.assertIsNotNone(timing)
        self.assertGreater(timing.audio_duration_s, 0.0)
        self.assertGreaterEqual(timing.queue_wait_s, 0.0)


if __name__ == "__main__":
    unittest.main()
