from dataclasses import dataclass
from enum import Enum

from .runtime_status import RuntimeProvider


class GraphicsVendor(str, Enum):
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GraphicsAdapter:
    """Descricao de hardware coletada sem depender do motor de inferencia."""

    name: str
    vendor: GraphicsVendor
    driver_version: str | None = None
    device_id: str | None = None
    is_integrated: bool | None = None


@dataclass(frozen=True)
class HardwareProfile:
    graphics_adapters: tuple[GraphicsAdapter, ...] = ()


@dataclass(frozen=True)
class RuntimeProfile:
    """Pacote de aceleracao selecionavel pelo futuro instalador."""

    profile_id: str
    engine: str
    provider: RuntimeProvider
    supported_vendors: tuple[GraphicsVendor, ...]
    runtime_family: str

    def supports(self, adapter: GraphicsAdapter) -> bool:
        return adapter.vendor in self.supported_vendors
