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
    """Monthly runoff after snow/soil spin-up to a periodic climatological year.

    Shapes: precip/temp ``[months, y, x]`` (temp may be ``[y, x]`` → broadcast).
    Published fields are the last spun year, not the cold-start year-1 hydrograph.
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

    years = max(int(spinup_years), 1)
    store = np.zeros((h, w), dtype=np.float64)
    soil = np.zeros((h, w), dtype=np.float64)
    pack: dict[str, NDArray[np.float64]] | None = None
    prev_runoff: NDArray[np.float64] | None = None
    year1_runoff: NDArray[np.float64] | None = None
    year2_runoff: NDArray[np.float64] | None = None
    periodic = False
    used_years = years
    kw = dict(
        precip=precip,
        temp=temp,
        ocean=ocean,
        snow_threshold_c=snow_threshold_c,
        snow_band_c=snow_band_c,
        melt_factor_per_c=melt_factor_per_c,
        max_snow_store=max_snow_store,
        precip_scale_mm=precip_scale_mm,
        soil_capacity=soil_capacity,
        soil_quickflow_frac=soil_quickflow_frac,
    )
    for year in range(years):
        pack = _simulate_runoff_year(store=store, soil=soil, **kw)
        store = pack["snow_store_end"]
        soil = pack["soil_store"]
        runoff = pack["runoff"]
        if year == 0:
            year1_runoff = runoff.copy()
        elif year == 1:
            year2_runoff = runoff.copy()
        if prev_runoff is not None:
            rel = _rel_field_delta(runoff, prev_runoff)
            if rel <= float(spinup_rel_tol):
                periodic = True
                used_years = year + 1
                break
        prev_runoff = runoff.copy()

    assert pack is not None
    # Honesty check: repeating the published year from ending stores.
    repeat = _simulate_runoff_year(store=store, soil=soil, **kw)
    published_vs_repeat = _rel_field_delta(pack["runoff"], repeat["runoff"])
    if published_vs_repeat <= float(spinup_rel_tol):
        periodic = True
    year2_vs_year1 = (
        _rel_field_delta(year2_runoff, year1_runoff)
        if year1_runoff is not None and year2_runoff is not None
        else float("nan")
    )

    diag = {
        "runoff_algorithm": "soil_bucket_periodic_v1",
        "snow_threshold_c": float(snow_threshold_c),
        "melt_factor_per_c": float(melt_factor_per_c),
        "max_snow_store": float(max_snow_store),
        "soil_capacity": float(soil_capacity),
        "soil_quickflow_frac": float(soil_quickflow_frac),
        "annual_rain_sum": float(np.sum(pack["rain"])),
        "annual_snow_sum": float(np.sum(pack["snowfall"])),
        "annual_melt_sum": float(np.sum(pack["melt"])),
        "annual_runoff_sum": float(np.sum(pack["runoff"])),
        "annual_soil_et_sum": float(np.sum(pack["soil_et"])),
        "final_snow_store_sum": float(np.sum(store)),
        "final_soil_store_sum": float(np.sum(soil)),
        "runoff_spinup_years": int(spinup_years),
        "runoff_spinup_years_used": int(used_years),
        "runoff_spinup_rel_tol": float(spinup_rel_tol),
        "runoff_periodic": bool(periodic),
        "runoff_year2_vs_year1_rel_delta": float(year2_vs_year1),
        "runoff_published_vs_repeat_rel_delta": float(published_vs_repeat),
    }
    return {
        "rain": pack["rain"],
        "snowfall": pack["snowfall"],
        "melt": pack["melt"],
        "runoff": pack["runoff"],
        "soil_et": pack["soil_et"],
        "residual_pet": pack["residual_pet"],
        "snow_store": pack["snow_store"],
        "soil_store": pack["soil_store"],
        "soil_store_monthly": pack["soil_store_monthly"],
        "diagnostics": diag,
    }
