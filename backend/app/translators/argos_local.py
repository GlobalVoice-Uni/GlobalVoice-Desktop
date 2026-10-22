import json
import os
import re
import shutil
import stat
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Optional


PACKAGE_INDEX_URL = (
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
)
ARGOS_INDEX_DOWNLOAD_PREFIX = "https://argos-net.com/v1/"
ARGOS_OFFICIAL_MIRROR_PREFIX = "https://data.argosopentech.com/argospm/v1/"
_MAX_TRANSLATION_SOURCE_TOKENS = 64


class TranslationError(RuntimeError):
    """Erro de tradução com mensagem adequada para a interface."""


class TranslationRuntimeUnavailable(TranslationError):
    pass


class TranslationModelUnavailable(TranslationError):
    pass


@dataclass(frozen=True)
class TranslationModel:
    source: str
    target: str
    download_size_mb: float


@dataclass(frozen=True)
class TranslationLanguagePack:
    code: str
    label: str
    languages: tuple[str, str]
    models: tuple[TranslationModel, ...]
    selected_by_default: bool = False

    @property
    def download_size_mb(self) -> float:
        return round(sum(model.download_size_mb for model in self.models), 2)

    def label_for_base(self, base_language: str) -> str:
        base = "pt-br" if base_language in {"pt", "pb"} else base_language
        if base not in self.languages:
            raise ValueError(f"Idioma principal não pertence ao par: {base_language}")
        names = {"pt-br": "Português", "en": "Inglês", "es": "Espanhol"}
        other = next(language for language in self.languages if language != base)
        return f"{names[other]} ↔ {names[base]}"


LANGUAGE_PACKS = (
    TranslationLanguagePack(
        code="en",
        label="Inglês ↔ Português",
        languages=("pt-br", "en"),
        selected_by_default=True,
        models=(
            TranslationModel("en", "pb", 63.11),
            TranslationModel("pb", "en", 66.23),
        ),
    ),
    TranslationLanguagePack(
        code="es",
        label="Espanhol ↔ Português",
        languages=("pt-br", "es"),
        models=(
            TranslationModel("es", "pt", 64.38),
            TranslationModel("pt", "es", 64.38),
        ),
    ),
    TranslationLanguagePack(
        code="en-es",
        label="Inglês ↔ Espanhol",
        languages=("en", "es"),
        models=(
            TranslationModel("en", "es", 83.45),
            TranslationModel("es", "en", 272.00),
        ),
    ),
)


def translation_data_root() -> Path:
    override = os.getenv("GLOBALVOICE_TRANSLATION_DATA")
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "GlobalVoice" / "translation"
    return Path.home() / ".globalvoice" / "translation"


def system_translation_data_root() -> Optional[Path]:
    """Pacotes instalados para todos os usuários pelo instalador Windows."""
    program_data = os.getenv("PROGRAMDATA")
    return Path(program_data) / "GlobalVoice" / "translation" if program_data else None


def _language_candidates(language: str) -> tuple[str, ...]:
    normalized = (language or "").strip().lower()
    if normalized in {"pt-br", "pb"}:
        return ("pb", "pt")
    if normalized == "pt":
        return ("pt", "pb")
    return (normalized,)


def _same_language(source: str, target: str) -> bool:
    return bool(set(_language_candidates(source)) & set(_language_candidates(target)))


def _load_translation_runtime():
    try:
        import ctranslate2
        import sentencepiece
    except (ImportError, OSError) as exc:
        raise TranslationRuntimeUnavailable(
            "O componente de tradução local não está disponível nesta instalação."
        ) from exc
    return ctranslate2.Translator, sentencepiece.SentencePieceProcessor


