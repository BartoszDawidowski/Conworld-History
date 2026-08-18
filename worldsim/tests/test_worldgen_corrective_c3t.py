"""C3T — named temperature-state integrity and optional continental seasonality."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.climate.insolation import monthly_insolation_field
from worldsim.physical.climate.pipeline import (
    ClimateParams,
    ClimateResult,
    latitude_grid,
    replace_climate_temperature,
    restamp_temperature_diagnostics,
)
from worldsim.physical.climate.temperature import (
    TEMPERATURE_STATE_BASE,
    TEMPERATURE_STATE_EQUILIBRIUM,
    TEMPERATURE_STATE_FINAL,
    TEMPERATURE_STATE_SST,
    apply_continental_seasonality,
    build_monthly_temperature_c,
    temperature_diagnostics,
)
from worldsim.physical.final.pipeline import correct_climate_for_dem
from worldsim.physical.ocean.pipeline import OceanResult, apply_ocean_temperature_to_climate
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics


def _toy_climate(*, h: int = 16, w: int = 24, land_elev: float = 200.0) -> ClimateResult:
    lat_deg, lat_rad = latitude_grid(h, w)
    insol = monthly_insolation_field(lat_rad, axial_tilt_deg=23.44, months=12)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    elev = np.full((h, w), land_elev, dtype=np.float64)
    elev[ocean] = -200.0
    base, cont, t_eq, diag = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat_rad,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=6.5,
        base_temp_c=25.0,
        continentality_scale_km=500.0,
        metrics=grid_metrics(w, h),
    )
    stats = temperature_diagnostics(
        base,
        latitude_deg=lat_deg,
        elevation_m=elev,
        ocean_mask=ocean,
        state_name=TEMPERATURE_STATE_BASE,
    )
    return ClimateResult(
        extent=SpatialExtent.from_shape(w, h),
        latitude_deg=lat_deg,
        insolation=insol,
        temperature_c=base.copy(),
        continentality=cont,
        elevation_m=elev,
        ocean_mask=ocean,
        diagnostics={
            "lapse_apply_count": 1,
            "sst_apply_count": 0,
            "lapse_rate_c_per_km": 6.5,
            **diag,
            **stats,
        },
        temperature_equilibrium_c=t_eq,
        temperature_base_c=base.copy(),
    )


def test_production_temperature_defaults_frozen() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.base_temp_c == pytest.approx(25.0)
    assert cfg.sst_mix == pytest.approx(0.28)
    assert cfg.sst_inland_decay_km == pytest.approx(1200.0)
    assert cfg.climate_continental_seasonality_gain == pytest.approx(0.0)
    assert ClimateParams(width=8, height=8).lapse_rate_c_per_km == pytest.approx(6.5)
    assert ClimateParams(width=8, height=8).continental_seasonality_gain == pytest.approx(
        0.0
    )


def test_temperature_diagnostics_match_direct_array() -> None:
    climate = _toy_climate()
    t = climate.temperature_c + 3.5
    stats = temperature_diagnostics(
        t,
        latitude_deg=climate.latitude_deg,
        elevation_m=climate.elevation_m,
        ocean_mask=climate.ocean_mask,
        state_name="probe_c",
    )
    assert stats["temperature_state"] == "probe_c"
    assert stats["diagnostics_source_state"] == "probe_c"
    assert stats["temperature_min_c"] == pytest.approx(float(np.min(t)))
    assert stats["temperature_max_c"] == pytest.approx(float(np.max(t)))
    assert stats["annual_mean_c"] == pytest.approx(float(np.mean(t.mean(axis=0))))


def test_dem_correction_updates_every_named_state() -> None:
    climate = _toy_climate(land_elev=400.0)
    h, w = climate.elevation_m.shape
    elev_v1 = np.full((h * 2, w * 2), 400.0)
    elev_v2 = elev_v1 + 1000.0
    ocean_t = np.zeros(elev_v1.shape, dtype=bool)
    ocean_t[:, :8] = True
    elev_v1[ocean_t] = -200.0
    elev_v2[ocean_t] = -200.0

    eq0 = climate.temperature_equilibrium_c.copy()
    base0 = climate.temperature_base_c.copy()
    pub0 = climate.temperature_c.copy()

    out = correct_climate_for_dem(
        climate,
        elev_terrain_v1=elev_v1,
        elev_terrain_v2=elev_v2,
        ocean_terrain=ocean_t,
        lapse_rate_c_per_km=6.5,
    )
    land = ~out.ocean_mask
    expected = -6.5 * (out.elevation_m - climate.elevation_m) / 1000.0
    d_land = expected[land]
    assert float(np.mean(np.abs(d_land))) > 0.1
    assert np.allclose(out.temperature_c[:, land], pub0[:, land] + expected[np.newaxis, land])
    assert np.allclose(
        out.temperature_base_c[:, land], base0[:, land] + expected[np.newaxis, land]
    )
    assert np.allclose(
        out.temperature_equilibrium_c[:, land],
        eq0[:, land] + expected[np.newaxis, land],
    )
    assert TEMPERATURE_STATE_BASE in out.diagnostics["temperature_states_updated"]
    assert TEMPERATURE_STATE_EQUILIBRIUM in out.diagnostics["temperature_states_updated"]
    assert out.diagnostics["lapse_apply_count"] == 2
    assert out.diagnostics["sst_apply_count"] == 0
    assert out.diagnostics["temperature_state"] == TEMPERATURE_STATE_BASE
    assert out.diagnostics["annual_mean_c"] == pytest.approx(
        float(np.mean(out.temperature_c.mean(axis=0)))
    )


def test_sst_writeback_restamps_diagnostics_from_new_array() -> None:
    climate = _toy_climate()
    coupled = climate.temperature_c + 4.0
    ocean = OceanResult(
        extent=climate.extent,
        current_u=np.zeros_like(climate.temperature_c),
        current_v=np.zeros_like(climate.temperature_c),
        sst_c=np.full_like(climate.temperature_c, 10.0),
        temperature_coupled_c=coupled,
        ocean_basin_id=np.zeros(climate.ocean_mask.shape, dtype=np.int32),
        western_boundary=np.zeros(climate.ocean_mask.shape, dtype=bool),
        eastern_boundary=np.zeros(climate.ocean_mask.shape, dtype=bool),
        diagnostics={"inland_decay_km": 1200.0, "land_temp_delta_mean_abs": 4.0},
    )
    stale_min = climate.diagnostics["temperature_min_c"]
    out = apply_ocean_temperature_to_climate(climate, ocean)
    assert out.diagnostics["temperature_state"] == TEMPERATURE_STATE_SST
    assert out.diagnostics["diagnostics_source_state"] == TEMPERATURE_STATE_SST
    assert out.diagnostics["annual_mean_c"] == pytest.approx(float(np.mean(coupled.mean(axis=0))))
    assert out.diagnostics["temperature_min_c"] == pytest.approx(float(np.min(coupled)))
    assert out.diagnostics["temperature_min_c"] != pytest.approx(stale_min)
    assert out.diagnostics["sst_apply_count"] == 1
    assert np.allclose(out.temperature_base_c, climate.temperature_base_c)
    assert np.allclose(out.temperature_equilibrium_c, climate.temperature_equilibrium_c)


def test_restamp_final_does_not_apply_lapse_or_sst_again() -> None:
    climate = _toy_climate()
    stamped = restamp_temperature_diagnostics(
        climate,
        state_name=TEMPERATURE_STATE_FINAL,
        extra={"provenance_lapse_then_sst": True},
    )
    assert stamped.diagnostics["temperature_state"] == TEMPERATURE_STATE_FINAL
    assert stamped.diagnostics["lapse_apply_count"] == 1
    assert stamped.diagnostics["sst_apply_count"] == 0
    assert np.allclose(stamped.temperature_c, climate.temperature_c)


def test_mirrored_fixture_is_ns_symmetric() -> None:
    h, w = 32, 40
    lat_deg, lat_rad = latitude_grid(h, w)
    insol = monthly_insolation_field(lat_rad, axial_tilt_deg=23.44, months=12)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :6] = True
    half = np.linspace(50.0, 900.0, h // 2)
    elev_col = np.concatenate([half, half[::-1]])
    elev = np.broadcast_to(elev_col[:, None], (h, w)).copy()
    elev[ocean] = -150.0
    temp, _cont, _eq, _diag = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat_rad,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=6.5,
        base_temp_c=25.0,
        continentality_scale_km=500.0,
        metrics=grid_metrics(w, h),
    )
    annual = temp.mean(axis=0)
    assert np.allclose(annual, annual[::-1, :], atol=0.15)
    stats = temperature_diagnostics(
        temp,
        latitude_deg=lat_deg,
        elevation_m=elev,
        ocean_mask=ocean,
        state_name=TEMPERATURE_STATE_BASE,
    )
    assert stats["seasonal_inversion_ok"] is True


def test_continental_gain_preserves_annual_mean_and_raises_inland_amplitude() -> None:
    climate = _toy_climate()
    inland = (~climate.ocean_mask) & (climate.continentality > 0.25)
    amp0 = climate.temperature_c.max(axis=0) - climate.temperature_c.min(axis=0)
    boosted, diag = apply_continental_seasonality(
        climate.temperature_c, climate.continentality, gain=0.5
    )
    assert diag["continental_seasonality_applied"] is True
    assert np.allclose(boosted.mean(axis=0), climate.temperature_c.mean(axis=0), atol=1e-9)
    amp1 = boosted.max(axis=0) - boosted.min(axis=0)
    assert float(amp1[inland].mean()) > float(amp0[inland].mean())
    peak0 = np.argmax(climate.temperature_c, axis=0)
    peak1 = np.argmax(boosted, axis=0)
    assert np.array_equal(peak0, peak1)
    none, zero_diag = apply_continental_seasonality(
        climate.temperature_c, climate.continentality, gain=0.0
    )
    assert zero_diag["continental_seasonality_applied"] is False
    assert np.allclose(none, climate.temperature_c)


def test_continental_seasonality_sweep_is_recorded_not_retuned() -> None:
    h, w = 24, 48
    _lat_deg, lat_rad = latitude_grid(h, w)
    insol = monthly_insolation_field(lat_rad, axial_tilt_deg=23.44, months=12)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :8] = True
    elev = np.full((h, w), 200.0)
    elev[ocean] = -200.0
    rows = []
    for scale_km in (300.0, 500.0, 800.0):
        for gain in (0.0, 0.25, 0.5):
            temp, cont, _eq, diag = build_monthly_temperature_c(
                insolation=insol,
                latitude_rad=lat_rad,
                elevation_m=elev,
                ocean_mask=ocean,
                lapse_rate_c_per_km=6.5,
                base_temp_c=25.0,
                continentality_scale_km=scale_km,
                metrics=grid_metrics(w, h),
                continental_seasonality_gain=gain,
            )
            inland = (~ocean) & (cont > 0.25)
            amp = temp.max(axis=0) - temp.min(axis=0)
            rows.append(
                {
                    "continentality_scale_km": scale_km,
                    "gain": gain,
                    "inland_amp_mean": float(amp[inland].mean()) if np.any(inland) else 0.0,
                    "annual_mean_c": float(temp.mean()),
                    "applied": diag["continental_seasonality_applied"],
                }
            )
    by = {(r["continentality_scale_km"], r["gain"]): r for r in rows}
    for scale in (300.0, 500.0, 800.0):
        a0 = by[(scale, 0.0)]["inland_amp_mean"]
        a25 = by[(scale, 0.25)]["inland_amp_mean"]
        a50 = by[(scale, 0.5)]["inland_amp_mean"]
        assert a50 > a25 > a0
        assert by[(scale, 0.0)]["applied"] is False
    assert load_planet_config(default_config_path()).climate_continental_seasonality_gain == 0.0
    test_continental_seasonality_sweep_is_recorded_not_retuned.rows = rows  # type: ignore[attr-defined]


def test_replace_keeps_named_states_unless_passed() -> None:
    climate = _toy_climate()
    hotter = climate.temperature_c + 1.0
    out = replace_climate_temperature(climate, hotter)
    assert np.allclose(out.temperature_c, hotter)
    assert np.allclose(out.temperature_base_c, climate.temperature_base_c)
    assert np.allclose(out.temperature_equilibrium_c, climate.temperature_equilibrium_c)
