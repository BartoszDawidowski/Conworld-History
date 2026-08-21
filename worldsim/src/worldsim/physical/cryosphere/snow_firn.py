"""G0 — mass-conserving seasonal snow, soil bucket, and explicit firn transfer."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.cryosphere.params import G0Params
from worldsim.physical.hydrology.water_balance import (
    holdridge_pet_proxy,
    partition_rain_snow,
    soil_step,
)
from worldsim.physical.hydrology.transmission import month_pet_fraction

G0_ALGORITHM = "g0_snow_soil_firn_v1"


def _rel_field_delta(a: NDArray[np.floating], b: NDArray[np.floating]) -> float:
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    denom = max(float(np.mean(np.abs(aa))), 1e-12)
    return float(np.mean(np.abs(aa - bb))) / denom


def g0_snow_firn_step(
    seasonal_snow: NDArray[np.floating],
    firn: NDArray[np.floating],
    snowfall: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    *,
    melt_factor_per_c: float,
    firn_melt_factor_per_c: float,
    max_seasonal_swe: float,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """One month: melt seasonal snow first, transfer excess to firn, then optional firn melt."""
    snow = np.maximum(np.asarray(seasonal_snow, dtype=np.float64), 0.0)
    firn_s = np.maximum(np.asarray(firn, dtype=np.float64), 0.0)
    snow = snow + np.maximum(np.asarray(snowfall, dtype=np.float64), 0.0)
    t = np.asarray(temperature_c, dtype=np.float64)
    potential = np.maximum(t, 0.0) * float(melt_factor_per_c)
    snow_melt = np.minimum(snow, potential)
    snow = snow - snow_melt

    cap = max(float(max_seasonal_swe), 0.0)
    firn_formation = np.maximum(snow - cap, 0.0)
    snow = snow - firn_formation
    firn_s = firn_s + firn_formation

    firn_potential = np.maximum(t, 0.0) * float(firn_melt_factor_per_c)
    can_melt_firn = snow <= 1e-12
    firn_melt = np.where(can_melt_firn, np.minimum(firn_s, firn_potential), 0.0)
    firn_s = firn_s - firn_melt

    return (
        snow.astype(np.float64),
        firn_s.astype(np.float64),
        snow_melt.astype(np.float64),
        firn_melt.astype(np.float64),
        firn_formation.astype(np.float64),
    )


def simulate_g0_year(
    *,
    precip: NDArray[np.float64],
    temp: NDArray[np.float64],
    ocean: NDArray[np.bool_],
    seasonal_snow: NDArray[np.float64],
    firn: NDArray[np.float64],
    soil: NDArray[np.float64],
    params: G0Params,
) -> dict[str, NDArray[np.float64]]:
    n = int(precip.shape[0])
    rain = np.zeros_like(precip)
    snowfall = np.zeros_like(precip)
    snow_melt = np.zeros_like(precip)
    firn_melt = np.zeros_like(precip)
    firn_formation = np.zeros_like(precip)
    runoff = np.zeros_like(precip)
    soil_et = np.zeros_like(precip)
    residual_pet = np.zeros_like(precip)
    seasonal_out = np.zeros_like(precip)
    firn_out = np.zeros_like(precip)
    soil_monthly = np.zeros_like(precip)

    snow_state = np.asarray(seasonal_snow, dtype=np.float64).copy()
    firn_state = np.asarray(firn, dtype=np.float64).copy()
    soil_state = np.asarray(soil, dtype=np.float64).copy()

    for m in range(n):
        r, s = partition_rain_snow(
            precip[m],
            temp[m],
            snow_threshold_c=params.snow_threshold_c,
            snow_band_c=params.snow_band_c,
        )
        r = np.where(ocean, 0.0, r)
        s = np.where(ocean, 0.0, s)
        snow_state, firn_state, mlt, f_mlt, f_form = g0_snow_firn_step(
            snow_state,
            firn_state,
            s,
            temp[m],
            melt_factor_per_c=params.melt_factor_per_c,
            firn_melt_factor_per_c=params.firn_melt_factor_per_c,
            max_seasonal_swe=params.max_seasonal_snow_swe,
        )
        snow_state = np.where(ocean, 0.0, snow_state)
        firn_state = np.where(ocean, 0.0, firn_state)
        mlt = np.where(ocean, 0.0, mlt)
        f_mlt = np.where(ocean, 0.0, f_mlt)
        f_form = np.where(ocean, 0.0, f_form)

        pet = holdridge_pet_proxy(
            temp[m],
            precip_scale_mm=params.precip_scale_mm,
            pet_year_fraction=month_pet_fraction(m),
        )
        pet = np.where(ocean, 0.0, pet)
        liquid = r + mlt + f_mlt
        soil_state, q_run, et = soil_step(
            soil_state,
            liquid,
            pet,
            capacity=params.soil_capacity,
            quickflow_frac=params.soil_quickflow_frac,
        )
        soil_state = np.where(ocean, 0.0, soil_state)
        q_run = np.where(ocean, 0.0, q_run)
        et = np.where(ocean, 0.0, et)

        rain[m] = r
        snowfall[m] = s
        snow_melt[m] = mlt
        firn_melt[m] = f_mlt
        firn_formation[m] = f_form
        runoff[m] = q_run
        soil_et[m] = et
        residual_pet[m] = np.maximum(pet - et, 0.0)
        seasonal_out[m] = snow_state
        firn_out[m] = firn_state
        soil_monthly[m] = soil_state

    return {
        "rainfall_monthly": rain,
        "snowfall_monthly": snowfall,
        "seasonal_snowmelt_monthly": snow_melt,
        "firn_melt_monthly": firn_melt,
        "firn_formation_monthly": firn_formation,
        "glacier_melt_monthly": np.zeros_like(precip),
        "liquid_input_monthly": rain + snow_melt + firn_melt,
        "runoff": runoff,
        "soil_et": soil_et,
        "residual_pet": residual_pet,
        "seasonal_snow_swe": seasonal_out,
        "firn_swe": firn_out,
        "soil_water": soil_state,
        "soil_store_monthly": soil_monthly,
        "seasonal_snow_end": snow_state,
        "firn_end": firn_state,
        "soil_end": soil_state,
    }


def _land_sum(field: NDArray[np.floating], land: NDArray[np.bool_]) -> float:
    arr = np.asarray(field, dtype=np.float64)
    if arr.ndim == 3:
        return float(np.sum(arr[:, land]))
    return float(np.sum(arr[land]))


def _annual_mass_balance(
    pack: dict[str, NDArray[np.float64]],
    *,
    seasonal_start: NDArray[np.float64],
    firn_start: NDArray[np.float64],
    soil_start: NDArray[np.float64],
    ocean: NDArray[np.bool_],
) -> dict[str, float]:
    land = ~ocean
    precip = pack["rainfall_monthly"] + pack["snowfall_monthly"]
    inputs = _land_sum(precip, land) if np.any(land) else float(np.sum(precip))
    outputs = (
        _land_sum(pack["runoff"], land)
        + _land_sum(pack["soil_et"], land)
        + _land_sum(pack["seasonal_snow_end"] - seasonal_start, land)
        + _land_sum(pack["firn_end"] - firn_start, land)
        + _land_sum(pack["soil_end"] - soil_start, land)
    )
    residual = inputs - outputs
    denom = max(inputs, 1e-12)
    return {
        "annual_precip_sum": inputs,
        "annual_mass_outputs_sum": outputs,
        "annual_mass_balance_residual": residual,
        "annual_mass_balance_rel": abs(residual) / denom,
        "annual_firn_gain_m_swe": _land_sum(pack["firn_formation_monthly"], land),
        "clip_overflow_m_swe": 0.0,
    }


def build_g0_climatology(
    *,
    precipitation: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    params: G0Params | None = None,
) -> dict[str, NDArray[np.float64] | dict[str, Any]]:
    """Spin up G0 to a repeating climatological year and publish SurfaceWaterForcing."""
    p = params or G0Params()
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

    years = max(int(p.spinup_years), 1)
    seasonal = np.zeros((h, w), dtype=np.float64)
    firn = np.zeros((h, w), dtype=np.float64)
    soil = np.zeros((h, w), dtype=np.float64)
    pack: dict[str, NDArray[np.float64]] | None = None
    prev_runoff: NDArray[np.float64] | None = None
    prev_seasonal_end: NDArray[np.float64] | None = None
    prev_soil: NDArray[np.float64] | None = None
    year1_runoff: NDArray[np.float64] | None = None
    year2_runoff: NDArray[np.float64] | None = None
    runoff_periodic = False
    seasonal_periodic = False
    soil_periodic = False
    used_years = years
    spinup_converged_early = False
    last_mass: dict[str, float] = {
        "annual_mass_balance_rel": 0.0,
        "annual_firn_gain_m_swe": 0.0,
    }

    for year in range(years):
        start_seasonal = seasonal.copy()
        start_firn = firn.copy()
        start_soil = soil.copy()
        pack = simulate_g0_year(
            precip=precip,
            temp=temp,
            ocean=ocean,
            seasonal_snow=seasonal,
            firn=firn,
            soil=soil,
            params=p,
        )
        seasonal = pack["seasonal_snow_end"]
        firn = pack["firn_end"]
        soil = pack["soil_end"]
        runoff = pack["runoff"]
        if year == 0:
            year1_runoff = runoff.copy()
        elif year == 1:
            year2_runoff = runoff.copy()
        if prev_runoff is not None and prev_seasonal_end is not None and prev_soil is not None:
            # Seasonal periodicity uses end-of-year store (2D), not the monthly cube.
            # Growing firn changes firn-melt and thus intra-year snow trajectories even
            # when the seasonal store itself has reached a repeating climatology
            # (addendum §7.3: seasonal stores repeat; accumulation closes via firn).
            rel_r = _rel_field_delta(runoff, prev_runoff)
            rel_s = _rel_field_delta(seasonal, prev_seasonal_end)
            rel_o = _rel_field_delta(soil, prev_soil)
            runoff_periodic = rel_r <= float(p.spinup_rel_tol)
            seasonal_periodic = rel_s <= float(p.spinup_rel_tol)
            soil_periodic = rel_o <= float(p.spinup_rel_tol)
            if runoff_periodic and seasonal_periodic and soil_periodic:
                used_years = year + 1
                spinup_converged_early = True
                mass = _annual_mass_balance(
                    pack,
                    seasonal_start=start_seasonal,
                    firn_start=start_firn,
                    soil_start=start_soil,
                    ocean=ocean,
                )
                last_mass = mass
                break
        prev_runoff = runoff.copy()
        prev_seasonal_end = seasonal.copy()
        prev_soil = soil.copy()
        mass = _annual_mass_balance(
            pack,
            seasonal_start=start_seasonal,
            firn_start=start_firn,
            soil_start=start_soil,
            ocean=ocean,
        )
        last_mass = mass

    assert pack is not None
    if spinup_converged_early:
        published_vs_repeat = 0.0
        seasonal_vs_repeat = 0.0
        soil_vs_repeat = 0.0
    else:
        repeat = simulate_g0_year(
            precip=precip,
            temp=temp,
            ocean=ocean,
            seasonal_snow=seasonal,
            firn=firn,
            soil=soil,
            params=p,
        )
        published_vs_repeat = _rel_field_delta(pack["runoff"], repeat["runoff"])
        seasonal_vs_repeat = _rel_field_delta(
            seasonal, np.asarray(repeat["seasonal_snow_end"], dtype=np.float64)
        )
        soil_vs_repeat = _rel_field_delta(pack["soil_end"], repeat["soil_end"])
        if published_vs_repeat <= float(p.spinup_rel_tol):
            runoff_periodic = True
        if seasonal_vs_repeat <= float(p.spinup_rel_tol):
            seasonal_periodic = True
        if soil_vs_repeat <= float(p.spinup_rel_tol):
            soil_periodic = True

    state_periodic = bool(runoff_periodic and seasonal_periodic and soil_periodic)
    mass_ok = bool(last_mass["annual_mass_balance_rel"] <= float(p.mass_balance_tol))
    firn_transfer = float(last_mass["annual_firn_gain_m_swe"]) > 0.0
    # Repeating seasonal+soil+runoff is enough; firn may keep growing as an
    # explicit transfer (not a hidden seasonal clip).
    periodic_or_firn = bool(
        state_periodic
        or (
            runoff_periodic
            and soil_periodic
            and seasonal_periodic
            and mass_ok
            and firn_transfer
        )
    )

    year2_vs_year1 = (
        _rel_field_delta(year2_runoff, year1_runoff)
        if year1_runoff is not None and year2_runoff is not None
        else float("nan")
    )

    diag: dict[str, Any] = {
        "cryosphere_algorithm": G0_ALGORITHM,
        "runoff_algorithm": G0_ALGORITHM,
        "snow_threshold_c": float(p.snow_threshold_c),
        "melt_factor_per_c": float(p.melt_factor_per_c),
        "max_seasonal_snow_swe": float(p.max_seasonal_snow_swe),
        "max_snow_store": float(p.max_seasonal_snow_swe),
        "soil_capacity": float(p.soil_capacity),
        "soil_quickflow_frac": float(p.soil_quickflow_frac),
        "annual_rain_sum": float(np.sum(pack["rainfall_monthly"])),
        "annual_snow_sum": float(np.sum(pack["snowfall_monthly"])),
        "annual_melt_sum": float(
            np.sum(pack["seasonal_snowmelt_monthly"]) + np.sum(pack["firn_melt_monthly"])
        ),
        "annual_runoff_sum": float(np.sum(pack["runoff"])),
        "annual_soil_et_sum": float(np.sum(pack["soil_et"])),
        "final_seasonal_snow_sum": float(np.sum(seasonal)),
        "final_firn_swe_sum": float(np.sum(firn)),
        "final_snow_store_sum": float(np.sum(seasonal)),
        "final_soil_store_sum": float(np.sum(soil)),
        "firn_gain_m_swe_per_year": float(last_mass["annual_firn_gain_m_swe"]),
        "runoff_spinup_years": int(p.spinup_years),
        "runoff_spinup_years_used": int(used_years),
        "runoff_spinup_rel_tol": float(p.spinup_rel_tol),
        "g0_repeat_year_skipped": bool(spinup_converged_early),
        "runoff_periodic": bool(runoff_periodic),
        "seasonal_snow_periodic": bool(seasonal_periodic),
        "soil_store_periodic": bool(soil_periodic),
        "snow_soil_state_periodic": bool(state_periodic),
        "snow_soil_state_periodic_or_firn_transfer_ok": bool(periodic_or_firn),
        "snow_soil_firn_mass_balance_ok": bool(mass_ok),
        "runoff_year2_vs_year1_rel_delta": float(year2_vs_year1),
        "runoff_published_vs_repeat_rel_delta": float(published_vs_repeat),
        "seasonal_published_vs_repeat_rel_delta": float(seasonal_vs_repeat),
        "soil_published_vs_repeat_rel_delta": float(soil_vs_repeat),
        **last_mass,
    }

    return {
        "rainfall_monthly": pack["rainfall_monthly"],
        "snowfall_monthly": pack["snowfall_monthly"],
        "seasonal_snowmelt_monthly": pack["seasonal_snowmelt_monthly"],
        "firn_melt_monthly": pack["firn_melt_monthly"],
        "firn_formation_monthly": pack["firn_formation_monthly"],
        "glacier_melt_monthly": pack["glacier_melt_monthly"],
        "liquid_input_monthly": pack["liquid_input_monthly"],
        "runoff": pack["runoff"],
        "soil_et": pack["soil_et"],
        "residual_pet": pack["residual_pet"],
        "seasonal_snow_swe": pack["seasonal_snow_swe"],
        "firn_swe": pack["firn_swe"],
        "soil_water": pack["soil_water"],
        "soil_store_monthly": pack["soil_store_monthly"],
        # Legacy hydrology field names
        "rain": pack["rainfall_monthly"],
        "snowfall": pack["snowfall_monthly"],
        "melt": pack["seasonal_snowmelt_monthly"],
        "snow_store": pack["seasonal_snow_swe"],
        "soil_store": pack["soil_water"],
        "diagnostics": diag,
    }
