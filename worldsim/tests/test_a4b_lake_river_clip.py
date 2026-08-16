"""Milestone A4b/A4c — lake sanitize + river clip/snap outside lakes."""

from __future__ import annotations

import numpy as np

from worldsim.physical.vectorize.lakes import _sanitize_ring
from worldsim.physical.vectorize.rivers import (
    _midpoint_norm,
    clip_polyline_outside_lakes,
)


def test_sanitize_ring_rejects_degenerate() -> None:
    assert _sanitize_ring([]) == []
    assert _sanitize_ring([(0.0, 0.0), (0.0, 0.0)]) == []
    assert _sanitize_ring([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (0.0, 0.0)]) == []


def test_sanitize_ring_keeps_simple_triangle() -> None:
    ring = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0), (0.0, 0.0)]
    out = _sanitize_ring(ring)
    assert len(out) >= 4
    assert out[0] == out[-1]


def test_clip_polyline_outside_lakes_splits() -> None:
    lakes = np.zeros((4, 4), dtype=bool)
    lakes[1:3, 1:3] = True
    lake_id = np.zeros((4, 4), dtype=np.int32)
    lake_id[1:3, 1:3] = 7
    geom = [
        (0.1, 0.0),
        (0.2, 0.0),
        (0.4, 0.0),
        (0.5, 0.0),
        (0.8, 0.0),
        (0.9, 0.0),
    ]
    pieces = clip_polyline_outside_lakes(geom, lakes, lake_id)
    assert pieces, "expected at least one outside piece"
    for piece in pieces:
        assert len(piece.geometry) >= 2
        for x, y in piece.geometry:
            r = int(np.clip(np.floor((1.0 - y) * 0.5 * 4), 0, 3))
            c = int(np.clip(np.floor(x * 4), 0, 3))
            # Snap points may sit on the land/lake edge; allow lake edge cells
            # only if they are endpoints with lake_id set.
            if lakes[r, c]:
                assert piece.to_lake_id == 7 or piece.from_lake_id == 7


def test_clip_snaps_to_shore_and_sets_lake_id() -> None:
    lakes = np.zeros((4, 4), dtype=bool)
    lakes[2, 2] = True
    lake_id = np.zeros((4, 4), dtype=np.int32)
    lake_id[2, 2] = 3
    # y=0 → row 2; x=0.1→col0 land, x=0.6→col2 lake, x=0.9→col3 land
    geom = [(0.1, 0.0), (0.25, 0.0), (0.6, 0.0), (0.9, 0.0)]
    pieces = clip_polyline_outside_lakes(geom, lakes, lake_id)
    assert len(pieces) == 2
    inlet = pieces[0]
    outlet = pieces[1]
    assert inlet.to_lake_id == 3
    assert outlet.from_lake_id == 3
    # Last point of inlet should be shore mid between land and lake verts
    expected_in = _midpoint_norm((0.25, 0.0), (0.6, 0.0))
    assert abs(inlet.geometry[-1][0] - expected_in[0]) < 1e-9
    assert abs(inlet.geometry[-1][1] - expected_in[1]) < 1e-9
    expected_out = _midpoint_norm((0.6, 0.0), (0.9, 0.0))
    assert abs(outlet.geometry[0][0] - expected_out[0]) < 1e-9
