from __future__ import annotations

import hashlib
import statistics
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from experiments.asr_baseline.audio import LoadedAudio
from experiments.asr_baseline.metrics import word_error_rate
from experiments.asr_baseline.system_info import collect_environment, process_rss_mb


class BaselineTranscriber(Protocol):
    device: str

    def transcribe(
        self,
        audio_16k: np.ndarray,
        language: str,
        context_prompt: str | None = None,
    ) -> str: ...


TranscriberFactory = Callable[[str, str], BaselineTranscriber]


def _round(value: float) -> float:
    return round(value, 6)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as audio_file:
        for block in iter(lambda: audio_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(project_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _synchronize_cuda(device: str) -> None:
    if device != "cuda":
        return
    import torch

    torch.cuda.synchronize()


def _reset_gpu_peak(device: str) -> None:
    if device != "cuda":
        return
    import torch

    torch.cuda.reset_peak_memory_stats()


def _gpu_peak_mb(device: str) -> float | None:
    if device != "cuda":
        return None
    import torch

    return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 3)


def run_baseline(
    *,
    audio_path: Path,
    audio: LoadedAudio,
    reference: str | None,
    reference_path: Path | None,
    language: str,
    model_size: str,
    requested_device: str,
    runs: int,
    transcriber_factory: TranscriberFactory,
    project_root: Path,
) -> dict[str, Any]:
    """Mede o adaptador atual sem conectá-lo ao fluxo da interface."""
    if runs < 1:
        raise ValueError("O numero de repeticoes deve ser pelo menos 1.")

    rss_before_load = process_rss_mb()
    load_started = time.perf_counter()
    transcriber = transcriber_factory(model_size, requested_device)
    model_load_seconds = time.perf_counter() - load_started
    rss_after_load = process_rss_mb()
    resolved_device = transcriber.device

    measured_runs: list[dict[str, Any]] = []
    for index in range(1, runs + 1):
        _reset_gpu_peak(resolved_device)
        _synchronize_cuda(resolved_device)
        rss_before = process_rss_mb()
        cpu_started = time.process_time()
        wall_started = time.perf_counter()
        transcript = transcriber.transcribe(audio.samples, language, None)
        _synchronize_cuda(resolved_device)
        elapsed_seconds = time.perf_counter() - wall_started
        cpu_seconds = time.process_time() - cpu_started
        rss_after = process_rss_mb()
        wer = word_error_rate(reference, transcript) if reference is not None else None

        measured_runs.append(
            {
                "index": index,
                "elapsed_seconds": _round(elapsed_seconds),
                "cpu_seconds": _round(cpu_seconds),
                "real_time_factor": _round(elapsed_seconds / audio.duration_seconds),
                "rss_before_mb": rss_before,
                "rss_after_mb": rss_after,
                "rss_delta_mb": (
                    round(rss_after - rss_before, 3)
                    if rss_before is not None and rss_after is not None
                    else None
                ),
                "gpu_peak_allocated_mb": _gpu_peak_mb(resolved_device),
                "transcript": transcript,
                "word_error_rate": _round(wer) if wer is not None else None,
            }
        )

    elapsed_values = [entry["elapsed_seconds"] for entry in measured_runs]
    rtf_values = [entry["real_time_factor"] for entry in measured_runs]
    wer_values = [
        entry["word_error_rate"]
        for entry in measured_runs
        if entry["word_error_rate"] is not None
    ]

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": _git_revision(project_root),
        "source": {
            "audio_path": str(audio_path),
            "audio_sha256": _file_sha256(audio_path),
            "reference_path": str(reference_path) if reference_path else None,
            "reference_text": reference,
            "duration_seconds": _round(audio.duration_seconds),
            "original_sample_rate": audio.original_sample_rate,
            "target_sample_rate": audio.target_sample_rate,
        },
        "configuration": {
            "engine": "faster-whisper",
            "adapter": "backend.app.transcribers.local_faster_whisper.LocalFasterWhisperTranscriber",
            "model_size": model_size,
            "requested_device": requested_device,
            "resolved_device": resolved_device,
            "language": language,
            "runs": runs,
        },
        "environment": collect_environment(),
        "model_load": {
            "seconds": _round(model_load_seconds),
            "rss_before_mb": rss_before_load,
            "rss_after_mb": rss_after_load,
            "rss_delta_mb": (
                round(rss_after_load - rss_before_load, 3)
                if rss_before_load is not None and rss_after_load is not None
                else None
            ),
        },
        "runs": measured_runs,
        "summary": {
            "elapsed_seconds_median": _round(statistics.median(elapsed_values)),
            "elapsed_seconds_min": _round(min(elapsed_values)),
            "elapsed_seconds_max": _round(max(elapsed_values)),
            "real_time_factor_median": _round(statistics.median(rtf_values)),
            "word_error_rate_median": (
                _round(statistics.median(wer_values)) if wer_values else None
            ),
        },
    }
