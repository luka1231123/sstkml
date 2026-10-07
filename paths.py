"""Writable player data stays outside a packaged application."""
import os
import sys
from pathlib import Path


def data_root() -> Path:
    if directory := os.environ.get("STTKML_DATA_DIR"):
        return Path(directory).expanduser()
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Say To The King"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Say To The King"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "say-to-the-king"


SAVES = data_root() / "saves"
