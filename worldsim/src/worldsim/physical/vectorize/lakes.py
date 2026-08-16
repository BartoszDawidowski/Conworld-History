"""Lake polygons from lake_id raster (Milestone 12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.vectorize.coords import cell_center_norm
from worldsim.spatial.extent import SpatialExtent


@dataclass
class Lake:
    id: int
    polygon: list[tuple[float, float]]
    surface_elevation: float
    basin_id: int
    inlet_river_ids: list[int] = field(default_factory=list)
    outlet_river_id: int | None = None
    closed_basin: bool = True
    area_cells: int = 0
    water_state: str = "endorheic"
    spill_elevation: float | None = None
    mean_effective_inflow: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "polygon": [[float(x), float(y)] for x, y in self.polygon],
            "surface_elevation": self.surface_elevation,
            "basin_id": self.basin_id,
            "inlet_river_ids": list(self.inlet_river_ids),
            "outlet_river_id": self.outlet_river_id,
            "closed_basin": self.closed_basin,
            "area_cells": self.area_cells,
            "water_state": self.water_state,
            "spill_elevation": self.spill_elevation,
            "mean_effective_inflow": self.mean_effective_inflow,
        }


def _sanitize_ring(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop consecutive duplicates; require ≥3 unique verts and non-zero area."""
    if len(ring) < 3:
        return []
    cleaned: list[tuple[float, float]] = [ring[0]]
    for p in ring[1:]:
        if abs(p[0] - cleaned[-1][0]) > 1e-12 or abs(p[1] - cleaned[-1][1]) > 1e-12:
            cleaned.append(p)
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
        cleaned = cleaned[:-1]
    if len(cleaned) < 3:
        return []
    # Unique (quantised)
    keys = {(round(x, 8), round(y, 8)) for x, y in cleaned}
    if len(keys) < 3:
        return []
    area2 = 0.0
    n = len(cleaned)
    for i in range(n):
        x0, y0 = cleaned[i]
        x1, y1 = cleaned[(i + 1) % n]
        area2 += x0 * y1 - x1 * y0
    if abs(area2) < 1e-14:
        return []
    out = list(cleaned)
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def _boundary_ring(
    mask: NDArray[np.bool_],
    extent: SpatialExtent,
) -> list[tuple[float, float]]:
    """Axis-aligned boundary loop of a connected lake mask (may be coarse)."""
    h, w = mask.shape
    # Collect unique edge midpoints as polygon vertices via contour of bbox + edge walk
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return []
    # Use sorted boundary cells' centres as a simple ring via convex-ish hull of edge cells
    edge = np.zeros_like(mask)
    for r, c in zip(rows.tolist(), cols.tolist()):
        for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            rr, cc = r + dj, (c + di) % w
            if rr < 0 or rr >= h or not mask[rr, cc]:
                edge[r, c] = True
                break
    er, ec = np.where(edge)
    if len(er) == 0:
        # single cell — not a drawable polygon
        return []
    # Order by angle around centroid for a closed ring
    pts = np.column_stack([ec.astype(np.float64), er.astype(np.float64)])
    cy, cx = float(pts[:, 1].mean()), float(pts[:, 0].mean())
    ang = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
    order = np.argsort(ang)
    ring = [cell_center_norm(float(pts[i, 0]), float(pts[i, 1]), extent) for i in order]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return _sanitize_ring(ring)


def build_lakes(
    *,
    lake_id: NDArray[np.integer],
    lake_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    basin_id: NDArray[np.integer],
    extent: SpatialExtent,
    lake_records: list[dict[str, Any]] | None = None,
    river_network: Any | None = None,
) -> list[Lake]:
    records_by_id = {
        int(r["lake_id"]): r for r in (lake_records or []) if "lake_id" in r
    }
    # Inlet/outlet river ids from network segments touching lakes
    inlets: dict[int, list[int]] = {}
    outlets: dict[int, int] = {}
    if river_network is not None:
        for seg in getattr(river_network, "segments", []):
            if int(seg.to_lake_id) > 0:
                inlets.setdefault(int(seg.to_lake_id), []).append(int(seg.id))
            if int(seg.from_lake_id) > 0:
                outlets[int(seg.from_lake_id)] = int(seg.id)

    lids = np.unique(lake_id[lake_id > 0])
    lakes: list[Lake] = []
    for lid in lids:
        m = lake_id == int(lid)
        if not np.any(m):
            continue
        ring = _boundary_ring(m, extent)
        if len(ring) < 4:  # closed ring → at least 3 unique + close
            continue
        elev = float(np.mean(elevation_m[m]))
        bids, counts = np.unique(basin_id[m], return_counts=True)
        bid = int(bids[int(np.argmax(counts))]) if len(bids) else 0
        rec = records_by_id.get(int(lid), {})
        closed = bool(rec.get("closed_basin", True))
        lakes.append(
            Lake(
                id=int(lid),
                polygon=ring,
                surface_elevation=float(rec.get("surface_elevation_m", elev)),
                basin_id=int(rec.get("basin_id", bid)),
                inlet_river_ids=list(inlets.get(int(lid), [])),
                outlet_river_id=outlets.get(int(lid)),
                closed_basin=closed,
                area_cells=int(np.count_nonzero(m)),
                water_state=str(rec.get("water_state", "endorheic" if closed else "open")),
                spill_elevation=(
                    float(rec["spill_elevation_m"])
                    if rec.get("spill_elevation_m") is not None
                    else None
                ),
                mean_effective_inflow=float(rec.get("mean_effective_inflow", 0.0)),
            )
        )
    return lakes


def lake_raster_consistency(
    lakes: list[Lake],
    lake_mask: NDArray[np.bool_],
    *,
    samples: int = 200,
) -> float:
    """Fraction of sampled lake polygon vertices falling on/near lake_mask."""
    mask = np.asarray(lake_mask, dtype=np.bool_)
    h, w = mask.shape
    if not lakes:
        return 1.0  # vacuously OK when no lakes
    pts: list[tuple[float, float]] = []
    for lake in lakes:
        pts.extend(lake.polygon[:-1] if len(lake.polygon) > 1 else lake.polygon)
    if not pts:
        return 0.0
    rng = np.random.default_rng(2)
    pick = rng.choice(len(pts), size=min(samples, len(pts)), replace=False)
    ok = 0
    for i in pick:
        x, y = pts[int(i)]
        c = int(np.clip(np.floor(x * w), 0, w - 1))
        r = int(np.clip(np.floor((1.0 - y) * 0.5 * h), 0, h - 1))
        # allow 1-cell neighbourhood
        window = mask[
            max(0, r - 1) : min(h, r + 2),
            :,
        ]
        # wrap x neighbourhood manually
        cols = [(c - 1) % w, c, (c + 1) % w]
        if any(mask[rr, cc] for rr in range(max(0, r - 1), min(h, r + 2)) for cc in cols):
            ok += 1
    return float(ok / max(len(pick), 1))
