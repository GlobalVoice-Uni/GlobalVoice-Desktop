import argparse
import json
from datetime import datetime
from pathlib import Path

from experiments.asr_baseline.audio import load_wav
from experiments.asr_baseline.benchmark import run_baseline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mede o Faster-Whisper atual sem iniciar a interface do Global Voice."
    )
    parser.add_argument("--audio", required=True, type=Path, help="Arquivo WAV de entrada.")
    parser.add_argument(
        "--reference",
        type=Path,
        help="TXT UTF-8 com a transcricao esperada para calcular WER.",
    )
    parser.add_argument("--language", default="pt", help="Codigo do idioma do audio.")
    parser.add_argument("--model", default="small", help="Tamanho do modelo Faster-Whisper.")
    parser.add_argument(
        "--device",
        default="cpu",
        choices=("cpu", "gpu", "cuda"),
        help="Dispositivo solicitado ao adaptador atual.",
    )
    parser.add_argument("--runs", default=3, type=int, help="Numero de repeticoes medidas.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Destino do JSON; por padrao usa a pasta results ignorada pelo Git.",
    )
    return parser


def _create_transcriber(model_size: str, device: str):
    # Import tardio: consultar --help e rodar os testes nao carrega Faster-Whisper.
    from backend.app.transcribers.local_faster_whisper import LocalFasterWhisperTranscriber

    return LocalFasterWhisperTranscriber(model_size=model_size, device=device)


def main() -> int:
    args = _build_parser().parse_args()
    audio_path = args.audio.expanduser().resolve()
    reference_path = args.reference.expanduser().resolve() if args.reference else None
    reference = reference_path.read_text(encoding="utf-8").strip() if reference_path else None
    audio = load_wav(audio_path)

    result = run_baseline(
        audio_path=audio_path,
        audio=audio,
        reference=reference,
        reference_path=reference_path,
        language=args.language,
        model_size=args.model,
        requested_device=args.device,
        runs=args.runs,
        transcriber_factory=_create_transcriber,
        project_root=PROJECT_ROOT,
    )

    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = DEFAULT_RESULTS_DIR / f"baseline-{args.model}-{args.device}-{timestamp}.json"
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = result["summary"]
    print(f"Resultado salvo em: {output_path}")
    print(f"Device resolvido: {result['configuration']['resolved_device']}")
    print(f"Carga do modelo: {result['model_load']['seconds']:.3f} s")
    print(f"RTF mediano: {summary['real_time_factor_median']:.3f}")
    if summary["word_error_rate_median"] is not None:
        print(f"WER mediano: {summary['word_error_rate_median']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

