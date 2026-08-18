"""Lake polygons from lake_id raster (Milestone 12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

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
    # C0: topographic identity vs current liquid object; three independent axes.
    feature_id: int = 0
    water_body_id: int = 0
    outlet_type: str = ""
    hydroperiod: str = ""
    ice_regime: str = ""
    envelope_area_km2: float = 0.0
    mean_wet_area_km2: float = 0.0

    def __post_init__(self) -> None:
        from worldsim.physical.hydrology.lakes_meta import (
            apply_lake_identity,
            derive_lake_axes,
        )

        axes = derive_lake_axes(
            water_state=self.water_state,
            closed_basin=self.closed_basin,
            outlet_type=self.outlet_type,
            hydroperiod=self.hydroperiod,
            ice_regime=self.ice_regime,
        )
        self.outlet_type = axes["outlet_type"]
        self.hydroperiod = axes["hydroperiod"]
        self.ice_regime = axes["ice_regime"]
        if axes["water_state"]:
            self.water_state = axes["water_state"]
        ident = apply_lake_identity(
            {
                "id": self.id,
                "basin_id": self.basin_id,
                "water_state": self.water_state,
                "feature_id": self.feature_id,
                "water_body_id": self.water_body_id,
            }
        )
        self.feature_id = int(ident["feature_id"])
        self.water_body_id = int(ident["water_body_id"])

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
            "feature_id": int(self.feature_id),
            "water_body_id": int(self.water_body_id),
            "outlet_type": self.outlet_type,
            "hydroperiod": self.hydroperiod,
            "ice_regime": self.ice_regime,
            "envelope_area_km2": float(self.envelope_area_km2),
            "mean_wet_area_km2": float(self.mean_wet_area_km2),
        }


def lake_atlas_properties(lake: Lake) -> dict[str, Any]:
    """GeoJSON properties for atlas lakes (no geometry)."""
    from worldsim.physical.hydrology.lakes_meta import LAKE_VECTOR_SCHEMA

    props = lake.to_dict()
    props.pop("polygon", None)
    props["lake_vector_schema"] = LAKE_VECTOR_SCHEMA
    return props


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


def _corner_norm(
    col_v: float,
    row_v: float,
    extent: SpatialExtent,
) -> tuple[float, float]:
    """Cell-corner (not centre) to normalised cylindrical (x, y)."""
    width, height = extent.width, extent.height
    x = float(col_v) / float(width)
    y = 1.0 - float(row_v) * 2.0 / float(height)
    return float(x % 1.0), float(y)


def _directed_outline_rings(
    mask: NDArray[np.bool_],
) -> list[list[tuple[int, int]]]:
    """Clockwise outer rings of 4-connected True cells (cell-corner vertices).

    Each True cell contributes the sides that face False / NS-out. Chaining
    those directed edges gives a non-self-intersecting outline for concave
    bodies (CR-6 / F-20). Angular sort around the centroid is not used.
    """
    body = np.asarray(mask, dtype=bool)
    h, w = body.shape
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a: tuple[int, int], b: tuple[int, int]) -> None:
        edges.setdefault(a, []).append(b)

    rows, cols = np.where(body)
    for r, c in zip(rows.tolist(), cols.tolist()):
        west = body[r, (c - 1) % w]
        east = body[r, (c + 1) % w]
        north = body[r - 1, c] if r > 0 else False
        south = body[r + 1, c] if r + 1 < h else False
        # Image y increases south. Walk so the interior is on the right.
        if not west:
            add((c, r + 1), (c, r))
        if not east:
            add((c + 1, r), (c + 1, r + 1))
        if not north:
            add((c, r), (c + 1, r))
        if not south:
            add((c + 1, r + 1), (c, r + 1))

    rings: list[list[tuple[int, int]]] = []
    while edges:
        start = next(iter(edges))
        ring = [start]
        cur = start
        for _ in range(h * w * 4 + 2):
            nxts = edges.get(cur)
            if not nxts:
                break
            nxt = nxts.pop(0)
            if not nxts:
                del edges[cur]
            ring.append(nxt)
            cur = nxt
            if cur == start and len(ring) > 2:
                break
        if cur in edges and not edges[cur]:
            del edges[cur]
        if len(ring) >= 4:
            rings.append(ring)
        # Drop leftover stubs from this component.
        if start in edges and not edges[start]:
            del edges[start]
    return rings


def _boundary_ring(
    mask: NDArray[np.bool_],
    extent: SpatialExtent,
) -> list[tuple[float, float]]:
    """Outer contour of a connected lake mask (cell-edge union, not centroid sort)."""
    rings = _directed_outline_rings(mask)
    if not rings:
        return []
    verts = max(rings, key=len)
    ring = [_corner_norm(float(x), float(y), extent) for x, y in verts]
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
                feature_id=int(rec.get("feature_id") or 0),
                water_body_id=int(rec.get("water_body_id") or 0),
                outlet_type=str(rec.get("outlet_type") or ""),
                hydroperiod=str(rec.get("hydroperiod") or ""),
                ice_regime=str(rec.get("ice_regime") or ""),
                envelope_area_km2=float(rec.get("envelope_area_km2") or 0.0),
                mean_wet_area_km2=float(rec.get("mean_wet_area_km2") or 0.0),
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
