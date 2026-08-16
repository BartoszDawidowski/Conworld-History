"""DEM conditioning helpers for PyFlwDir (Milestone 11)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

NODATA = -9999.0


def dem_for_flow(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    nodata: float = NODATA,
) -> NDArray[np.float64]:
    """Land elevations with ocean set to ``nodata`` (coastal outlets)."""
    elev = np.asarray(elevation_m, dtype=np.float64).copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    elev[ocean] = float(nodata)
    return elev


def ew_pad(
    array: NDArray,
    pad: int,
) -> NDArray:
    """Pad array in X by wrapping columns (cylindrical E–W)."""
    if pad <= 0:
        return np.asarray(array)
    a = np.asarray(array)
    return np.concatenate([a[:, -pad:], a, a[:, :pad]], axis=1)


def ew_crop(
    array: NDArray,
    pad: int,
    width: int,
) -> NDArray:
    """Crop a previously E–W-padded array back to ``width`` columns."""
    if pad <= 0:
        return np.asarray(array)
    a = np.asarray(array)
    return a[:, pad : pad + width].copy()


def wrap_pad_cells(width: int) -> int:
    """Padding width for E–W wrap (bounded for small test grids)."""
    return int(np.clip(width // 8, 2, 64))
