import unittest
from unittest.mock import MagicMock, patch

from frontend.src.transcription_window import backend_bridge as bridge_module


class LocalBackendBridgeTests(unittest.TestCase):
    def test_maps_request_to_local_session(self):
        request = bridge_module.SessionRequest(
            model_size="base",
            device="cpu",
            language="en",
            context_window=3,
            max_duration_s=10.0,
            vad_type="energy",
            speech_peak_threshold=0.003,
            min_speech_window_s=0.3,
            min_silence_window_s=0.5,
            max_utterance_s=4.0,
            min_utterance_s=0.8,
            boundary_overlap_s=0.4,
            tail_guard_words=3,
            forced_split_policy="protect_boundary",
            forced_split_extra_tail_words=2,
        )
        audio_source = object()
        transcriber = object()
        detector = object()
        session = MagicMock()
        session.run.return_value = "texto final"
        on_text = MagicMock()
        on_status = MagicMock()

        with (
            patch.object(
                bridge_module,
                "MicrophoneAudioSource",
                return_value=audio_source,
            ) as audio_source_class,
            patch.object(
                bridge_module,
                "LocalFasterWhisperTranscriber",
                return_value=transcriber,
            ) as transcriber_class,
            patch.object(
                bridge_module,
                "build_speech_detector",
                return_value=(detector, "energy"),
            ) as detector_builder,
            patch.object(
                bridge_module,
                "RealtimeTranscriptionSession",
                return_value=session,
            ) as session_class,
        ):
            result = bridge_module.LocalBackendBridge().run(
                request=request,
                on_text=on_text,
                on_status=on_status,
            )

        self.assertEqual(result, "texto final")
        audio_source_class.assert_called_once_with(
            step_duration_s=0.2,
            target_sample_rate=16000,
        )
        transcriber_class.assert_called_once_with(model_size="base", device="cpu")
        detector_builder.assert_called_once()

        session_arguments = session_class.call_args.kwargs
        self.assertIs(session_arguments["audio_source"], audio_source)
        self.assertIs(session_arguments["transcriber"], transcriber)
        self.assertIs(session_arguments["speech_detector"], detector)
        self.assertEqual(session_arguments["language"], "en")
        self.assertEqual(session_arguments["context_window"], 3)
        self.assertEqual(session_arguments["tail_guard_words"], 3)
        session.run.assert_called_once_with(
            on_text=on_text,
            on_status=on_status,
            max_duration_s=10.0,
        )

    def test_stop_is_forwarded_to_active_session(self):
        bridge = bridge_module.LocalBackendBridge()
        bridge._session = MagicMock()

        bridge.stop()

        bridge._session.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
