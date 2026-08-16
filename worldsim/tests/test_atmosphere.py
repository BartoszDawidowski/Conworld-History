from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.atmosphere.circulation import (
    CirculationZone,
    apply_coriolis,
    base_wind_from_zones,
    classify_circulation_zones,
    itcz_latitude_deg,
    pressure_proxy_field,
)
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def test_itcz_migrates_with_season() -> None:
    assert itcz_latitude_deg(5) > 0.0  # June → NH
    assert itcz_latitude_deg(11) < 0.0  # December → SH
    assert itcz_latitude_deg(5) > itcz_latitude_deg(11)


def test_pressure_has_subtropical_highs() -> None:
    lat = np.linspace(80, -80, 161)[:, None]
    lat = np.repeat(lat, 4, axis=1)
    p = pressure_proxy_field(lat, itcz_deg=0.0)
    # Around ±28° should be higher than equator
    eq = np.abs(lat[:, 0]) < 5
    sth = (np.abs(lat[:, 0] - 28) < 5) | (np.abs(lat[:, 0] + 28) < 5)
    assert float(p[sth].mean()) > float(p[eq].mean())


def test_zonal_wind_tendencies() -> None:
    height, width = 90, 16
    lat = np.linspace(85, -85, height)[:, None]
    lat = np.repeat(lat, width, axis=1)
    zones = classify_circulation_zones(lat, 0.0)
    u, v = base_wind_from_zones(lat, zones, 0.0)
    assert float(u[zones == int(CirculationZone.HADLEY)].mean()) < 0.0
    assert float(u[zones == int(CirculationZone.FERREL)].mean()) > 0.0
    assert float(u[zones == int(CirculationZone.POLAR)].mean()) < 0.0
    # Hadley meridional toward ITCZ (equator here)
    hadley = zones == int(CirculationZone.HADLEY)
    toward = -np.sign(lat)
    assert float(np.mean(v[hadley] * toward[hadley])) > 0.0


def test_coriolis_deflects_nh_to_the_right() -> None:
    # Pure northward wind in NH → gains eastward component (right deflection)
    u = np.zeros((5, 5))
    v = np.ones((5, 5))
    lat = np.full((5, 5), np.radians(45.0))
    u2, v2 = apply_coriolis(u, v, lat, strength=0.35)
    assert float(u2.mean()) > 0.0


def test_atmosphere_from_small_climate(tmp_path: Path) -> None:
    tectonics = run_pyplatec_extended(
        seed=44,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=3,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atm = build_atmosphere(climate=climate, params=AtmosphereParams())
    assert atm.wind_u.shape == (12, 32, 64)
    assert atm.pressure_proxy.shape == atm.wind_u.shape
    assert atm.diagnostics["expected_zonal_tendencies_ok"] is True
    assert atm.diagnostics["trades_easterly"] is True
    assert atm.diagnostics["ferrel_westerly"] is True
    assert atm.diagnostics["polar_easterly"] is True
    assert atm.diagnostics["zonal_coherence_ok"] is True
    atm.save(tmp_path / "atmosphere")
    assert (tmp_path / "atmosphere" / "atmosphere.npz").is_file()
    data = np.load(tmp_path / "atmosphere" / "atmosphere.npz")
    assert "wind_u" in data.files and "circulation_zone" in data.files
