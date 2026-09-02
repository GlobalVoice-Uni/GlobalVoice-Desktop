"""Compara o Silero atual (PyTorch) com o candidato ONNX em streaming."""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.asr_baseline.audio import load_wav
from backend.app.detectors.silero_onnx import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    SileroOnnxStreamingModel,
)


def _default_signal() -> np.ndarray:
    """Sinal deterministico apenas para uma verificacao tecnica inicial."""
    rng = np.random.default_rng(20260901)
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    timeline = np.arange(SAMPLE_RATE * 2, dtype=np.float32) / SAMPLE_RATE
    tone = (0.12 * np.sin(2 * np.pi * 180 * timeline)).astype(np.float32)
    noise = rng.normal(0, 0.025, SAMPLE_RATE).astype(np.float32)
    return np.concatenate((silence, tone, silence[: SAMPLE_RATE // 2], noise, silence))


def _frames(audio: np.ndarray) -> list[np.ndarray]:
    remainder = len(audio) % FRAME_SAMPLES
    if remainder:
        audio = np.pad(audio, (0, FRAME_SAMPLES - remainder), mode="constant")
    return [audio[start : start + FRAME_SAMPLES] for start in range(0, len(audio), FRAME_SAMPLES)]


class _RecordingModel:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.probabilities: list[float] = []

    def reset_states(self) -> None:
        self.model.reset_states()

    def __call__(self, frame: Any, sample_rate: int) -> Any:
        result = self.model(frame, sample_rate)
        self.probabilities.append(float(result.item()))
        return result


def _run_current(
    frames: list[np.ndarray],
    threshold: float,
    min_silence_ms: int,
    speech_pad_ms: int,
) -> tuple[list[float], list[bool], list[dict[str, int]], float]:
    started_at = time.perf_counter()
    from silero_vad import VADIterator, load_silero_vad

    recording_model = _RecordingModel(load_silero_vad(onnx=False))
    iterator = VADIterator(
        recording_model,
        threshold=threshold,
        sampling_rate=SAMPLE_RATE,
        min_silence_duration_ms=min_silence_ms,
        speech_pad_ms=speech_pad_ms,
    )
    load_seconds = time.perf_counter() - started_at

    active = False
    active_by_frame: list[bool] = []
    events: list[dict[str, int]] = []
    started_at = time.perf_counter()
    for index, frame in enumerate(frames):
        event = iterator(frame, return_seconds=False)
        if event:
            normalized = {key: int(value) for key, value in event.items()}
            normalized["frame"] = index
            events.append(normalized)
            active = "start" in event or (active and "end" not in event)
        active_by_frame.append(active)
    inference_seconds = time.perf_counter() - started_at
    return recording_model.probabilities, active_by_frame, events, load_seconds + inference_seconds


def _run_candidate(
    frames: list[np.ndarray],
    threshold: float,
    min_silence_ms: int,
    speech_pad_ms: int,
    model_path: Path | None,
) -> tuple[list[float], list[bool], list[dict[str, int]], float]:
    started_at = time.perf_counter()
    detector = SileroOnnxStreamingModel(
        threshold=threshold,
        min_silence_duration_ms=min_silence_ms,
        speech_pad_ms=speech_pad_ms,
        model_path=model_path,
    )
    load_seconds = time.perf_counter() - started_at

    probabilities: list[float] = []
    active_by_frame: list[bool] = []
    events: list[dict[str, int]] = []
    started_at = time.perf_counter()
    for index, frame in enumerate(frames):
        result = detector.process(frame)
        probabilities.append(result.probability)
        active_by_frame.append(result.active)
        if result.event:
            event = dict(result.event)
            event["frame"] = index
            events.append(event)
    inference_seconds = time.perf_counter() - started_at
    return probabilities, active_by_frame, events, load_seconds + inference_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, help="WAV real para a comparacao")
    parser.add_argument("--output", type=Path, help="Destino opcional do resultado JSON")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--min-silence-ms", type=int, default=120)
    parser.add_argument("--speech-pad-ms", type=int, default=30)
    parser.add_argument(
        "--candidate-model",
        choices=("faster-whisper", "silero-6.2", "silero-6.2-op15"),
        default="silero-6.2-op15",
        help="Arquivo ONNX usado pelo candidato sem PyTorch",
    )
    args = parser.parse_args()

    if args.audio:
        loaded = load_wav(args.audio)
        audio = loaded.samples
        source = str(args.audio.resolve())
    else:
        audio = _default_signal()
        source = "sinal sintetico deterministico"

    frames = _frames(audio)
    candidate_model_path = None
    if args.candidate_model.startswith("silero-6.2"):
        package_spec = importlib.util.find_spec("silero_vad")
        if not package_spec or not package_spec.origin:
            raise RuntimeError("Pacote silero-vad 6.2 nao encontrado para a comparacao")
        model_name = (
            "silero_vad_16k_op15.onnx"
            if args.candidate_model == "silero-6.2-op15"
            else "silero_vad.onnx"
        )
        candidate_model_path = Path(package_spec.origin).parent / "data" / model_name
    current_probs, current_active, current_events, current_seconds = _run_current(
        frames,
        args.threshold,
        args.min_silence_ms,
        args.speech_pad_ms,
    )
    candidate_probs, candidate_active, candidate_events, candidate_seconds = _run_candidate(
        frames,
        args.threshold,
        args.min_silence_ms,
        args.speech_pad_ms,
        candidate_model_path,
    )

    differences = np.abs(np.asarray(current_probs) - np.asarray(candidate_probs))
    active_mismatches = sum(
        current != candidate
        for current, candidate in zip(current_active, candidate_active)
    )
    result = {
        "source": source,
        "candidate_model": args.candidate_model,
        "duration_seconds": len(audio) / SAMPLE_RATE,
        "frames": len(frames),
        "probability_difference": {
            "maximum": float(differences.max(initial=0.0)),
            "mean": float(differences.mean() if differences.size else 0.0),
        },
        "active_state_mismatches": active_mismatches,
        "current_events": current_events,
        "candidate_events": candidate_events,
        "events_equal": current_events == candidate_events,
        "elapsed_seconds": {
            "current_total": current_seconds,
            "candidate_total": candidate_seconds,
        },
    }

    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    return 0 if active_mismatches == 0 and current_events == candidate_events else 1


if __name__ == "__main__":
    raise SystemExit(main())
