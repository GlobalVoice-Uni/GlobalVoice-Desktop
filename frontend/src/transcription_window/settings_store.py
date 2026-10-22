import configparser
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

SETTINGS_ORG = "GlobalVoice"
SETTINGS_APP = "RealtimeSettings"

DEFAULT_SETTINGS = {
    "settings_revision": 2,
    "model_size": "small",
    "device": "gpu",
    "language": "pt-br",
    "user_language": "pt-br",
    "meeting_language": "en",
    "display_mode": "translation_only",
    "capture_mode": "automatic",
    "audio_source": "microphone",
    "audio_device_id": "",
    "meeting_device_id": "",
    "voice_output_enabled": False,
    "voice_output_device_id": "",
    "meeting_voice_enabled": False,
    "meeting_voice_device_id": "",
    "english_voice": "en-ljspeech",
    "context_window": 0,
    "max_duration_s": 0.0,
    "vad_type": "silero",
    "speech_peak_threshold": 0.0018,
    "silero_threshold": 0.5,
    "silero_min_silence_ms": 120,
    "silero_speech_pad_ms": 30,
    "min_speech_window_s": 0.2,
    "min_silence_window_s": 0.55,
    "max_utterance_s": 3.2,
    "min_utterance_s": 0.7,
    "boundary_overlap_s": 0.45,
    "tail_guard_words": 4,
    "forced_split_policy": "protect_boundary",
    "forced_split_extra_tail_words": 1,
    "ui_transcription_font_size": 14,
    "ui_transcription_window_width": 500,
    "ui_transcription_window_height": 400,
    "ui_transcription_window_x": -1,
    "ui_transcription_window_y": -1,
    "ui_toolbar_x": -1,
    "ui_toolbar_y": -1,
}


def _coerce_value(value, default):
    if value is None:
        return default
    try:
        if isinstance(default, bool):
            if isinstance(value, str):
                normalized = value.strip().casefold()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
                return default
            return bool(value)
        if isinstance(default, int) and not isinstance(default, bool):
            return int(value)
        if isinstance(default, float):
            return float(value)
    except (TypeError, ValueError):
        return default
    return str(value)


def _installation_language_selection(
    path: Path | None = None,
) -> tuple[str, str, str] | None:
    if path is None:
        if not getattr(sys, "frozen", False):
            return None
        path = Path(sys.executable).parent / "installation.ini"
    if not path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        language = parser.get("Language", "Base", fallback="").strip().lower()
        pairs = [
            pair.strip().lower()
            for pair in parser.get("Language", "Pairs", fallback="").split(",")
        ]
        install_id = parser.get("App", "InstallId", fallback="").strip()
        if not install_id:
            install_id = str(path.stat().st_mtime_ns)
    except (OSError, UnicodeError, configparser.Error):
        return None
    if language not in {"pt-br", "en", "es"}:
        return None
    targets = {
        "pt-br": {"en": "en", "es": "es"},
        "en": {"en": "pt-br", "en-es": "es"},
        "es": {"es": "pt-br", "en-es": "en"},
    }
    fallback = "en" if language == "pt-br" else "pt-br"
    target = next((targets[language][pair] for pair in pairs if pair in targets[language]), fallback)
    return language, target, install_id


def _installation_base_language(path: Path | None = None) -> str | None:
    selection = _installation_language_selection(path)
    return selection[0] if selection else None


def load_settings():
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    selection = _installation_language_selection()
    if selection is not None:
        base, target, install_id = selection
        if settings.value("installation_id", None) != install_id:
            set_initial_base_language(base, settings, target_language=target, force=True)
            settings.setValue("installation_id", install_id)
            settings.sync()
    values = {}
    for key, default in DEFAULT_SETTINGS.items():
        values[key] = _coerce_value(settings.value(key, default), default)
    if values["device"] == "auto":
        values["device"] = "gpu"
    saved_revision = _coerce_value(settings.value("settings_revision", 1), 1)
    if saved_revision < 2:
        saved_silence = _coerce_value(
            settings.value("min_silence_window_s", 0.4), 0.4
        )
        if abs(saved_silence - 0.4) < 0.001:
            values["min_silence_window_s"] = 0.55
    return values


def save_settings(values):
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    for key in DEFAULT_SETTINGS:
        if key in values:
            settings.setValue(key, values[key])
    settings.sync()


def set_initial_base_language(
    language: str,
    settings: QSettings | None = None,
    *,
    target_language: str | None = None,
    force: bool = False,
) -> bool:
    """Aplica a escolha do instalador em um perfil novo ou nova instalação."""
    if language not in {"pt-br", "en", "es"}:
        raise ValueError(f"Idioma principal inválido: {language}")
    settings = settings if settings is not None else QSettings(SETTINGS_ORG, SETTINGS_APP)
    if not force and settings.value("user_language", None) is not None:
        return False
    meeting_language = target_language or ("en" if language == "pt-br" else "pt-br")
    if meeting_language not in {"pt-br", "en", "es"} or meeting_language == language:
        raise ValueError(f"Idioma da chamada inválido: {meeting_language}")
    settings.setValue("user_language", language)
    settings.setValue("meeting_language", meeting_language)
    settings.setValue("language", meeting_language)
    settings.sync()
    return True
