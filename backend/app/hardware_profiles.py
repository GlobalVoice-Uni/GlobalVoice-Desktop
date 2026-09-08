from dataclasses import dataclass
from enum import Enum
import os

from .runtime_status import RuntimeProvider


DISPLAY_ADAPTER_CLASS_GUID = "{4D36E968-E325-11CE-BFC1-08002BE10318}"
PCI_VENDOR_IDS = {
    "VEN_10DE": "nvidia",
    "VEN_1002": "amd",
    "VEN_8086": "intel",
}


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


def graphics_vendor_from_device_id(device_id: str) -> GraphicsVendor:
    normalized = (device_id or "").upper()
    for vendor_id, vendor_name in PCI_VENDOR_IDS.items():
        if vendor_id in normalized:
            return GraphicsVendor(vendor_name)
    return GraphicsVendor.UNKNOWN


def _clean_device_name(value: str, fallback: str) -> str:
    name = (value or "").split(";")[-1].strip()
    return name or fallback


def detect_windows_graphics_adapters() -> tuple[GraphicsAdapter, ...]:
    """Le adaptadores PCI no Registro sem depender de um runtime de inferencia."""
    if os.name != "nt":
        return ()

    try:
        import winreg

        pci_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Enum\PCI",
        )
    except (ImportError, OSError):
        return ()

    adapters: list[GraphicsAdapter] = []
    try:
        device_index = 0
        while True:
            try:
                device_key_name = winreg.EnumKey(pci_key, device_index)
            except OSError:
                break
            device_index += 1

            vendor = graphics_vendor_from_device_id(device_key_name)
            if vendor == GraphicsVendor.UNKNOWN:
                continue

            try:
                device_key = winreg.OpenKey(pci_key, device_key_name)
            except OSError:
                continue

            with device_key:
                instance_index = 0
                while True:
                    try:
                        instance_key_name = winreg.EnumKey(device_key, instance_index)
                    except OSError:
                        break
                    instance_index += 1

                    try:
                        instance_key = winreg.OpenKey(device_key, instance_key_name)
                    except OSError:
                        continue

                    with instance_key:
                        try:
                            class_guid = str(
                                winreg.QueryValueEx(instance_key, "ClassGUID")[0]
                            )
                        except OSError:
                            continue
                        if class_guid.upper() != DISPLAY_ADAPTER_CLASS_GUID.upper():
                            continue

                        name = "Adaptador grafico"
                        for value_name in ("FriendlyName", "DeviceDesc"):
                            try:
                                value = str(winreg.QueryValueEx(instance_key, value_name)[0])
                            except OSError:
                                continue
                            name = _clean_device_name(value, name)
                            break

                        adapters.append(
                            GraphicsAdapter(
                                name=name,
                                vendor=vendor,
                                device_id=f"{device_key_name}\\{instance_key_name}",
                            )
                        )
    finally:
        pci_key.Close()

    unique: dict[str, GraphicsAdapter] = {}
    for adapter in adapters:
        unique[adapter.device_id or adapter.name] = adapter
    return tuple(unique.values())
