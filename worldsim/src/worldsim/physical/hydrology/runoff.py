"""Monthly runoff with rain/snow partition, snow store, and a soil bucket (CR-7)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.transmission import month_pet_fraction
from worldsim.physical.hydrology.water_balance import (
    holdridge_pet_proxy,
    partition_rain_snow,
    soil_step,
)


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


def _rel_field_delta(a: NDArray[np.floating], b: NDArray[np.floating]) -> float:
    """Mean absolute relative change of two fields."""
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    denom = max(float(np.mean(np.abs(aa))), 1e-12)
    return float(np.mean(np.abs(aa - bb))) / denom


def _simulate_runoff_year(
    *,
    precip: NDArray[np.float64],
    temp: NDArray[np.float64],
    ocean: NDArray[np.bool_],
    store: NDArray[np.float64],
    soil: NDArray[np.float64],
    snow_threshold_c: float,
    snow_band_c: float,
    melt_factor_per_c: float,
    max_snow_store: float,
    precip_scale_mm: float,
    soil_capacity: float,
    soil_quickflow_frac: float,
) -> dict[str, NDArray[np.float64]]:
    n = int(precip.shape[0])
    rain = np.zeros_like(precip)
    snow = np.zeros_like(precip)
    melt = np.zeros_like(precip)
    runoff = np.zeros_like(precip)
    soil_et = np.zeros_like(precip)
    residual_pet = np.zeros_like(precip)
    store_out = np.zeros_like(precip)
    soil_monthly = np.zeros_like(precip)
    snow_state = np.asarray(store, dtype=np.float64).copy()
    soil_state = np.asarray(soil, dtype=np.float64).copy()
    for m in range(n):
        r, s = partition_rain_snow(
            precip[m],
            temp[m],
            snow_threshold_c=snow_threshold_c,
            snow_band_c=snow_band_c,
        )
        r = np.where(ocean, 0.0, r)
        s = np.where(ocean, 0.0, s)
        snow_state, mlt = snow_step(
            snow_state,
            s,
            temp[m],
            melt_factor_per_c=melt_factor_per_c,
            max_store=max_snow_store,
        )
        snow_state = np.where(ocean, 0.0, snow_state)
        mlt = np.where(ocean, 0.0, mlt)
        pet = holdridge_pet_proxy(
            temp[m],
            precip_scale_mm=precip_scale_mm,
            pet_year_fraction=month_pet_fraction(m),
        )
        pet = np.where(ocean, 0.0, pet)
        soil_state, q_run, et = soil_step(
            soil_state,
            r + mlt,
            pet,
            capacity=soil_capacity,
            quickflow_frac=soil_quickflow_frac,
        )
        soil_state = np.where(ocean, 0.0, soil_state)
        q_run = np.where(ocean, 0.0, q_run)
        et = np.where(ocean, 0.0, et)
        rain[m] = r
        snow[m] = s
        melt[m] = mlt
        runoff[m] = q_run
        soil_et[m] = et
        residual_pet[m] = np.maximum(pet - et, 0.0)
        store_out[m] = snow_state
        soil_monthly[m] = soil_state
    return {
        "rain": rain,
        "snowfall": snow,
        "melt": melt,
        "runoff": runoff,
        "soil_et": soil_et,
        "residual_pet": residual_pet,
        "snow_store": store_out,
        "soil_store": soil_state,
        "soil_store_monthly": soil_monthly,
        "snow_store_end": snow_state,
    }


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
    spinup_years: int = 8,
    spinup_rel_tol: float = 0.01,
) -> dict[str, NDArray[np.float64] | dict[str, Any]]:
    """Monthly runoff via G0 cryosphere foundation (legacy entry point)."""
    from worldsim.physical.cryosphere.pipeline import build_g0_surface_water

    return build_g0_surface_water(
        precipitation=precipitation,
        temperature_c=temperature_c,
        ocean_mask=ocean_mask,
        snow_threshold_c=snow_threshold_c,
        snow_band_c=snow_band_c,
        melt_factor_per_c=melt_factor_per_c,
        max_snow_store=max_snow_store,
        precip_scale_mm=precip_scale_mm,
        soil_capacity=soil_capacity,
        soil_quickflow_frac=soil_quickflow_frac,
        spinup_years=spinup_years,
        spinup_rel_tol=spinup_rel_tol,
    )
