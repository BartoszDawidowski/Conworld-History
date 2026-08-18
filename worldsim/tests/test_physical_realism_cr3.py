"""CR-3 — moisture store spin-up, SST anomaly coupling, local monsoon."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.atmosphere.monsoon import apply_monsoon_wind_anomaly
from worldsim.physical.moisture.transport import build_monthly_moisture
from worldsim.physical.ocean.sst import couple_temperature_with_sst_inland


def _tropical_continent_fixture(*, months: int = 12):
    h, w = 36, 48
    lat = np.linspace(40, -40, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :18] = True
    wu0 = np.full((months, h, w), -2.0)
    wv0 = np.zeros((months, h, w))
    temp = np.full((months, h, w), 26.0)
    sst = np.full((months, h, w), np.nan)
    sst[:, ocean] = 27.0
    nh_land = (lat >= 8.0) & (lat <= 28.0) & (~ocean)
    for m in range(months):
        phase = np.sin(2.0 * np.pi * (m - 2) / 12.0)
        temp[m] = np.where(nh_land, 26.0 + 10.0 * phase, temp[m])
        sst[m, ocean] = 27.0 - 1.0 * phase
    return lat, ocean, wu0, wv0, temp, sst, nh_land


def test_spinup_gates_on_land_store_as_well_as_q() -> None:
    h, w = 20, 40
    elev = np.zeros((h, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :8] = True
    lat = np.linspace(20, -20, h)[:, None] * np.ones((1, w))
    temp = np.full((12, h, w), 24.0)
    wu = np.full((12, h, w), 4.0)
    wv = np.zeros((12, h, w))
    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=12,
        advect_steps=6,
        plume_strength=0.1,
        land_store_capacity=4.0,
        itcz_convective_scale=0.0,
        spinup_max_years=48,
        spinup_tolerance_relative=0.02,
        spinup_tolerance_absolute=0.001,
    )
    budget = fields["budget"]
    assert budget["spinup_store_gated"] is True
    assert "spinup_closure_store_max_abs" in budget
    assert budget["spinup_converged"] is True
    assert budget["spinup_years_used"] <= 48


def test_config_cr3_defaults() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.sst_mix == pytest.approx(0.28)
    assert cfg.moisture_spinup_max_years == 48
    assert cfg.moisture_monsoon_strength == pytest.approx(0.35)
    o = cfg.to_ocean_params()
    assert o.sst_mix == pytest.approx(0.28)


def test_monsoon_local_not_hemisphere_mean() -> None:
    """Opposite seasonal land signals in NH/SH still produce local onshore in NH summer."""
    lat, ocean, wu0, wv0, temp, sst, nh_land = _tropical_continent_fixture()
    sh_land = (lat <= -8.0) & (lat >= -28.0) & (~ocean)
    for m in range(12):
        phase = np.sin(2.0 * np.pi * (m - 2) / 12.0)
        temp[m] = np.where(sh_land, 26.0 - 10.0 * phase, temp[m])
    u, _v, diag = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=0.8,
        max_anomaly_ms=4.0,
        coast_reach_cells=8.0,
    )
    onshore = diag["monthly_onshore_anomaly_ms"]
    # Global mean can dilute when SH is anti-phased; NH coast must still flip locally.
    coast_nh = nh_land & (np.arange(ocean.shape[1])[None, :] < 26)
    june_du = float(np.mean(u[5][coast_nh] - wu0[5][coast_nh]))
    dec_du = float(np.mean(u[11][coast_nh] - wu0[11][coast_nh]))
    assert june_du > 0.15
    assert dec_du < -0.15
    assert june_du > 0.1  # onshore (eastward) on west coast of land
    assert diag.get("algorithm") == "monsoon_sector_gate_v1"


def test_sst_anomaly_coast_gt_deep() -> None:
    h, w = 20, 48
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :14] = True
    temp = np.full((1, h, w), 12.0)
    sst = np.full((1, h, w), np.nan)
    sst[:, :, :14] = 14.0
    sst[:, :, 8:14] = 26.0
    coupled, diag = couple_temperature_with_sst_inland(
        temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        mix=0.3,
        inland_decay_cells=10.0,
    )
    coast = float(coupled[0, h // 2, 14] - 12.0)
    deep = float(coupled[0, h // 2, 40] - 12.0)
    assert coast > deep
    assert coast > 0.2
    assert abs(deep) < abs(coast)
    assert diag["sst_coupling_mode"] == "anomaly_zonal_v1"
