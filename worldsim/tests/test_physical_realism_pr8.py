"""PR-8 — revised B9: transport-first monsoon wind anomaly."""

from __future__ import annotations

import numpy as np

from worldsim.physical.atmosphere.monsoon import apply_monsoon_wind_anomaly
from worldsim.physical.moisture.transport import build_monthly_moisture


def _tropical_continent_fixture(*, months: int = 12):
    """Ocean west, land east; tropical NH strip with seasonal land–SST contrast."""
    h, w = 36, 48
    lat = np.linspace(40, -40, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :18] = True
    # Weak base easterlies so summer onshore (+u) can reverse toward the land.
    wu0 = np.full((months, h, w), -2.0)
    wv0 = np.zeros((months, h, w))
    temp = np.full((months, h, w), 26.0)
    sst = np.full((months, h, w), np.nan)
    sst[:, ocean] = 27.0
    # NH summer (month 5): land much warmer; winter (month 11): land cooler
    nh_land = (lat >= 8.0) & (lat <= 28.0) & (~ocean)
    for m in range(months):
        # Seasonal land swing peaking in June
        phase = np.sin(2.0 * np.pi * (m - 2) / 12.0)
        temp[m] = np.where(nh_land, 26.0 + 10.0 * phase, temp[m])
        sst[m, ocean] = 27.0 - 1.0 * phase
    return lat, ocean, wu0, wv0, temp, sst, nh_land


def test_seasonal_onshore_offshore_contrast() -> None:
    lat, ocean, wu0, wv0, temp, sst, _ = _tropical_continent_fixture()
    u, v, diag = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=0.8,
        lat_band_min_abs_deg=5.0,
        lat_band_max_abs_deg=32.0,
        max_anomaly_ms=4.0,
        coast_reach_cells=8.0,
    )
    assert diag["b9_terms_active"] is True
    # June onshore (positive inland / eastward on west-coast of land), Dec offshore
    onshore = diag["monthly_onshore_anomaly_ms"]
    assert onshore[5] > 0.2
    assert onshore[11] < -0.2
    assert diag.get("seasonal_onshore_sign_flip") is True
    assert diag.get("algorithm") == "monsoon_anomaly_gate_v1"


def test_trades_preserved_outside_monsoon_band() -> None:
    lat, ocean, wu0, wv0, temp, sst, _ = _tropical_continent_fixture()
    u, v, _ = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=0.8,
        lat_band_min_abs_deg=5.0,
        lat_band_max_abs_deg=32.0,
    )
    # Equatorial open ocean (outside min band) and high latitudes stay near base easterlies
    eq = (np.abs(lat) < 3.0) & ocean
    polar = np.abs(lat) > 35.0
    assert float(np.mean(u[5][eq])) < -1.5
    assert float(np.max(np.abs(u[5][polar] - wu0[5][polar]))) < 0.05
    assert float(np.max(np.abs(v[5][polar] - wv0[5][polar]))) < 0.05


def test_precip_seasonality_follows_transport() -> None:
    lat, ocean, wu0, wv0, temp, sst, nh_land = _tropical_continent_fixture(months=12)
    elev = np.zeros(ocean.shape)
    # Coastal land strip just inland of ocean
    coast_land = nh_land & (np.arange(ocean.shape[1])[None, :] >= 18) & (
        np.arange(ocean.shape[1])[None, :] < 28
    )

    u_on, v_on, _ = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=1.0,
        max_anomaly_ms=5.0,
        coast_reach_cells=14.0,
    )
    assert float(u_on[5][coast_land].mean()) > float(wu0[5][coast_land].mean())
    assert float(u_on[5][coast_land].mean()) > 0.0  # onshore reverses local flow

    wet = build_monthly_moisture(
        temperature_c=temp,
        wind_u=u_on,
        wind_v=v_on,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        sst_c=sst,
        months=12,
        advect_steps=10,
        advect_wind_scale=0.15,
        large_scale_frac=0.25,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
        spinup_max_years=2,
    )
    dry_winds = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu0,
        wind_v=wv0,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        sst_c=sst,
        months=12,
        advect_steps=10,
        advect_wind_scale=0.15,
        large_scale_frac=0.25,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
        spinup_max_years=2,
    )
    june_boost = float(wet["atmospheric_moisture"][5][coast_land].mean()) - float(
        dry_winds["atmospheric_moisture"][5][coast_land].mean()
    )
    dec_boost = float(wet["atmospheric_moisture"][11][coast_land].mean()) - float(
        dry_winds["atmospheric_moisture"][11][coast_land].mean()
    )
    # Summer onshore raises coastal moisture vs base; winter offshore does not.
    assert june_boost > 0.02
    assert june_boost > dec_boost
    assert float(wet["budget"]["max_abs_component_sum_error"]) < 1e-9
    precip_sum = abs(float(wet["budget"]["annual_precipitation_sum"])) + 1e-9
    # Upwind scheme is not globally conservative; residual stays a small fraction.
    assert abs(wet["budget"]["annual_numerical_residual"]) / precip_sum < 0.1


def test_strength_zero_is_identity() -> None:
    lat, ocean, wu0, wv0, temp, sst, _ = _tropical_continent_fixture(months=3)
    u, v, diag = apply_monsoon_wind_anomaly(
        wu0,
        wv0,
        land_temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        latitude_deg=lat,
        strength=0.0,
    )
    assert diag["b9_terms_active"] is False
    assert np.allclose(u, wu0)
    assert np.allclose(v, wv0)
