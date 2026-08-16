"""Biotemperature and PET ratio for Holdridge (Milestone 14 / Stage N)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def annual_biotemperature_c(
    temperature_c: NDArray[np.floating],
    *,
    cap_c: float = 30.0,
) -> NDArray[np.float64]:
    """Holdridge biotemperature: mean of monthly temps clamped to [0, cap].

    ``temperature_c`` shape ``[months, y, x]``.
    """
    t = np.asarray(temperature_c, dtype=np.float64)
    clamped = np.clip(t, 0.0, float(cap_c))
    return clamped.mean(axis=0)


def holdridge_pet_mm(
    biotemperature_c: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Holdridge potential evapotranspiration (mm/yr) ≈ 58.93 × biotemp."""
    bio = np.asarray(biotemperature_c, dtype=np.float64)
    return 58.93 * bio


def pet_ratio(
    *,
    biotemperature_c: NDArray[np.floating],
    annual_precipitation: NDArray[np.floating],
    precip_scale_mm: float = 200.0,
) -> NDArray[np.float64]:
    """PET / precipitation. Precipitation is a model proxy → scaled to mm-like units."""
    pet = holdridge_pet_mm(biotemperature_c)
    # annual_precipitation from moisture stage is a proxy; scale to plausible mm
    precip = np.maximum(np.asarray(annual_precipitation, dtype=np.float64), 0.0)
    precip_mm = precip * float(precip_scale_mm)
    return pet / np.maximum(precip_mm, 1.0)
