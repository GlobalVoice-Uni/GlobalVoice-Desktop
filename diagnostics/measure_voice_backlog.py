"""Estima atraso mínimo da reprodução a partir dos chunks reais de duas fontes."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backend.app.audio.speech_output import PiperSpeechSynthesizer
from backend.app.translators.argos_local import ArgosLocalTranslator


def measure(stt_report: dict) -> dict:
    translator = ArgosLocalTranslator()
    voice = PiperSpeechSynthesizer()
    routes = {
        "usuario": ("pt-br", "en"),
        "reuniao": ("en", "pt-br"),
    }
    for target in ("en", "pt-br"):
        voice.preload(target)

    results = {}
    for channel, (source, target) in routes.items():
        items = []
        next_free_at = 0.0
        for job in stt_report["jobs"]:
            if job["source"] != channel or not job["text"].strip():
                continue
            started = time.perf_counter()
            translated = translator.translate(job["text"], source, target)
            translation_s = time.perf_counter() - started
            if not translated.strip():
                continue
            started = time.perf_counter()
            samples, rate = voice.synthesize(translated, target)
            synthesis_s = time.perf_counter() - started
            ready_at = (
                job["index"] * stt_report["utterance_s"]
                + job["delay_after_audio_s"]
                + translation_s
                + synthesis_s
            )
            voice_s = len(samples) / rate
            start_delay_s = max(0.0, next_free_at - ready_at)
            next_free_at = max(ready_at, next_free_at) + voice_s
            items.append({
                "index": job["index"],
                "translation_s": round(translation_s, 3),
                "synthesis_s": round(synthesis_s, 3),
                "voice_s": round(voice_s, 3),
                "start_delay_if_all_played_s": round(start_delay_s, 3),
            })
        results[channel] = {
            "phrases": len(items),
            "total_voice_s": round(sum(item["voice_s"] for item in items), 3),
            "max_start_delay_if_all_played_s": round(
                max((item["start_delay_if_all_played_s"] for item in items), default=0), 3
            ),
            "items": items,
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stt-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(json.loads(args.stt_report.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: {k: v for k, v in data.items() if k != "items"}
                      for key, data in report.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
