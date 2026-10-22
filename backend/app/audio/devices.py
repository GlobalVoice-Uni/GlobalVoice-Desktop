from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import sounddevice as sd

from .windows_com import windows_com_initialized


class AudioDeviceKind(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    LOOPBACK = "loopback"


@dataclass(frozen=True)
class AudioDeviceInfo:
    """Descricao estavel de um endpoint de audio exposto para a interface."""

    id: str
    name: str
    kind: AudioDeviceKind
    channels: int
    is_default: bool = False
    backend: str = ""


@dataclass(frozen=True)
class AudioDeviceCatalog:
    """Resultado da enumeracao com avisos que nao impedem uso parcial."""

    devices: Tuple[AudioDeviceInfo, ...]
    warnings: Tuple[str, ...] = ()

    def of_kind(self, kind: AudioDeviceKind) -> Tuple[AudioDeviceInfo, ...]:
        return tuple(device for device in self.devices if device.kind == kind)


def _load_soundcard():
    try:
        import soundcard as sc
    except (ImportError, OSError):
        return None
    return sc


def _safe_channels(device) -> int:
    try:
        return max(0, int(device.channels))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return 0


def enumerate_audio_devices(
    sounddevice_module=sd,
    soundcard_module=None,
) -> AudioDeviceCatalog:
    """Enumera entradas, saidas e endpoints de loopback disponiveis.

    Entradas e saídas para reprodução usam PortAudio/sounddevice. O loopback
    usa SoundCard porque ele abre endpoints de renderização WASAPI. Falha em
    um backend gera aviso e preserva os dispositivos do outro.
    """

    devices = []
    warnings = []

    try:
        raw_inputs = sounddevice_module.query_devices()
        try:
            hostapis = sounddevice_module.query_hostapis()
        except (AttributeError, RuntimeError):
            hostapis = ()

        def backend_name(raw_device) -> str:
            try:
                return str(hostapis[int(raw_device["hostapi"])]["name"])
            except (KeyError, IndexError, TypeError, ValueError):
                return "PortAudio"

        default_input = sounddevice_module.query_devices(kind="input")
        default_output = sounddevice_module.query_devices(kind="output")
        configured_default = getattr(
            getattr(sounddevice_module, "default", None),
            "device",
            (-1, -1),
        )
        default_input_index = int(
            default_input.get("index", configured_default[0])
        )
        default_output_index = int(
            default_output.get("index", configured_default[1])
        )

        for fallback_index, raw_device in enumerate(raw_inputs):
            channels = int(raw_device.get("max_input_channels", 0))
            if channels <= 0:
                continue
            index = int(raw_device.get("index", fallback_index))
            devices.append(
                AudioDeviceInfo(
                    id=str(index),
                    name=str(raw_device.get("name", f"Entrada {index}")),
                    kind=AudioDeviceKind.INPUT,
                    channels=channels,
                    is_default=index == default_input_index,
                    backend=backend_name(raw_device),
                )
            )
        for fallback_index, raw_device in enumerate(raw_inputs):
            channels = int(raw_device.get("max_output_channels", 0))
            if channels <= 0:
                continue
            index = int(raw_device.get("index", fallback_index))
            devices.append(
                AudioDeviceInfo(
                    id=str(index),
                    name=str(raw_device.get("name", f"Saída {index}")),
                    kind=AudioDeviceKind.OUTPUT,
                    channels=channels,
                    is_default=index == default_output_index,
                    backend=backend_name(raw_device),
                )
            )
    except Exception as exc:
        warnings.append(f"Não foi possível listar os dispositivos PortAudio: {exc}")

    with windows_com_initialized():
        sc = soundcard_module if soundcard_module is not None else _load_soundcard()
        if not sc:
            warnings.append(
                "A captura do áudio do sistema não está disponível; somente microfones podem ser usados."
            )
            return AudioDeviceCatalog(tuple(devices), tuple(warnings))

        try:
            default_speaker = sc.default_speaker()
            default_speaker_id = str(default_speaker.id) if default_speaker else ""
            speakers = sc.all_speakers()
            for speaker in speakers:
                speaker_id = str(speaker.id)
                common = {
                    "id": speaker_id,
                    "name": str(speaker.name),
                    "channels": _safe_channels(speaker),
                    "is_default": speaker_id == default_speaker_id,
                    "backend": "WASAPI",
                }
                devices.append(AudioDeviceInfo(kind=AudioDeviceKind.LOOPBACK, **common))
        except Exception as exc:
            warnings.append(f"Não foi possível listar as saídas de áudio: {exc}")

    return AudioDeviceCatalog(tuple(devices), tuple(warnings))


def select_device(
    catalog: AudioDeviceCatalog,
    kind: AudioDeviceKind,
    device_id: Optional[str],
) -> Optional[AudioDeviceInfo]:
    """Resolve o endpoint solicitado, usando o padrao quando o id e vazio."""

    candidates = catalog.of_kind(kind)
    if not candidates:
        return None

    if device_id not in (None, ""):
        for candidate in candidates:
            if candidate.id == str(device_id):
                return candidate

    for candidate in candidates:
        if candidate.is_default:
            return candidate
    return candidates[0]
