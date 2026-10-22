"""Prepara os modelos oficiais de tradução para os componentes do instalador."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.translators.argos_local import ArgosModelManager  # noqa: E402


def directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def prepare(output: Path, languages: list[str]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="globalvoice-argos-") as temporary:
        manager = ArgosModelManager(root=Path(temporary))
        manifests = []
        for language in languages:
            pack = next(
                item for item in manager.language_packs() if item.code == language
            )
            print(f"Baixando {pack.label} ({pack.download_size_mb:.2f} MiB)...")
            manager.install(language)
            if not manager.is_installed(language):
                raise RuntimeError(f"O pacote {language} não foi instalado por completo.")

            destination = output / language / "packages"
            if destination.exists():
                shutil.rmtree(destination)
            destination.mkdir(parents=True)
            package_names = []
            for package_path in manager.installed_package_paths(language):
                package_names.append(package_path.name)
                shutil.copytree(package_path, destination / package_path.name)

            installed_bytes = directory_size(destination)
            manifest = {
                "code": pack.code,
                "label": pack.label,
                "download_size_mb": pack.download_size_mb,
                "installed_size_mb": round(installed_bytes / (1024 * 1024), 2),
                "packages": sorted(package_names),
                "source": "https://github.com/argosopentech/argospm-index",
                "license": "MIT or CC0",
            }
            (output / language / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifests.append(manifest)
            print(
                f"MODEL_OK={language};INSTALLED_SIZE_MB={manifest['installed_size_mb']}"
            )

        (output / "manifest.json").write_text(
            json.dumps({"languages": manifests}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "dist" / "translation-packs",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=[pack.code for pack in ArgosModelManager.language_packs()],
        default=[pack.code for pack in ArgosModelManager.language_packs()],
    )
    arguments = parser.parse_args()
    prepare(arguments.output.resolve(), arguments.languages)


if __name__ == "__main__":
    main()
