"""Absolute-scale diagnostic maps (stable legends; not min–max stretch)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.export.pngutil import write_png_rgb


def _scalar_to_rgb(
    field: NDArray[np.floating],
    *,
    lo: float,
    hi: float,
    ocean_mask: NDArray[np.bool_] | None = None,
    ocean_rgb: tuple[int, int, int] = (20, 40, 70),
) -> NDArray[np.uint8]:
    arr = np.asarray(field, dtype=np.float64)
    t = np.clip((arr - lo) / max(hi - lo, 1e-12), 0.0, 1.0)
    # Magma-ish: dark → yellow (deterministic, no matplotlib dependency)
    r = (np.clip(1.2 * t, 0.0, 1.0) * 255).astype(np.uint8)
    g = (np.clip(t * t * 1.1, 0.0, 1.0) * 200).astype(np.uint8)
    b = (np.clip(0.35 + 0.65 * (1.0 - t), 0.0, 1.0) * 255).astype(np.uint8)
    rgb = np.stack([r, g, b], axis=-1)
    if ocean_mask is not None:
        ocean = np.asarray(ocean_mask, dtype=bool)
        rgb[ocean] = np.asarray(ocean_rgb, dtype=np.uint8)
    return rgb


def write_absolute_scalar_png(
    path: Path,
    field: NDArray[np.floating],
    *,
    lo: float,
    hi: float,
    unit: str,
    ocean_mask: NDArray[np.bool_] | None = None,
    legend_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write PNG + sidecar JSON describing the absolute colour scale."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = _scalar_to_rgb(field, lo=lo, hi=hi, ocean_mask=ocean_mask)
    write_png_rgb(path, rgb)
    meta: dict[str, Any] = {
        "path": str(path.name),
        "lo": float(lo),
        "hi": float(hi),
        "unit": unit,
        "shape": list(np.asarray(field).shape),
        "stretch": "absolute",
    }
    if legend_extra:
        meta.update(legend_extra)
    side = path.with_suffix(path.suffix + ".legend.json")
    side.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta
