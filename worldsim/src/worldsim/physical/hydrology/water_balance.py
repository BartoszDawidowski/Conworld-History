"""Shared rain/snow partition and soil-bucket helpers (CR-7 / G0)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def partition_rain_snow(
    precip: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    *,
    snow_threshold_c: float = 0.0,
    snow_band_c: float = 2.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Soft partition of precipitation into rain and snowfall."""
    p = np.maximum(np.asarray(precip, dtype=np.float64), 0.0)
    t = np.asarray(temperature_c, dtype=np.float64)
    band = max(float(snow_band_c), 1e-6)
    snow_frac = np.clip((float(snow_threshold_c) + band - t) / (2.0 * band), 0.0, 1.0)
    snow = p * snow_frac
    rain = p - snow
    return rain, snow


def holdridge_pet_proxy(
    temperature_c: NDArray[np.floating],
    *,
    precip_scale_mm: float,
    pet_year_fraction: float,
) -> NDArray[np.float64]:
    """Monthly Holdridge PET in the same proxy units as precipitation."""
    bio = np.clip(np.asarray(temperature_c, dtype=np.float64), 0.0, 30.0)
    pet_mm = 58.93 * bio * max(float(pet_year_fraction), 0.0)
    return pet_mm / max(float(precip_scale_mm), 1e-6)


def soil_step(
    store: NDArray[np.floating],
    water_in: NDArray[np.floating],
    pet_proxy: NDArray[np.floating],
    *,
    capacity: float,
    quickflow_frac: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """One monthly soil bucket: return ``(new_store, runoff, et)``."""
    s = np.maximum(np.asarray(store, dtype=np.float64), 0.0)
    available = np.maximum(np.asarray(water_in, dtype=np.float64), 0.0)
    pet = np.maximum(np.asarray(pet_proxy, dtype=np.float64), 0.0)
    cap = max(float(capacity), 0.0)
    quick_frac = float(np.clip(quickflow_frac, 0.0, 1.0))
    quick = quick_frac * available
    infil = available - quick
    s = s + infil
    et = np.minimum(s, pet)
    s = s - et
    if cap <= 0.0:
        overflow = s
        s = np.zeros_like(s)
    else:
        overflow = np.maximum(s - cap, 0.0)
        s = np.minimum(s, cap)
    runoff = quick + overflow
    return s, runoff, et
