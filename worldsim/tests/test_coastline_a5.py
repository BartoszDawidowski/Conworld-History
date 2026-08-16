"""Milestone A5 — coastline merge + dateline seam safety."""

from __future__ import annotations

import time

import numpy as np

from worldsim.physical.terrain.coastline import (
    _crosses_seam,
    count_micro_edges,
    extract_coastline_segments,
)


def test_no_full_width_chord_at_dateline() -> None:
    w, h = 32, 16
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, : w // 2] = True
    ocean[:, -1] = True
    ocean[:, -2] = False
    feats = extract_coastline_segments(ocean, max_features=50_000)
    assert feats
    for f in feats:
        geom = f.geometry
        for i in range(len(geom) - 1):
            dx = abs(geom[i + 1][0] - geom[i][0])
            assert dx <= 0.5 + 1e-9, (geom[i], geom[i + 1], dx)


def test_merge_reduces_feature_count() -> None:
    rng = np.random.default_rng(0)
    ocean = rng.random((64, 128)) > 0.55
    micro = count_micro_edges(ocean)
    merged = extract_coastline_segments(ocean, max_features=200_000)
    assert len(merged) > 0
    assert len(merged) < micro
    assert len(merged) * 2 <= micro


def test_crosses_seam_helper() -> None:
    assert _crosses_seam((0.01, 0.0), (0.99, 0.0))
    assert not _crosses_seam((0.10, 0.0), (0.12, 0.0))


def test_atlas_resolution_coast_metrics() -> None:
    """Blocky landmasses (not pixel noise): merge ≫ micro-edges, finishes fast."""
    rng = np.random.default_rng(124)
    # 32×16 macro cells → 1024×512 grid (Atlas terrain-ish)
    macro = rng.random((16, 32)) > 0.45
    ocean = np.repeat(np.repeat(macro, 32, axis=0), 32, axis=1)
    assert ocean.shape == (512, 1024)
    t0 = time.perf_counter()
    micro_n = count_micro_edges(ocean)
    feats = extract_coastline_segments(ocean, max_features=200_000)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, elapsed
    assert len(feats) < micro_n
    ratio = micro_n / max(len(feats), 1)
    assert ratio >= 5.0, (micro_n, len(feats), ratio)
    print(
        f"A5 metrics atlas-like: micro={micro_n} merged={len(feats)} "
        f"ratio={ratio:.1f} time_s={elapsed:.3f}"
    )


def test_last_column_horizontal_edge_not_wrapped() -> None:
    """Regression: i=width-1 horizontal edge must stay near x=1, not jump to 0."""
    w, h = 8, 4
    ocean = np.zeros((h, w), dtype=bool)
    ocean[1, w - 1] = True
    ocean[2, w - 1] = False
    feats = extract_coastline_segments(ocean, max_features=1000)
    # At least one horizontal edge near the right side
    assert any(
        all(pt[0] > 0.5 for pt in f.geometry) for f in feats
    ), [f.geometry for f in feats]
