import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.transcript import TranscriptChunk
from backend.app.translators.installer import install_from_installer
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

    def test_long_transcript_is_translated_in_complete_segments(self):
        class WordProcessor(FakeProcessor):
            def encode(self, text, out_type=str):
                return text.split()

        class TruncatingTranslator(FakeTranslator):
            def translate_batch(self, tokenized, **options):
                return [
                    SimpleNamespace(hypotheses=[tokens[:4]])
                    for tokens in tokenized
                ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_installed_package(root, "en", "pb")
            translator = ArgosLocalTranslator(
                root=root,
                translator_factory=TruncatingTranslator,
                processor_factory=WordProcessor,
            )
            original = "one two three four five six seven eight nine ten"
            with patch("backend.app.translators.argos_local._MAX_TRANSLATION_SOURCE_TOKENS", 4):
                translated = translator.translate(original, "en", "pt-br")

            self.assertEqual(translated, original)

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

    def test_language_packs_follow_base_without_intermediate_language(self):
        self.assertEqual(
            [pack.code for pack in ArgosModelManager.language_packs("pt-br")],
            ["en", "es"],
        )
        self.assertEqual(
            [pack.code for pack in ArgosModelManager.language_packs("en")],
            ["en", "en-es"],
        )
        self.assertEqual(
            [pack.code for pack in ArgosModelManager.language_packs("es")],
            ["es", "en-es"],
        )
        for pack in ArgosModelManager.language_packs():
            self.assertEqual(len(pack.models), 2)
            self.assertEqual(
                {(model.source, model.target) for model in pack.models},
                {(pack.models[0].source, pack.models[0].target),
                 (pack.models[0].target, pack.models[0].source)},
            )
        spanish_english = next(
            pack for pack in ArgosModelManager.language_packs() if pack.code == "en-es"
        )
        self.assertEqual(spanish_english.download_size_mb, 355.45)
        labels = {
            base: [pack.label_for_base(base) for pack in ArgosModelManager.language_packs(base)]
            for base in ("pt-br", "en", "es")
        }
        self.assertEqual(labels["pt-br"], ["Inglês ↔ Português", "Espanhol ↔ Português"])
        self.assertEqual(labels["en"], ["Português ↔ Inglês", "Espanhol ↔ Inglês"])
        self.assertEqual(labels["es"], ["Português ↔ Espanhol", "Inglês ↔ Espanhol"])

    def test_english_spanish_pack_installs_both_direct_directions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archives = {}
            index = []
            for source, target in (("en", "es"), ("es", "en")):
                archive = root / f"{source}-{target}.argosmodel"
                create_model_archive(archive, source, target)
                url = f"https://models.test/{source}-{target}"
                archives[url] = archive
                index.append({"from_code": source, "to_code": target, "links": [url]})

            manager = ArgosModelManager(
                root=root / "data",
                index_loader=lambda: index,
                downloader=lambda url, destination: shutil.copyfile(archives[url], destination),
            )
            manager.install("en-es")
            self.assertTrue(manager.is_installed("en-es"))
            self.assertEqual(len(manager.installed_package_paths("en-es")), 2)
            translator = ArgosLocalTranslator(
                root=root / "data",
                translator_factory=FakeTranslator,
                processor_factory=FakeProcessor,
            )
            translator.ensure_available("en", "es")
            translator.ensure_available("es", "en")

    def test_download_reports_real_transferred_bytes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "model.argosmodel"
            response = io.BytesIO(b"model-data")
            response.headers = {"Content-Length": "10"}
            events = []
            with patch(
                "backend.app.translators.argos_local.urllib.request.urlopen",
                return_value=response,
            ):
                ArgosModelManager._download_file(
                    "https://models.test/model", destination,
                    lambda received, total: events.append((received, total)),
                )
            self.assertEqual(destination.read_bytes(), b"model-data")
            self.assertEqual(events[-1], (10, 10))

    def test_download_tries_official_mirror_before_catalog_host(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "model.argosmodel"
            visited = []

            def open_url(request, timeout):
                visited.append(request.full_url)
                if len(visited) == 1:
                    raise OSError("servidor indisponível")
                response = io.BytesIO(b"model-data")
                response.headers = {"Content-Length": "10"}
                return response

            with patch(
                "backend.app.translators.argos_local.urllib.request.urlopen",
                side_effect=open_url,
            ):
                ArgosModelManager._download_file(
                    "https://argos-net.com/v1/translate-en_pb-1_9.argosmodel",
                    destination,
                )
            self.assertEqual(destination.read_bytes(), b"model-data")
            self.assertEqual(visited, [
                "https://data.argosopentech.com/argospm/v1/translate-en_pb-1_9.argosmodel",
                "https://argos-net.com/v1/translate-en_pb-1_9.argosmodel",
            ])

    def test_model_manager_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "invalid.argosmodel"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "invalid")

            with self.assertRaises(TranslationError):
                ArgosModelManager._validate_archive(archive)


    def test_installer_archives_are_visible_to_all_users_without_becoming_removable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            downloads = root / "downloads"
            downloads.mkdir()
            system_root = root / "system"
            user_root = root / "user"
            for source, target in (("en", "pb"), ("pb", "en")):
                create_model_archive(downloads / f"{source}-{target}.argosmodel", source, target)
            install_from_installer(downloads, system_root, "en")
            with patch("backend.app.translators.argos_local.translation_data_root", return_value=user_root), patch(
                "backend.app.translators.argos_local.system_translation_data_root", return_value=system_root
            ):
                manager = ArgosModelManager()
                self.assertTrue(manager.is_installed("en"))
                self.assertTrue(manager.is_system_installed("en"))
                manager.uninstall("en")
                self.assertTrue(manager.is_installed("en"))
                translator = ArgosLocalTranslator(
                    translator_factory=FakeTranslator, processor_factory=FakeProcessor
                )
                translator.ensure_available("en", "pt-br")
                translator.ensure_available("pt-br", "en")

    def test_installer_validates_every_archive_before_installing_any(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            downloads = root / "downloads"
            downloads.mkdir()
            create_model_archive(downloads / "en-pb.argosmodel", "en", "pb")
            with self.assertRaisesRegex(TranslationError, "ausente"):
                install_from_installer(downloads, root / "installed", "en")
            self.assertFalse((root / "installed" / "packages").exists())

    def test_installer_rejects_archive_with_wrong_language(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            downloads = root / "downloads"
            downloads.mkdir()
            create_model_archive(downloads / "en-pb.argosmodel", "en", "pb")
            create_model_archive(downloads / "pb-en.argosmodel", "en", "es")
            with self.assertRaisesRegex(TranslationError, "não corresponde"):
                install_from_installer(downloads, root / "installed", "en")


if __name__ == "__main__":
    unittest.main()
