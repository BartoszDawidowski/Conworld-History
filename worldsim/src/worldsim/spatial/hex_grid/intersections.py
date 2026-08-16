"""Hex ↔ vector intersection caches and river edge mask."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.hex_grid.layout import (
    EDGE_BITS,
    HexGridSpec,
    _NEIGH_EVEN_Q,
    _NEIGH_ODD_Q,
    hex_id,
    xy_to_hex,
)


def _point_hex(x: float, y: float, spec: HexGridSpec) -> int:
    q, r = xy_to_hex(x, y, width=spec.width, height=spec.height)
    return hex_id(q, r, width=spec.width)


def river_ids_per_hex(
    river_segments: list[Any],
    spec: HexGridSpec,
) -> list[list[int]]:
    """Hex → list of river segment ids whose polylines touch the hex."""
    out: list[list[int]] = [[] for _ in range(spec.n_cells)]
    seen: list[set[int]] = [set() for _ in range(spec.n_cells)]
    for seg in river_segments:
        sid = int(seg.id)
        for x, y in seg.geometry:
            hid = _point_hex(float(x), float(y), spec)
            if sid not in seen[hid]:
                seen[hid].add(sid)
                out[hid].append(sid)
    return out


def lake_ids_per_hex(
    lakes: list[Any],
    spec: HexGridSpec,
) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in range(spec.n_cells)]
    seen: list[set[int]] = [set() for _ in range(spec.n_cells)]
    for lake in lakes:
        lid = int(lake.id)
        for x, y in lake.polygon:
            hid = _point_hex(float(x), float(y), spec)
            if lid not in seen[hid]:
                seen[hid].add(lid)
                out[hid].append(lid)
    return out


def coastline_ids_per_hex(
    coastline: list[Any],
    spec: HexGridSpec,
    *,
    max_per_hex: int = 32,
) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in range(spec.n_cells)]
    counts = np.zeros(spec.n_cells, dtype=np.int32)
    for feat in coastline:
        fid = int(feat.id)
        if len(feat.geometry) < 1:
            continue
        x = float(feat.geometry[0][0])
        y = float(feat.geometry[0][1])
        if len(feat.geometry) >= 2:
            x = 0.5 * (x + float(feat.geometry[1][0]))
            y = 0.5 * (y + float(feat.geometry[1][1]))
        hid = _point_hex(x, y, spec)
        if counts[hid] < max_per_hex:
            out[hid].append(fid)
            counts[hid] += 1
    return out


def _edge_index_for_neighbor(
    q: int, r: int, nq: int, nr: int, *, width: int
) -> int | None:
    deltas = _NEIGH_ODD_Q if (q & 1) else _NEIGH_EVEN_Q
    dq = (nq - q) % width
    if dq > width // 2:
        dq -= width
    dr = nr - r
    for i, (ddq, ddr) in enumerate(deltas):
        if ddq == dq and ddr == dr:
            return i
    return None


def river_edge_mask(
    river_segments: list[Any],
    spec: HexGridSpec,
) -> NDArray[np.uint8]:
    """Bitmask of edges crossed by river polylines (derived cache).

    Bit order matches ``EDGE_BITS``: NE, E, SE, SW, W, NW.
    """
    _ = EDGE_BITS  # documented coupling
    masks = np.zeros(spec.n_cells, dtype=np.uint8)
    for seg in river_segments:
        geom = seg.geometry
        if len(geom) < 2:
            continue
        for (x0, y0), (x1, y1) in zip(geom, geom[1:]):
            h0 = _point_hex(float(x0), float(y0), spec)
            h1 = _point_hex(float(x1), float(y1), spec)
            if h0 == h1:
                continue
            q0, r0 = h0 % spec.width, h0 // spec.width
            q1, r1 = h1 % spec.width, h1 // spec.width
            e0 = _edge_index_for_neighbor(q0, r0, q1, r1, width=spec.width)
            if e0 is not None:
                masks[h0] |= np.uint8(1 << e0)
            e1 = _edge_index_for_neighbor(q1, r1, q0, r0, width=spec.width)
            if e1 is not None:
                masks[h1] |= np.uint8(1 << e1)
    return masks
