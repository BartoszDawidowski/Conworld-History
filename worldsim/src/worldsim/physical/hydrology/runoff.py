"""Monthly runoff with rain/snow partition and a bounded snow store (PR-6)."""

from __future__ import annotations

from typing import Any

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
    # 1 below (threshold - band), 0 above (threshold + band)
    snow_frac = np.clip((float(snow_threshold_c) + band - t) / (2.0 * band), 0.0, 1.0)
    snow = p * snow_frac
    rain = p - snow
    return rain, snow


def snow_step(
    store: NDArray[np.floating],
    snowfall: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    *,
    melt_factor_per_c: float = 0.08,
    max_store: float = 40.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Update snow store; return ``(new_store, melt)``."""
    s = np.maximum(np.asarray(store, dtype=np.float64), 0.0)
    s = s + np.maximum(np.asarray(snowfall, dtype=np.float64), 0.0)
    t = np.asarray(temperature_c, dtype=np.float64)
    potential = np.maximum(t, 0.0) * float(melt_factor_per_c)
    melt = np.minimum(s, potential)
    s = np.minimum(np.maximum(s - melt, 0.0), float(max_store))
    return s, melt


def build_monthly_runoff(
    *,
    precipitation: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    snow_threshold_c: float = 0.0,
    snow_band_c: float = 2.0,
    melt_factor_per_c: float = 0.08,
    max_snow_store: float = 40.0,
) -> dict[str, NDArray[np.float64] | dict[str, Any]]:
    """Monthly runoff = rain + melt; carries a bounded snow store across months.

    Shapes: precip/temp ``[months, y, x]`` (temp may be ``[y, x]`` → broadcast).
    """
    precip = np.asarray(precipitation, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if precip.ndim != 3:
        raise ValueError("precipitation must be [months, y, x]")
    n, h, w = precip.shape
    if temperature_c.ndim == 2:
        temp = np.broadcast_to(
            np.asarray(temperature_c, dtype=np.float64), (n, h, w)
        ).copy()
    else:
        temp = np.asarray(temperature_c, dtype=np.float64)
        if temp.shape != precip.shape:
            raise ValueError("temperature_c shape mismatch")

    rain = np.zeros_like(precip)
    snow = np.zeros_like(precip)
    melt = np.zeros_like(precip)
    runoff = np.zeros_like(precip)
    store_out = np.zeros_like(precip)
    store = np.zeros((h, w), dtype=np.float64)

    for m in range(n):
        r, s = partition_rain_snow(
            precip[m],
            temp[m],
            snow_threshold_c=snow_threshold_c,
            snow_band_c=snow_band_c,
        )
        r = np.where(ocean, 0.0, r)
        s = np.where(ocean, 0.0, s)
        store, mlt = snow_step(
            store,
            s,
            temp[m],
            melt_factor_per_c=melt_factor_per_c,
            max_store=max_snow_store,
        )
        store = np.where(ocean, 0.0, store)
        mlt = np.where(ocean, 0.0, mlt)
        rain[m] = r
        snow[m] = s
        melt[m] = mlt
        runoff[m] = r + mlt
        store_out[m] = store

    diag = {
        "runoff_algorithm": "rain_snow_store_v1",
        "snow_threshold_c": float(snow_threshold_c),
        "melt_factor_per_c": float(melt_factor_per_c),
        "max_snow_store": float(max_snow_store),
        "annual_rain_sum": float(np.sum(rain)),
        "annual_snow_sum": float(np.sum(snow)),
        "annual_melt_sum": float(np.sum(melt)),
        "annual_runoff_sum": float(np.sum(runoff)),
        "final_snow_store_sum": float(np.sum(store)),
    }
    return {
        "rain": rain,
        "snowfall": snow,
        "melt": melt,
        "runoff": runoff,
        "snow_store": store_out,
        "diagnostics": diag,
    }
