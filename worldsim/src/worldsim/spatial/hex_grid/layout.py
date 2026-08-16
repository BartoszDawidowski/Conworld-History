"""Flat-top hex layout on cylindrical equal-area plane (Milestone 15 / PR-1).

Grid is 256×128 = 32 768 cells. Placement is uniform in normalised ``(x, y)``
(equal-area cylindrical), so hexes cover approximately equal surface area.

PR-1 layout algorithm v2: odd-q columns occupy interleaved half-rows so centres
never clip to ``y = ±1`` and the latitude field is N–S symmetric.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.coordinates import wrap_x, y_to_lat

# Bump when centre geometry changes — invalidates hex caches / aggregates.
HEX_LAYOUT_ALGORITHM_VERSION = 2

# Flat-top odd-q offset neighbour deltas (dq, dr) for even / odd columns.
_NEIGH_EVEN_Q: tuple[tuple[int, int], ...] = (
    (+1, 0),
    (+1, -1),
    (0, -1),
    (-1, -1),
    (-1, 0),
    (0, +1),
)
_NEIGH_ODD_Q: tuple[tuple[int, int], ...] = (
    (+1, +1),
    (+1, 0),
    (0, -1),
    (-1, 0),
    (-1, +1),
    (0, +1),
)

# Bit order for river_edge_mask: NE, E, SE, SW, W, NW
EDGE_BITS: tuple[str, ...] = ("NE", "E", "SE", "SW", "W", "NW")


@dataclass(frozen=True)
class HexGridSpec:
    width: int = 256
    height: int = 128
    orientation: str = "flat_top"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("hex grid dimensions must be positive")
        if self.orientation != "flat_top":
            raise ValueError("only flat_top orientation is supported")

    @property
    def n_cells(self) -> int:
        return int(self.width * self.height)


def hex_id(q: int, r: int, *, width: int) -> int:
    return int(r) * int(width) + int(q)


def hex_qr(hex_index: int, *, width: int) -> tuple[int, int]:
    return int(hex_index) % int(width), int(hex_index) // int(width)


def _half_row_index(q: int, r: int) -> int:
    """Interleaved half-row in ``[0, 2*height)`` for balanced odd-q stagger."""
    return 2 * int(r) + (int(q) & 1)


def hex_center_xy(q: int, r: int, *, width: int, height: int) -> tuple[float, float]:
    """Centre of hex ``(q,r)`` in normalised cylindrical ``(x, y)``.

    ``r = 0`` is north (``y → +1``). Flat-top odd-q stagger uses interleaved
    half-rows so no centre reaches the poles ``y = ±1``.
    """
    x = (float(q) + 0.5) / float(width)
    half = _half_row_index(q, r)
    # half ∈ [0, 2H-1] → y ∈ (1 - 0.5/H, -1 + 0.5/H)
    y = 1.0 - (float(half) + 0.5) / float(height)
    return wrap_x(x), float(y)


def all_hex_centers(spec: HexGridSpec) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(x[n], y[n])`` centres in hex-id order."""
    n = spec.n_cells
    xs = np.empty(n, dtype=np.float64)
    ys = np.empty(n, dtype=np.float64)
    for r in range(spec.height):
        for q in range(spec.width):
            i = hex_id(q, r, width=spec.width)
            xs[i], ys[i] = hex_center_xy(q, r, width=spec.width, height=spec.height)
    return xs, ys


