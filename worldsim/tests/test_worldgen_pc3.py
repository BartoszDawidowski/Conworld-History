"""PC3 — G0 mass-conserving snow/soil/firn foundation."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.cryosphere.params import G0Params
from worldsim.physical.cryosphere.pipeline import build_g0_surface_water
from worldsim.physical.cryosphere.snow_firn import G0_ALGORITHM, simulate_g0_year
from worldsim.physical.ecology.biome_v2 import CLASS_DISPLAY_NAMES, BiomeV2Class
from worldsim.physical.ecology.holdridge import HoldridgeOverride, zone_label_for_id
from worldsim.physical.hydrology.runoff import build_monthly_runoff

pytestmark = pytest.mark.pc3


def _ocean_grid(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w), dtype=bool)


def test_cold_dry_no_snowfall_no_firn() -> None:
    n, h, w = 12, 4, 4
    temp = np.full((n, h, w), -20.0)
    precip = np.zeros((n, h, w), dtype=np.float64)
    out = build_g0_surface_water(
        precipitation=precip, temperature_c=temp, ocean_mask=_ocean_grid(h, w)
    )
    diag = out["diagnostics"]
    assert float(np.sum(out["snowfall_monthly"])) == 0.0
    assert float(diag["final_firn_swe_sum"]) == 0.0
    assert float(diag["final_seasonal_snow_sum"]) == 0.0


def test_cold_wet_accumulates_then_transfers_to_firn() -> None:
    n, h, w = 12, 4, 4
    temp = np.full((n, h, w), -8.0)
    precip = np.full((n, h, w), 2.0)
    out = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=6,
        max_snow_store=10.0,
    )
    diag = out["diagnostics"]
    assert float(diag["final_seasonal_snow_sum"]) > 0.0
    assert float(diag["firn_gain_m_swe_per_year"]) > 0.0
    assert float(diag["clip_overflow_m_swe"]) == 0.0
    assert diag["snow_soil_state_periodic_or_firn_transfer_ok"]


def test_warm_seasonal_cycle_melt_once_in_runoff() -> None:
    n, h, w = 12, 6, 6
    temp = np.full((n, h, w), 18.0)
    precip = np.full((n, h, w), 1.5)
    out = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=4,
    )
    liquid = np.asarray(out["liquid_input_monthly"])
    runoff = np.asarray(out["runoff"])
    rain = np.asarray(out["rainfall_monthly"])
    melt = np.asarray(out["seasonal_snowmelt_monthly"])
    assert float(np.sum(runoff)) <= float(np.sum(rain + melt)) + 1e-6
    assert float(np.sum(melt)) < float(np.sum(precip)) * 0.5


def test_non_accumulating_climate_repeats_seasonal_stores() -> None:
    n, h, w = 12, 6, 6
    temp = np.full((n, h, w), 18.0)
    precip = np.full((n, h, w), 1.5)
    out = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=8,
        spinup_rel_tol=0.01,
    )
    diag = out["diagnostics"]
    assert diag["runoff_algorithm"] == G0_ALGORITHM
    assert diag["snow_soil_state_periodic"]
    assert diag["snow_soil_firn_mass_balance_ok"]


def test_accumulating_climate_firn_transfer_closes_ledger() -> None:
    n, h, w = 12, 4, 4
    temp = np.full((n, h, w), -8.0)
    precip = np.full((n, h, w), 2.0)
    out = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=6,
        max_snow_store=8.0,
    )
    diag = out["diagnostics"]
    assert diag["seasonal_snow_periodic"]
    assert float(diag["firn_gain_m_swe_per_year"]) > 0.0
    assert diag["snow_soil_state_periodic_or_firn_transfer_ok"]
    assert diag["snow_soil_firn_mass_balance_ok"]


def test_cold_start_not_marked_state_periodic() -> None:
    n, h, w = 12, 4, 4
    temp = np.full((n, h, w), -8.0)
    precip = np.full((n, h, w), 2.0)
    cold = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=1,
    )
    spun = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        spinup_years=6,
    )
    assert not cold["diagnostics"]["snow_soil_state_periodic"]
    assert spun["diagnostics"]["snow_soil_state_periodic_or_firn_transfer_ok"]


def test_small_cap_overflow_transfers_not_clips() -> None:
    n, h, w = 12, 3, 3
    temp = np.full((n, h, w), -10.0)
    precip = np.full((n, h, w), 3.0)
    out = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=_ocean_grid(h, w),
        max_snow_store=2.0,
        spinup_years=4,
    )
    diag = out["diagnostics"]
    assert float(diag["clip_overflow_m_swe"]) == 0.0
    assert float(diag["firn_gain_m_swe_per_year"]) > 0.0
    assert float(diag["annual_mass_balance_rel"]) <= 1e-4


def test_mass_conservation_within_tolerance() -> None:
    n, h, w = 12, 5, 5
    temp = np.linspace(-5, 15, n)[:, None, None] * np.ones((n, h, w))
    precip = np.full((n, h, w), 1.2)
    params = G0Params(spinup_years=5)
    seasonal = np.zeros((h, w))
    firn = np.zeros((h, w))
    soil = np.zeros((h, w))
    ocean = _ocean_grid(h, w)
    pack = simulate_g0_year(
        precip=precip,
        temp=temp,
        ocean=ocean,
        seasonal_snow=seasonal,
        firn=firn,
        soil=soil,
        params=params,
    )
    inputs = float(np.sum(pack["rainfall_monthly"] + pack["snowfall_monthly"]))
    outputs = (
        float(np.sum(pack["runoff"]))
        + float(np.sum(pack["soil_et"]))
        + float(np.sum(pack["seasonal_snow_end"] - seasonal))
        + float(np.sum(pack["firn_end"] - firn))
        + float(np.sum(pack["soil_end"] - soil))
    )
    assert abs(inputs - outputs) / max(inputs, 1e-9) <= params.mass_balance_tol


def test_legacy_runoff_entry_delegates_to_g0() -> None:
    precip = np.full((12, 4, 4), 1.5)
    temp = np.full((12, 4, 4), 16.0)
    ocean = _ocean_grid(4, 4)
    out = build_monthly_runoff(
        precipitation=precip, temperature_c=temp, ocean_mask=ocean, spinup_years=4
    )
    assert out["diagnostics"]["runoff_algorithm"] == G0_ALGORITHM
    assert "liquid_input_monthly" in out or np.asarray(out["runoff"]).shape == (12, 4, 4)


def test_honest_ecology_ice_labels() -> None:
    assert zone_label_for_id(int(HoldridgeOverride.ICE)) == (
        "Permanent ice (thermal potential)"
    )
    assert CLASS_DISPLAY_NAMES[int(BiomeV2Class.ICE)] == "ice_climate_potential"
