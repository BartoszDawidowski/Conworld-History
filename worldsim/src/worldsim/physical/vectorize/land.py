"""Land polygons from ocean mask (Plan B3 — atlas presentation rings)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from worldsim.physical.vectorize.lakes import _sanitize_ring

_MAX_DX = 0.5
_Q = 1e6  # endpoint quantisation


@dataclass
class LandPolygon:
    id: int
    ring: list[tuple[float, float]]  # closed normalised ring
    area_cells: int
    component_id: int

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "properties": {
                "id": self.id,
                "area_cells": self.area_cells,
                "component_id": self.component_id,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[float(x), float(y)] for x, y in self.ring]],
            },
        }


def _qkey(x: float, y: float) -> tuple[int, int]:
    return int(round(x * _Q)), int(round(y * _Q))


def _xy_corner(i: float, j: float, width: int, height: int) -> tuple[float, float]:
    """Grid corner / edge endpoint → normalised (x,y); x clamped to [0,1)."""
    x = (float(i) + 0.5) / float(width)
    if x >= 1.0:
        x = float(np.nextafter(1.0, 0.0))
    if x < 0.0:
        x = 0.0
    y = 1.0 - (float(j) + 0.5) * 2.0 / float(height)
    return float(x), float(y)


def _label_land_cylindrical(land: NDArray[np.bool_]) -> tuple[NDArray[np.int32], int]:
    """8-connected land labels with E–W wrap merge."""
    land = np.asarray(land, dtype=bool)
    h, w = land.shape
    structure = np.ones((3, 3), dtype=bool)
    labeled, n = ndimage.label(land, structure=structure)
    if n == 0:
        return np.zeros((h, w), dtype=np.int32), 0

    parent = np.arange(n + 1, dtype=np.int32)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = int(parent[a])
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Merge labels that touch across the dateline.
    for j in range(h):
        a = int(labeled[j, 0])
        b = int(labeled[j, w - 1])
        if a > 0 and b > 0:
            union(a, b)
        # diagonal wrap touches
        if j + 1 < h:
            a2 = int(labeled[j + 1, 0])
            b2 = int(labeled[j, w - 1])
            if a2 > 0 and b2 > 0:
                union(a2, b2)
            a3 = int(labeled[j, 0])
            b3 = int(labeled[j + 1, w - 1])
            if a3 > 0 and b3 > 0:
                union(a3, b3)

    remap = np.zeros(n + 1, dtype=np.int32)
    next_id = 0
    for lab in range(1, n + 1):
        root = find(lab)
        if remap[root] == 0:
            next_id += 1
            remap[root] = next_id
        remap[lab] = remap[root]
    out = remap[labeled]
    return out.astype(np.int32), int(next_id)


def _component_boundary_segments(
    component: NDArray[np.bool_],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Land/ocean (or exterior) edge segments as normalised 2-point lines."""
    land = np.asarray(component, dtype=bool)
    h, w = land.shape
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []

    # Horizontal interfaces between row j and j+1
    for j in range(h - 1):
        for i in range(w):
            a = bool(land[j, i])
            b = bool(land[j + 1, i])
            if a == b:
                continue
            p0 = _xy_corner(i - 0.5, j + 0.5, w, h)
            p1 = _xy_corner(i + 0.5, j + 0.5, w, h)
            if abs(p1[0] - p0[0]) <= _MAX_DX:
                segs.append((p0, p1))

    # Vertical interfaces between col i and i+1 (no wrap chord)
    for i in range(w - 1):
        for j in range(h):
            a = bool(land[j, i])
            b = bool(land[j, i + 1])
            if a == b:
                continue
            p0 = _xy_corner(i + 0.5, j - 0.5, w, h)
            p1 = _xy_corner(i + 0.5, j + 0.5, w, h)
            if abs(p0[0] - p1[0]) <= _MAX_DX:
                segs.append((p0, p1))
    # Dateline vertical: land[j,0] vs land[j,w-1] — emit edge at x≈0 and x≈1 separately
    # as short verticals (no horizontal chord across the map).
    for j in range(h):
        a = bool(land[j, 0])
        b = bool(land[j, w - 1])
        if a == b:
            continue
        # Edge on west side (x near 0) and east side (x near 1) as two vertical stubs
        # belonging to the land cell's outer face.
        if a and not b:
            p0 = _xy_corner(-0.5, j - 0.5, w, h)
            p1 = _xy_corner(-0.5, j + 0.5, w, h)
            segs.append((p0, p1))
        elif b and not a:
            p0 = _xy_corner(w - 0.5, j - 0.5, w, h)
            p1 = _xy_corner(w - 0.5, j + 0.5, w, h)
            segs.append((p0, p1))

    return segs


