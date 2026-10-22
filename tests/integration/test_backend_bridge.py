import unittest
from unittest.mock import ANY, MagicMock, patch

from backend.app.audio.devices import AudioDeviceCatalog, AudioDeviceInfo, AudioDeviceKind
from backend.app.runtime_status import (
    ActiveDevice,
    DevicePreference,
    RuntimeProvider,
    RuntimeStatus,
)
from frontend.src.transcription_window import backend_bridge as bridge_module


class LocalBackendBridgeTests(unittest.TestCase):
    def setUp(self):
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("headphones", "Headphones", AudioDeviceKind.LOOPBACK, 2, is_default=True),
            AudioDeviceInfo("speaker", "Speaker", AudioDeviceKind.OUTPUT, 2, is_default=True),
        ))
        devices = patch.object(bridge_module, "enumerate_audio_devices", return_value=catalog)
        cable_status = patch.object(bridge_module, "vb_cable_status", return_value="not_installed")
        devices.start()
        cable_status.start()
        self.addCleanup(devices.stop)
        self.addCleanup(cable_status.stop)

    def test_disabled_voice_keeps_text_but_does_not_create_tts(self):
        runtime = RuntimeStatus(
            preference=DevicePreference.CPU, active_device=ActiveDevice.CPU,
            engine="faster-whisper", provider=RuntimeProvider.CPU, compute_type="int8",
        )
        for source, language, target in (
            ("microphone", "pt-br", "en"),
            ("loopback", "en", "pt-br"),
        ):
            with self.subTest(source=source):
                request = bridge_module.SessionRequest(
                    audio_source=source, language=language, target_language=target,
                    display_mode="both", voice_output_enabled=False,
                    meeting_voice_enabled=False,
                )
                session = MagicMock()
                session.run.side_effect = lambda *, on_text, **kwargs: on_text("frase")
                translator = MagicMock()
                translator.translate.return_value = "translated"
                synth_factory = MagicMock()
                sink_factory = MagicMock()
                chunks = []
                with (
                    patch.object(bridge_module, "find_vb_cable", return_value=None),
                    patch.object(bridge_module, "MicrophoneAudioSource", return_value=object()),
                    patch.object(bridge_module, "create_audio_source", return_value=object()),
                    patch.object(bridge_module, "LocalFasterWhisperTranscriber", return_value=MagicMock(runtime_status=runtime)),
                    patch.object(bridge_module, "build_speech_detector", return_value=(object(), "energy")),
                    patch.object(bridge_module, "RealtimeTranscriptionSession", return_value=session),
                    patch.object(bridge_module, "SpeechOutputQueue") as output_queue,
                ):
                    bridge_module.LocalBackendBridge(
                        translator_factory=lambda: translator,
                        synthesizer_factory=synth_factory,
                        sink_factory=sink_factory,
                    ).run(request, chunks.append)
                self.assertEqual(
                    chunks[0].translated_text,
                    "translated" if source == "loopback" else "",
                )
                synth_factory.assert_not_called()
                sink_factory.assert_not_called()
                output_queue.assert_not_called()

    def test_maps_request_to_local_session(self):
        request = bridge_module.SessionRequest(
            model_size="base",
            device="cpu",
            language="en",
            capture_mode="push_to_talk",
            context_window=3,
            max_duration_s=10.0,
            vad_type="energy",
            speech_peak_threshold=0.003,
            min_speech_window_s=0.3,
            min_silence_window_s=0.5,
            new_speech_silence_s=1.4,
            max_utterance_s=4.0,
            min_utterance_s=0.8,
            boundary_overlap_s=0.4,
            tail_guard_words=3,
            forced_split_policy="protect_boundary",
            forced_split_extra_tail_words=2,
        )
        audio_source = object()
        runtime_status = RuntimeStatus(
            preference=DevicePreference.CPU,
            active_device=ActiveDevice.CPU,
            engine="faster-whisper",
            provider=RuntimeProvider.CPU,
            compute_type="int8",
        )
        transcriber = MagicMock(runtime_status=runtime_status)
        detector = object()
        session = MagicMock()
        session.run.return_value = "texto final"
        on_text = MagicMock()
        on_status = MagicMock()
        on_runtime_status = MagicMock()
        on_speech_start = MagicMock()
        on_voice_activity = MagicMock()

        with (
            patch.object(bridge_module, "find_vb_cable", return_value=None),
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
                on_runtime_status=on_runtime_status,
                on_speech_start=on_speech_start,
                on_voice_activity=on_voice_activity,
            )

        self.assertEqual(result, "texto final")
        audio_source_class.assert_called_once_with(
            step_duration_s=0.2,
            target_sample_rate=16000,
        )
        transcriber_class.assert_called_once_with(model_size="base", device="cpu")
        on_runtime_status.assert_called_once_with(runtime_status)
        on_status.assert_any_call(runtime_status.user_message)
        detector_builder.assert_called_once()

        session_arguments = session_class.call_args.kwargs
        self.assertIs(session_arguments["audio_source"], audio_source)
        self.assertIs(session_arguments["transcriber"], transcriber)
        self.assertIs(session_arguments["speech_detector"], detector)
        self.assertEqual(session_arguments["language"], "en")
        self.assertEqual(session_arguments["capture_mode"], "push_to_talk")
        self.assertEqual(session_arguments["context_window"], 3)
        self.assertEqual(session_arguments["new_speech_silence_s"], 1.4)
        self.assertEqual(session_arguments["tail_guard_words"], 3)
        session.run.assert_called_once_with(
            on_text=ANY,
            on_status=on_status,
            on_speech_start=on_speech_start,
            on_voice_activity=on_voice_activity,
            max_duration_s=10.0,
        )
        session.set_talk_active.assert_called_once_with(False)
        session.set_microphone_muted.assert_called_once_with(False)

        publish_chunk = session.run.call_args.kwargs["on_text"]
        publish_chunk("hello")
        emitted = on_text.call_args.args[0]
        self.assertEqual(emitted.channel, "user")
        self.assertEqual(emitted.original_text, "hello")

    def test_stop_is_forwarded_to_active_session(self):
        bridge = bridge_module.LocalBackendBridge()
        bridge._session = MagicMock()

        bridge.stop()

        bridge._session.stop.assert_called_once_with()

    def test_loopback_translates_confirmed_chunks_to_user_language(self):
        request = bridge_module.SessionRequest(
            device="cpu",
            audio_source="loopback",
            language="en",
            target_language="pt-br",
            display_mode="both",
        )
        runtime_status = RuntimeStatus(
            preference=DevicePreference.CPU,
            active_device=ActiveDevice.CPU,
            engine="faster-whisper",
            provider=RuntimeProvider.CPU,
            compute_type="int8",
        )
        translator = MagicMock()
        translator.translate.return_value = "olá"
        translator_factory = MagicMock(return_value=translator)
        session = MagicMock()
        session.run.return_value = "hello"
        on_text = MagicMock()

        with (
            patch.object(bridge_module, "create_audio_source", return_value=object()),
            patch.object(
                bridge_module,
                "LocalFasterWhisperTranscriber",
                return_value=MagicMock(runtime_status=runtime_status),
            ),
            patch.object(
                bridge_module,
                "build_speech_detector",
                return_value=(object(), "silero"),
            ),
            patch.object(
                bridge_module,
                "RealtimeTranscriptionSession",
                return_value=session,
            ),
        ):
            bridge_module.LocalBackendBridge(
                translator_factory=translator_factory
            ).run(request=request, on_text=on_text)

        translator.ensure_available.assert_called_once_with("en", "pt-br")
        publish_chunk = session.run.call_args.kwargs["on_text"]
        publish_chunk("hello")
        translator.translate.assert_called_once_with("hello", "en", "pt-br")
        chunk = on_text.call_args.args[0]
        self.assertEqual(chunk.channel, "meeting")
        self.assertEqual(chunk.original_text, "hello")
        self.assertEqual(chunk.translated_text, "olá")
        self.assertEqual(chunk.display_mode, "both")

    def test_push_to_talk_state_is_forwarded_to_active_session(self):
        bridge = bridge_module.LocalBackendBridge()
        bridge._session = MagicMock()

        bridge.set_talk_active(True)

        self.assertTrue(bridge._talk_active)
        bridge._session.set_talk_active.assert_called_once_with(True)

    def test_microphone_mute_is_forwarded_to_active_session(self):
        bridge = bridge_module.LocalBackendBridge()
        bridge._session = MagicMock()

        bridge.set_microphone_muted(True)

        self.assertTrue(bridge._microphone_muted)
        bridge._session.set_microphone_muted.assert_called_once_with(True)

    def test_both_sources_translate_independently_and_send_user_voice(self):
        request = bridge_module.SessionRequest(
            audio_source="both", language="pt-br", target_language="en",
            user_language="pt-br", meeting_language="en",
            audio_device_id="microphone", meeting_device_id="headphones",
            voice_output_enabled=True, voice_output_device_id="virtual",
            display_mode="both",
        )
        runtime_status = RuntimeStatus(
            preference=DevicePreference.CPU, active_device=ActiveDevice.CPU,
            engine="faster-whisper", provider=RuntimeProvider.CPU,
            compute_type="int8",
        )
        sessions = [MagicMock(), MagicMock()]
        emitted = []
        for session, text in zip(sessions, ("bom dia", "good morning")):
            def run(*, on_text, text=text, **kwargs):
                on_text(text)
                return text
            session.run.side_effect = run
        translator = MagicMock()
        translator.translate.side_effect = lambda text, source, target: f"{target}:{text}"
        output = MagicMock()
        with (
            patch.object(bridge_module, "MicrophoneAudioSource", return_value=object()),
            patch.object(bridge_module, "create_audio_source", return_value=object()),
            patch.object(bridge_module, "LocalFasterWhisperTranscriber", return_value=MagicMock(runtime_status=runtime_status)),
            patch.object(bridge_module, "build_speech_detector", return_value=(object(), "silero")),
            patch.object(bridge_module, "RealtimeTranscriptionSession", side_effect=sessions),
            patch.object(bridge_module, "SpeechOutputQueue", return_value=output),
        ):
            bridge_module.LocalBackendBridge(
                translator_factory=lambda: translator,
                synthesizer_factory=MagicMock(), sink_factory=MagicMock(),
            ).run(request, emitted.append)
        self.assertEqual({chunk.channel for chunk in emitted}, {"user", "meeting"})
        self.assertEqual(translator.ensure_available.call_count, 2)
        output.enqueue.assert_called_once_with("en:bom dia")
        output.stop.assert_called_once()
        sessions[0].run.assert_called_once()
        sessions[1].run.assert_called_once()

    def test_feedback_route_matches_physical_endpoint_across_backend_ids(self):
        from backend.app.audio.devices import AudioDeviceCatalog, AudioDeviceInfo, AudioDeviceKind
        catalog = AudioDeviceCatalog((
            AudioDeviceInfo("25", "HeadSet Realtek", AudioDeviceKind.OUTPUT, 2),
            AudioDeviceInfo("{wasapi-guid}", "HeadSet Realtek", AudioDeviceKind.LOOPBACK, 2),
        ))
        request = bridge_module.SessionRequest(
            audio_source="both", meeting_device_id="{wasapi-guid}",
            voice_output_enabled=True, voice_output_device_id="25",
        )
        with (
            patch.object(bridge_module, "enumerate_audio_devices", return_value=catalog),
            patch.object(bridge_module, "LocalFasterWhisperTranscriber") as transcriber,
        ):
            with self.assertRaisesRegex(ValueError, "mesma saída"):
                bridge_module.LocalBackendBridge().run(request, lambda chunk: None)
        transcriber.assert_not_called()

    def test_both_sources_reject_feedback_route_before_loading_models(self):
        request = bridge_module.SessionRequest(
            audio_source="both", meeting_device_id="speaker",
            voice_output_enabled=True, voice_output_device_id="speaker",
        )
        with patch.object(bridge_module, "LocalFasterWhisperTranscriber") as transcriber:
            with self.assertRaisesRegex(ValueError, "mesma saída"):
                bridge_module.LocalBackendBridge().run(request, lambda chunk: None)
        transcriber.assert_not_called()


if __name__ == "__main__":
    unittest.main()
