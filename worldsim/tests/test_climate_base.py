from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from worldsim.physical.climate.insolation import (
    daily_mean_relative_insolation,
    mid_month_day_of_year,
    monthly_insolation_field,
    solar_declination_rad,
)
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.climate.temperature import (
    apply_thermal_inertia,
    build_monthly_temperature_c,
    continentality_factor,
)
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def test_june_declination_positive_nh_summer() -> None:
    # Mid-June day ~166 → positive declination (NH summer).
    doy = mid_month_day_of_year(5)
    assert 160 <= doy <= 175
    decl = solar_declination_rad(doy, axial_tilt_deg=23.44)
    assert decl > 0.3  # radians ~ >17°


def test_december_declination_negative() -> None:
    decl = solar_declination_rad(mid_month_day_of_year(11), axial_tilt_deg=23.44)
    assert decl < -0.3


def test_seasonal_insolation_inversion_nh_sh() -> None:
    # 1D latitude column expanded to tiny 2D grid.
    height, width = 64, 8
    y = np.linspace(1.0 - 1.0 / height, -1.0 + 1.0 / height, height)
    lat = np.arcsin(np.clip(y, -1.0, 1.0))[:, None]
    lat = np.repeat(lat, width, axis=1)
    insol = monthly_insolation_field(lat, axial_tilt_deg=23.44)
    nh = lat[:, 0] > np.radians(40)
    sh = lat[:, 0] < np.radians(-40)
    assert float(insol[5, nh, :].mean()) > float(insol[11, nh, :].mean())
    assert float(insol[11, sh, :].mean()) > float(insol[5, sh, :].mean())


def test_polar_night_zero_insolation() -> None:
    # North pole in December.
    lat = np.array([[np.radians(90.0)]])
    decl = solar_declination_rad(mid_month_day_of_year(11))
    insol = daily_mean_relative_insolation(lat, decl)
    assert float(np.asarray(insol).reshape(-1)[0]) == pytest.approx(0.0, abs=1e-9)


def test_elevation_lapse_cools_high_land() -> None:
    height, width = 16, 16
    lat = np.zeros((height, width))
    insol = np.full((12, height, width), 0.35)
    elev = np.zeros((height, width))
    elev[:, width // 2 :] = 4000.0
    ocean = np.zeros((height, width), dtype=np.bool_)
    temp, _, _, _ = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=6.5,
    )
    annual = temp.mean(axis=0)
    assert float(annual[:, width // 2 :].mean()) < float(annual[:, : width // 2].mean()) - 15.0


def test_ocean_has_weaker_seasonal_amplitude() -> None:
    height, width = 20, 20
    t_eq = np.zeros((12, height, width))
    # Strong seasonal forcing
    for m in range(12):
        t_eq[m] = 10.0 + 20.0 * np.sin(2 * np.pi * m / 12)
    ocean = np.zeros((height, width), dtype=np.bool_)
    ocean[:, width // 2 :] = True
    cont = continentality_factor(ocean)
    temp = apply_thermal_inertia(t_eq, ocean, cont)
    land_amp = float(temp[:, :, : width // 2].std())
    ocean_amp = float(temp[:, :, width // 2 :].std())
    assert ocean_amp < land_amp


def test_climate_from_small_terrain(tmp_path: Path) -> None:
    tectonics = run_pyplatec_extended(
        seed=33,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=7,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32, axial_tilt_deg=23.44),
    )
    assert climate.temperature_c.shape == (12, 32, 64)
    assert climate.insolation.shape == (12, 32, 64)
    assert climate.diagnostics["seasonal_inversion_ok"] is True
    assert climate.diagnostics["polar_colder_than_tropics"] is True
    assert climate.diagnostics["elevation_trend_ok"] is True
    climate.save(tmp_path / "climate")
    assert (tmp_path / "climate" / "climate_base.npz").is_file()
    data = np.load(tmp_path / "climate" / "climate_base.npz")
    assert "temperature_c" in data.files
