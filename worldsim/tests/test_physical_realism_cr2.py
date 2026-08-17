"""CR-2 — subgrid transpose, km reaches, metric gradient honesty."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.climate.pipeline import (
    downsample_elevation_subgrid_stats,
    downsample_land_elevation_mean,
)
from worldsim.physical.moisture.pipeline import MoistureParams, _plume_steps_for_grid
from worldsim.spatial.metrics import grid_metrics
from worldsim.validation.physical_realism.seed_suites import PROFILE_GRIDS


def test_subgrid_ridge_lands_in_correct_coarse_cell() -> None:
    """Known fine-cell spike → stats belong to that coarse block (F-10)."""
    out_h, out_w = 4, 8
    by, bx = 4, 4
    in_h, in_w = out_h * by, out_w * bx
    elev = np.zeros((in_h, in_w), dtype=np.float64)
    # Spike in coarse cell (j=1, i=3) at local fine offset (2, 1)
    cj, ci = 1, 3
    fj, fi = cj * by + 2, ci * bx + 1
    elev[fj, fi] = 5000.0

    stats = downsample_elevation_subgrid_stats(elev, out_w, out_h)
    jj, ii = np.unravel_index(
        int(np.argmax(stats["elev_ridge_m"])), stats["elev_ridge_m"].shape
    )
    assert (jj, ii) == (cj, ci)
    # Without transpose the spike landed in column ci+1; keep that regression locked.
    assert float(stats["elev_ridge_m"][cj, ci]) > float(
        stats["elev_ridge_m"][cj, ci + 1]
    )
    assert float(stats["elev_slope_rms"][cj, ci]) > 0.0
    assert float(stats["elevation_m"][cj, ci]) == pytest.approx(5000.0 / (by * bx))


def test_metric_ns_central_difference_uses_full_span() -> None:
    """Linear field slope = constant; NS gradient must not be doubled (CR-2)."""
    h, w = 11, 16
    g = grid_metrics(w, h)
    ns = g.ns_spacing_km() * 1000.0
    elev = np.zeros((h, w), dtype=np.float64)
    y = np.zeros(h, dtype=np.float64)
    for j in range(1, h):
        y[j] = y[j - 1] + ns[j - 1]
    elev[:] = y[:, None]  # 1 m rise per metre south
    _gx, gy = g.metric_gradients(elev)
    mid = gy[2:-2]
    assert float(np.mean(mid)) == pytest.approx(1.0, rel=1e-6, abs=1e-6)


def test_explicit_sst_inland_decay_km_default() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.sst_inland_decay_km == pytest.approx(1200.0)
    o = cfg.to_ocean_params()
    assert o.inland_decay_km == pytest.approx(1200.0)
    lengths = cfg.resolve_length_units()
    assert lengths.resolved["sst_inland_decay_km"].source == "km"


def test_plume_steps_scale_with_resolution_for_fixed_km() -> None:
    reach = 500.0
    aw, ah = PROFILE_GRIDS["atlas"]["climate"]
    fw, fh = PROFILE_GRIDS["full"]["climate"]
    steps_a = _plume_steps_for_grid(
        width=aw, height=ah, reach_km=reach, legacy_steps=None, planet_radius_km=6371.0
    )
    steps_f = _plume_steps_for_grid(
        width=fw, height=fh, reach_km=reach, legacy_steps=None, planet_radius_km=6371.0
    )
    assert steps_f > steps_a
    # Full climate is 2× Atlas linearly; rounding may nudge the integer ratio.
    assert steps_f / steps_a == pytest.approx(float(fw) / float(aw), rel=0.12)
    mp = MoistureParams(plume_mix_reach_km=reach)
    assert mp.plume_mix_reach_km == reach


def test_monsoon_coast_reach_km_on_config() -> None:
    cfg = load_planet_config(default_config_path())
    mp = cfg.to_moisture_params()
    assert mp.monsoon_coast_reach_km == pytest.approx(800.0)
    assert mp.plume_mix_reach_km == pytest.approx(500.0)


def test_land_only_downsample_avoids_bathymetry_mix() -> None:
    h, w = 8, 16
    elev = np.full((h, w), 1000.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :8] = True
    elev[:, :8] = -2000.0  # deep bathymetry
    out, ocean_out = downsample_land_elevation_mean(elev, ocean, 4, 2)
    assert float(out[0, 2]) == pytest.approx(1000.0)
    assert bool(ocean_out[0, 0]) is True
    assert float(out[0, 0]) == pytest.approx(-2000.0)
