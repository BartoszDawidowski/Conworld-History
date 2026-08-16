from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.ocean.currents import (
    basin_ids_on_mask,
    western_eastern_boundary_masks,
)
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_climate_atm():
    tectonics = run_pyplatec_extended(
        seed=51,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=2,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atmosphere = build_atmosphere(climate=climate, params=AtmosphereParams())
    return climate, atmosphere


def test_currents_zero_on_land() -> None:
    climate, atmosphere = _small_climate_atm()
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    land = ~climate.ocean_mask
    assert float(np.hypot(ocean.current_u, ocean.current_v)[:, land].max()) == 0.0
    assert ocean.diagnostics["no_land_crossing"] is True


def test_equatorial_westward_and_coherent() -> None:
    climate, atmosphere = _small_climate_atm()
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    assert ocean.diagnostics["equatorial_westward"] is True
    assert ocean.diagnostics["coherent_circulation"] is True
    assert ocean.diagnostics["acceptance_ok"] is True


def test_sst_ocean_only_and_coupling(tmp_path: Path) -> None:
    from worldsim.physical.ocean import apply_ocean_temperature_to_climate

    climate, atmosphere = _small_climate_atm()
    base = climate.temperature_c.copy()
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    land = ~climate.ocean_mask
    assert np.all(np.isnan(ocean.sst_c[:, land]))
    assert np.all(np.isfinite(ocean.sst_c[:, climate.ocean_mask]))
    assert ocean.temperature_coupled_c.shape == climate.temperature_c.shape
    # build_ocean does not mutate climate_v1 (final applies writeback once)
    assert np.allclose(climate.temperature_c, base)
    applied = apply_ocean_temperature_to_climate(climate, ocean)
    assert np.allclose(applied.temperature_c, ocean.temperature_coupled_c)
    assert applied.diagnostics.get("ocean_temperature_applied") is True
    assert ocean.diagnostics.get("inland_decay_cells") == 60.0
    coast_d = float(ocean.diagnostics.get("coast_temp_delta_mean_abs", 0.0))
    deep_d = float(ocean.diagnostics.get("deep_inland_temp_delta_mean_abs", 0.0))
    if coast_d > 0.0 and deep_d >= 0.0:
        assert coast_d >= deep_d - 1e-9
    ocean.save(tmp_path / "ocean")
    assert (tmp_path / "ocean" / "ocean_circulation.npz").is_file()
    data = np.load(tmp_path / "ocean" / "ocean_circulation.npz")
    assert "current_u" in data.files and "sst_c" in data.files


def test_inland_sst_decay_stronger_at_coast() -> None:
    from worldsim.physical.ocean.sst import couple_temperature_with_sst_inland

    h, w = 24, 48
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :16] = True
    temp = np.full((3, h, w), 10.0)
    sst = np.full((3, h, w), np.nan)
    sst[:, :, :16] = 20.0
    coupled, diag = couple_temperature_with_sst_inland(
        temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        mix=0.35,
        inland_decay_cells=8.0,
    )
    # Coast land column 16 warmer pull than far inland column 40
    coast_delta = float(coupled[0, h // 2, 16] - 10.0)
    deep_delta = float(coupled[0, h // 2, 40] - 10.0)
    assert coast_delta > deep_delta
    assert coast_delta > 0.5
    assert deep_delta < coast_delta * 0.5
    assert diag["coast_temp_delta_mean_abs"] >= diag["deep_inland_temp_delta_mean_abs"]


def test_basin_and_boundary_masks() -> None:
    ocean = np.zeros((20, 40), dtype=bool)
    ocean[:, 5:35] = True  # open channel with land on both sides
    ocean[8:12, :] = False  # land belt creating more coasts
    # Restore ocean in middle band parts
    ocean[:, 5:35] = True
    western, eastern = western_eastern_boundary_masks(ocean, width_cells=2)
    assert np.any(western) and np.any(eastern)
    basins = basin_ids_on_mask(ocean)
    assert int(basins.max()) >= 1
