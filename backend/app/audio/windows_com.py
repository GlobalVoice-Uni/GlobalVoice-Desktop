"""Inicialização de COM exigida pelo WASAPI em cada thread que o utiliza."""

from __future__ import annotations

import ctypes
import sys
from contextlib import contextmanager


RPC_E_CHANGED_MODE = -2147417850


@contextmanager
def windows_com_initialized():
    if sys.platform != "win32":
        yield
        return

    ole32 = ctypes.windll.ole32
    result = ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
    if result not in (0, 1, RPC_E_CHANGED_MODE):
        raise OSError(f"Não foi possível inicializar COM: 0x{result & 0xffffffff:08X}")
    owns_initialization = result in (0, 1)
    try:
        yield
    finally:
        if owns_initialization:
            ole32.CoUninitialize()
