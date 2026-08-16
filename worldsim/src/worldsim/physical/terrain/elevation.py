"""Elevation unit conversion to metres relative to calibrated sea level."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def raw_to_elevation_m(
    elevation_raw: NDArray[np.floating],
    sea_level_raw: float,
    *,
    land_scale_m: float = 6000.0,
    ocean_scale_m: float = 5000.0,
) -> NDArray[np.float64]:
    """Map raw tectonic elevation to metres with sea level at 0.

    Empirical linear mapping: land positive up to ~``land_scale_m``, ocean
    negative down to ~``-ocean_scale_m`` before bathymetric reshaping.
    """
    elev = np.asarray(elevation_raw, dtype=np.float64)
    centered = elev - float(sea_level_raw)
    land = centered >= 0.0
    out = np.empty_like(elev)
    land_max = float(np.max(centered[land])) if np.any(land) else 1.0
    ocean_min = float(np.min(centered[~land])) if np.any(~land) else -1.0
    if land_max <= 1e-12:
        land_max = 1.0
    if ocean_min >= -1e-12:
        ocean_min = -1.0
    out[land] = centered[land] / land_max * land_scale_m
    out[~land] = centered[~land] / abs(ocean_min) * ocean_scale_m
    return out
