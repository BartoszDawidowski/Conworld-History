"""Monthly runoff with rain/snow partition, snow store, and a soil bucket (CR-7)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.transmission import month_pet_fraction


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


def build_monthly_runoff(
    *,
    precipitation: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    snow_threshold_c: float = 0.0,
    snow_band_c: float = 2.0,
    melt_factor_per_c: float = 0.08,
    max_snow_store: float = 40.0,
    precip_scale_mm: float = 200.0,
    soil_capacity: float = 1.0,
    soil_quickflow_frac: float = 0.20,
) -> dict[str, NDArray[np.float64] | dict[str, Any]]:
    """Monthly runoff after snow store and a shared soil bucket (ET before Q).

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
    soil_et = np.zeros_like(precip)
    residual_pet = np.zeros_like(precip)
    store_out = np.zeros_like(precip)
    soil_out = np.zeros((h, w), dtype=np.float64)
    store = np.zeros((h, w), dtype=np.float64)
    soil = np.zeros((h, w), dtype=np.float64)

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
        pet = holdridge_pet_proxy(
            temp[m],
            precip_scale_mm=precip_scale_mm,
            pet_year_fraction=month_pet_fraction(m),
        )
        pet = np.where(ocean, 0.0, pet)
        soil, q_run, et = soil_step(
            soil,
            r + mlt,
            pet,
            capacity=soil_capacity,
            quickflow_frac=soil_quickflow_frac,
        )
        soil = np.where(ocean, 0.0, soil)
        q_run = np.where(ocean, 0.0, q_run)
        et = np.where(ocean, 0.0, et)
        rain[m] = r
        snow[m] = s
        melt[m] = mlt
        runoff[m] = q_run
        soil_et[m] = et
        residual_pet[m] = np.maximum(pet - et, 0.0)
        store_out[m] = store

    soil_out = soil
    diag = {
        "runoff_algorithm": "soil_bucket_v1",
        "snow_threshold_c": float(snow_threshold_c),
        "melt_factor_per_c": float(melt_factor_per_c),
        "max_snow_store": float(max_snow_store),
        "soil_capacity": float(soil_capacity),
        "soil_quickflow_frac": float(soil_quickflow_frac),
        "annual_rain_sum": float(np.sum(rain)),
        "annual_snow_sum": float(np.sum(snow)),
        "annual_melt_sum": float(np.sum(melt)),
        "annual_runoff_sum": float(np.sum(runoff)),
        "annual_soil_et_sum": float(np.sum(soil_et)),
        "final_snow_store_sum": float(np.sum(store)),
        "final_soil_store_sum": float(np.sum(soil_out)),
    }
    return {
        "rain": rain,
        "snowfall": snow,
        "melt": melt,
        "runoff": runoff,
        "soil_et": soil_et,
        "residual_pet": residual_pet,
        "snow_store": store_out,
        "soil_store": soil_out,
        "diagnostics": diag,
    }
