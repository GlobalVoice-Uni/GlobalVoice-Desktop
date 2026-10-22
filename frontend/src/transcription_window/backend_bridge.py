from dataclasses import dataclass
import threading
import time
from typing import Callable, Optional, Protocol

from backend.app.audio.audio_capture import MicrophoneAudioSource, create_audio_source
from backend.app.audio.devices import AudioDeviceCatalog, AudioDeviceKind, enumerate_audio_devices, select_device
from backend.app.audio.microphone_relay import MicrophoneRelay
from backend.app.audio.speech_output import PiperSpeechSynthesizer, SoundDeviceAudioSink, SpeechOutputQueue
from backend.app.audio.virtual_cable import (
    find_vb_cable, is_vb_cable_render_device, vb_cable_status,
)
from backend.app.sessions.realtime_session import RealtimeTranscriptionSession
from backend.app.detectors.speech_detectors import build_speech_detector
from backend.app.runtime_status import RuntimeStatus
from backend.app.transcript import TranscriptChunk
from backend.app.transcribers.local_faster_whisper import LocalFasterWhisperTranscriber
from backend.app.translators.argos_local import ArgosLocalTranslator


@dataclass
class SessionRequest:
    """Parametros de execucao da sessao realtime.

    Este objeto e o formato unico de entrada entre UI e camada de execucao.
    """

    model_size: str = "small"
    device: str = "gpu"
    language: str = "pt-br"
    target_language: str = "pt-br"
    display_mode: str = "translation_only"
    capture_mode: str = "automatic"
    audio_source: str = "microphone"
    audio_device_id: Optional[str] = None
    user_language: Optional[str] = None
    meeting_language: Optional[str] = None
    meeting_device_id: Optional[str] = None
    voice_output_enabled: bool = False
    voice_output_device_id: Optional[str] = None
    meeting_voice_enabled: bool = False
    meeting_voice_device_id: Optional[str] = None
    english_voice: str = "en-ljspeech"
    context_window: int = 0
    max_duration_s: Optional[float] = None

    # Config de detector de fala.
    vad_type: str = "silero"
    speech_peak_threshold: float = 0.0018
    silero_threshold: float = 0.5
    silero_min_silence_ms: int = 120
    silero_speech_pad_ms: int = 30

    # Janelas e limites de segmentacao.
    min_speech_window_s: float = 0.2
    min_silence_window_s: float = 0.55
    new_speech_silence_s: float = 2.0
    max_utterance_s: float = 3.2
    min_utterance_s: float = 0.7

    # Regras de fronteira para cortes forcados.
    boundary_overlap_s: float = 0.45
    tail_guard_words: int = 4
    forced_split_policy: str = "protect_boundary"
    forced_split_extra_tail_words: int = 1


class TranscriptionBridge(Protocol):
    """Contrato da ponte entre frontend e backend.

    Hoje a ponte e local. Futuramente pode ser remota mantendo a mesma API.
    """

    def run(
        self,
        request: SessionRequest,
        on_text: Callable[[object], None],
        on_status: Optional[Callable[[str], None]] = None,
        on_runtime_status: Optional[Callable[[RuntimeStatus], None]] = None,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_voice_activity: Optional[Callable[[bool], None]] = None,
    ) -> str:
        """Starts a realtime session and returns the final transcript when done."""

    def stop(self) -> None:
        """Requests stop for the running session."""

    def set_talk_active(self, active: bool) -> None:
        """Controls microphone capture while push-to-talk is selected."""

    def set_microphone_muted(self, muted: bool) -> None:
        """Mutes microphone processing while automatic capture is selected."""

    def set_meeting_audio_muted(self, muted: bool) -> None:
        """Mutes only the local translated meeting voice."""


class LoopbackPlaybackGate:
    """Pausa a captura do retorno enquanto o TTS toca no mesmo endpoint."""

    def __init__(self, tail_s: float = 0.35) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._blocked_until = 0.0
        self._tail_s = tail_s

    def set_active(self, active: bool) -> None:
        with self._lock:
            self._active = active
            if not active:
                self._blocked_until = time.monotonic() + self._tail_s

    def is_suppressed(self) -> bool:
        with self._lock:
            return self._active or time.monotonic() < self._blocked_until


