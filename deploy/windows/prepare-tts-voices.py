"""Baixa e confere as vozes Piper usadas na build de teste."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / ".build/tts-voices"
VOICES = {
    "pt_BR-cadu-medium": (
        "pt/pt_BR/cadu/medium",
        "765f0809a6ea9035d4a6d0d008dbf8876e68b2dd32029312672fa8f405bdb535",
    ),
    "en_US-ljspeech-medium": (
        "en/en_US/ljspeech/medium",
        "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
    ),
    "en_US-joe-medium": (
        "en/en_US/joe/medium",
        "58afce0321b8d9c46d7cdf9c16500cc55a793b4220212dba6b70fb788b3baf06",
    ),
    "es_ES-davefx-medium": (
        "es/es_ES/davefx/medium",
        "6658b03b1a6c316ee4c265a9896abc1393353c2d9e1bca7d66c2c442e222a917",
    ),
}


def verify() -> None:
    for name, (_, expected) in VOICES.items():
        model = DESTINATION / f"{name}.onnx"
        config = DESTINATION / f"{name}.onnx.json"
        card = DESTINATION / f"{name}.MODEL_CARD"
        if not all(path.is_file() for path in (model, config, card)):
            raise RuntimeError(f"Voz incompleta: {name}. Execute prepare-tts-voices.py.")
        with model.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"SHA-256 diferente para {name}: {actual}")
        print(f"VOICE_OK={name};SHA256={actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args()
    if not options.verify_only:
        DESTINATION.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", "--data-dir", str(DESTINATION), *VOICES],
            check=True,
        )
        for name, (folder, _) in VOICES.items():
            url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{folder}/MODEL_CARD"
            card = DESTINATION / f"{name}.MODEL_CARD"
            with urlopen(url, timeout=30) as response:
                card.write_bytes(response.read())
    verify()


if __name__ == "__main__":
    main()
