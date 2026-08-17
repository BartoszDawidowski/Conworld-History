"""CR-1 — moisture param propagation + honest acceptance_ok."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from worldsim.config import load_planet_config
from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.erosion import ErosionParams, build_erosion_pass_one
from worldsim.physical.final import FinalRecalcParams, build_final_recalculation
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.landforms import LandformParams, build_landform_analysis
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.spatial.extent import SpatialExtent


def _climate_stack(seed: int = 61):
    tectonics = run_pyplatec_extended(
        seed=seed,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=4,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atmosphere = build_atmosphere(climate=climate, params=AtmosphereParams())
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    return terrain, climate, atmosphere, ocean, interpretation


def test_failed_spinup_rejects_moisture_acceptance() -> None:
    _, climate, atmosphere, ocean, _ = _climate_stack()
    moist = build_moisture(
        climate=climate,
        atmosphere=atmosphere,
        ocean=ocean,
        params=MoistureParams(spinup_max_years=1),
    )
    assert moist.diagnostics["spinup_converged"] is False
    assert moist.diagnostics["acceptance_ok"] is False
    assert moist.diagnostics["acceptance_requires_spinup"] is True


def test_planet_config_to_moisture_params_includes_b8_b9() -> None:
    from worldsim.config import default_config_path

    cfg = load_planet_config(default_config_path())
    mp = cfg.to_moisture_params()
    assert mp.plume_strength == pytest.approx(cfg.moisture_plume_strength)
    assert mp.land_store_capacity == pytest.approx(cfg.moisture_land_store_capacity)
    assert mp.itcz_convective_scale == pytest.approx(cfg.moisture_itcz_convective_scale)
    assert mp.monsoon_strength == pytest.approx(cfg.moisture_monsoon_strength)
    assert mp.monsoon_lat_band_min_abs_deg == pytest.approx(
        cfg.moisture_monsoon_lat_band_min_abs_deg
    )
    assert mp.monsoon_coast_reach_cells == pytest.approx(
        cfg.moisture_monsoon_coast_reach_cells
    )


def test_final_pass_propagates_plume_itcz_monsoon_land_store() -> None:
    terrain, climate, atmosphere, ocean, interpretation = _climate_stack(seed=77)
    moisture = build_moisture(
        climate=climate,
        atmosphere=atmosphere,
        ocean=ocean,
        params=MoistureParams(spinup_max_years=12),
    )
    erosion = build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(iterations=2),
    )
    hydrology = build_hydrology(
        erosion=erosion, moisture=moisture, params=HydrologyParams()
    )

    base = MoistureParams(
        spinup_max_years=12,
        plume_strength=0.05,
        land_store_capacity=2.0,
        itcz_convective_scale=0.5,
        monsoon_strength=0.0,
    )
    high = replace(
        base,
        plume_strength=0.35,
        land_store_capacity=12.0,
        itcz_convective_scale=2.0,
        monsoon_strength=0.55,
    )

    low_final = build_final_recalculation(
        erosion_v1=erosion,
        hydrology_v1=hydrology,
        climate_v1=climate,
        terrain=terrain,
        interpretation=interpretation,
        params=FinalRecalcParams(fluvial_iterations=2, moisture=base),
    )
    high_final = build_final_recalculation(
        erosion_v1=erosion,
        hydrology_v1=hydrology,
        climate_v1=climate,
        terrain=terrain,
        interpretation=interpretation,
        params=FinalRecalcParams(fluvial_iterations=2, moisture=high),
    )

    ld = low_final.moisture.diagnostics
    hd = high_final.moisture.diagnostics
    assert ld["plume_strength"] == pytest.approx(0.05)
    assert hd["plume_strength"] == pytest.approx(0.35)
    assert ld["land_store_capacity"] == pytest.approx(2.0)
    assert hd["land_store_capacity"] == pytest.approx(12.0)
    assert ld["itcz_convective_scale"] == pytest.approx(0.5)
    assert hd["itcz_convective_scale"] == pytest.approx(2.0)
    assert ld["monsoon_strength"] == pytest.approx(0.0)
    assert hd["monsoon_strength"] == pytest.approx(0.55)
    # Ecology-facing precip should move when B8 knobs change.
    assert not np.allclose(
        low_final.moisture.annual_precipitation,
        high_final.moisture.annual_precipitation,
    )


def test_landform_disabled_is_not_acceptance_ok() -> None:
    h, w = 32, 48
    elev = np.full((h, w), 100.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    elev = np.where(ocean, -50.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        extent=SpatialExtent(width=w, height=h),
        params=LandformParams(enabled=False),
    )
    assert res.diagnostics["enabled"] is False
    assert res.diagnostics["acceptance_ok"] is False
    assert res.diagnostics["calibrated"] is False
