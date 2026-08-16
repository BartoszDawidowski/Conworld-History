"""Runtime path helpers for frozen (PyInstaller) and editable installs."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def meipass_dir() -> Path | None:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return None


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """Resolve a data file bundled next to the package or inside the freeze root."""
    rel = Path(*parts)
    if is_frozen():
        base = meipass_dir()
        assert base is not None
        candidate = base / rel
        if candidate.is_file() or candidate.is_dir():
            return candidate
        side = executable_dir() / rel
        if side.is_file() or side.is_dir():
            return side
        return candidate
    # Editable / wheel: worldsim/configs lives beside src/
    pkg_root = Path(__file__).resolve().parents[2]
    return pkg_root / rel
