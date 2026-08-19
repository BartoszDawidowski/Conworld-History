"""Canonical landform objects with seam-aware deterministic IDs (PR-9C)."""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.landforms.classify import BroadContext, _dilate_cylindrical
from worldsim.physical.landforms.params import (
    LandformParams,
    effective_min_cells_honest,
)


@dataclass
class MountainRange:
    id: int
    cell_count: int
    area_cells: int
    area_km2: float
    centroid_j: float
    centroid_i: float
    mean_elev_m: float
    max_elev_m: float
    base_elev_m: float
    local_relief_m: float
    orientation_deg: float
    elongation: float
    provenance_mode: int
    confidence: float
    crosses_ew_seam: bool
    ridge_line: list[list[float]] = field(default_factory=list)
    system_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cell_count": self.cell_count,
            "area_cells": self.area_cells,
            "area_km2": self.area_km2,
            "centroid_j": self.centroid_j,
            "centroid_i": self.centroid_i,
            "mean_elev_m": self.mean_elev_m,
            "max_elev_m": self.max_elev_m,
            "base_elev_m": self.base_elev_m,
            "local_relief_m": self.local_relief_m,
            "orientation_deg": self.orientation_deg,
            "elongation": self.elongation,
            "provenance_mode": self.provenance_mode,
            "confidence": self.confidence,
            "crosses_ew_seam": self.crosses_ew_seam,
            "ridge_line": list(self.ridge_line),
            "system_id": int(self.system_id or self.id),
        }


