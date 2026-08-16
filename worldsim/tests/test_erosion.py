from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.erosion import ErosionParams, build_erosion_pass_one
from worldsim.physical.erosion.pass_one import (
    apply_erosion_pass_one,
    count_land_local_minima,
    rock_resistance_proxy,
)
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_stack_with_terrain():
    tectonics = run_pyplatec_extended(
        seed=71,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=5,
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
    return terrain, moisture, interpretation


def test_synthetic_drainage_and_macro() -> None:
    h, w = 32, 48
    elev = np.linspace(100, 800, h)[:, None] * np.ones((1, w))
    # Add noisy pits
    rng = np.random.default_rng(0)
    elev = elev + rng.normal(0, 25, size=(h, w))
    elev[:, 20:28] += 1200  # ridge macro feature
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-4:, :] = True
    elev[ocean] = -200
    precip = np.full((h, w), 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=(h, w)
    )
    before_min = count_land_local_minima(elev, ocean)
    dem, delta = apply_erosion_pass_one(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resist,
        iterations=6,
    )
    after_min = count_land_local_minima(dem, ocean)
    assert after_min <= before_min
    land = ~ocean
    corr = float(np.corrcoef(elev[land], dem[land])[0, 1])
    assert corr > 0.97
    assert np.allclose(dem[ocean], elev[ocean])
    assert float(np.mean(np.abs(delta[land]))) > 0.0


def test_erosion_from_small_world(tmp_path: Path) -> None:
    terrain, moisture, interpretation = _small_stack_with_terrain()
    result = build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(iterations=4),
    )
    assert result.elevation_m.shape == terrain.elevation_m.shape
    assert result.diagnostics["macro_relief_preserved"] is True
    assert result.diagnostics["drainage_quality_improved"] is True
    assert result.diagnostics["acceptance_ok"] is True
    result.save(tmp_path / "erosion")
    assert (tmp_path / "erosion" / "erosion_pass1.npz").is_file()
