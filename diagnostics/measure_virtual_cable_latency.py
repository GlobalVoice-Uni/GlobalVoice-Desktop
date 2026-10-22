"""Mede atraso adicional microfone -> GlobalVoice -> VB-CABLE com palmas.

Execute com o GlobalVoice aberto, captura de microfone iniciada e a opção
"Enviar voz traduzida à chamada" desligada. Faça várias palmas perto do
microfone durante a gravação; o áudio fica somente na memória.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import time

import numpy as np
import sounddevice as sd
from scipy.signal import correlate, correlation_lags, resample_poly

from backend.app.audio.audio_capture import _wasapi_alias_for_default_microphone
from backend.app.audio.devices import enumerate_audio_devices
from backend.app.audio.virtual_cable import find_vb_cable


@dataclass(frozen=True)
class CaptureBlock:
    adc_time: float
    sample_rate: int
    audio: np.ndarray


def estimate_added_latency_ms(
    microphone_blocks: list[CaptureBlock],
    cable_blocks: list[CaptureBlock],
    sample_rate: int = 48000,
) -> tuple[float, float]:
    """Alinha timestamps dos dois inputs e correlaciona seus transientes."""

    if not microphone_blocks or not cable_blocks:
        raise ValueError("Nenhum áudio foi capturado nos dois dispositivos.")
    start = min(microphone_blocks[0].adc_time, cable_blocks[0].adc_time)

    def timeline(blocks: list[CaptureBlock]) -> np.ndarray:
        end = max(
            block.adc_time + len(block.audio) / block.sample_rate
            for block in blocks
        )
        result = np.zeros(int((end - start) * sample_rate) + sample_rate, dtype=np.float32)
        for block in blocks:
            data = block.audio
            if block.sample_rate != sample_rate:
                from math import gcd
                divisor = gcd(block.sample_rate, sample_rate)
                data = resample_poly(
                    data, sample_rate // divisor, block.sample_rate // divisor,
                ).astype(np.float32)
            offset = round((block.adc_time - start) * sample_rate)
            result[offset : offset + len(data)] = data
        return result

    microphone = timeline(microphone_blocks)
    cable = timeline(cable_blocks)
    length = max(len(microphone), len(cable))
    microphone = np.pad(microphone, (0, length - len(microphone)))
    cable = np.pad(cable, (0, length - len(cable)))
    microphone = np.diff(microphone)
    cable = np.diff(cable)
    if np.max(np.abs(microphone)) < 0.01 or np.max(np.abs(cable)) < 0.01:
        raise ValueError("Sinal insuficiente. Faça várias palmas perto do microfone.")
    matched = correlate(cable, microphone, mode="full", method="fft")
    lags = correlation_lags(len(cable), len(microphone), mode="full")
    allowed = (lags >= 0) & (lags <= int(0.15 * sample_rate))
    candidates = matched[allowed]
    index = int(np.argmax(candidates))
    lag_samples = int(lags[allowed][index])
    normalized = float(candidates[index]) / (
        float(np.linalg.norm(cable)) * float(np.linalg.norm(microphone)) + 1e-12
    )
    return lag_samples * 1000 / sample_rate, normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=8.0)
    args = parser.parse_args()
    route = find_vb_cable(enumerate_audio_devices())
    if route is None:
        parser.error("VB-CABLE não encontrado. Instale o driver e reinicie o Windows.")
    microphone_id = _wasapi_alias_for_default_microphone()
    if microphone_id is None:
        parser.error("O microfone padrão não tem um endpoint WASAPI equivalente.")
    cable_id = int(route.capture.id)
    microphone_rate = int(sd.query_devices(microphone_id)["default_samplerate"])
    cable_rate = int(sd.query_devices(cable_id)["default_samplerate"])
    microphone_blocks: list[CaptureBlock] = []
    cable_blocks: list[CaptureBlock] = []

    def collect(blocks: list[CaptureBlock], rate: int):
        def callback(indata, frames, time_info, status):
            del frames, status
            blocks.append(CaptureBlock(
                float(time_info.inputBufferAdcTime), rate, indata[:, 0].copy(),
            ))
        return callback

    print("Faça várias palmas perto do microfone. Gravando apenas na memória...")
    with sd.InputStream(
        device=microphone_id, samplerate=microphone_rate, channels=1,
        dtype="float32", latency="low", callback=collect(microphone_blocks, microphone_rate),
    ) as microphone_stream, sd.InputStream(
        device=cable_id, samplerate=cable_rate, channels=1,
        dtype="float32", latency="low", callback=collect(cable_blocks, cable_rate),
    ) as cable_stream:
        def clock_offset(stream) -> float:
            before = time.perf_counter()
            stream_time = stream.time
            after = time.perf_counter()
            return (before + after) / 2 - stream_time

        microphone_offset = clock_offset(microphone_stream)
        cable_offset = clock_offset(cable_stream)
        time.sleep(args.seconds)
    microphone_blocks = [
        CaptureBlock(block.adc_time + microphone_offset, block.sample_rate, block.audio)
        for block in microphone_blocks
    ]
    cable_blocks = [
        CaptureBlock(block.adc_time + cable_offset, block.sample_rate, block.audio)
        for block in cable_blocks
    ]
    latency_ms, correlation = estimate_added_latency_ms(microphone_blocks, cable_blocks)
    print(f"Atraso adicional medido: {latency_ms:.1f} ms")
    print(f"Correlação normalizada: {correlation:.3f}")
    if correlation < 0.15:
        print("Medição inconclusiva: repita com palmas mais fortes e pouco ruído.")
        return 2
    print("Resultado: " + ("dentro" if latency_ms <= 30 else "acima") + " do limite de 30 ms.")
    return 0 if latency_ms <= 30 else 1


if __name__ == "__main__":
    raise SystemExit(main())
