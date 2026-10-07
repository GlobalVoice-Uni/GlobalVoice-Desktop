import argparse
import math
import wave
from pathlib import Path

import numpy as np

from backend.app.audio.audio_capture import AudioSourceError, WasapiLoopbackAudioSource
from backend.app.audio.devices import AudioDeviceKind, enumerate_audio_devices


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "results" / "loopback_sample.wav"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Captura uma amostra WAV do audio reproduzido pelo Windows."
    )
    parser.add_argument("--list", action="store_true", help="Lista as saidas disponiveis.")
    parser.add_argument("--device-id", help="ID WASAPI da saida; vazio usa a padrao.")
    parser.add_argument("--duration", type=float, default=5.0, help="Duracao em segundos.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Arquivo WAV de saida.")
    return parser


def list_loopbacks() -> int:
    catalog = enumerate_audio_devices()
    for warning in catalog.warnings:
        print(f"Aviso: {warning}")

    devices = catalog.of_kind(AudioDeviceKind.LOOPBACK)
    if not devices:
        print("Nenhuma saida com loopback foi encontrada.")
        return 1

    for device in devices:
        default_label = " [padrao]" if device.is_default else ""
        print(f"{device.name}{default_label}\n  {device.id}")
    return 0


def capture_sample(device_id: str | None, duration_s: float, output: Path) -> int:
    if duration_s <= 0:
        raise ValueError("A duracao deve ser maior que zero.")

    source = WasapiLoopbackAudioSource(output_device=device_id)
    chunks = []
    with source:
        step_count = max(1, math.ceil(duration_s / source.step_duration_s))
        print(f"Capturando {duration_s:.1f}s de {source.display_name}...")
        for _ in range(step_count):
            audio, _peak = source.read_step()
            chunks.append(audio)

    captured = np.concatenate(chunks).astype(np.float32)
    peak = float(np.max(np.abs(captured))) if len(captured) else 0.0
    rms = float(np.sqrt(np.mean(np.square(captured)))) if len(captured) else 0.0
    pcm16 = np.clip(captured, -1.0, 1.0)
    pcm16 = (pcm16 * 32767.0).astype("<i2")

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(source.target_sample_rate)
        wav_file.writeframes(pcm16.tobytes())

    print(f"Amostra: {output}")
    print(f"Taxa: {source.target_sample_rate} Hz | pico: {peak:.6f} | RMS: {rms:.6f}")
    if peak < 0.00001:
        print("A captura ficou silenciosa. Reproduza um audio e tente novamente.")
        return 2
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    if args.list:
        return list_loopbacks()
    try:
        return capture_sample(args.device_id, args.duration, args.output)
    except (AudioSourceError, OSError, ValueError) as exc:
        print(f"Falha: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
