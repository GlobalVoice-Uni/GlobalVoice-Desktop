"""Reproduz áudios em tempo real pelos endpoints do Windows e mede a sessão real."""

from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from backend.app.audio.devices import AudioDeviceKind, enumerate_audio_devices
from backend.app.audio.audio_capture import WasapiLoopbackAudioSource
from backend.app.audio.virtual_cable import find_vb_cable
from backend.app.sessions.realtime_session import RealtimeTranscriptionSession
from diagnostics.measure_bidirectional_pipeline import decode_audio
from frontend.src.transcription_window import backend_bridge as bridge_module
from frontend.src.transcription_window.backend_bridge import LocalBackendBridge, SessionRequest


class TimedSilentSink:
    """Preserva o tempo de reprodução sem misturar TTS nos áudios de teste."""

    def __init__(self, _device_id, *, virtual_microphone=False):
        self.virtual_microphone = virtual_microphone
        self.playbacks = []

    def play(self, audio, sample_rate, stop_event):
        duration = len(audio) / sample_rate
        began = time.monotonic()
        stop_event.wait(duration)
        self.playbacks.append({
            "began_s": began,
            "duration_s": round(duration, 3),
            "virtual_microphone": self.virtual_microphone,
        })


def play_file(path: Path, device_id: str, gain: float, start_gate: threading.Event):
    audio = decode_audio(path)
    device = sd.query_devices(int(device_id), kind="output")
    sample_rate = int(device["default_samplerate"])
    divisor = np.gcd(sample_rate, 16000)
    samples = resample_poly(audio, sample_rate // divisor, 16000 // divisor)
    samples = np.clip(samples * gain, -0.9, 0.9).astype(np.float32)
    channels = min(2, int(device["max_output_channels"]))
    if channels < 1:
        raise ValueError(f"Saída sem canais: {device_id}")
    if not start_gate.wait(timeout=30):
        raise TimeoutError("A captura não ficou pronta para a reprodução.")
    block = max(1, sample_rate // 10)
    with sd.OutputStream(
        samplerate=sample_rate, channels=channels, dtype="float32",
        device=int(device_id), latency="low",
    ) as stream:
        for offset in range(0, len(samples), block):
            mono = samples[offset:offset + block].reshape(-1, 1)
            stream.write(np.repeat(mono, channels, axis=1))


def measure(args):
    catalog = enumerate_audio_devices()
    cable = find_vb_cable(catalog)
    default_loopback = next(
        (item for item in catalog.of_kind(AudioDeviceKind.LOOPBACK) if item.is_default), None
    )
    if default_loopback is None:
        raise RuntimeError("Nenhuma saída padrão com loopback foi encontrada.")
    meeting_output = next(
        (item for item in catalog.of_kind(AudioDeviceKind.OUTPUT)
         if item.name.casefold() == default_loopback.name.casefold()
         and item.backend == "Windows WASAPI"), None
    )
    if meeting_output is None:
        raise RuntimeError("Não foi possível reproduzir na saída padrão capturada.")
    if args.both and cable is None:
        raise RuntimeError("O teste de duas fontes exige VB-CABLE já instalado.")
    cable_loopback = next(
        (item for item in catalog.of_kind(AudioDeviceKind.LOOPBACK)
         if item.name.casefold() == cable.render.name.casefold()), None
    ) if cable else None
    if args.microphone_via_loopback and cable_loopback is None:
        raise RuntimeError("O loopback do VB-CABLE não foi encontrado.")

    statuses = []
    chunks = []
    playback_sinks = []
    timings = []
    capture_ready = threading.Event()
    capture_count = 0
    session_result = {}
    began = time.monotonic()

    def sink_factory(device_id, **kwargs):
        sink = TimedSilentSink(device_id, **kwargs)
        playback_sinks.append(sink)
        return sink

    class TimedSession(RealtimeTranscriptionSession):
        def _record_transcription_timing(self, timing):
            super()._record_transcription_timing(timing)
            timings.append({
                "at_s": round(time.monotonic() - began, 3),
                "source": self.audio_source.display_name,
                "audio_s": round(timing.audio_duration_s, 3),
                "queue_wait_s": round(timing.queue_wait_s, 3),
                "stt_s": round(timing.processing_s, 3),
            })

    bridge_module.RealtimeTranscriptionSession = TimedSession
    if args.microphone_via_loopback:
        def cable_as_microphone(*, step_duration_s, target_sample_rate, **_kwargs):
            return WasapiLoopbackAudioSource(
                output_device=cable_loopback.id,
                step_duration_s=step_duration_s,
                target_sample_rate=target_sample_rate,
            )

        bridge_module.MicrophoneAudioSource = cable_as_microphone
    bridge = LocalBackendBridge(sink_factory=sink_factory)
    request = SessionRequest(
        model_size="small", device="gpu",
        audio_source="both" if args.both else "loopback",
        language="en", target_language="pt-br",
        user_language="pt-br", meeting_language="en",
        audio_device_id=cable.capture.id if args.both else None,
        meeting_device_id=default_loopback.id,
        voice_output_enabled=args.both and args.voices,
        voice_output_device_id=cable.render.id if args.both else None,
        meeting_voice_enabled=args.voices,
        meeting_voice_device_id=cable.render.id if cable else meeting_output.id,
        max_duration_s=args.duration_s + 6,
    )

    def on_status(message):
        nonlocal capture_count
        statuses.append({"at_s": round(time.monotonic() - began, 3), "message": message})
        if message.startswith("Captura ativa:"):
            capture_count += 1
            if capture_count >= (2 if args.both else 1):
                capture_ready.set()

    def on_text(chunk):
        chunks.append({
            "at_s": round(time.monotonic() - began, 3),
            "channel": chunk.channel,
            "original_characters": len(chunk.original_text),
            "translated_characters": len(chunk.translated_text),
        })

    def run_bridge():
        try:
            bridge.run(
                request, on_text, on_status=on_status,
                on_runtime_status=lambda status: session_result.update({
                    "device": status.active_device.value,
                    "compute_type": status.compute_type,
                    "fallback": str(status.fallback_reason or ""),
                }),
            )
        except Exception as exc:
            session_result["error"] = traceback.format_exc()
            capture_ready.set()

    worker = threading.Thread(target=run_bridge, daemon=True)
    worker.start()
    if not capture_ready.wait(timeout=30):
        bridge.stop()
        raise TimeoutError("A sessão não iniciou a captura em 30 s.")
    if "error" in session_result:
        raise RuntimeError(session_result["error"])

    sources = [(args.english, meeting_output.id)]
    if args.both:
        sources.append((args.portuguese, cable.render.id))
    play_gate = threading.Event()
    errors = []

    def play_and_catch(path, device_id):
        try:
            play_file(path, device_id, args.gain, play_gate)
        except Exception as exc:
            errors.append(repr(exc))

    players = [threading.Thread(target=play_and_catch, args=item, daemon=True)
               for item in sources]
    for player in players:
        player.start()
    play_gate.set()
    for player in players:
        player.join(timeout=args.duration_s + 10)
    if errors:
        bridge.stop()
        raise RuntimeError("; ".join(errors))
    worker.join(timeout=12)
    if worker.is_alive():
        bridge.stop()
        worker.join(timeout=5)

    return {
        "mode": "both" if args.both else "meeting",
        "source_duration_s": args.duration_s,
        "elapsed_s": round(time.monotonic() - began, 3),
        "meeting_output": meeting_output.name,
        "microphone_input": cable.capture.name if args.both else None,
        "microphone_via_loopback": args.microphone_via_loopback,
        "runtime": session_result,
        "chunks": chunks,
        "playbacks": [item for sink in playback_sinks for item in sink.playbacks],
        "timings": timings,
        "statuses": statuses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--portuguese", type=Path)
    parser.add_argument("--both", action="store_true")
    parser.add_argument("--microphone-via-loopback", action="store_true")
    parser.add_argument("--voices", action="store_true")
    parser.add_argument("--duration-s", type=float, default=30)
    parser.add_argument("--gain", type=float, default=0.15)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.both and not args.portuguese:
        parser.error("--both exige --portuguese")
    if args.microphone_via_loopback and not args.both:
        parser.error("--microphone-via-loopback exige --both")
    report = measure(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "mode": report["mode"], "elapsed_s": report["elapsed_s"],
        "runtime": report["runtime"], "chunks": len(report["chunks"]),
        "playbacks": len(report["playbacks"]),
        "delay_notices": [item for item in report["statuses"]
                          if "Atraso" in item["message"] or "atras" in item["message"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
