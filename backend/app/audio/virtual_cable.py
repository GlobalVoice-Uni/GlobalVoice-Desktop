"""Descoberta da rota de chamada pelo VB-CABLE instalado no Windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import ExitStack
import configparser
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import platform
import sys
import urllib.request
from zipfile import ZipFile

from .devices import AudioDeviceCatalog, AudioDeviceInfo, AudioDeviceKind


VB_CABLE_PAGE = "https://vb-audio.com/Cable/"
VB_CABLE_LICENSE = "https://vb-audio.com/Services/licensing.htm"
VB_CABLE_DOWNLOAD = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"
VB_CABLE_SHA256 = "b950e39f01af1d04ea623c8f6d8eb9b6ea5c477c637295fabf20631c85116bfb"


@dataclass(frozen=True)
class VirtualCableRoute:
    render: AudioDeviceInfo  # CABLE Input: saída em que o aplicativo reproduz
    capture: AudioDeviceInfo  # CABLE Output: microfone escolhido na chamada


def is_vb_cable_render_device(device: AudioDeviceInfo | None) -> bool:
    return bool(
        device
        and device.name.casefold().startswith("cable input")
        and "vb-audio" in device.name.casefold()
    )


def _driver_device_present() -> bool:
    """Consulta a instância PnP, pois a chave do serviço persiste após remoção."""
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\VBAudioVACMME\Enum",
        ) as key:
            return int(winreg.QueryValueEx(key, "Count")[0]) > 0
    except (OSError, TypeError, ValueError):
        return False


def _restart_markers() -> tuple[Path, ...]:
    markers = []
    if getattr(sys, "frozen", False):
        markers.append(Path(sys.executable).parent / "installation.ini")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        markers.append(Path(local) / "GlobalVoice" / "vb-cable-restart.txt")
    return tuple(markers)


def _restart_requested_at(path: Path) -> datetime | None:
    try:
        if path.suffix.casefold() == ".ini":
            config = configparser.ConfigParser()
            config.read(path, encoding="utf-8")
            raw = config.get("VirtualCable", "RestartRequestedAt", fallback="")
        else:
            raw = path.read_text(encoding="utf-8").strip()
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except (OSError, UnicodeError, ValueError, configparser.Error):
        return None


def _restart_pending() -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    boot_time = datetime.now() - timedelta(milliseconds=kernel32.GetTickCount64())
    return any(
        requested is not None and requested > boot_time
        for requested in map(_restart_requested_at, _restart_markers())
    )


def _cable_endpoints_ready(route: VirtualCableRoute) -> bool:
    """Confirma que as duas pontas abrem, sem iniciar captura ou reprodução."""
    try:
        import sounddevice as sd

        render_id = int(route.render.id)
        capture_id = int(route.capture.id)
        render_rate = int(sd.query_devices(render_id, kind="output")["default_samplerate"])
        capture_rate = int(sd.query_devices(capture_id, kind="input")["default_samplerate"])
        with ExitStack() as streams:
            render = sd.RawOutputStream(
                device=render_id, samplerate=render_rate, channels=2,
            )
            streams.callback(render.close)
            capture = sd.RawInputStream(
                device=capture_id, samplerate=capture_rate, channels=2,
            )
            streams.callback(capture.close)
        return True
    except Exception:
        return False


def vb_cable_status(catalog: AudioDeviceCatalog) -> str:
    """Retorna available, restart_required, incomplete ou not_installed."""
    route = find_vb_cable(catalog)
    if _restart_pending():
        if route is None or not _cable_endpoints_ready(route):
            return "restart_required"
    if route is not None:
        return "available"
    if _driver_device_present():
        return "incomplete"
    return "not_installed"


def mark_vb_cable_restart_pending() -> None:
    """Guarda a tentativa iniciada dentro do aplicativo para o boot atual."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return
    path = Path(local) / "GlobalVoice" / "vb-cable-restart.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")


def bundled_vb_cable_setup() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "drivers" / "VB-CABLE" / "VBCABLE_Setup_x64.exe"
    return Path(__file__).resolve().parents[3] / ".build" / "VBCABLE_Driver_Pack45" / "VBCABLE_Setup_x64.exe"


