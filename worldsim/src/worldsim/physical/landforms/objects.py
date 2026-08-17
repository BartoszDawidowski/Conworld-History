"""Canonical landform objects with seam-aware deterministic IDs (PR-9C)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.landforms.classify import BroadContext
from worldsim.physical.landforms.params import LandformParams, min_object_cells


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


def _ridge_centerline(
    mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
) -> list[list[float]]:
    """Highest cells along the PCA long axis, as normalised (x, y) vertices."""
    ys, xs = np.where(mask)
    h, w = mask.shape
    if ys.size < 2:
        if ys.size == 1:
            return [[(float(xs[0]) + 0.5) / w, 1.0 - 2.0 * (float(ys[0]) + 0.5) / h]]
        return []
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    mean = pts.mean(axis=0)
    cov = np.cov(pts.T)
    if cov.size < 4 or not np.all(np.isfinite(cov)):
        return []
    axis = np.linalg.eigh(cov)[1][:, -1]
    proj = (pts - mean) @ axis
    n_bins = int(max(4, min(48, ys.size // 2)))
    line: list[list[float]] = []
    elev = np.asarray(elevation_m, dtype=np.float64)
    for b in range(n_bins):
        lo = float(np.quantile(proj, b / n_bins))
        hi = float(np.quantile(proj, (b + 1) / n_bins))
        sel = (proj >= lo) & (proj <= hi + 1e-12)
        if not np.any(sel):
            continue
        idx = np.flatnonzero(sel)
        best = int(idx[np.argmax(elev[ys[idx], xs[idx]])])
        line.append(
            [
                (float(xs[best]) + 0.5) / float(w),
                1.0 - 2.0 * (float(ys[best]) + 0.5) / float(h),
            ]
        )
    return line


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
    min_cells = max(
        min_object_cells(
            min_km2=params.min_range_km2,
            min_cells=params.min_range_cells,
            cell_area_km2=cell_area_km2,
        ),
        int(params.min_component_cells),
    )
    for old, area, cj, ci in ordered:
        if area < min_cells:
            continue
        sel = raw == old
        xs = np.where(sel)[1]
        crosses = bool(np.any(xs == 0) and np.any(xs == elev.shape[1] - 1))
        e = elev[sel]
        # Orientation from PCA of coordinates
        ys, xsi = np.where(sel)
        if ys.size >= 2:
            pts = np.column_stack(
                [xsi.astype(np.float64), ys.astype(np.float64)]
            )
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
            ridge_line=_ridge_centerline(sel, elev),
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
    min_cells = max(
        min_object_cells(
            min_km2=params.min_plateau_km2,
            min_cells=params.min_plateau_cells,
            cell_area_km2=cell_area_km2,
        ),
        int(params.min_component_cells),
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
        line = list(rec.ridge_line)
        if len(line) < 2:
            continue
        feats.append(
            {
                "type": "Feature",
                "properties": {"id": rec.id, "kind": "ridge_centerline"},
                "geometry": {"type": "LineString", "coordinates": line},
            }
        )
    return feats
