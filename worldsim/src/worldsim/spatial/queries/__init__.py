"""Spatial query helpers over WorldSpatialModel stores (Milestone 16)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from worldsim.spatial.coordinates import clamp_y, wrap_x
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.hex_grid.layout import xy_to_hex, hex_id
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult
from worldsim.spatial.raster_store import RasterStore
from worldsim.spatial.vector_store import VectorStore


def _sample_scalar(
    field: np.ndarray,
    extent: SpatialExtent,
    x: float,
    y: float,
) -> float:
    idx = extent.xy_to_index(x, y, clamp_ns=True)
    return float(field[idx.j, idx.i])


def _sample_monthly(
    field: np.ndarray,
    extent: SpatialExtent,
    x: float,
    y: float,
    month: int,
) -> float:
    if month < 0 or month >= field.shape[0]:
        raise ValueError(f"month must be in [0, {field.shape[0]})")
    idx = extent.xy_to_index(x, y, clamp_ns=True)
    return float(field[month, idx.j, idx.i])


def _polyline_bbox(
    coords: list[tuple[float, float]],
) -> tuple[float, float, float, float] | None:
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    # Simple AABB; E–W wrap not expanded (acceptable for v1 queries).
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _point_segment_dist2(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-18:
        dx, dy = px - ax, py - ay
        return dx * dx + dy * dy
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
    cx, cy = ax + t * abx, ay + t * aby
    dx, dy = px - cx, py - cy
    return dx * dx + dy * dy


class SpatialQueries:
    """Godot-free query surface over raster / vector / hex stores."""

    def __init__(
        self,
        *,
        rasters: RasterStore,
        vectors: VectorStore,
        hex_grid: HexAnalysisResult,
        climate_extent: SpatialExtent,
    ) -> None:
        self.rasters = rasters
        self.vectors = vectors
        self.hex_grid = hex_grid
        self.climate_extent = climate_extent

    def hex_at(self, x: float, y: float) -> int:
        q, r = xy_to_hex(
            wrap_x(x),
            clamp_y(y),
            width=self.hex_grid.spec.width,
            height=self.hex_grid.spec.height,
        )
        return hex_id(q, r, width=self.hex_grid.spec.width)

    def environment_at(self, x: float, y: float) -> dict[str, Any]:
        hid = self.hex_at(x, y)
        elev = self.sample_elevation(x, y)
        ocean = bool(
            _sample_scalar(
                self.rasters.get("climate/ocean_mask").astype(bool),
                self.climate_extent,
                x,
                y,
            )
        )
        return {
            "x": wrap_x(x),
            "y": clamp_y(y),
            "hex_id": hid,
            "elevation_m": elev,
            "ocean": ocean,
            "temperature_c_month0": self.sample_climate(x, y, 0),
            "land_fraction_hex": float(self.hex_grid.land_fraction[hid]),
            "holdridge_hex": int(self.hex_grid.holdridge_dominant[hid]),
        }

    def sample_elevation(self, x: float, y: float) -> float:
        return _sample_scalar(
            self.rasters.get("climate/elevation_m"),
            self.climate_extent,
            x,
            y,
        )

    def sample_climate(self, x: float, y: float, month: int) -> float:
        return _sample_monthly(
            self.rasters.get("climate/temperature_c"),
            self.climate_extent,
            x,
            y,
            month,
        )

    def hex_environment(self, hex_id_value: int) -> dict[str, Any]:
        h = int(hex_id_value)
        if h < 0 or h >= self.hex_grid.n_cells:
            raise IndexError(f"hex_id {h} out of range")
        return {
            "hex_id": h,
            "latitude_deg": float(self.hex_grid.latitude_deg[h]),
            "land_fraction": float(self.hex_grid.land_fraction[h]),
            "ocean_fraction": float(self.hex_grid.ocean_fraction[h]),
            "lake_fraction": float(self.hex_grid.lake_fraction[h]),
            "elevation_mean": float(self.hex_grid.elevation_mean[h]),
            "temperature_mean": self.hex_grid.temperature_mean[h].tolist(),
            "precipitation_mean": self.hex_grid.precipitation_mean[h].tolist(),
            "holdridge_dominant": int(self.hex_grid.holdridge_dominant[h]),
            "river_ids": list(self.hex_grid.river_ids[h]),
            "lake_ids": list(self.hex_grid.lake_ids[h]),
            "river_edge_mask": int(self.hex_grid.river_edge_mask[h]),
        }

    def neighbour_hexes(self, hex_id_value: int) -> list[int | None]:
        h = int(hex_id_value)
        row = self.hex_grid.neighbours[h]
        return [None if int(v) < 0 else int(v) for v in row.tolist()]

    def rivers_crossing_hex(self, hex_id_value: int) -> list[int]:
        return list(self.hex_grid.river_ids[int(hex_id_value)])

    def rivers_in_bbox(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> list[int]:
        box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        out: list[int] = []
        for seg in self.vectors.rivers.segments:
            bb = _polyline_bbox(seg.geometry)
            if bb is not None and _bbox_intersects(box, bb):
                out.append(int(seg.id))
        return out

    def lakes_in_bbox(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> list[int]:
        box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        out: list[int] = []
        for lake in self.vectors.lakes:
            bb = _polyline_bbox(lake.polygon)
            if bb is not None and _bbox_intersects(box, bb):
                out.append(int(lake.id))
        return out

    def coast_distance(self, x: float, y: float) -> float:
        """Approximate planar distance to nearest coastline segment (norm units)."""
        px, py = wrap_x(x), clamp_y(y)
        best = math.inf
        # Prefer spatial index neighbourhood, fall back to all coasts
        candidates = self.vectors.spatial_index.query_point(px, py)
        coast_ids = {
            int(fid) for layer, fid in candidates if layer == "coastline"
        }
        features = (
            [f for f in self.vectors.coastline if f.id in coast_ids]
            if coast_ids
            else self.vectors.coastline
        )
        if not features:
            features = self.vectors.coastline
        for feat in features:
            geom = feat.geometry
            for (ax, ay), (bx, by) in zip(geom, geom[1:]):
                # unwrap seam for short edges
                dx = bx - ax
                if dx > 0.5:
                    bx -= 1.0
                elif dx < -0.5:
                    bx += 1.0
                d2 = _point_segment_dist2(px, py, ax, ay, bx, by)
                if d2 < best:
                    best = d2
        if not math.isfinite(best):
            return float("nan")
        return float(math.sqrt(best))