def _stitch_rings(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Chain 2-point segments into closed rings (endpoint matching)."""
    if not segments:
        return []
    adj: dict[tuple[int, int], list[tuple[tuple[int, int], tuple[float, float], int]]] = (
        defaultdict(list)
    )
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[float, float], tuple[float, float]]] = []
    for p0, p1 in segments:
        k0, k1 = _qkey(*p0), _qkey(*p1)
        if k0 == k1:
            continue
        edges.append((k0, k1, p0, p1))
    used = np.zeros(len(edges), dtype=bool)
    for ei, (k0, k1, p0, p1) in enumerate(edges):
        adj[k0].append((k1, p1, ei))
        adj[k1].append((k0, p0, ei))

    rings: list[list[tuple[float, float]]] = []
    for start_ei, (sk0, sk1, sp0, sp1) in enumerate(edges):
        if used[start_ei]:
            continue
        used[start_ei] = True
        ring: list[tuple[float, float]] = [sp0, sp1]
        curr_k = sk1
        start_k = sk0
        guard = 0
        while curr_k != start_k and guard < len(edges) + 2:
            guard += 1
            progressed = False
            for other_k, pb, ei in adj[curr_k]:
                if used[ei]:
                    continue
                used[ei] = True
                ring.append(pb)
                curr_k = other_k
                progressed = True
                break
            if not progressed:
                break
        if curr_k == start_k and len(ring) >= 3:
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            rings.append(ring)
    return rings


def _split_dateline_ring(
    ring: list[tuple[float, float]],
) -> list[list[tuple[float, float]]]:
    """Split a ring into pieces that do not jump |Δx|>0.5; close each piece."""
    if len(ring) < 4:
        return []
    # Drop closing duplicate for walk
    pts = list(ring)
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return []

    pieces: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = [pts[0]]
    for i in range(1, len(pts)):
        x0, _y0 = cur[-1]
        x1, y1 = pts[i]
        if abs(x1 - x0) > _MAX_DX:
            if len(cur) >= 3:
                pieces.append(cur)
            cur = [(x1, y1)]
        else:
            cur.append((x1, y1))
    # close loop: last → first may also cross
    if len(cur) >= 1:
        x0, _y0 = cur[-1]
        x1, y1 = pts[0]
        if abs(x1 - x0) <= _MAX_DX:
            # merge with first piece if we split
            if pieces and abs(pieces[0][0][0] - x0) <= _MAX_DX:
                cur.extend(pieces[0])
                pieces[0] = cur
            else:
                pieces.append(cur)
        else:
            pieces.append(cur)

    out: list[list[tuple[float, float]]] = []
    for piece in pieces:
        if len(piece) < 3:
            continue
        cleaned = _sanitize_ring(piece)
        if len(cleaned) >= 4:
            out.append(cleaned)
    return out


def _ring_area_abs(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return abs(a) * 0.5


def _ring_interior_on_land(
    ring: list[tuple[float, float]],
    land: NDArray[np.bool_],
) -> bool:
    """True if the ring interior is land (exterior), not ocean (inland-sea hole).

    Samples inward offsets from edge midpoints (both normals; keep in-ring side)
    so concave continents with large lakes are not misclassified by centroid.
    """
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    if len(pts) < 3:
        return False
    h, w = land.shape
    step = max(0.5 / float(w), 1.0 / float(h))
    land_votes = 0
    ocean_votes = 0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        mx = (x0 + x1) * 0.5
        my = (y0 + y1) * 0.5
        dx, dy = x1 - x0, y1 - y0
        length = float(np.hypot(dx, dy))
        if length < 1e-12:
            continue
        nx = (-dy / length) * step
        ny = (dx / length) * step
        for sx, sy in ((mx + nx, my + ny), (mx - nx, my - ny)):
            if not _point_in_ring(sx, sy, ring):
                continue
            c = int(np.clip(np.floor(sx * w), 0, w - 1))
            r = int(np.clip(np.floor((1.0 - sy) * 0.5 * h), 0, h - 1))
            if land[r, c]:
                land_votes += 1
            else:
                ocean_votes += 1
    if land_votes + ocean_votes == 0:
        return False
    return land_votes >= ocean_votes


def extract_land_polygons(
    ocean_mask: NDArray[np.bool_],
    *,
    min_cells: int = 4,
    min_ring_area: float = 1e-8,
    max_polygons: int = 50_000,
) -> list[LandPolygon]:
    """Build closed land rings from ``ocean_mask`` (Atlas presentation SoT).

    Uses 8-connected components with cylindrical E–W merge, boundary segment
    chaining, and dateline splits so Godot never receives full-width chords.

    Inland-sea hole rings are dropped (centroid on ocean) so fill never paints
    lakes as land.
    """
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    if not np.any(land):
        return []

    labeled, n_comp = _label_land_cylindrical(land)
    polys: list[LandPolygon] = []
    next_id = 1

    for cid in range(1, n_comp + 1):
        comp = labeled == cid
        area_cells = int(np.count_nonzero(comp))
        if area_cells < min_cells:
            continue
        segs = _component_boundary_segments(comp)
        rings = _stitch_rings(segs)
        for ring in rings:
            for piece in _split_dateline_ring(ring):
                if _ring_area_abs(piece) < min_ring_area:
                    continue
                if not _ring_interior_on_land(piece, land):
                    continue
                polys.append(
                    LandPolygon(
                        id=next_id,
                        ring=piece,
                        area_cells=area_cells,
                        component_id=cid,
                    )
                )
                next_id += 1
                if len(polys) >= max_polygons:
                    return polys
    return polys


def land_cell_recall(
    polygons: list[LandPolygon],
    ocean_mask: NDArray[np.bool_],
    *,
    samples: int = 2000,
) -> float:
    """Fraction of sampled land cell centres that fall inside some land ring."""
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    h, w = land.shape
    if not polygons or not np.any(land):
        return 1.0 if not np.any(land) else 0.0
    ys, xs = np.where(land)
    rng = np.random.default_rng(4)
    n = min(int(samples), int(ys.size))
    pick = rng.choice(ys.size, size=n, replace=False)
    ok = 0
    for k in pick:
        r, c = int(ys[k]), int(xs[k])
        x = (c + 0.5) / w
        y = 1.0 - (r + 0.5) * 2.0 / h
        if any(_point_in_ring(x, y, p.ring) for p in polygons):
            ok += 1
    return float(ok / max(n, 1))


def land_coverage_score(
    polygons: list[LandPolygon],
    ocean_mask: NDArray[np.bool_],
    *,
    samples: int = 800,
) -> float:
    """Fraction of sampled interior test points that fall on land cells."""
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    h, w = land.shape
    if not polygons or not np.any(land):
        return 1.0 if not polygons else 0.0

    rng = np.random.default_rng(3)
    ok = 0
    total = 0
    for poly in polygons:
        ring = poly.ring
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        # sample bbox centres in norm space
        for _ in range(max(1, samples // max(len(polygons), 1))):
            x = float(rng.uniform(min(xs), max(xs)))
            y = float(rng.uniform(min(ys), max(ys)))
            if not _point_in_ring(x, y, ring):
                continue
            total += 1
            c = int(np.clip(np.floor(x * w), 0, w - 1))
            r = int(np.clip(np.floor((1.0 - y) * 0.5 * h), 0, h - 1))
            if land[r, c]:
                ok += 1
    if total == 0:
        # fallback: vertex neighbourhood
        return coastline_vertex_land_score(polygons, land)
    return float(ok / total)


def coastline_vertex_land_score(
    polygons: list[LandPolygon],
    land: NDArray[np.bool_],
) -> float:
    h, w = land.shape
    ok = 0
    n = 0
    for poly in polygons:
        for x, y in poly.ring[:-1]:
            c = int(np.clip(np.floor(x * w), 0, w - 1))
            r = int(np.clip(np.floor((1.0 - y) * 0.5 * h), 0, h - 1))
            cols = [(c - 1) % w, c, (c + 1) % w]
            if any(
                land[rr, cc]
                for rr in range(max(0, r - 1), min(h, r + 2))
                for cc in cols
            ):
                ok += 1
            n += 1
    return float(ok / max(n, 1))


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Even-odd rule; assumes ring does not cross dateline."""
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
        ):
            inside = not inside
        j = i
    return inside


def land_polygons_to_geojson(polygons: list[LandPolygon]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [p.to_geojson_feature() for p in polygons],
    }
