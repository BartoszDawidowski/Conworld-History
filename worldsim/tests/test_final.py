from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.erosion import ErosionParams, build_erosion_pass_one
from worldsim.physical.erosion.fluvial import apply_fluvial_erosion
from worldsim.physical.erosion.pass_one import rock_resistance_proxy
from worldsim.physical.final import FinalRecalcParams, build_final_recalculation
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_v1_stack():
    tectonics = run_pyplatec_extended(
        seed=101,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=8,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atmosphere = build_atmosphere(climate=climate, params=AtmosphereParams())
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    moisture = build_moisture(
        climate=climate, atmosphere=atmosphere, ocean=ocean, params=MoistureParams()
    )
    erosion = build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(iterations=3),
    )
    hydrology = build_hydrology(
        erosion=erosion, moisture=moisture, params=HydrologyParams()
    )
    return terrain, climate, erosion, hydrology, interpretation


def test_fluvial_incises_rivers_stably() -> None:
    h, w = 32, 48
    elev = np.linspace(50, 900, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-3:, :] = True
    elev[ocean] = -100
    river = np.zeros((h, w), dtype=bool)
    river[:, w // 2] = True
    river &= ~ocean
    q = np.where(river, 50.0, 1.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=(h, w)
    )
    dem2, delta = apply_fluvial_erosion(
        elevation_m=elev,
        ocean_mask=ocean,
        river_mask=river,
        discharge_proxy=q,
        resistance=resist,
        iterations=3,
    )
    land = ~ocean
    assert float(np.corrcoef(elev[land], dem2[land])[0, 1]) > 0.95
    assert float(delta[river].mean()) < 0.0  # net incision on river
    assert np.allclose(dem2[ocean], elev[ocean])


def test_final_recalculation(tmp_path: Path) -> None:
    terrain, climate, erosion, hydrology, interpretation = _small_v1_stack()
    final = build_final_recalculation(
        erosion_v1=erosion,
        hydrology_v1=hydrology,
        climate_v1=climate,
        terrain=terrain,
        interpretation=interpretation,
        params=FinalRecalcParams(
            fluvial_iterations=3,
            moisture=MoistureParams(spinup_max_years=12),
        ),
    )
    assert final.elevation_v2_m.shape == erosion.elevation_m.shape
    assert final.diagnostics["stable_final_geography"] is True
    assert final.diagnostics["no_catastrophic_feedback"] is True
    assert final.diagnostics["acceptance_ok"] is True
    assert final.hydrology.diagnostics["acceptance_ok"] is True
    assert final.vectors.diagnostics["acceptance_ok"] is True
    final.save(tmp_path / "final")
    assert (tmp_path / "final" / "terrain_v2.npz").is_file()
    assert (tmp_path / "final" / "hydrology" / "hydrology.npz").is_file()
    assert (tmp_path / "final" / "vectors" / "rivers.geojson").is_file()
