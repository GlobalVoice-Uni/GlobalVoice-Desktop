import ctypes
import os
import platform
import sys
from ctypes import wintypes
from importlib.metadata import PackageNotFoundError, version
from typing import Any


def process_rss_mb() -> float | None:
    """Le o working set do processo no Windows sem adicionar dependencias."""
    if platform.system() != "Windows":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    success = get_process_memory_info(
        ctypes.windll.kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    )
    if not success:
        return None
    return round(counters.WorkingSetSize / (1024 * 1024), 3)


def collect_environment() -> dict[str, Any]:
    """Registra informacoes suficientes para contextualizar a medicao."""
    environment: dict[str, Any] = {
        "operating_system": platform.platform(),
        "python": sys.version.split()[0],
        "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER"),
        "logical_cpu_count": os.cpu_count(),
        "packages": {},
    }

    for package in ("faster-whisper", "ctranslate2", "numpy", "scipy"):
        try:
            environment["packages"][package] = version(package)
        except PackageNotFoundError:
            environment["packages"][package] = None

    try:
        import torch

        environment.update(
            {
                "torch": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "torch_cuda": torch.version.cuda,
                "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            }
        )
    except ImportError:
        environment["torch"] = None

    return environment
