"""PR-1 GridMetrics + hex layout + length-unit migration tests."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.spatial.hex_grid.layout import (
    HEX_LAYOUT_ALGORITHM_VERSION,
    HexGridSpec,
    all_hex_centers,
    hex_center_xy,
    hex_latitudes_deg,
    xy_to_hex,
)
from worldsim.spatial.metrics import EARTH_RADIUS_KM, grid_metrics
from worldsim.spatial.units_migration import (
    LENGTH_UNITS_SCHEMA_VERSION,
    emit_length_migration_warnings,
    metrics_for_profile,
    resolve_planet_lengths,
)


def test_hex_layout_version_is_v2() -> None:
    assert HEX_LAYOUT_ALGORITHM_VERSION == 2


def test_hex_no_pole_clip_production() -> None:
    spec = HexGridSpec(width=256, height=128)
    _xs, ys = all_hex_centers(spec)
    assert np.all(np.abs(ys) < 1.0 - 1e-12)


def test_hex_mean_latitude_near_zero() -> None:
    lats = hex_latitudes_deg(HexGridSpec(width=256, height=128))
    assert abs(float(lats.mean())) < 0.25


def test_hex_row_y_mirror_symmetry() -> None:
    w, h = 32, 16
    row_y = []
    for r in range(h):
        ys = [hex_center_xy(q, r, width=w, height=h)[1] for q in range(w)]
        row_y.append(float(np.mean(ys)))
    for r in range(h // 2):
        assert abs(row_y[r] + row_y[h - 1 - r]) < 1e-9


def test_xy_to_hex_roundtrip_sample() -> None:
    w, h = 64, 32
    for q, r in ((0, 0), (1, 0), (3, 5), (63, 31), (31, 16)):
        x, y = hex_center_xy(q, r, width=w, height=h)
        q2, r2 = xy_to_hex(x, y, width=w, height=h)
        assert (q2, r2) == (q, r)


def test_grid_metrics_cell_area_sums_to_sphere() -> None:
    g = grid_metrics(512, 256)
    total = g.cell_area_km2 * g.width * g.height
    sphere = 4.0 * np.pi * EARTH_RADIUS_KM**2
    assert total == pytest.approx(sphere, rel=1e-12)


def test_grid_metrics_atlas_full_ew_midlat_comparable_physical() -> None:
    """Same planet radius: mid-lat EW km/cell differs by resolution, not meaning."""
    atlas = metrics_for_profile("atlas")
    full = metrics_for_profile("full")
    # 60 Atlas climate cells → km; Full needs ~2× cells for same km (512 vs 1024)
    km = atlas.km_from_cells_isotropic_midlat(60.0)
    cells_full = full.cells_from_km_ew(km, row=full.height // 2)
    assert cells_full == pytest.approx(120.0, rel=0.02)


def test_grid_metrics_distance_to_mask_wraps_ew() -> None:
    g = grid_metrics(32, 16)
    mask = np.zeros((16, 32), dtype=bool)
    mask[8, 0] = True
    dist = g.distance_to_mask_km(mask, connectivity=4)
    # Cell just west of seam (col 31) should be one EW step from col 0
    step = float(g.ew_spacing_km()[8])
    assert dist[8, 31] == pytest.approx(step, rel=1e-6)


def test_metric_gradients_finite() -> None:
    g = grid_metrics(40, 20)
    elev = np.linspace(0, 1000, 40 * 20, dtype=np.float64).reshape(20, 40)
    gx, gy = g.metric_gradients(elev)
    assert np.all(np.isfinite(gx)) and np.all(np.isfinite(gy))
    slope = g.metric_slope(elev)
    assert float(slope.mean()) > 0.0


def test_length_migration_converts_cells_with_warning_payload() -> None:
    from worldsim.spatial import units_migration as um

    um._EMITTED_WARNINGS.clear()
    effective = resolve_planet_lengths(
        {},
        inland_decay_cells=60.0,
        source_profile="atlas",
    )
    assert effective.length_units_schema_version == LENGTH_UNITS_SCHEMA_VERSION
    sst = effective.resolved["sst_inland_decay_km"]
    assert sst.source == "cells_converted"
    assert sst.legacy_cells == 60.0
    assert sst.value_km > 0.0
    assert sst.warning is not None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        emit_length_migration_warnings(effective)
    assert any("inland_decay_cells" in str(w.message) for w in caught)


def test_length_migration_prefers_explicit_km() -> None:
    raw = {"ocean": {"sst_inland_decay_km": 1234.5, "inland_decay_cells": 60.0}}
    effective = resolve_planet_lengths(raw, inland_decay_cells=60.0)
    sst = effective.resolved["sst_inland_decay_km"]
    assert sst.source == "km"
    assert sst.value_km == pytest.approx(1234.5)


def test_planet_config_resolve_length_units() -> None:
    config = load_planet_config(default_config_path())
    effective = config.resolve_length_units()
    assert "sst_inland_decay_km" in effective.resolved
    assert config.planet_radius_km == pytest.approx(6371.0)
