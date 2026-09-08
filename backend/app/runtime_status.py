from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DevicePreference(str, Enum):
    """Preferencia escolhida pelo usuario para executar a inferencia."""

    GPU = "gpu"
    CPU = "cpu"

    @classmethod
    def from_value(cls, value: str | None) -> "DevicePreference":
        return cls.CPU if (value or "").strip().lower() == cls.CPU.value else cls.GPU


class ActiveDevice(str, Enum):
    GPU = "gpu"
    CPU = "cpu"


class RuntimeProvider(str, Enum):
    """Provedores que um motor pode usar no Windows."""

    CUDA = "cuda"
    DIRECTML = "directml"
    WINML = "winml"
    ROCM = "rocm"
    CPU = "cpu"
    UNKNOWN = "unknown"


class FallbackReason(str, Enum):
    ACCELERATOR_NOT_FOUND = "accelerator_not_found"
    UNSUPPORTED_GRAPHICS_VENDOR = "unsupported_graphics_vendor"
    NVIDIA_DRIVER_UNAVAILABLE = "nvidia_driver_unavailable"
    CUDA_LIBRARIES_MISSING = "cuda_libraries_missing"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    INITIALIZATION_FAILED = "initialization_failed"


@dataclass(frozen=True)
class RuntimeStatus:
    """Estado efetivo da inferencia, independente do motor utilizado."""

    preference: DevicePreference
    active_device: ActiveDevice
    engine: str
    provider: RuntimeProvider
    compute_type: Optional[str] = None
    fallback_reason: Optional[FallbackReason] = None

    @property
    def is_fallback(self) -> bool:
        return self.preference == DevicePreference.GPU and self.active_device == ActiveDevice.CPU

    @property
    def display_label(self) -> str:
        if self.active_device == ActiveDevice.GPU:
            return f"GPU · {self.provider.value.upper()}"
        if self.is_fallback:
            return "CPU · fallback"
        return "CPU"

    @property
    def user_message(self) -> str:
        if self.active_device == ActiveDevice.GPU:
            return "Transcricao carregada na GPU."
        if self.fallback_reason == FallbackReason.ACCELERATOR_NOT_FOUND:
            return "GPU compativel nao encontrada. A sessao esta usando CPU."
        if self.fallback_reason == FallbackReason.UNSUPPORTED_GRAPHICS_VENDOR:
            return (
                "Uma GPU AMD ou Intel foi detectada, mas o motor atual acelera "
                "somente em NVIDIA. A sessao esta usando CPU."
            )
        if self.fallback_reason == FallbackReason.NVIDIA_DRIVER_UNAVAILABLE:
            return (
                "Uma GPU NVIDIA foi detectada, mas o driver nao disponibilizou "
                "CUDA para o motor atual. A sessao esta usando CPU."
            )
        if self.fallback_reason == FallbackReason.CUDA_LIBRARIES_MISSING:
            return (
                "Os componentes de aceleracao NVIDIA nao estao disponiveis. "
                "A sessao esta usando CPU."
            )
        if self.fallback_reason == FallbackReason.RUNTIME_UNAVAILABLE:
            return "O suporte de GPU nao esta disponivel. A sessao esta usando CPU."
        if self.fallback_reason == FallbackReason.INITIALIZATION_FAILED:
            return "A GPU nao pode ser inicializada. A sessao esta usando CPU."
        return "Transcricao carregada na CPU por escolha do usuario."

    @property
    def tooltip(self) -> str:
        if self.active_device == ActiveDevice.GPU:
            compute = f" com computacao {self.compute_type}" if self.compute_type else ""
            return (
                f"Dispositivo ativo: GPU. Provedor: {self.provider.value.upper()}{compute}."
            )
        return self.user_message
