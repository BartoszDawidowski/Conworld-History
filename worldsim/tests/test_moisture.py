from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.moisture.transport import (
    build_monthly_moisture,
    orographic_lift,
)
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_stack():
    tectonics = run_pyplatec_extended(
        seed=61,
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
    return climate, atmosphere, ocean


def test_synthetic_windward_leeward() -> None:
    h, w = 24, 48
    elev = np.zeros((h, w), dtype=np.float64)
    # North-south ridge at x=24
    elev[:, 22:27] = 3000.0
    elev[:, 23:26] = 4500.0
    u = np.full((h, w), 8.0)  # eastward wind → windward west face
    v = np.zeros((h, w))
    lift = orographic_lift(wind_u=u, wind_v=v, elevation_m=elev)
    # West slope of ridge (ascending) should be positive; east descending negative
    assert float(lift[:, 22].mean()) > 0.0
    assert float(lift[:, 27].mean()) < 0.0

    temp = np.full((1, h, w), 22.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :10] = True
    lat = np.linspace(20, -20, h)[:, None] * np.ones((1, w))
    wu = np.broadcast_to(u, (1, h, w)).copy()
    wv = np.zeros((1, h, w))
    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=1,
        advect_steps=8,
    )
    precip = fields["precipitation"][0]
    windward = precip[:, 20:23].mean()
    leeward = precip[:, 27:30].mean()
    assert windward > leeward


def test_moisture_from_small_world(tmp_path: Path) -> None:
    climate, atmosphere, ocean = _small_stack()
    moisture = build_moisture(
        climate=climate,
        atmosphere=atmosphere,
        ocean=ocean,
        params=MoistureParams(spinup_max_years=48),
    )
    assert moisture.precipitation.shape[0] == 12
    assert moisture.precipitation.shape[1:] == climate.ocean_mask.shape
    assert moisture.diagnostics["downwind_moisture_transport_ok"] is True
    assert moisture.diagnostics["earth_like_wet_dry_ok"] is True
    assert moisture.diagnostics["spinup_converged"] is True
    assert moisture.diagnostics["acceptance_ok"] is True
    moisture.save(tmp_path / "moisture")
    assert (tmp_path / "moisture" / "moisture.npz").is_file()
    data = np.load(tmp_path / "moisture" / "moisture.npz")
    assert "precipitation" in data.files and "annual_precipitation" in data.files


def test_moisture_advect_knob_moves_precip_inland() -> None:
    """Higher advect / lower rainout should wet interiors relative to defaults."""
    h, w = 20, 40
    elev = np.zeros((h, w), dtype=np.float64)
    temp = np.full((1, h, w), 24.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :6] = True
    lat = np.zeros((h, w))
    wu = np.full((1, h, w), 10.0)
    wv = np.zeros((1, h, w))
    dry = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=1,
        advect_steps=4,
        advect_wind_scale=0.04,
        large_scale_frac=0.7,
    )["precipitation"][0]
    wet = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=1,
        advect_steps=16,
        advect_wind_scale=0.1,
        large_scale_frac=0.25,
    )["precipitation"][0]
    land = ~ocean
    # Transport raises near-inland precip; deep interior is allowed to stay drier
    # than a high-rainout uniform drizzle (C5 stratiform).
    near_inland = land.copy()
    near_inland[:, :8] = False
    near_inland[:, 18:] = False
    assert float(wet[near_inland].mean()) > float(dry[near_inland].mean())


def test_ocean_evap_exceeds_land() -> None:
    climate, atmosphere, ocean = _small_stack()
    moisture = build_moisture(
        climate=climate, atmosphere=atmosphere, ocean=ocean, params=MoistureParams()
    )
    ocean_m = climate.ocean_mask
    land = ~ocean_m
    assert float(moisture.evaporation[5][ocean_m].mean()) > float(
        moisture.evaporation[5][land].mean()
    )


def test_inland_lake_increases_humidity_and_precip() -> None:
    """Large inland lakes should humidify/precipitate more than bare land."""
    h, w = 24, 48
    elev = np.zeros((h, w), dtype=np.float64)
    temp = np.full((1, h, w), 24.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    lake = np.zeros((h, w), dtype=bool)
    lake[8:16, 28:40] = True
    lat = np.zeros((h, w))
    wu = np.zeros((1, h, w))
    wv = np.zeros((1, h, w))
    dry = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=1,
        advect_steps=4,
    )
    wet = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        lake_mask=lake,
        months=1,
        advect_steps=4,
    )
    assert float(wet["evaporation"][0][lake].mean()) > float(
        dry["evaporation"][0][lake].mean()
    )
    assert float(wet["humidity"][0][lake].mean()) > float(
        dry["humidity"][0][lake].mean()
    )
    # Neighbour ring around lake (not ocean)
    ring = np.zeros((h, w), dtype=bool)
    ring[6:18, 26:42] = True
    ring &= ~lake & ~ocean
    assert float(wet["precipitation"][0][ring].mean()) > float(
        dry["precipitation"][0][ring].mean()
    )


def test_river_evap_exceeds_bare_land() -> None:
    h, w = 16, 32
    temp = np.full((h, w), 22.0)
    ocean = np.zeros((h, w), dtype=bool)
    river = np.zeros((h, w), dtype=bool)
    river[:, 16] = True
    from worldsim.physical.moisture.transport import evaporation_field

    bare = evaporation_field(temperature_c=temp, ocean_mask=ocean)
    with_r = evaporation_field(
        temperature_c=temp, ocean_mask=ocean, river_mask=river, river_rate=0.40
    )
    assert float(with_r[river].mean()) > float(bare[river].mean())
