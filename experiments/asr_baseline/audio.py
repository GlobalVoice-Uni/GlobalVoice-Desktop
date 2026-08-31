from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly


TARGET_SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class LoadedAudio:
    samples: np.ndarray
    original_sample_rate: int
    target_sample_rate: int
    duration_seconds: float


def _to_float32(samples: np.ndarray) -> np.ndarray:
    """Normaliza amostras PCM ou float para o intervalo esperado pelo Whisper."""
    if np.issubdtype(samples.dtype, np.floating):
        normalized = samples.astype(np.float32)
    elif samples.dtype == np.uint8:
        normalized = (samples.astype(np.float32) - 128.0) / 128.0
    elif np.issubdtype(samples.dtype, np.signedinteger):
        limits = np.iinfo(samples.dtype)
        scale = float(max(abs(limits.min), limits.max))
        normalized = samples.astype(np.float32) / scale
    else:
        raise ValueError(f"Formato PCM nao suportado: {samples.dtype}")

    return np.clip(normalized, -1.0, 1.0)


def load_wav(path: str | Path, target_sample_rate: int = TARGET_SAMPLE_RATE) -> LoadedAudio:
    """Carrega WAV, converte para mono e reamostra para 16 kHz."""
    audio_path = Path(path).expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Arquivo de audio nao encontrado: {audio_path}")
    if target_sample_rate <= 0:
        raise ValueError("A taxa de amostragem de destino deve ser positiva.")

    original_sample_rate, raw_samples = wavfile.read(audio_path)
    if original_sample_rate <= 0 or raw_samples.size == 0:
        raise ValueError("O arquivo WAV esta vazio ou possui taxa de amostragem invalida.")
    if raw_samples.ndim not in (1, 2):
        raise ValueError("O WAV deve ser mono ou multicanal.")

    samples = _to_float32(raw_samples)
    if samples.ndim == 2:
        samples = samples.mean(axis=1, dtype=np.float32)

    duration_seconds = len(samples) / float(original_sample_rate)
    if original_sample_rate != target_sample_rate:
        divisor = gcd(original_sample_rate, target_sample_rate)
        samples = resample_poly(
            samples,
            target_sample_rate // divisor,
            original_sample_rate // divisor,
        ).astype(np.float32)

    return LoadedAudio(
        samples=np.ascontiguousarray(samples, dtype=np.float32),
        original_sample_rate=original_sample_rate,
        target_sample_rate=target_sample_rate,
        duration_seconds=duration_seconds,
    )

