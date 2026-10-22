"""Versão exibida pela aplicação, lida da instalação quando disponível."""

from __future__ import annotations

import configparser
import sys
from pathlib import Path


DEVELOPMENT_VERSION = "0.4.1"


def app_version(installation_file: Path | None = None) -> str:
    if installation_file is None:
        if not getattr(sys, "frozen", False):
            return DEVELOPMENT_VERSION
        installation_file = Path(sys.executable).parent / "installation.ini"
    parser = configparser.ConfigParser()
    try:
        parser.read(installation_file, encoding="utf-8")
        value = parser.get("App", "Version", fallback="").strip()
    except (OSError, UnicodeError, configparser.Error):
        value = ""
    return value if value and all(part.isdigit() for part in value.split(".")) else DEVELOPMENT_VERSION