def install_bundled_vb_cable() -> None:
    """Instala em segundo plano pelo pacote incluído ou baixado da VB-Audio."""
    if os.name != "nt":
        raise OSError("O microfone virtual requer Windows.")
    setup = bundled_vb_cable_setup()
    if not setup.is_file():
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        setup = prepare_vb_cable_setup(local / "GlobalVoice" / "drivers" / "VB-CABLE")

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = str(setup)
    info.lpParameters = "-i -h"
    info.lpDirectory = str(setup.parent)
    info.nShow = 0
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:
            raise OSError("A autorização do Windows para instalar o VB-CABLE foi cancelada.")
        raise ctypes.WinError(error)
    try:
        if kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF) != 0:
            raise OSError("Não foi possível aguardar a instalação do VB-CABLE.")
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if exit_code.value not in (0, 3010):
            raise OSError(f"A instalação do VB-CABLE falhou (código {exit_code.value}).")
    finally:
        kernel32.CloseHandle(info.hProcess)
    mark_vb_cable_restart_pending()


def find_vb_cable(catalog: AudioDeviceCatalog) -> VirtualCableRoute | None:
    """Seleciona o cabo original, preferindo WASAPI às cópias MME/DirectSound."""

    def matching(kind: AudioDeviceKind, prefix: str) -> list[AudioDeviceInfo]:
        return sorted(
            (
                device for device in catalog.of_kind(kind)
                if device.name.casefold().startswith(prefix)
                and "vb-audio" in device.name.casefold()
            ),
            key=lambda device: (
                "wasapi" not in device.backend.casefold(),
                device.name.casefold(),
            ),
        )

    render = matching(AudioDeviceKind.OUTPUT, "cable input")
    capture = matching(AudioDeviceKind.INPUT, "cable output")
    if not render or not capture:
        return None
    return VirtualCableRoute(render[0], capture[0])


def prepare_vb_cable_setup(
    destination: Path,
    on_progress=None,
    *,
    url: str = VB_CABLE_DOWNLOAD,
    expected_sha256: str = VB_CABLE_SHA256,
) -> Path:
    """Baixa o pacote oficial e extrai somente os arquivos verificados do fornecedor."""

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "VBCABLE_Driver_Pack45.zip"
    temporary = destination / "VBCABLE_Driver_Pack45.zip.download"
    if not archive.is_file() or _sha256(archive) != expected_sha256:
        try:
            with urllib.request.urlopen(url, timeout=30) as response, temporary.open("wb") as output:
                total = int(response.headers.get("Content-Length", 0))
                written = 0
                while chunk := response.read(65536):
                    output.write(chunk)
                    written += len(chunk)
                    if on_progress and total:
                        on_progress(min(99, int(written * 100 / total)))
            if _sha256(temporary) != expected_sha256:
                raise ValueError("O pacote do VB-CABLE mudou ou falhou na verificação SHA-256.")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)

    setup_name = (
        "VBCABLE_Setup_x64.exe"
        if platform.machine().casefold() in {"amd64", "x86_64", "arm64", "aarch64"}
        else "VBCABLE_Setup.exe"
    )
    with ZipFile(archive) as package:
        members = {item.filename: item for item in package.infolist()}
        if setup_name not in members:
            raise ValueError("O pacote oficial não contém o instalador esperado.")
        # O setup procura os arquivos do driver no mesmo diretório.
        for filename, member in members.items():
            if member.is_dir():
                continue
            if Path(filename).name != filename or filename in {".", ".."}:
                raise ValueError("O pacote contém um caminho inesperado.")
            (destination / filename).write_bytes(package.read(member))
    if on_progress:
        on_progress(100)
    return destination / setup_name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def launch_vb_cable_setup(setup: Path) -> None:
    """Abre o instalador assinado do fornecedor com elevação explícita do Windows."""

    if os.name != "nt":
        raise OSError("O instalador do VB-CABLE está disponível somente no Windows.")
    os.startfile(str(setup), "runas")
