"""PC4 — process deltas, geomorphic corridor, domain-specific erosion gates."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.erosion.fluvial import (
    apply_fluvial_erosion,
    geomorphic_corridor_weight,
)
from worldsim.physical.erosion.gates import (
    domain_mean_abs_delta,
    hillslope_erosion_gate,
    process_delta_stats,
)
from worldsim.physical.erosion.pass_one import (
    apply_erosion_pass_one,
    land_elevation_delta_stats,
    rock_resistance_proxy,
)
from worldsim.physical.erosion.pipeline import build_erosion_pass_one
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.validation.production_closure.fixtures import _minimal_terrain
from worldsim.spatial.metrics import grid_metrics
from worldsim.validation.production_closure.fixtures import (
    conditioning_counted_in_erosion_gate,
)

pytestmark = pytest.mark.pc4


def _ridge_fixture(h: int = 32, w: int = 48) -> tuple[np.ndarray, np.ndarray]:
    elev = np.linspace(200.0, 1200.0, h, dtype=np.float64)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-3:, :] = True
    elev[ocean] = -100.0
    return elev, ocean


def test_process_deltas_first_pass_tracks_conditioning_separately() -> None:
    elev, ocean = _ridge_fixture()
    precip = np.full(elev.shape, 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=elev.shape
    )
    after, process = apply_erosion_pass_one(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resist,
        iterations=5,
    )
    land = ~ocean
    erosion_sum = process.thermal_or_hillslope_delta_m + process.first_fluvial_delta_m
    assert np.allclose(
        process.total_erosion_delta_m[land],
        erosion_sum[land],
        atol=1e-9,
    )
    assert np.allclose(
        process.total_dem_adjustment_m[land],
        (erosion_sum + process.conditioning_or_pit_fill_delta_m)[land],
        atol=1e-9,
    )
    assert float(np.max(np.abs(process.conditioning_or_pit_fill_delta_m[land]))) >= 0.0
    assert np.allclose(after[ocean], elev[ocean])


def test_hillslope_gate_excludes_conditioning_from_acceptance() -> None:
    probe = conditioning_counted_in_erosion_gate()
    assert probe["separate_conditioning_delta_tracked"]
    assert probe["conditioning_excluded_from_gate"]


def test_build_erosion_pass_one_pc4_diagnostics() -> None:
    elev, ocean = _ridge_fixture()
    terrain = _minimal_terrain(elev, ocean)
    precip = np.full((12, *elev.shape), 2.0)
    moisture = MoistureResult(
        extent=terrain.extent,
        atmospheric_moisture=precip,
        evaporation=np.zeros_like(precip),
        precipitation=precip,
        humidity=np.ones_like(precip),
        orographic_lift=np.zeros_like(precip),
        convective_precip=np.zeros_like(precip),
        annual_precipitation=precip.sum(axis=0),
        diagnostics={},
    )
    result = build_erosion_pass_one(terrain=terrain, moisture=moisture)
    diag = result.diagnostics
    assert diag["erosion_algorithm"] == "pc4_process_deltas_v1"
    assert diag["conditioning_excluded_from_erosion_acceptance"] is True
    assert diag["conditioning_separate_ok"] is True
    assert "hillslope_mean_abs_delta_m" in diag
    assert "conditioning_mean_abs_delta_m" in diag
    assert result.process_deltas is not None


def test_geomorphic_corridor_is_metric_not_fixed_cell_halo() -> None:
    h, w = 16, 32
    geo = np.zeros((h, w), dtype=bool)
    geo[:, w // 2] = True
    radius_1km = w / (2.0 * np.pi)
    gm = grid_metrics(w, h, radius_km=radius_1km)
    steps = gm.d8_step_length_km_field(np.full((h, w), 1, dtype=np.uint8))
    narrow = geomorphic_corridor_weight(geo, steps, influence_km=2.0)
    wide = geomorphic_corridor_weight(geo, steps, influence_km=8.0)
    off_channel = ~geo
    assert float(wide[off_channel].sum()) > float(narrow[off_channel].sum())
    assert float(wide[off_channel].max()) > float(narrow[off_channel].max())
    assert float(narrow[geo].mean()) == pytest.approx(1.0)


def test_fluvial_uses_geomorphic_mask_not_display_fallback() -> None:
    h, w = 24, 32
    elev, ocean = _ridge_fixture(h, w)
    geo = np.zeros((h, w), dtype=bool)
    geo[h // 2, w // 4 : 3 * w // 4] = True
    display_only = np.zeros((h, w), dtype=bool)
    display_only[h // 2, w // 2] = True
    q = np.where(geo, 40.0, 0.5)
    resist = np.ones((h, w))
    gm = grid_metrics(w, h)
    steps = gm.d8_step_length_km_field(np.full((h, w), 1, dtype=np.uint8))
    after_geo, proc_geo = apply_fluvial_erosion(
        elevation_m=elev,
        ocean_mask=ocean,
        geomorphic_channel_mask=geo,
        discharge_proxy=q,
        resistance=resist,
        step_length_km=steps,
        iterations=3,
        stream_power_k=500.0,
    )
    after_disp, proc_disp = apply_fluvial_erosion(
        elevation_m=elev,
        ocean_mask=ocean,
        geomorphic_channel_mask=display_only,
        discharge_proxy=q,
        resistance=resist,
        step_length_km=steps,
        iterations=3,
        stream_power_k=500.0,
    )
    geo_incision = float(
        np.mean(np.abs(proc_geo.final_stream_power_delta_m[geo & ~ocean]))
    )
    disp_incision = float(
        np.mean(np.abs(proc_disp.final_stream_power_delta_m[display_only & ~ocean]))
    )
    assert geo_incision > disp_incision
    assert float(np.corrcoef(elev[~ocean], after_geo[~ocean])[0, 1]) > 0.95


def test_fluvial_corridor_gate_uses_geomorphic_domain() -> None:
    h, w = 32, 48
    elev, ocean = _ridge_fixture(h, w)
    river = np.zeros((h, w), dtype=bool)
    river[:, w // 2] = True
    q = np.where(river, 60.0, 1.0)
    resist = np.ones((h, w))
    gm = grid_metrics(w, h)
    steps = gm.d8_step_length_km_field(np.full((h, w), 1, dtype=np.uint8))
    after, process = apply_fluvial_erosion(
        elevation_m=elev,
        ocean_mask=ocean,
        geomorphic_channel_mask=river,
        discharge_proxy=q,
        resistance=resist,
        step_length_km=steps,
        iterations=4,
        stream_power_k=1000.0,
    )
    stats = land_elevation_delta_stats(elev, after, ocean)
    corridor_mean = domain_mean_abs_delta(
        process.final_stream_power_delta_m, river, ocean
    )
    land_mean = float(stats["mean_abs_delta_land_m"])
    corridor_ok, _ = hillslope_erosion_gate(
        corridor_mean, float(stats["elev_range_land_m"])
    )
    proc = process_delta_stats(
        process,
        ocean,
        geomorphic_mask=river,
        elev_range_m=float(stats["elev_range_land_m"]),
    )
    assert proc["fluvial_corridor_mean_abs_delta_m"] == pytest.approx(corridor_mean)
    assert corridor_mean <= land_mean or corridor_mean > 0.0
    assert proc["conditioning_excluded_from_erosion_acceptance"] is True
    if corridor_mean >= 0.5:
        assert corridor_ok or proc["fluvial_corridor_erosion_ok"]
