"""PR-3 — periodic thermal response + physical climate/ocean scales."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.climate.temperature import (
    apply_periodic_thermal_inertia,
    build_monthly_temperature_c,
    continentality_factor,
    equilibrium_temperature_c,
)
from worldsim.physical.ocean.currents import western_eastern_boundary_masks
from worldsim.physical.ocean.sst import couple_temperature_with_sst_inland
from worldsim.spatial.metrics import grid_metrics
from worldsim.spatial.units_migration import resolve_planet_lengths
from worldsim.validation.physical_realism.seed_suites import PROFILE_GRIDS


def test_periodic_ocean_phase_lag_and_amplitude() -> None:
    h, w = 8, 8
    t_eq = np.zeros((12, h, w), dtype=np.float64)
    for m in range(12):
        t_eq[m] = 10.0 + 20.0 * np.sin(2 * np.pi * m / 12.0)
    ocean = np.ones((h, w), dtype=bool)
    cont = np.zeros((h, w), dtype=np.float64)
    temp, diag = apply_periodic_thermal_inertia(
        t_eq,
        ocean,
        cont,
        tau_land_months=0.55,
        tau_ocean_months=2.8,
        spinup_years=6,
    )
    assert diag["periodic_closure_ok"] is True
    # Ocean amplitude damped vs forcing
    assert float(temp.std()) < float(t_eq.std())
    # Phase lag: ocean max later than forcing max (forcing peaks near month 3)
    force_peak = int(np.argmax(t_eq[:, 0, 0]))
    resp_peak = int(np.argmax(temp[:, 0, 0]))
    lag = (resp_peak - force_peak) % 12
    assert 1 <= lag <= 4


def test_land_ocean_amplitude_contrast() -> None:
    h, w = 12, 24
    t_eq = np.zeros((12, h, w), dtype=np.float64)
    for m in range(12):
        t_eq[m] = 10.0 + 18.0 * np.sin(2 * np.pi * m / 12.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, w // 2 :] = True
    cont = continentality_factor(ocean, scale_cells=8.0)
    temp, _ = apply_periodic_thermal_inertia(t_eq, ocean, cont)
    land_amp = float(temp[:, :, : w // 2].std())
    ocean_amp = float(temp[:, :, w // 2 :].std())
    assert ocean_amp < land_amp


def test_ns_symmetry_annual_mean() -> None:
    height, width = 64, 32
    y = np.linspace(1.0 - 1.0 / height, -1.0 + 1.0 / height, height)
    lat = np.arcsin(np.clip(y, -1.0, 1.0))[:, None]
    lat = np.repeat(lat, width, axis=1)
    from worldsim.physical.climate.insolation import monthly_insolation_field

    insol = monthly_insolation_field(lat, axial_tilt_deg=23.44)
    elev = np.zeros((height, width))
    ocean = np.zeros((height, width), dtype=bool)
    ocean[:, :] = True  # all ocean → no continentality asymmetry
    temp, cont, t_eq, diag = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat,
        elevation_m=elev,
        ocean_mask=ocean,
        continentality_scale_km=1500.0,
        metrics=grid_metrics(width, height),
    )
    annual = temp.mean(axis=0)
    # Row j mirrors row height-1-j
    flipped = np.flipud(annual)
    assert float(np.max(np.abs(annual - flipped))) < 0.05
    assert diag["thermal_inertia"] == "periodic_first_order_v1"
    assert t_eq.shape == temp.shape
    assert cont.shape == (height, width)


def test_seasonal_phase_opposite_hemispheres() -> None:
    height, width = 48, 16
    y = np.linspace(1.0 - 1.0 / height, -1.0 + 1.0 / height, height)
    lat = np.arcsin(np.clip(y, -1.0, 1.0))[:, None]
    lat = np.repeat(lat, width, axis=1)
    from worldsim.physical.climate.insolation import monthly_insolation_field

    insol = monthly_insolation_field(lat, axial_tilt_deg=23.44)
    elev = np.zeros((height, width))
    ocean = np.ones((height, width), dtype=bool)
    temp, _, _, _ = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat,
        elevation_m=elev,
        ocean_mask=ocean,
        continentality_scale_km=1000.0,
        metrics=grid_metrics(width, height),
    )
    lat_deg = np.degrees(lat)
    nh = (lat_deg[:, 0] > 40.0) & (lat_deg[:, 0] < 55.0)
    sh = (lat_deg[:, 0] < -40.0) & (lat_deg[:, 0] > -55.0)
    nh_series = temp[:, nh, :].mean(axis=(1, 2))
    sh_series = temp[:, sh, :].mean(axis=(1, 2))
    assert int(np.argmax(nh_series)) != int(np.argmax(sh_series))
    assert float(nh_series[5]) > float(nh_series[11])
    assert float(sh_series[11]) > float(sh_series[5])


def test_lapse_controls_for_latitude() -> None:
    h, w = 20, 20
    lat = np.zeros((h, w))
    insol = np.full((12, h, w), 0.35)
    elev = np.zeros((h, w))
    elev[:, w // 2 :] = 3000.0
    ocean = np.zeros((h, w), dtype=bool)
    t_eq = equilibrium_temperature_c(
        insol,
        latitude_rad=lat,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=6.5,
        base_temp_c=15.0,
    )
    assert float(t_eq[:, :, w // 2 :].mean()) < float(t_eq[:, :, : w // 2].mean()) - 15.0


def test_sst_inland_decay_physical_km() -> None:
    h, w = 24, 64
    metrics = grid_metrics(w, h)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :20] = True
    temp = np.full((3, h, w), 10.0)
    sst = np.full((3, h, w), np.nan)
    sst[:, :, :20] = 22.0
    decay_km = 800.0
    coupled, diag = couple_temperature_with_sst_inland(
        temperature_c=temp,
        sst_c=sst,
        ocean_mask=ocean,
        mix=0.4,
        inland_decay_km=decay_km,
        metrics=metrics,
    )
    # Physical distance inland along equator-ish mid row
    j = h // 2
    coast_i = 20
    far_i = min(w - 1, coast_i + int(round(metrics.cells_from_km_ew(decay_km, j))))
    coast_d = float(coupled[0, j, coast_i] - 10.0)
    far_d = float(coupled[0, j, far_i] - 10.0)
    assert coast_d > far_d
    assert diag["inland_decay_km"] == decay_km


def test_same_km_reach_atlas_vs_full_cell_count_differs() -> None:
    """Same physical km → different cell counts on Atlas vs Full (no reinterpret)."""
    lengths = resolve_planet_lengths(None, inland_decay_cells=60.0)
    km = float(lengths.resolved["sst_inland_decay_km"].value_km)
    aw, ah = PROFILE_GRIDS["atlas"]["climate"]
    fw, fh = PROFILE_GRIDS["full"]["climate"]
    atlas = grid_metrics(aw, ah)
    full = grid_metrics(fw, fh)
    cells_atlas = atlas.cells_from_km_ew(km, ah // 2)
    cells_full = full.cells_from_km_ew(km, fh // 2)
    # Full climate is 2× Atlas climate linearly → ~2× cells for same km
    assert cells_full / cells_atlas == pytest.approx(float(fw) / float(aw), rel=0.05)
    # Boundary width similarly
    bkm = float(lengths.resolved["western_boundary_width_km"].value_km)
    ba = atlas.cells_from_km_ew(bkm, ah // 2)
    bf = full.cells_from_km_ew(bkm, fh // 2)
    assert bf / ba == pytest.approx(float(fw) / float(aw), rel=0.05)


def test_boundary_width_km_scales_with_resolution() -> None:
    ocean = np.zeros((32, 64), dtype=bool)
    ocean[:, 8:56] = True
    m_coarse = grid_metrics(64, 32)
    m_fine = grid_metrics(128, 64)
    # Same physical width on coarser grid → fewer cells
    width_km = m_coarse.km_from_cells_isotropic_midlat(3.0)
    w_c, _ = western_eastern_boundary_masks(ocean, width_km=width_km, metrics=m_coarse)
    ocean_f = np.zeros((64, 128), dtype=bool)
    ocean_f[:, 16:112] = True
    w_f, _ = western_eastern_boundary_masks(
        ocean_f, width_km=width_km, metrics=m_fine
    )
    # Fine strip should be thicker in cells for 2× linear resolution
    assert np.count_nonzero(w_f) > np.count_nonzero(w_c)


def test_config_ocean_params_include_km() -> None:
    config = load_planet_config(default_config_path())
    o = config.to_ocean_params()
    assert o.inland_decay_km is not None and o.inland_decay_km > 1000.0
    assert o.western_boundary_width_km is not None and o.western_boundary_width_km > 0.0
    assert o.inland_decay_cells == 60.0


def test_named_temperature_states_in_build() -> None:
    h, w = 16, 16
    lat = np.zeros((h, w))
    insol = np.full((12, h, w), 0.32)
    for m in range(12):
        insol[m] = 0.25 + 0.15 * np.sin(2 * np.pi * m / 12.0)
    elev = np.zeros((h, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    base, cont, t_eq, diag = build_monthly_temperature_c(
        insolation=insol,
        latitude_rad=lat,
        elevation_m=elev,
        ocean_mask=ocean,
        continentality_scale_km=1200.0,
        metrics=grid_metrics(w, h),
    )
    assert diag["temperature_state"] == "temperature_base_c"
    assert diag["lapse_owner"] == "climate_equilibrium"
    assert not np.allclose(base, t_eq)
    assert cont.max() > 0.0
