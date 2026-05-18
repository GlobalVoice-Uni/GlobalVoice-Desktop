from PySide6.QtCore import QSettings

SETTINGS_ORG = "GlobalVoice"
SETTINGS_APP = "RealtimeSettings"

DEFAULT_SETTINGS = {
    "model_size": "small",
    "device": "gpu",
    "language": "pt-br",
    "context_window": 0,
    "max_duration_s": 0.0,
    "vad_type": "silero",
    "speech_peak_threshold": 0.0018,
    "silero_threshold": 0.5,
    "silero_min_silence_ms": 120,
    "silero_speech_pad_ms": 30,
    "min_speech_window_s": 0.2,
    "min_silence_window_s": 0.4,
    "max_utterance_s": 3.2,
    "min_utterance_s": 0.7,
    "boundary_overlap_s": 0.45,
    "tail_guard_words": 4,
    "forced_split_policy": "protect_boundary",
    "forced_split_extra_tail_words": 1,
    "ui_transcription_font_size": 14,
    "ui_transcription_window_width": 500,
    "ui_transcription_window_height": 400,
}


def _coerce_value(value, default):
    if value is None:
        return default
    try:
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int) and not isinstance(default, bool):
            return int(value)
        if isinstance(default, float):
            return float(value)
    except (TypeError, ValueError):
        return default
    return str(value)


def load_settings():
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    values = {}
    for key, default in DEFAULT_SETTINGS.items():
        values[key] = _coerce_value(settings.value(key, default), default)
    return values


def save_settings(values):
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    for key in DEFAULT_SETTINGS:
        if key in values:
            settings.setValue(key, values[key])
    settings.sync()
