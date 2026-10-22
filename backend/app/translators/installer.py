"""Ponte entre o assistente Windows e o gerenciador de pacotes Argos."""

from pathlib import Path

from backend.app.translators.argos_local import ArgosModelManager, TranslationError


ARCHIVE_NAMES = {
    ("en", "pb"): "en-pb.argosmodel",
    ("pb", "en"): "pb-en.argosmodel",
    ("es", "pt"): "es-pt.argosmodel",
    ("pt", "es"): "pt-es.argosmodel",
    ("en", "es"): "en-es.argosmodel",
    ("es", "en"): "es-en.argosmodel",
}


def install_from_installer(download_dir: Path, destination: Path, pack_codes: str) -> None:
    codes = pack_codes.split(",")
    if not codes or any(not code for code in codes) or len(set(codes)) != len(codes):
        raise TranslationError("Seleção de idiomas inválida no instalador.")
    manager = ArgosModelManager(root=destination)
    expected = {
        (model.source, model.target)
        for code in codes
        for model in manager._get_pack(code).models
    }
    archives = {pair: download_dir / ARCHIVE_NAMES[pair] for pair in expected}
    manager.install_archives(archives, codes)