def _read_metadata(package_path: Path) -> Optional[dict]:
    try:
        return json.loads(
            (package_path / "metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError):
        return None


def _installed_packages(root: Path):
    packages_root = root / "packages"
    if not packages_root.exists():
        return
    for package_path in packages_root.iterdir():
        if not package_path.is_dir():
            continue
        metadata = _read_metadata(package_path)
        if metadata is not None:
            yield package_path, metadata


class _CTranslatePackage:
    def __init__(
        self,
        package_path: Path,
        metadata: dict,
        translator_factory,
        processor_factory,
    ):
        model_path = package_path / "model"
        tokenizer_path = package_path / "sentencepiece.model"
        if not model_path.is_dir() or not tokenizer_path.is_file():
            raise TranslationModelUnavailable(
                "O modelo de tradução instalado está incompleto. Reinstale o idioma."
            )
        self._translator = translator_factory(
            str(model_path),
            device="cpu",
            compute_type="int8",
        )
        self._processor = processor_factory(model_file=str(tokenizer_path))
        self._target_prefix = str(metadata.get("target_prefix") or "")

    def translate(self, text: str) -> str:
        segments = self._segments(text)
        tokenized = [self._processor.encode(segment, out_type=str) for segment in segments]
        target_prefix = (
            [[self._target_prefix] for _ in segments] if self._target_prefix else None
        )
        results = self._translator.translate_batch(
            tokenized,
            target_prefix=target_prefix,
            replace_unknowns=True,
            beam_size=4,
            num_hypotheses=1,
            length_penalty=0.2,
        )
        if len(results) != len(segments):
            raise TranslationError("A tradução local retornou um trecho incompleto.")
        translated_segments = []
        for result in results:
            if not result.hypotheses or not result.hypotheses[0]:
                raise TranslationError("A tradução local retornou um trecho vazio.")
            translated = self._processor.decode(result.hypotheses[0])
            if self._target_prefix and translated.startswith(self._target_prefix):
                translated = translated[len(self._target_prefix) :]
            translated_segments.append(translated.replace("▁", " ").replace("_", " ").strip())
        return " ".join(translated_segments)

    def _segments(self, text: str) -> list[str]:
        """Mantém frases curtas para o modelo não encerrar uma fala longa cedo."""
        segments = []
        for sentence in re.split(r"(?<=[.!?;:])\s+", text.strip()):
            current = []
            for word in sentence.split():
                candidate = " ".join([*current, word])
                if current and len(self._processor.encode(candidate, out_type=str)) > _MAX_TRANSLATION_SOURCE_TOKENS:
                    segments.append(" ".join(current))
                    current = [word]
                else:
                    current.append(word)
            if current:
                segments.append(" ".join(current))
        return segments


class ArgosLocalTranslator:
    """Traduz localmente com CTranslate2 e modelos no formato Argos."""

    def __init__(
        self,
        root: Optional[Path] = None,
        translator_factory=None,
        processor_factory=None,
    ):
        self.root = (root or translation_data_root()).expanduser().resolve()
        self.system_root = None if root is not None else system_translation_data_root()
        if translator_factory is None or processor_factory is None:
            default_translator, default_processor = _load_translation_runtime()
            translator_factory = translator_factory or default_translator
            processor_factory = processor_factory or default_processor
        self._translator_factory = translator_factory
        self._processor_factory = processor_factory
        self._translations: dict[tuple[str, str], _CTranslatePackage] = {}

    def _resolve_translation(self, source_language: str, target_language: str):
        key = (source_language, target_language)
        if key in self._translations:
            return self._translations[key]

        packages = list(_installed_packages(self.root) or ())
        if self.system_root is not None and self.system_root != self.root:
            packages.extend(_installed_packages(self.system_root) or ())
        for source_code in _language_candidates(source_language):
            for target_code in _language_candidates(target_language):
                for package_path, metadata in packages:
                    if (
                        metadata.get("from_code") == source_code
                        and metadata.get("to_code") == target_code
                    ):
                        translation = _CTranslatePackage(
                            package_path,
                            metadata,
                            self._translator_factory,
                            self._processor_factory,
                        )
                        self._translations[key] = translation
                        return translation

        raise TranslationModelUnavailable(
            "O modelo de tradução "
            f"{source_language.upper()} → {target_language.upper()} não está instalado.\n"
            "Abra Configurações > Idiomas para instalá-lo."
        )

    def ensure_available(self, source_language: str, target_language: str) -> None:
        if _same_language(source_language, target_language):
            return
        self._resolve_translation(source_language, target_language)

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        if _same_language(source_language, target_language):
            return cleaned

        try:
            return self._resolve_translation(
                source_language, target_language
            ).translate(cleaned)
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(
                "A tradução local falhou. Tente novamente ou reinstale o idioma."
            ) from exc


class ArgosModelManager:
    """Instala e remove modelos oficiais por idioma, fora do executável."""

    def __init__(
        self,
        root: Optional[Path] = None,
        index_loader: Optional[Callable[[], list[dict]]] = None,
        downloader: Optional[Callable[[str, Path], None]] = None,
    ):
        self.root = (root or translation_data_root()).expanduser().resolve()
        self.system_root = None if root is not None else system_translation_data_root()
        self.packages_root = self.root / "packages"
        self.downloads_root = self.root / "downloads"
        self._index_loader = index_loader or self._load_official_index
        self._downloader = downloader or self._download_file
        self._supports_progress = downloader is None
        self._lock = threading.Lock()

    @staticmethod
    def language_packs(base_language: str | None = None) -> tuple[TranslationLanguagePack, ...]:
        if base_language is None:
            return LANGUAGE_PACKS
        base = "pt-br" if base_language in {"pt", "pb", "pt-br"} else base_language
        return tuple(pack for pack in LANGUAGE_PACKS if base in pack.languages)

    def _installed_pairs(self) -> dict[tuple[str, str], Path]:
        installed = {
            (str(metadata.get("from_code")), str(metadata.get("to_code"))): path
            for path, metadata in (_installed_packages(self.root) or ())
        }
        if self.system_root is not None and self.system_root != self.root:
            for path, metadata in (_installed_packages(self.system_root) or ()):
                installed.setdefault(
                    (str(metadata.get("from_code")), str(metadata.get("to_code"))), path
                )
        return installed

    def is_system_installed(self, pack_code: str) -> bool:
        if self.system_root is None:
            return False
        pack = self._get_pack(pack_code)
        pairs = {
            (metadata.get("from_code"), metadata.get("to_code"))
            for _, metadata in (_installed_packages(self.system_root) or ())
        }
        return all((model.source, model.target) in pairs for model in pack.models)

    def is_installed(self, pack_code: str) -> bool:
        pack = self._get_pack(pack_code)
        installed = self._installed_pairs()
        return all((model.source, model.target) in installed for model in pack.models)

    def installed_package_paths(self, pack_code: str) -> tuple[Path, ...]:
        pack = self._get_pack(pack_code)
        installed = self._installed_pairs()
        return tuple(
            installed[(model.source, model.target)]
            for model in pack.models
            if (model.source, model.target) in installed
        )

    def install(
        self,
        pack_code: str,
        progress_callback: Optional[Callable[[int, int, int, Optional[int]], None]] = None,
    ) -> None:
        pack = self._get_pack(pack_code)
        with self._lock:
            installed = self._installed_pairs()
            missing = [
                model
                for model in pack.models
                if (model.source, model.target) not in installed
            ]
            if not missing:
                return

            available = self._index_loader()
            self.downloads_root.mkdir(parents=True, exist_ok=True)
            for file_index, model in enumerate(missing, 1):
                candidate = next(
                    (
                        package
                        for package in available
                        if package.get("from_code") == model.source
                        and package.get("to_code") == model.target
                    ),
                    None,
                )
                if candidate is None:
                    raise TranslationModelUnavailable(
                        f"O modelo {model.source.upper()} → {model.target.upper()} "
                        "não está disponível no catálogo oficial."
                    )
                link = next(
                    (
                        value
                        for value in candidate.get("links", ())
                        if str(value).startswith("https://")
                    ),
                    None,
                )
                if link is None:
                    raise TranslationError(
                        "O catálogo não informou uma origem HTTPS para o idioma."
                    )

                handle, archive_name = tempfile.mkstemp(
                    prefix=f"{model.source}-{model.target}-",
                    suffix=".argosmodel",
                    dir=self.downloads_root,
                )
                os.close(handle)
                archive = Path(archive_name)
                try:
                    if self._supports_progress and progress_callback is not None:
                        self._downloader(
                            str(link),
                            archive,
                            lambda received, total, current=file_index: progress_callback(
                                current, len(missing), received, total
                            ),
                        )
                    else:
                        self._downloader(str(link), archive)
                    self._validate_archive(archive)
                    self._install_archive(archive, model)
                finally:
                    archive.unlink(missing_ok=True)

    def uninstall(self, pack_code: str) -> None:
        pack = self._get_pack(pack_code)
        pairs = {(model.source, model.target) for model in pack.models}
        with self._lock:
            for package_path, metadata in list(_installed_packages(self.root) or ()):
                pair = (metadata.get("from_code"), metadata.get("to_code"))
                if pair in pairs:
                    shutil.rmtree(package_path)

    def install_archives(self, archives: dict[tuple[str, str], Path], pack_codes: list[str]) -> None:
        """Instala arquivos já baixados pelo assistente, sem acesso à rede."""
        expected = {
            (model.source, model.target): model
            for code in pack_codes
            for model in self._get_pack(code).models
        }
        if set(archives) != set(expected):
            raise TranslationError("Os arquivos baixados não correspondem aos pares escolhidos.")
        with self._lock:
            for pair, archive in archives.items():
                if not archive.is_file():
                    raise TranslationError(f"Arquivo de idioma ausente: {archive.name}")
                self._validate_archive(archive)
            for pair, archive in archives.items():
                self._install_archive(archive, expected[pair])

    def _install_archive(self, archive_path: Path, model: TranslationModel) -> None:
        self.packages_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=self.packages_root))
        try:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(staging)
            candidates = [
                path
                for path in staging.iterdir()
                if path.is_dir() and (path / "metadata.json").is_file()
            ]
            if len(candidates) != 1:
                raise TranslationError(
                    "O pacote de idioma não possui uma estrutura reconhecida."
                )
            package_path = candidates[0]
            metadata = _read_metadata(package_path) or {}
            if (
                metadata.get("from_code") != model.source
                or metadata.get("to_code") != model.target
            ):
                raise TranslationError(
                    "O conteúdo do pacote não corresponde ao idioma solicitado."
                )
            if not (package_path / "model").is_dir() or not (
                package_path / "sentencepiece.model"
            ).is_file():
                raise TranslationError("O pacote de idioma está incompleto.")

            # A aplicação traduz trechos curtos já segmentados pelo pipeline de
            # áudio. Modelos auxiliares de segmentação do pacote não são usados.
            for unused_segmenter in ("stanza", "spacy", "minisbd"):
                shutil.rmtree(package_path / unused_segmenter, ignore_errors=True)

            destination = self.packages_root / package_path.name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(package_path), str(destination))
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _load_official_index() -> list[dict]:
        request = urllib.request.Request(
            PACKAGE_INDEX_URL,
            headers={"User-Agent": "GlobalVoice/translation-model-manager"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except Exception as exc:
            raise TranslationError(
                "Não foi possível consultar os idiomas disponíveis. Verifique sua conexão."
            ) from exc
        if not isinstance(payload, list):
            raise TranslationError("O catálogo de idiomas retornou um formato inválido.")
        return payload

    @staticmethod
    def _download_file(
        url: str,
        destination: Path,
        progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
    ) -> None:
        sources = [url]
        if url.startswith(ARGOS_INDEX_DOWNLOAD_PREFIX):
            sources.insert(0, url.replace(
                ARGOS_INDEX_DOWNLOAD_PREFIX, ARGOS_OFFICIAL_MIRROR_PREFIX, 1
            ))
        for source in sources:
            request = urllib.request.Request(
                source,
                headers={"User-Agent": "GlobalVoice/translation-model-manager"},
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    header = response.headers.get("Content-Length")
                    total = int(header) if header and header.isdigit() else None
                    received = 0
                    with destination.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            received += len(chunk)
                            if progress_callback is not None:
                                progress_callback(received, total)
                return
            except Exception as exc:
                destination.unlink(missing_ok=True)
                last_error = exc
        raise TranslationError(
            "O download do idioma falhou nos servidores oficiais. Tente novamente mais tarde."
        ) from last_error

    @staticmethod
    def _validate_archive(path: Path) -> None:
        """Bloqueia links, caminhos absolutos ou travessia antes da extração."""

        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    normalized = PurePosixPath(member.filename.replace("\\", "/"))
                    file_type = (member.external_attr >> 16) & 0o170000
                    if (
                        normalized.is_absolute()
                        or ".." in normalized.parts
                        or file_type == stat.S_IFLNK
                    ):
                        raise TranslationError(
                            "O pacote de idioma recebido possui caminhos inválidos."
                        )
        except zipfile.BadZipFile as exc:
            raise TranslationError("O pacote de idioma baixado está corrompido.") from exc

    @staticmethod
    def _get_pack(pack_code: str) -> TranslationLanguagePack:
        for pack in LANGUAGE_PACKS:
            if pack.code == pack_code:
                return pack
        raise ValueError(f"Pacote de idioma desconhecido: {pack_code}")