@dataclass
class Plateau:
    id: int
    cell_count: int
    area_cells: int
    area_km2: float
    centroid_j: float
    centroid_i: float
    mean_elev_m: float
    base_elev_m: float
    internal_relief_m: float
    mean_slope: float
    provenance_mode: int
    confidence: float
    crosses_ew_seam: bool
    rim_line: list[list[float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cell_count": self.cell_count,
            "area_cells": self.area_cells,
            "area_km2": self.area_km2,
            "centroid_j": self.centroid_j,
            "centroid_i": self.centroid_i,
            "mean_elev_m": self.mean_elev_m,
            "base_elev_m": self.base_elev_m,
            "internal_relief_m": self.internal_relief_m,
            "mean_slope": self.mean_slope,
            "provenance_mode": self.provenance_mode,
            "confidence": self.confidence,
            "crosses_ew_seam": self.crosses_ew_seam,
            "rim_line": list(self.rim_line),
        }


def _label_components_cylindrical(mask: NDArray[np.bool_]) -> NDArray[np.int32]:
    """4-connected components with E–W wrap; labels are temporary."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent: list[int] = [0]

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    next_id = 1
    for j in range(h):
        for i in range(w):
            if not mask[j, i]:
                continue
            neigh_ids: list[int] = []
            if i > 0 and labels[j, i - 1] > 0:
                neigh_ids.append(int(labels[j, i - 1]))
            elif i == 0 and labels[j, w - 1] > 0:
                neigh_ids.append(int(labels[j, w - 1]))
            if j > 0 and labels[j - 1, i] > 0:
                neigh_ids.append(int(labels[j - 1, i]))
            if not neigh_ids:
                parent.append(next_id)
                labels[j, i] = next_id
                next_id += 1
            else:
                root = find(neigh_ids[0])
                labels[j, i] = root
                for n in neigh_ids[1:]:
                    union(root, n)
                labels[j, i] = find(int(labels[j, i]))

    # Second pass: unify wrap edges
    for j in range(h):
        if mask[j, 0] and mask[j, w - 1] and labels[j, 0] and labels[j, w - 1]:
            union(int(labels[j, 0]), int(labels[j, w - 1]))

    flat = labels.ravel()
    for idx in range(flat.size):
        if flat[idx] > 0:
            flat[idx] = find(int(flat[idx]))
    return labels


def _components_sorted(
    labels: NDArray[np.int32],
) -> list[tuple[int, int, float, float]]:
    """Return (old_label, area, centroid_j, centroid_i) sorted for stable IDs."""
    ids = np.unique(labels)
    ids = ids[ids > 0]
    rows: list[tuple[int, int, float, float]] = []
    h, w = labels.shape
    for lab in ids.tolist():
        ys, xs = np.where(labels == lab)
        area = int(ys.size)
        # Circular mean for longitude index
        ang = 2.0 * np.pi * xs.astype(np.float64) / float(w)
        ci = float(
            (np.arctan2(np.mean(np.sin(ang)), np.mean(np.cos(ang))) % (2.0 * np.pi))
            * w
            / (2.0 * np.pi)
        )
        cj = float(np.mean(ys))
        rows.append((int(lab), area, cj, ci))
    rows.sort(key=lambda t: (t[2], t[3], -t[1], t[0]))
    return rows


def _contiguous_ew_shift(mask: NDArray[np.bool_]) -> int:
    """Shift so a wrapping component becomes a single interior blob when possible."""
    col = np.any(np.asarray(mask, dtype=bool), axis=0)
    w = int(col.size)
    if w == 0 or not (bool(col[0]) and bool(col[-1])):
        return 0
    a = 0
    while a < w and col[a]:
        a += 1
    if a >= w:
        return 0
    return int(a)


def _cell_xy(i: float, j: float, h: int, w: int) -> list[float]:
    return [
        (float(i) + 0.5) / float(w),
        1.0 - 2.0 * (float(j) + 0.5) / float(h),
    ]


def _prune_polyline(points: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for pt in points:
        if out and abs(out[-1][0] - pt[0]) < 1e-12 and abs(out[-1][1] - pt[1]) < 1e-12:
            continue
        out.append([float(pt[0]), float(pt[1])])
    return out


def _split_polyline_at_seam(line: list[list[float]]) -> list[list[list[float]]]:
    if len(line) < 2:
        return [line] if len(line) == 1 else []
    parts: list[list[list[float]]] = []
    cur = [line[0]]
    for prev, nxt in zip(line, line[1:]):
        if abs(float(prev[0]) - float(nxt[0])) > 0.5:
            if len(cur) >= 2:
                parts.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)
    if len(cur) >= 2:
        parts.append(cur)
    return parts


def _ridge_centerline(
    mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    tpi: NDArray[np.floating] | None = None,
) -> list[list[float]]:
    """High-ground / TPI-weighted spine; geodesic diameter of the mask is not the ridge."""
    sel = np.asarray(mask, dtype=bool)
    elev = np.asarray(elevation_m, dtype=np.float64)
    h, w = sel.shape
    ys, xs = np.where(sel)
    if ys.size == 0:
        return []
    if ys.size == 1:
        return [_cell_xy(float(xs[0]), float(ys[0]), h, w)]

    shift = _contiguous_ew_shift(sel)
    sel_u = np.roll(sel, -shift, axis=1) if shift else sel
    elev_u = np.roll(elev, -shift, axis=1) if shift else elev
    tpi_u = None
    if tpi is not None and np.asarray(tpi).shape == elev.shape:
        tpi_u = np.roll(np.asarray(tpi, dtype=np.float64), -shift, axis=1) if shift else np.asarray(
            tpi, dtype=np.float64
        )
    ys_u, xs_u = np.where(sel_u)
    n = int(ys_u.size)
    index = -np.ones((h, w), dtype=np.int32)
    index[ys_u, xs_u] = np.arange(n, dtype=np.int32)
    e_sel = elev_u[ys_u, xs_u]
    e_min = float(np.min(e_sel))
    e_span = max(float(np.max(e_sel) - e_min), 1.0)
    elev_n = (e_sel - e_min) / e_span
    if tpi_u is not None:
        t_sel = tpi_u[ys_u, xs_u]
        t_min = float(np.min(t_sel))
        t_span = max(float(np.max(t_sel) - t_min), 1.0)
        tpi_n = (t_sel - t_min) / t_span
    else:
        tpi_n = elev_n
    prefer = np.clip(0.55 * elev_n + 0.45 * tpi_n, 0.0, 1.0)
    weight = 0.12 + 0.88 * prefer

    def neighbours(k: int) -> list[int]:
        j, i = int(ys_u[k]), int(xs_u[k])
        out: list[int] = []
        for dj in (-1, 0, 1):
            jj = j + dj
            if jj < 0 or jj >= h:
                continue
            for di in (-1, 0, 1):
                if dj == 0 and di == 0:
                    continue
                ii = i + di
                if ii < 0 or ii >= w:
                    continue
                nb = int(index[jj, ii])
                if nb >= 0:
                    out.append(nb)
        return out

    def farthest(start: int) -> tuple[int, list[int]]:
        dist = np.full(n, np.inf, dtype=np.float64)
        prev = np.full(n, -1, dtype=np.int32)
        dist[start] = 0.0
        heap: list[tuple[float, int]] = [(0.0, start)]
        while heap:
            d, u = heappop(heap)
            if d > dist[u]:
                continue
            uj, ui = int(ys_u[u]), int(xs_u[u])
            for v in neighbours(u):
                vj, vi = int(ys_u[v]), int(xs_u[v])
                step = float(np.hypot(vj - uj, vi - ui)) / max(float(weight[v]), 0.08)
                nd = d + step
                if nd + 1e-12 < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heappush(heap, (nd, v))
        finite = np.where(np.isfinite(dist))[0]
        end = int(finite[int(np.argmax(dist[finite]))])
        path = [end]
        while prev[path[-1]] >= 0:
            path.append(int(prev[path[-1]]))
        path.reverse()
        return end, path

    seed = int(np.argmax(prefer))
    a, _ = farthest(seed)
    _b, path = farthest(a)
    line: list[list[float]] = []
    for k in path:
        i_orig = (int(xs_u[k]) + shift) % w
        line.append(_cell_xy(float(i_orig), float(ys_u[k]), h, w))
    return _prune_polyline(line)


def _ridge_samples_in_mask(
    line: list[list[float]], mask: NDArray[np.bool_]
) -> bool:
    if not line:
        return True
    h, w = mask.shape
    for x, y in line:
        i = int(np.floor(float(x) * w)) % w
        j = int(np.clip(np.floor((1.0 - float(y)) * 0.5 * h), 0, h - 1))
        if not bool(mask[j, i]):
            return False
    return True


def ridge_geometry_ok(
    line: list[list[float]], mask: NDArray[np.bool_]
) -> dict[str, bool]:
    dup = False
    for a, b in zip(line, line[1:]):
        if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
            dup = True
            break
    return {
        "in_mask": _ridge_samples_in_mask(line, mask),
        "no_consecutive_duplicates": not dup,
    }


def _split_component_at_saddles(
    sel: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    *,
    min_child_cells: int,
) -> list[NDArray[np.bool_]]:
    """Split a range blob at thin saddles / width constrictions."""
    mask = np.asarray(sel, dtype=bool)
    elev = np.asarray(elevation_m, dtype=np.float64)
    ys, xs = np.where(mask)
    if ys.size < max(int(min_child_cells) * 2, 8):
        return [mask]
    line = _ridge_centerline(mask, elev)
    if len(line) < 5:
        return [mask]
    h, w = mask.shape
    cut = np.zeros_like(mask)
    cells: list[tuple[int, int]] = []
    for x, y in line:
        i = int(np.floor(float(x) * w)) % w
        j = int(np.clip(np.floor((1.0 - float(y)) * 0.5 * h), 0, h - 1))
        cells.append((j, i))
    for k in range(1, len(cells) - 1):
        j, i = cells[k]
        j0, i0 = cells[k - 1]
        j1, i1 = cells[k + 1]
        if not mask[j, i]:
            continue
        thick = 0
        for dj in (-1, 0, 1):
            jj = j + dj
            if jj < 0 or jj >= h:
                continue
            for di in (-1, 0, 1):
                ii = (i + di) % w
                if mask[jj, ii]:
                    thick += 1
        saddle = float(elev[j, i]) + 40.0 <= min(float(elev[j0, i0]), float(elev[j1, i1]))
        # Width constriction (thin bar) or a true saddle on a slightly thicker neck.
        if thick <= 3 or (thick <= 4 and saddle):
            cut[j, i] = True
    if not np.any(cut):
        return [mask]
    remaining = mask & ~cut
    labels = _label_components_cylindrical(remaining)
    kids: list[NDArray[np.bool_]] = []
    for lab in np.unique(labels):
        if int(lab) <= 0:
            continue
        child = labels == int(lab)
        if int(np.count_nonzero(child)) >= int(min_child_cells):
            kids.append(child)
    if len(kids) < 2:
        return [mask]
    return kids


def extract_mountain_ranges(
    *,
    mountain_score: NDArray[np.floating],
    plateau_score: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    provenance_id: NDArray[np.integer],
    confidence: NDArray[np.floating],
    relief_meso: NDArray[np.floating],
    params: LandformParams,
    cell_area_km2: float = 1.0,
    tpi: NDArray[np.floating] | None = None,
) -> tuple[NDArray[np.int32], list[MountainRange]]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    score = np.asarray(mountain_score, dtype=np.float64)
    plat = np.asarray(plateau_score, dtype=np.float64)
    relief = np.asarray(relief_meso, dtype=np.float64)
    mask = (
        (~ocean)
        & (score >= params.mountain_score_threshold)
        & (relief >= 220.0)
        & (score >= plat + 0.08)
    )
    raw = _label_components_cylindrical(mask)
    ordered = _components_sorted(raw)
    id_map = np.zeros(ocean.shape, dtype=np.int32)
    ranges: list[MountainRange] = []
    elev = np.asarray(elevation_m, dtype=np.float64)
    new_id = 1
    min_cells, _meta = effective_min_cells_honest(
        min_km2=params.min_range_km2,
        min_cells=params.min_range_cells,
        cell_area_km2=cell_area_km2,
        min_component_cells=params.min_component_cells,
    )
    pieces: list[tuple[NDArray[np.bool_], int]] = []
    system = 1
    for old, area, cj, ci in ordered:
        if area < min_cells:
            continue
        sel = raw == old
        children = _split_component_at_saddles(sel, elev, min_child_cells=min_cells)
        for child in children:
            pieces.append((child, system))
        system += 1
    new_id = 1
    for sel, sys_id in pieces:
        area = int(np.count_nonzero(sel))
        if area < min_cells:
            continue
        xs = np.where(sel)[1]
        crosses = bool(np.any(xs == 0) and np.any(xs == elev.shape[1] - 1))
        e = elev[sel]
        ys, xsi = np.where(sel)
        cj = float(np.mean(ys))
        ang = 2.0 * np.pi * xsi.astype(np.float64) / float(elev.shape[1])
        ci = float(
            (np.arctan2(np.mean(np.sin(ang)), np.mean(np.cos(ang))) % (2.0 * np.pi))
            * elev.shape[1]
            / (2.0 * np.pi)
        )
        if ys.size >= 2:
            shift = _contiguous_ew_shift(sel)
            xs_u = (xsi.astype(np.float64) - shift) % elev.shape[1]
            pts = np.column_stack([xs_u, ys.astype(np.float64)])
            pts -= pts.mean(axis=0)
            cov = pts.T @ pts / max(pts.shape[0] - 1, 1)
            eig = np.linalg.eigvalsh(cov)
            vecs = np.linalg.eigh(cov)[1]
            orient = float(np.degrees(np.arctan2(vecs[1, -1], vecs[0, -1])) % 180.0)
            elong = float(np.sqrt(max(eig[-1], 1e-9) / max(eig[0], 1e-9)))
        else:
            orient, elong = 0.0, 1.0
        prov = int(np.bincount(np.asarray(provenance_id[sel], dtype=np.int64)).argmax())
        rec = MountainRange(
            id=new_id,
            cell_count=area,
            area_cells=area,
            area_km2=float(area) * float(cell_area_km2),
            centroid_j=cj,
            centroid_i=ci,
            mean_elev_m=float(np.mean(e)),
            max_elev_m=float(np.max(e)),
            base_elev_m=float(np.percentile(e, 10)),
            local_relief_m=float(np.mean(relief_meso[sel])),
            orientation_deg=orient,
            elongation=elong,
            provenance_mode=prov,
            confidence=float(np.mean(confidence[sel])),
            crosses_ew_seam=crosses,
            ridge_line=_ridge_centerline(sel, elev, tpi=tpi),
            system_id=int(sys_id),
        )
        ranges.append(rec)
        id_map[sel] = new_id
        new_id += 1
    return id_map, ranges


def extract_plateaus(
    *,
    context_id: NDArray[np.integer],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    provenance_id: NDArray[np.integer],
    confidence: NDArray[np.floating],
    slope: NDArray[np.floating],
    relief_fine: NDArray[np.floating],
    mean_elev_macro: NDArray[np.floating],
    params: LandformParams,
    cell_area_km2: float = 1.0,
) -> tuple[NDArray[np.int32], list[Plateau]]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    mask = (~ocean) & (np.asarray(context_id) == int(BroadContext.PLATEAU))
    # Also include high plateau_score flats classified as upland rim interiors
    raw = _label_components_cylindrical(mask)
    ordered = _components_sorted(raw)
    id_map = np.zeros(ocean.shape, dtype=np.int32)
    plateaus: list[Plateau] = []
    elev = np.asarray(elevation_m, dtype=np.float64)
    new_id = 1
    min_cells, _meta = effective_min_cells_honest(
        min_km2=params.min_plateau_km2,
        min_cells=params.min_plateau_cells,
        cell_area_km2=cell_area_km2,
        min_component_cells=params.min_component_cells,
    )
    for old, area, cj, ci in ordered:
        if area < min_cells:
            continue
        sel = raw == old
        xs = np.where(sel)[1]
        crosses = bool(np.any(xs == 0) and np.any(xs == elev.shape[1] - 1))
        e = elev[sel]
        prov = int(np.bincount(np.asarray(provenance_id[sel], dtype=np.int64)).argmax())
        rec = Plateau(
            id=new_id,
            cell_count=area,
            area_cells=area,
            area_km2=float(area) * float(cell_area_km2),
            centroid_j=cj,
            centroid_i=ci,
            mean_elev_m=float(np.mean(e)),
            base_elev_m=float(np.mean(mean_elev_macro[sel])),
            internal_relief_m=float(np.mean(relief_fine[sel])),
            mean_slope=float(np.mean(slope[sel])),
            provenance_mode=prov,
            confidence=float(np.mean(confidence[sel])),
            crosses_ew_seam=crosses,
            rim_line=_plateau_steep_rim_line(sel, slope, params),
        )
        plateaus.append(rec)
        id_map[sel] = new_id
        new_id += 1
    return id_map, plateaus


def _mask_contour_ring(mask: NDArray[np.bool_]) -> list[list[float]]:
    """Cell-edge outer ring in normalised cylindrical coordinates (CR-9)."""
    from worldsim.physical.vectorize.lakes import (
        _directed_outline_rings,
        _sanitize_ring,
    )

    h, w = mask.shape
    rings = _directed_outline_rings(mask)
    if not rings:
        return []
    verts = max(rings, key=len)
    ring = [
        [float(x) / float(w), 1.0 - 2.0 * float(y) / float(h)] for x, y in verts
    ]
    sanitized = _sanitize_ring([(p[0], p[1]) for p in ring])
    return [[float(x), float(y)] for x, y in sanitized]


def _plateau_steep_rim_line(
    mask: NDArray[np.bool_],
    slope: NDArray[np.floating],
    params: LandformParams,
) -> list[list[float]]:
    """Rim follows the steep/scarp edge, not a duplicate of the filled outline."""
    sel = np.asarray(mask, dtype=bool)
    slp = np.asarray(slope, dtype=np.float64)
    edge = sel & _dilate_cylindrical(~sel)
    steep = edge & (slp >= float(params.escarpment_slope))
    use = steep if int(np.count_nonzero(steep)) >= 3 else edge
    return _prune_polyline(_mask_contour_ring(use))


def components_to_geojson_polygons(
    id_map: NDArray[np.int32],
    records: list[Any],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    """Cell-edge contours per object (not bbox / centroid hull)."""
    feats: list[dict[str, Any]] = []
    for rec in records:
        rid = int(rec.id)
        sel = id_map == rid
        if not np.any(sel):
            continue
        if getattr(rec, "crosses_ew_seam", False):
            h, w = id_map.shape
            geom: dict[str, Any] = {
                "type": "Point",
                "coordinates": [
                    float(rec.centroid_i) / w,
                    1.0 - 2.0 * float(rec.centroid_j) / h,
                ],
            }
        else:
            ring = _mask_contour_ring(sel)
            if len(ring) < 4:
                continue
            geom = {"type": "Polygon", "coordinates": [ring]}
        props = rec.to_dict()
        props["kind"] = kind
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    return feats


def components_to_geojson_ridges(
    records: list[MountainRange],
) -> list[dict[str, Any]]:
    feats: list[dict[str, Any]] = []
    for rec in records:
        for part in _split_polyline_at_seam(_prune_polyline(list(rec.ridge_line))):
            if len(part) < 2:
                continue
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"id": rec.id, "kind": "ridge_centerline"},
                    "geometry": {"type": "LineString", "coordinates": part},
                }
            )
    return feats


def components_to_geojson_rims(
    records: list[Plateau],
) -> list[dict[str, Any]]:
    feats: list[dict[str, Any]] = []
    for rec in records:
        for part in _split_polyline_at_seam(_prune_polyline(list(rec.rim_line))):
            if len(part) < 2:
                continue
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"id": rec.id, "kind": "plateau_rim"},
                    "geometry": {"type": "LineString", "coordinates": part},
                }
            )
    return feats
