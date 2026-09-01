import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


CUDA_LIBRARY_NAMES = (
    "cublasLt64_12.dll",
    "cublas64_12.dll",
)

_LOADED_LIBRARY_HANDLES: list[object] = []
_DLL_DIRECTORY_HANDLES: list[object] = []


@dataclass(frozen=True)
class CudaRuntimeCheck:
    available: bool
    source_directory: Optional[Path] = None


def _candidate_directories() -> tuple[Path, ...]:
    candidates: list[Path] = []

    configured = os.environ.get("GLOBALVOICE_CUDA_RUNTIME")
    if configured:
        candidates.append(Path(configured))

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates.append(Path(frozen_root))

    # Compatibilidade com o ambiente de desenvolvimento anterior. O aplicativo
    # empacotado nao depende do PyTorch CUDA; ele recebe um perfil proprio.
    candidates.append(Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib")

    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def _load_from_directory(directory: Path) -> bool:
    if not all((directory / name).is_file() for name in CUDA_LIBRARY_NAMES):
        return False

    directory_handle = None
    try:
        if hasattr(os, "add_dll_directory"):
            directory_handle = os.add_dll_directory(str(directory))
        handles = [ctypes.WinDLL(str(directory / name)) for name in CUDA_LIBRARY_NAMES]
    except (OSError, AttributeError):
        if directory_handle is not None:
            directory_handle.close()
        return False

    if directory_handle is not None:
        _DLL_DIRECTORY_HANDLES.append(directory_handle)
    _LOADED_LIBRARY_HANDLES.extend(handles)
    return True


def _load_from_system() -> bool:
    try:
        handles = [ctypes.WinDLL(name) for name in CUDA_LIBRARY_NAMES]
    except (OSError, AttributeError):
        return False

    _LOADED_LIBRARY_HANDLES.extend(handles)
    return True


def prepare_cuda_runtime(
    search_directories: Optional[Iterable[Path]] = None,
) -> CudaRuntimeCheck:
    """Carrega somente as bibliotecas CUDA exigidas pelo CTranslate2 no Windows."""
    if os.name != "nt":
        return CudaRuntimeCheck(available=True)

    directories = tuple(search_directories or _candidate_directories())
    for directory in directories:
        if _load_from_directory(directory):
            return CudaRuntimeCheck(available=True, source_directory=directory)

    if _load_from_system():
        return CudaRuntimeCheck(available=True)
    return CudaRuntimeCheck(available=False)
