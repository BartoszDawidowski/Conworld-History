"""CR-8 — conservative CFL advection, lee condensation brake, monsoon gate, hydro loop."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.atmosphere.monsoon import apply_monsoon_wind_anomaly
from worldsim.physical.final import FinalRecalcParams
from worldsim.physical.moisture.transport import (
    build_monthly_moisture,
    partition_precipitation,
    saturation_capacity,
)


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


def test_lee_is_condensation_brake_not_mass_sink() -> None:
    h, w = 12, 24
    q = np.full((h, w), 20.0)
    cap = saturation_capacity(np.full((h, w), 22.0))
    lift = np.zeros((h, w))
    lift[:, 10:14] = 1.5
    lift[:, 14:18] = -1.5
    kwargs = dict(
        q=q,
        capacity=cap,
        land_dry=np.full((h, w), 0.1),
        lift=lift,
        temperature_c=np.full((h, w), 22.0),
        latitude_deg=np.zeros((h, w)),
        large_scale_frac=0.4,
        orographic_frac=1.5,
        convective_scale=0.0,
    )
    off = partition_precipitation(**kwargs, lee_dry=0.0)
    on = partition_precipitation(**kwargs, lee_dry=0.12)
    lee_cols = slice(14, 18)
    wind_cols = slice(10, 14)
    assert float(on["precipitation"][:, lee_cols].mean()) < float(
        off["precipitation"][:, lee_cols].mean()
    )
    assert float(np.sum(on["lee_sink"])) == pytest.approx(0.0)
    assert float(np.sum(on["lee_inhibited"][:, lee_cols])) > 0.0
    remaining_on = q - on["precipitation"]
    remaining_off = q - off["precipitation"]
    assert float(remaining_on[:, lee_cols].mean()) >= float(
        remaining_off[:, lee_cols].mean()
    )
    assert float(on["precipitation"][:, wind_cols].mean()) > float(
        on["precipitation"][:, lee_cols].mean()
    )


def test_lee_sink_not_in_monthly_budget() -> None:
    h, w = 10, 20
    elev = np.zeros((h, w))
    elev[:, 8:12] = 2500.0
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    fields = build_monthly_moisture(
        temperature_c=np.full((12, h, w), 22.0),
        wind_u=np.full((12, h, w), 6.0),
        wind_v=np.zeros((12, h, w)),
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=np.zeros((h, w)),
        months=12,
        advect_steps=8,
        lee_dry=0.12,
        spinup_max_years=3,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
    )
    budget = fields["budget"]
    assert budget["lee_mode"] == "condensation_brake"
    assert budget["annual_lee_sink_sum"] == pytest.approx(0.0)
    precip = abs(float(budget["annual_precipitation_sum"])) + 1e-9
    assert float(budget["annual_lee_inhibited_sum"]) / precip < 0.5
    assert budget["advect_algorithm"] == "finite_volume_cfl_v1"
    assert int(budget["advect_steps_used_max"]) <= 8


def test_monsoon_anomalies_flip_when_land_always_cooler() -> None:
    """Absolute land−SST can stay negative; seasonal anomalies still reverse."""
    lat, ocean, wu0, wv0, _temp, sst, nh_land = _tropical_continent_fixture()
    temp = np.full_like(_temp, 20.0)
    sst = np.full_like(sst, np.nan)
    sst[:, ocean] = 28.0
    for m in range(12):
        phase = np.sin(2.0 * np.pi * (m - 2) / 12.0)
        temp[m] = np.where(nh_land, 20.0 + 6.0 * phase, temp[m])
        sst[m, ocean] = 28.0 - 0.5 * phase
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
    assert diag["monsoon_sign_gate_on"] is True
    assert onshore[5] > 0.05
    assert onshore[11] < -0.05
    assert diag["algorithm"] == "monsoon_anomaly_gate_v1"
    coast_nh = nh_land & (np.arange(ocean.shape[1])[None, :] < 26)
    assert float(np.mean(u[5][coast_nh] - wu0[5][coast_nh])) > 0.0


def test_monsoon_gates_off_without_sign_flip() -> None:
    lat, ocean, wu0, wv0, temp, sst, _ = _tropical_continent_fixture()
    temp = np.full_like(temp, 24.0)
    sst = np.full_like(sst, np.nan)
    sst[:, ocean] = 27.0
    u, v, diag = apply_monsoon_wind_anomaly(
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
    assert diag["monsoon_sign_gate_on"] is False
    assert np.allclose(u, wu0)
    assert np.allclose(v, wv0)


def test_config_cr8_frozen_moisture_knobs() -> None:
    cfg = load_planet_config(default_config_path())
    mp = cfg.to_moisture_params()
    assert mp.orographic_frac == pytest.approx(0.85)
    assert mp.ocean_evap_rate == pytest.approx(1.4)
    assert mp.lee_dry == pytest.approx(0.12)
    assert mp.monsoon_strength == pytest.approx(0.35)
    assert mp.monsoon_regional_mean_km == pytest.approx(500.0)
    assert mp.advect_steps == 32
    assert FinalRecalcParams().hydro_evap_blend == pytest.approx(0.5)
