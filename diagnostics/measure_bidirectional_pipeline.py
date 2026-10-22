"""Mede STT simultâneo e custo de tradução/voz sem abrir dispositivos de áudio."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import av
import numpy as np

from backend.app.audio.speech_output import PiperSpeechSynthesizer
from backend.app.transcribers.local_faster_whisper import LocalFasterWhisperTranscriber
from backend.app.translators.argos_local import ArgosLocalTranslator


def decode_audio(path: Path) -> np.ndarray:
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
        chunks = []
        for frame in container.decode(stream):
            chunks.extend(
                np.asarray(part.to_ndarray(), dtype=np.float32).reshape(-1)
                for part in resampler.resample(frame)
            )
        chunks.extend(
            np.asarray(part.to_ndarray(), dtype=np.float32).reshape(-1)
            for part in resampler.resample(None)
        )
    if not chunks:
        raise ValueError(f"Arquivo sem áudio: {path}")
    return np.concatenate(chunks)


def chunks_of(audio: np.ndarray, seconds: float) -> list[np.ndarray]:
    size = int(16000 * seconds)
    return [
        audio[offset : offset + size]
        for offset in range(0, len(audio), size)
        if len(audio[offset : offset + size]) >= 16000 * 0.7
    ]


def measure(args) -> dict:
    gpu_memory_mib = []
    sampling_done = threading.Event()

    def sample_gpu_memory():
        while not sampling_done.is_set():
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2, check=True,
                )
                gpu_memory_mib.append(int(result.stdout.strip().splitlines()[0]))
            except (OSError, ValueError, subprocess.SubprocessError, IndexError):
                return
            sampling_done.wait(0.25)

    sampler = threading.Thread(target=sample_gpu_memory, daemon=True)
    sampler.start()
    sources = {
        "usuario": (decode_audio(args.portuguese), "pt-br", "en"),
        "reuniao": (decode_audio(args.english), "en", "pt-br"),
    }
    loaded_at = time.perf_counter()
    transcriber = LocalFasterWhisperTranscriber(model_size=args.model_size, device=args.device)
    load_s = time.perf_counter() - loaded_at
    lock = threading.Lock()
    measurements = []
    texts = {}
    start = time.perf_counter() + 0.1

    def run_source(name, audio, language, target):
        for index, chunk in enumerate(chunks_of(audio, args.utterance_s)):
            due = start + index * args.utterance_s
            time.sleep(max(0, due - time.perf_counter()))
            ready_at = time.perf_counter()
            with lock:
                locked_at = time.perf_counter()
                text = transcriber.transcribe(
                    chunk, "pt" if language == "pt-br" else language
                )
            done_at = time.perf_counter()
            measurements.append({
                "source": name,
                "index": index,
                "audio_s": round(len(chunk) / 16000, 3),
                "ready_delay_s": round(ready_at - due, 3),
                "shared_model_wait_s": round(locked_at - ready_at, 3),
                "stt_s": round(done_at - locked_at, 3),
                "delay_after_audio_s": round(done_at - due, 3),
                "text": text,
            })
            if text and name not in texts:
                texts[name] = (text, language, target)

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(run_source, name, *source)
            for name, source in sources.items()
        ]
        for future in futures:
            future.result()
    sampling_done.set()
    sampler.join(timeout=2)

    voice = PiperSpeechSynthesizer()
    translator = ArgosLocalTranslator()
    stages = {}
    for name, (text, language, target) in texts.items():
        try:
            began = time.perf_counter()
            translated = translator.translate(text, language, target)
            translation_s = time.perf_counter() - began
            began = time.perf_counter()
            synthesized, rate = voice.synthesize(translated, target)
            synthesis_s = time.perf_counter() - began
            stages[name] = {
                "translation_s": round(translation_s, 3),
                "synthesis_s": round(synthesis_s, 3),
                "voice_duration_s": round(len(synthesized) / rate, 3),
                "text": translated,
            }
        except Exception as exc:
            stages[name] = {"error": str(exc)}

    measurements.sort(key=lambda item: (item["index"], item["source"]))
    return {
        "model_size": args.model_size,
        "requested_device": args.device,
        "active_device": transcriber.device,
        "compute_type": transcriber.compute_type,
        "fallback_reason": str(transcriber.fallback_reason or ""),
        "load_s": round(load_s, 3),
        "gpu_memory_mib": {
            "first": gpu_memory_mib[0] if gpu_memory_mib else None,
            "peak": max(gpu_memory_mib) if gpu_memory_mib else None,
        },
        "utterance_s": args.utterance_s,
        "jobs": measurements,
        "later_stage_samples": stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portuguese", type=Path, required=True)
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--device", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--utterance-s", type=float, default=3.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(args)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
