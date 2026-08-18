"""C5 — precipitation mechanisms (metric orography, stratiform, regional monsoon)."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.atmosphere.monsoon import apply_monsoon_wind_anomaly
from worldsim.physical.moisture.transport import (
    build_monthly_moisture,
    orographic_lift,
    partition_precipitation,
    saturation_capacity,
)


def test_production_precip_knobs_documented() -> None:
    cfg = load_planet_config(default_config_path())
    mp = cfg.to_moisture_params()
    assert mp.orographic_frac == pytest.approx(0.85)
    assert mp.large_scale_frac == pytest.approx(0.15)
    assert mp.advect_wind_scale == pytest.approx(0.2)
    assert mp.convective_scale == pytest.approx(2.0)
    assert mp.itcz_convective_scale == pytest.approx(1.2)
    assert mp.monsoon_strength == pytest.approx(0.35)
    assert mp.plume_strength == pytest.approx(0.18)


def test_orographic_lift_is_metric_and_smoothed() -> None:
    h, w = 21, 32
    elev = np.zeros((h, w), dtype=np.float64)
    elev[10, 16] = 8000.0
    u = np.full((h, w), 6.0)
    v = np.zeros((h, w))
    dx = np.full(h, 40.0)
    dy = np.full(h, 40.0)
    raw = orographic_lift(wind_u=u, wind_v=v, elevation_m=elev)
    metric = orographic_lift(
        wind_u=u,
        wind_v=v,
        elevation_m=elev,
        dx_km=dx,
        dy_km=dy,
        smooth_km=150.0,
    )
    unsmooth = orographic_lift(
        wind_u=u,
        wind_v=v,
        elevation_m=elev,
        dx_km=dx,
        dy_km=dy,
        smooth_km=0.0,
    )
    assert float(np.max(np.abs(metric))) <= 1.0 + 1e-9
    assert float(np.max(np.abs(raw))) <= 1.0 + 1e-9
    assert float(np.max(np.abs(metric))) < float(np.max(np.abs(unsmooth)))


def test_supersaturation_becomes_large_scale_not_capacity_sink() -> None:
    h, w = 8, 16
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    fields = build_monthly_moisture(
        temperature_c=np.full((12, h, w), 22.0),
        wind_u=np.full((12, h, w), 3.0),
        wind_v=np.zeros((12, h, w)),
        elevation_m=np.zeros((h, w)),
        ocean_mask=ocean,
        latitude_deg=np.zeros((h, w)),
        months=12,
        advect_steps=4,
        spinup_max_years=3,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
        orographic_frac=0.0,
        large_scale_frac=0.2,
        convective_scale=0.0,
        ocean_evap_rate=1.2,
        land_et_rate=0.0,
    )
    budget = fields["budget"]
    q_end = fields["atmospheric_moisture"][-1]
    cap_end = saturation_capacity(np.full((h, w), 22.0))
    assert float(np.max(q_end - cap_end)) <= 1e-9
    assert float(budget["precip_share_large_scale"]) > 0.5
    assert budget["moisture_budget_ok"] is True
    assert float(budget["max_month_residual_rel"]) <= 1e-6


def test_lee_is_efficiency_not_mass_sink() -> None:
    h, w = 10, 20
    q = np.full((h, w), 12.0)
    cap = saturation_capacity(np.full((h, w), 24.0))
    lift = np.zeros((h, w))
    lift[:, 8:12] = 0.8
    lift[:, 12:16] = -0.8
    kwargs = dict(
        q=q,
        capacity=cap,
        land_dry=np.ones((h, w)),
        lift=lift,
        temperature_c=np.full((h, w), 24.0),
        latitude_deg=np.zeros((h, w)),
        large_scale_frac=0.5,
        orographic_frac=0.5,
        convective_scale=0.0,
    )
    off = partition_precipitation(**kwargs, lee_dry=0.0)
    on = partition_precipitation(**kwargs, lee_dry=0.12)
    lee = slice(12, 16)
    assert float(on["precipitation"][:, lee].mean()) < float(
        off["precipitation"][:, lee].mean()
    )
    assert float(np.sum(on["lee_sink"])) == pytest.approx(0.0)
    remaining = q - on["precipitation"]
    remaining_off = q - off["precipitation"]
    assert float(remaining[:, lee].mean()) >= float(remaining_off[:, lee].mean())


def test_mechanisms_all_active_on_ridge_continent() -> None:
    h, w = 24, 48
    lat = np.linspace(30, -30, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :12] = True
    elev = np.zeros((h, w))
    elev[:, 22:27] = 2500.0
    elev[:, 23:26] = 4000.0
    fields = build_monthly_moisture(
        temperature_c=np.full((12, h, w), 26.0),
        wind_u=np.full((12, h, w), 6.0),
        wind_v=np.zeros((12, h, w)),
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=12,
        advect_steps=8,
        advect_wind_scale=0.2,
        large_scale_frac=0.15,
        orographic_frac=0.85,
        convective_scale=2.0,
        itcz_convective_scale=1.2,
        plume_strength=0.0,
        land_store_capacity=0.0,
        spinup_max_years=4,
        ocean_evap_rate=1.4,
        land_et_rate=0.2,
    )
    b = fields["budget"]
    assert b["orographic_algorithm"] == "metric_smooth_ascent_v1"
    assert float(b["precip_share_orographic"]) > 0.02
    assert float(b["precip_share_large_scale"]) > 0.02
    assert float(b["precip_share_convective_itcz"]) > 0.02
    assert float(b["precip_share_orographic"]) < 0.90
    assert float(b["precip_share_large_scale"]) < 0.90
    assert float(b["max_month_residual_rel"]) <= 1e-6
    precip = fields["precipitation"].sum(axis=0)
    windward = float(precip[:, 20:23].mean())
    leeward = float(precip[:, 27:30].mean())
    assert windward > leeward * 1.05


def test_opposite_nh_landmasses_do_not_cancel_monsoon() -> None:
    h, w = 36, 64
    lat = np.linspace(40, -40, h)[:, None] * np.ones((1, w))
    ocean = np.ones((h, w), dtype=bool)
    ocean[:, 8:20] = False
    ocean[:, 40:52] = False
    months = 12
    wu0 = np.full((months, h, w), -2.0)
    wv0 = np.zeros((months, h, w))
    temp = np.full((months, h, w), 26.0)
    sst = np.full((months, h, w), np.nan)
    sst[:, ocean] = 27.0
    west = (lat >= 8.0) & (lat <= 28.0) & (~ocean) & (np.arange(w)[None, :] < 24)
    east = (lat >= 8.0) & (lat <= 28.0) & (~ocean) & (np.arange(w)[None, :] > 36)
    for m in range(months):
        phase = np.sin(2.0 * np.pi * (m - 2) / 12.0)
        temp[m] = np.where(west, 26.0 + 10.0 * phase, temp[m])
        temp[m] = np.where(east, 26.0 - 10.0 * phase, temp[m])
        sst[m, ocean] = 27.0
    u, _v, diag = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=0.8,
        max_anomaly_ms=4.0,
        coast_reach_cells=6.0,
    )
    assert diag["algorithm"] == "monsoon_sector_gate_v1"
    assert diag["monsoon_sign_gate_on"] is True
    west_coast = west & (np.arange(w)[None, :] <= 10)
    east_coast = east & (np.arange(w)[None, :] <= 42)
    assert float(np.mean(u[5][west_coast] - wu0[5][west_coast])) > 0.1
    assert float(np.mean(u[5][east_coast] - wu0[5][east_coast])) < -0.1
    eq_ocean = (np.abs(lat) < 3.0) & ocean
    assert float(np.mean(u[5][eq_ocean])) < -1.5


def test_monsoon_precip_ratio_follows_onshore_wind() -> None:
    h, w = 36, 48
    lat = np.linspace(40, -40, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :18] = True
    months = 12
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
    u_on, v_on, diag = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=1.0,
        max_anomaly_ms=5.0,
        coast_reach_cells=12.0,
    )
    onshore = diag["monthly_onshore_anomaly_ms"]
    assert onshore[5] > 0.1
    assert onshore[11] < -0.1
    coast_land = nh_land & (np.arange(w)[None, :] >= 18) & (np.arange(w)[None, :] < 26)
    kwargs = dict(
        temperature_c=temp,
        elevation_m=np.zeros((h, w)),
        ocean_mask=ocean,
        latitude_deg=lat,
        sst_c=sst,
        months=12,
        advect_steps=8,
        advect_wind_scale=0.2,
        large_scale_frac=0.25,
        orographic_frac=0.0,
        convective_scale=0.5,
        itcz_convective_scale=0.0,
        plume_strength=0.0,
        land_store_capacity=0.0,
        spinup_max_years=3,
    )
    wet = build_monthly_moisture(**kwargs, wind_u=u_on, wind_v=v_on)
    dry = build_monthly_moisture(**kwargs, wind_u=wu0, wind_v=wv0)
    june_ratio = float(wet["precipitation"][5][coast_land].mean()) / max(
        float(dry["precipitation"][5][coast_land].mean()), 1e-9
    )
    dec_ratio = float(wet["precipitation"][11][coast_land].mean()) / max(
        float(dry["precipitation"][11][coast_land].mean()), 1e-9
    )
    assert june_ratio > 1.05
    assert june_ratio > dec_ratio
    eq = (np.abs(lat) < 3.0) & ocean
    assert abs(float(np.mean(u_on[5][eq] - wu0[5][eq]))) < 0.05
    assert float(wet["budget"]["max_month_residual_rel"]) <= 1e-6
    assert float(dry["budget"]["max_month_residual_rel"]) <= 1e-6
