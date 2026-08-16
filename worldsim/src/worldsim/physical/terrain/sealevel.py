"""Sea-level calibration against an Earth-like ocean-fraction target."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def calibrate_sea_level(
    elevation: NDArray[np.floating],
    *,
    ocean_fraction_target: float = 0.71,
) -> float:
    """Return elevation threshold such that ``P(elev < thr) ≈ target``.

    Does not hardcode a Platec internal sea-level parameter as final sea level.
    """
    if not 0.0 < ocean_fraction_target < 1.0:
        raise ValueError("ocean_fraction_target must be in (0, 1)")
    elev = np.asarray(elevation, dtype=np.float64).ravel()
    return float(np.quantile(elev, ocean_fraction_target))


def ocean_mask_from_sea_level(
    elevation: NDArray[np.floating],
    sea_level: float,
) -> NDArray[np.bool_]:
    return np.asarray(elevation, dtype=np.float64) < float(sea_level)


def measured_ocean_fraction(ocean_mask: NDArray[np.bool_]) -> float:
    return float(np.mean(np.asarray(ocean_mask, dtype=np.bool_)))