class LocalBackendBridge:
    """Implementacao atual: roda captura+ASR no mesmo processo da aplicacao."""

    def __init__(
        self,
        translator_factory=ArgosLocalTranslator,
        synthesizer_factory=PiperSpeechSynthesizer,
        sink_factory=SoundDeviceAudioSink,
    ):
        self._session: Optional[RealtimeTranscriptionSession] = None
        self._sessions: dict[str, RealtimeTranscriptionSession] = {}
        self._outputs: list[SpeechOutputQueue] = []
        self._meeting_output: SpeechOutputQueue | None = None
        self._meeting_audio_muted = False
        self._talk_active = False
        self._microphone_muted = False
        self._translator_factory = translator_factory
        self._synthesizer_factory = synthesizer_factory
        self._sink_factory = sink_factory

    def run(
        self,
        request: SessionRequest,
        on_text: Callable[[object], None],
        on_status: Optional[Callable[[str], None]] = None,
        on_runtime_status: Optional[Callable[[RuntimeStatus], None]] = None,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_voice_activity: Optional[Callable[[bool], None]] = None,
    ) -> str:
        """Monta dependencias locais e executa sessao realtime."""
        if request.audio_source not in {"microphone", "loopback", "both"}:
            raise ValueError(f"Fonte de áudio inválida: {request.audio_source}")
        catalog = enumerate_audio_devices()
        cable_state = vb_cable_status(catalog)
        cable = find_vb_cable(catalog) if cable_state == "available" else None
        voice_output_device_id = request.voice_output_device_id
        if request.voice_output_enabled and cable_state == "restart_required":
            raise ValueError(
                "O VB-CABLE foi instalado, mas precisa de uma reinicialização do Windows "
                "antes de enviar voz à chamada."
            )
        if request.voice_output_enabled and not voice_output_device_id:
            if cable is None:
                raise ValueError(
                    "Instale o VB-CABLE e reinicie o Windows antes de enviar voz traduzida à chamada."
                )
            voice_output_device_id = cable.render.id

        def same_endpoint(output_id: Optional[str], captured_id: Optional[str]) -> bool:
            if output_id and output_id == captured_id:
                return True
            output = (
                next((item for item in catalog.of_kind(AudioDeviceKind.OUTPUT) if item.id == output_id), None)
                if output_id else select_device(catalog, AudioDeviceKind.OUTPUT, None)
            )
            loopback = (
                next((item for item in catalog.of_kind(AudioDeviceKind.LOOPBACK) if item.id == captured_id), None)
                if captured_id else select_device(catalog, AudioDeviceKind.LOOPBACK, None)
            )
            return bool(output and loopback and output.name.casefold() == loopback.name.casefold())

        if request.audio_source in {"both", "loopback"}:
            meeting_capture_id = (
                request.meeting_device_id if request.audio_source == "both"
                else request.audio_device_id
            )
            meeting_loopback = select_device(
                catalog, AudioDeviceKind.LOOPBACK, meeting_capture_id
            )
            if is_vb_cable_render_device(meeting_loopback):
                raise ValueError(
                    "A reunião está sendo capturada de CABLE Input, que é a saída do "
                    "microfone virtual. Defina seu headset ou alto-falante como saída "
                    "padrão do Windows para ouvir e capturar a reunião. Em Configurações "
                    "> Voz, 'Saída de Áudio' controla somente onde você ouve a tradução."
                )
        if request.audio_source == "both":
            if request.voice_output_enabled and same_endpoint(voice_output_device_id, request.meeting_device_id):
                raise ValueError("A voz enviada à chamada está usando a mesma saída da captura da reunião. Confira a saída padrão do Windows.")
            if cable is not None and same_endpoint(cable.render.id, request.meeting_device_id):
                raise ValueError("CABLE Input não pode ser a saída padrão capturada para a reunião.")
        meeting_capture_id = (
            request.meeting_device_id if request.audio_source == "both"
            else request.audio_device_id
        )
        playback_gate = (
            LoopbackPlaybackGate()
            if request.audio_source in {"loopback", "both"}
            and request.meeting_voice_enabled
            and same_endpoint(request.meeting_voice_device_id, meeting_capture_id)
            else None
        )
        transcriber = LocalFasterWhisperTranscriber(model_size=request.model_size, device=request.device)
        runtime_status = transcriber.runtime_status
        if on_runtime_status:
            on_runtime_status(runtime_status)
        if on_status:
            on_status(runtime_status.user_message)
        self._sessions = {}
        self._outputs = []
        self._meeting_output = None
        transcriber_lock = threading.Lock()

        def make_session(kind: str, language: str, target: str, device_id: Optional[str]):
            if kind == "loopback":
                source = create_audio_source(
                    source="loopback", device_id=device_id,
                    step_duration_s=0.2, target_sample_rate=16000,
                    suppress_capture=(playback_gate.is_suppressed if playback_gate else None),
                )
            else:
                options = {"step_duration_s": 0.2, "target_sample_rate": 16000}
                if device_id not in (None, ""):
                    options["input_device"] = device_id
                if (
                    cable is not None
                    and not request.voice_output_enabled
                    and device_id != cable.capture.id
                ):
                    options["passthrough"] = MicrophoneRelay(
                        cable.render.id,
                        enabled=lambda: (
                            not self._microphone_muted
                            and (request.capture_mode != "push_to_talk" or self._talk_active)
                        ),
                    )
                source = MicrophoneAudioSource(**options)
            detector, _ = build_speech_detector(
                vad_type=request.vad_type,
                energy_peak_threshold=request.speech_peak_threshold,
                silero_threshold=request.silero_threshold,
                silero_min_silence_ms=request.silero_min_silence_ms,
                silero_speech_pad_ms=request.silero_speech_pad_ms,
                on_status=on_status,
            )
            translate = (
                language != target
                and (kind == "loopback" or request.voice_output_enabled or request.audio_source == "both")
                and (request.display_mode in {"translation_only", "both"}
                     or (kind == "microphone" and request.voice_output_enabled)
                     or (kind == "loopback" and request.meeting_voice_enabled))
            )
            translator = None
            if translate:
                if on_status:
                    on_status("Carregando tradução local...")
                translator = self._translator_factory()
                translator.ensure_available(language, target)

            output = None
            output_enabled = request.meeting_voice_enabled if kind == "loopback" else request.voice_output_enabled
            output_device = request.meeting_voice_device_id if kind == "loopback" else voice_output_device_id
            if output_enabled:
                sink = (
                    self._sink_factory(output_device)
                    if kind == "loopback"
                    else self._sink_factory(output_device, virtual_microphone=True)
                )
                output = SpeechOutputQueue(
                    self._synthesizer_factory(), sink, target,
                    voice_id=request.english_voice if target == "en" else None,
                    on_error=on_status,
                    on_notice=on_status,
                    on_playback_state=(
                        playback_gate.set_active if kind == "loopback" and playback_gate else None
                    ),
                )
                output.start()
                self._outputs.append(output)
                if kind == "loopback":
                    self._meeting_output = output
                    output.set_muted(self._meeting_audio_muted)

            def publish_chunk(text: str) -> None:
                translated = translator.translate(text, language, target) if translator else ""
                on_text(TranscriptChunk(
                    channel="meeting" if kind == "loopback" else "user",
                    original_text=text, translated_text=translated,
                    display_mode=request.display_mode,
                ))
                if output and translated:
                    output.enqueue(translated)

            session_transcriber = transcriber
            if request.audio_source == "both":
                class LockedTranscriber:
                    def transcribe(self, *args, **kwargs):
                        with transcriber_lock:
                            return transcriber.transcribe(*args, **kwargs)
                session_transcriber = LockedTranscriber()
            session = RealtimeTranscriptionSession(
                audio_source=source,
                transcriber=session_transcriber,
                speech_detector=detector,
                language=language,
                capture_mode=request.capture_mode if kind == "microphone" else "automatic",
                context_window=request.context_window,
                speech_peak_threshold=request.speech_peak_threshold,
                min_speech_window_s=request.min_speech_window_s,
                min_silence_window_s=request.min_silence_window_s,
                new_speech_silence_s=request.new_speech_silence_s,
                max_utterance_s=request.max_utterance_s,
                min_utterance_s=request.min_utterance_s,
                boundary_overlap_s=request.boundary_overlap_s,
                tail_guard_words=request.tail_guard_words,
                forced_split_policy=request.forced_split_policy,
                forced_split_extra_tail_words=request.forced_split_extra_tail_words,
            )
            if kind == "microphone":
                session.set_talk_active(self._talk_active)
                session.set_microphone_muted(self._microphone_muted)
            elif request.audio_source != "both":
                session.set_talk_active(self._talk_active)
                session.set_microphone_muted(self._microphone_muted)
            self._sessions[kind] = session
            return session, publish_chunk

        try:
            if request.audio_source == "both":
                user_lang = request.user_language or request.language
                meeting_lang = request.meeting_language or request.target_language
                mic, mic_callback = make_session("microphone", user_lang, meeting_lang, request.audio_device_id)
                meeting, meeting_callback = make_session("loopback", meeting_lang, user_lang, request.meeting_device_id)
                self._session = mic
                meeting_result = {"error": None}

                def run_meeting() -> None:
                    try:
                        meeting.run(
                            on_text=meeting_callback, on_status=on_status,
                            on_speech_start=on_speech_start,
                            on_voice_activity=None, max_duration_s=request.max_duration_s,
                        )
                    except Exception as exc:
                        meeting_result["error"] = exc
                    finally:
                        mic.stop()

                meeting_thread = threading.Thread(target=run_meeting, daemon=True)
                meeting_thread.start()
                try:
                    result = mic.run(
                        on_text=mic_callback, on_status=on_status,
                        on_speech_start=on_speech_start,
                        on_voice_activity=on_voice_activity,
                        max_duration_s=request.max_duration_s,
                    )
                finally:
                    meeting.stop()
                    meeting_thread.join(timeout=5)
                if meeting_result["error"] is not None:
                    raise meeting_result["error"]
                return result

            kind = request.audio_source
            session, callback = make_session(kind, request.language, request.target_language, request.audio_device_id)
            self._session = session
            return session.run(
                on_text=callback, on_status=on_status,
                on_speech_start=on_speech_start,
                on_voice_activity=on_voice_activity,
                max_duration_s=request.max_duration_s,
            )
        finally:
            for output in self._outputs:
                output.stop()
            self._outputs = []
            self._sessions = {}
            self._session = None

    def stop(self) -> None:
        """Encaminha pedido de parada para a sessao ativa."""
        for session in tuple(self._sessions.values()):
            session.stop()
        if not self._sessions and self._session is not None:
            self._session.stop()
        for output in self._outputs:
            output.stop()

    def set_talk_active(self, active: bool) -> None:
        self._talk_active = bool(active)
        session = self._sessions.get("microphone", self._session)
        if session is not None:
            session.set_talk_active(self._talk_active)

    def set_microphone_muted(self, muted: bool) -> None:
        self._microphone_muted = bool(muted)
        session = self._sessions.get("microphone", self._session)
        if session is not None:
            session.set_microphone_muted(self._microphone_muted)

    def set_meeting_audio_muted(self, muted: bool) -> None:
        self._meeting_audio_muted = bool(muted)
        if self._meeting_output is not None:
            self._meeting_output.set_muted(self._meeting_audio_muted)


def get_audio_device_catalog() -> AudioDeviceCatalog:
    """Disponibiliza a enumeracao sem acoplar a UI aos backends de audio."""

    return enumerate_audio_devices()
