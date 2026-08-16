"""Plan B6 — stroke simplify + Chaikin."""

from __future__ import annotations

from worldsim.export.stroke_smooth import (
    chaikin_open,
    douglas_peucker,
    smooth_closed_ring,
    smooth_open_polyline,
    split_seam_safe,
)


def test_douglas_peucker_keeps_endpoints_and_reduces() -> None:
    pts = [(i * 0.01, 0.0) for i in range(20)]
    pts += [(0.2 + i * 0.01, i * 0.01) for i in range(20)]
    out = douglas_peucker(pts, 0.005)
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]
    assert len(out) < len(pts)


def test_chaikin_keeps_endpoints() -> None:
    pts = [(0.0, 0.0), (0.5, 0.2), (1.0, 0.0)]
    out = chaikin_open(pts, iterations=2)
    assert out[0] == (0.0, 0.0)
    assert out[-1] == (1.0, 0.0)
    assert len(out) > len(pts)


def test_seam_split_no_wrap_chord() -> None:
    pts = [(0.9, 0.0), (0.95, 0.0), (0.05, 0.0), (0.1, 0.0)]
    pieces = split_seam_safe(pts)
    assert len(pieces) == 2
    for piece in pieces:
        for a, b in zip(piece, piece[1:]):
            assert abs(b[0] - a[0]) <= 0.5


def test_smooth_open_polyline_seam_safe() -> None:
    pts = [(0.0, 0.0), (0.2, 0.05), (0.4, 0.0), (0.6, -0.05), (0.8, 0.0)]
    pieces = smooth_open_polyline(pts, simplify_eps=0.001, chaikin_iters=2)
    assert pieces
    for piece in pieces:
        assert len(piece) >= 2
        for a, b in zip(piece, piece[1:]):
            assert abs(b[0] - a[0]) <= 0.5


def test_smooth_closed_ring_preserves_large_shape() -> None:
    """Mild lake smooth must not collapse a simple lake ring."""
    square = [(0.0, 0.0), (0.4, 0.0), (0.4, 0.3), (0.0, 0.3), (0.0, 0.0)]
    out = smooth_closed_ring(square)
    assert len(out) >= 4


def test_smooth_closed_ring_noise_does_not_grow() -> None:
    pts: list[tuple[float, float]] = []
    for i in range(30):
        x = i / 29.0 * 0.5
        y = 0.08 if i % 2 else 0.0
        pts.append((x, y))
    pts += [(0.5, 0.4), (0.0, 0.4), (0.0, 0.0)]
    amp_in = max(p[1] for p in pts if p[1] <= 0.1) - min(
        p[1] for p in pts if p[1] <= 0.1
    )
    out = smooth_closed_ring(pts, laplacian_iters=3, chaikin_iters=1)
    bottom = [p[1] for p in out if p[1] <= 0.12 and 0.0 <= p[0] <= 0.5]
    assert bottom
    amp_out = max(bottom) - min(bottom)
    assert amp_out <= amp_in + 1e-9
