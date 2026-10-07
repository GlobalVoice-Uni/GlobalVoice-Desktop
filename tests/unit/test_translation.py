import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.transcript import TranscriptChunk
from backend.app.translators.argos_local import (
    ArgosLocalTranslator,
    ArgosModelManager,
    TranslationError,
    TranslationModelUnavailable,
)


class FakeTranslationResult:
    hypotheses = [["traduzido:", "hello"]]


class FakeTranslator:
    def __init__(self, model_path, **options):
        self.model_path = model_path
        self.options = options

    def translate_batch(self, tokenized, **options):
        self.tokenized = tokenized
        self.translation_options = options
        return [FakeTranslationResult()]


class FakeProcessor:
    def __init__(self, model_file):
        self.model_file = model_file

    def encode(self, text, out_type=str):
        return [text]

    def decode(self, tokens):
        return " ".join(tokens)


def create_installed_package(root: Path, source: str, target: str) -> Path:
    package = root / "packages" / f"translate-{source}_{target}-1_0"
    (package / "model").mkdir(parents=True)
    (package / "model" / "model.bin").write_bytes(b"model")
    (package / "sentencepiece.model").write_bytes(b"tokenizer")
    (package / "metadata.json").write_text(
        json.dumps({"from_code": source, "to_code": target}),
        encoding="utf-8",
    )
    return package


def create_model_archive(path: Path, source: str, target: str) -> None:
    package = f"translate-{source}_{target}-1_0"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(
            f"{package}/metadata.json",
            json.dumps({"from_code": source, "to_code": target}),
        )
        bundle.writestr(f"{package}/model/model.bin", "model")
        bundle.writestr(f"{package}/sentencepiece.model", "tokenizer")


class TranslationTests(unittest.TestCase):
    def test_translates_brazilian_portuguese_with_pb_model(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_installed_package(root, "en", "pb")
            translator = ArgosLocalTranslator(
                root=root,
                translator_factory=FakeTranslator,
                processor_factory=FakeProcessor,
            )

            result = translator.translate("Hello", "en", "pt-br")

            self.assertEqual(result, "traduzido: hello")

    def test_same_language_does_not_require_model(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            translator = ArgosLocalTranslator(
                root=Path(temporary_directory),
                translator_factory=FakeTranslator,
                processor_factory=FakeProcessor,
            )

            self.assertEqual(translator.translate("Olá", "pt-br", "pt"), "Olá")

    def test_missing_pair_has_actionable_message(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            translator = ArgosLocalTranslator(
                root=Path(temporary_directory),
                translator_factory=FakeTranslator,
                processor_factory=FakeProcessor,
            )

            with self.assertRaisesRegex(
                TranslationModelUnavailable, "Configurações > Idiomas"
            ) as error:
                translator.translate("Hola", "es", "pt-br")

            self.assertIn("instalado.\nAbra Configurações", str(error.exception))

    def test_transcript_chunk_formats_each_display_mode(self):
        original = "Hello"
        translated = "Olá"

        self.assertEqual(
            TranscriptChunk(
                "meeting", original, translated, "translation_only"
            ).format_for_display(),
            translated,
        )
        self.assertEqual(
            TranscriptChunk(
                "meeting", original, translated, "transcript_only"
            ).format_for_display(),
            original,
        )
        self.assertEqual(
            TranscriptChunk("meeting", original, translated, "both").format_for_display(),
            "Hello\nOlá",
        )

    def test_model_manager_installs_and_removes_complete_pack(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            en_pb_archive = root / "en-pb.argosmodel"
            pb_en_archive = root / "pb-en.argosmodel"
            create_model_archive(en_pb_archive, "en", "pb")
            create_model_archive(pb_en_archive, "pb", "en")
            archives = {
                "https://models.test/en-pb": en_pb_archive,
                "https://models.test/pb-en": pb_en_archive,
            }
            index = [
                {"from_code": "en", "to_code": "pb", "links": ["https://models.test/en-pb"]},
                {"from_code": "pb", "to_code": "en", "links": ["https://models.test/pb-en"]},
            ]

            def download(url, destination):
                shutil.copyfile(archives[url], destination)

            manager = ArgosModelManager(
                root=root / "data",
                index_loader=lambda: index,
                downloader=download,
            )

            manager.install("en")

            self.assertTrue(manager.is_installed("en"))
            self.assertEqual(len(manager.installed_package_paths("en")), 2)
            self.assertEqual(list((root / "data" / "downloads").glob("*.argosmodel")), [])
            manager.uninstall("en")
            self.assertFalse(manager.is_installed("en"))

    def test_model_manager_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "invalid.argosmodel"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "invalid")

            with self.assertRaises(TranslationError):
                ArgosModelManager._validate_archive(archive)


if __name__ == "__main__":
    unittest.main()