def xy_to_hex(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    """Approximate inverse: nearest hex by odd-q flat-top lattice."""
    y_c = float(np.clip(y, -1.0, 1.0))
    x_c = wrap_x(x)
    q0 = int(np.clip(np.floor(x_c * width), 0, width - 1))
    best_q, best_r = q0, 0
    best_d = 1e9
    half_est = (1.0 - y_c) * float(height) - 0.5
    for dq in (-1, 0, 1):
        q = (q0 + dq) % width
        if q & 1:
            r_est = (half_est - 1.0) * 0.5
        else:
            r_est = half_est * 0.5
        for dr in (-1, 0, 1):
            r = int(np.clip(round(r_est) + dr, 0, height - 1))
            cx, cy = hex_center_xy(q, r, width=width, height=height)
            dx = cx - x_c
            if dx > 0.5:
                dx -= 1.0
            elif dx < -0.5:
                dx += 1.0
            d = dx * dx + (cy - y_c) * (cy - y_c)
            if d < best_d:
                best_d = d
                best_q, best_r = q, r
    return best_q, best_r


def _center_xy_unclipped(q: int, r: int, *, width: int, height: int) -> tuple[float, float]:
    """Centre for Voronoi corners (phantom N/S neighbours may leave domain)."""
    x = (float(q) + 0.5) / float(width)
    half = _half_row_index(q, r)
    y = 1.0 - (float(half) + 0.5) / float(height)
    return wrap_x(x), float(y)


def _unwrap_x_near(x: float, ref: float) -> float:
    x = wrap_x(x)
    d = x - ref
    if d > 0.5:
        return x - 1.0
    if d < -0.5:
        return x + 1.0
    return x


def hex_corner_offsets(*, width: int, height: int) -> tuple[tuple[float, float], ...]:
    """Deprecated approximate offsets. Prefer ``hex_vertices_xy``."""
    dx = 1.0 / float(width)
    dy = 1.0 / float(height)  # half-row spacing in y for layout v2
    return (
        (0.5 * dx, 0.0),
        (0.25 * dx, -0.5 * dy),
        (-0.25 * dx, -0.5 * dy),
        (-0.5 * dx, 0.0),
        (-0.25 * dx, 0.5 * dy),
        (0.25 * dx, 0.5 * dy),
    )


def hex_vertices_xy(
    q: int,
    r: int,
    *,
    width: int,
    height: int,
) -> list[tuple[float, float]]:
    """Normalised vertices of hex ``(q,r)`` as Voronoi cell of the analytical lattice.

    Each corner is the mean of this centre and two consecutive neighbour centres
    (E–W wrap; phantom centres past N/S edges). Adjacent hexes share edges — no gaps.
    """
    cx, cy = _center_xy_unclipped(q, r, width=width, height=height)
    deltas = _NEIGH_ODD_Q if (int(q) & 1) else _NEIGH_EVEN_Q
    neigh_c: list[tuple[float, float]] = []
    for dq, dr in deltas:
        nq = (int(q) + int(dq)) % int(width)
        nr = int(r) + int(dr)
        neigh_c.append(_center_xy_unclipped(nq, nr, width=width, height=height))
    verts: list[tuple[float, float]] = []
    for i in range(6):
        x1, y1 = neigh_c[i]
        x2, y2 = neigh_c[(i + 1) % 6]
        x1u = _unwrap_x_near(x1, cx)
        x2u = _unwrap_x_near(x2, cx)
        vx = wrap_x((cx + x1u + x2u) / 3.0)
        vy = (cy + y1 + y2) / 3.0
        verts.append((vx, float(np.clip(vy, -1.0, 1.0))))
    return verts


def neighbours(
    q: int,
    r: int,
    *,
    width: int,
    height: int,
) -> list[int | None]:
    """Six neighbour hex ids (NE,E,SE,SW,W,NW). ``None`` if off north/south edge."""
    deltas = _NEIGH_ODD_Q if (q & 1) else _NEIGH_EVEN_Q
    out: list[int | None] = []
    for dq, dr in deltas:
        nq = (q + dq) % width  # E–W wrap
        nr = r + dr
        if nr < 0 or nr >= height:
            out.append(None)  # no N–S wrap
        else:
            out.append(hex_id(nq, nr, width=width))
    return out


def neighbour_matrix(spec: HexGridSpec) -> NDArray[np.int32]:
    """Shape ``[n_cells, 6]``; ``-1`` marks missing N/S neighbour."""
    n = spec.n_cells
    mat = np.full((n, 6), -1, dtype=np.int32)
    for r in range(spec.height):
        for q in range(spec.width):
            i = hex_id(q, r, width=spec.width)
            for e, nid in enumerate(
                neighbours(q, r, width=spec.width, height=spec.height)
            ):
                mat[i, e] = -1 if nid is None else int(nid)
    return mat


def hex_latitudes_deg(spec: HexGridSpec) -> NDArray[np.float64]:
    _xs, ys = all_hex_centers(spec)
    return np.array([y_to_lat(float(y)) for y in ys], dtype=np.float64)
