"""Gera amostras locais de vozes por idioma para comparação auditiva."""

from __future__ import annotations

import json
import time
import wave
from pathlib import Path

import numpy as np
from piper.voice import PiperVoice


ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / ".build/tts-voices"
CANDIDATES = ROOT / ".build/tts-candidates"
OUTPUT = ROOT / ".build/voice-previews"
SAMPLES = {
    "pt-br": (
        "A tradução da reunião está funcionando bem, mas precisamos reduzir o atraso da voz.",
        (("faber", CURRENT / "pt_BR-faber-medium.onnx"),
         ("cadu", CANDIDATES / "pt_BR-cadu-medium.onnx"),
         ("jeff", CANDIDATES / "pt_BR-jeff-medium.onnx"),
         ("dii", CANDIDATES / "pt_BR-dii-high.onnx")),
    ),
    "en": (
        "The meeting translation is working well, but we still need to reduce the delay.",
        (("ljspeech", CURRENT / "en_US-ljspeech-medium.onnx"),
         ("lessac", CURRENT / "en_US-lessac-medium.onnx"),
         ("joe", CANDIDATES / "en_US-joe-medium.onnx")),
    ),
    "es": (
        "La traducción de la reunión funciona bien, pero todavía tenemos que reducir el retraso.",
        (("sharvard", CURRENT / "es_ES-sharvard-medium.onnx"),
         ("davefx", CANDIDATES / "es_ES-davefx-medium.onnx")),
    ),
}


def synthesize(voice: PiperVoice, text: str) -> tuple[np.ndarray, int]:
    chunks = list(voice.synthesize(text))
    return np.concatenate([chunk.audio_float_array for chunk in chunks]), chunks[0].sample_rate


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    for language, (text, voices) in SAMPLES.items():
        for label, model in voices:
            if not model.is_file() or not Path(f"{model}.json").is_file():
                raise FileNotFoundError(model)
            began = time.perf_counter()
            voice = PiperVoice.load(model)
            load_s = time.perf_counter() - began
            began = time.perf_counter()
            samples, sample_rate = synthesize(voice, text)
            first_s = time.perf_counter() - began
            began = time.perf_counter()
            synthesize(voice, text)
            warm_s = time.perf_counter() - began
            output = OUTPUT / f"{language}-{label}.wav"
            pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
            with wave.open(str(output), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm.tobytes())
            results.append({
                "language": language,
                "voice": label,
                "model_mib": round(model.stat().st_size / 1024**2, 2),
                "load_s": round(load_s, 3),
                "first_s": round(first_s, 3),
                "warm_s": round(warm_s, 3),
                "audio_s": round(len(samples) / sample_rate, 3),
                "preview": str(output),
            })
    (OUTPUT / "measurements.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
