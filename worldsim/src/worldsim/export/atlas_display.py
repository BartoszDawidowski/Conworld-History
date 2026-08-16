"""Export Godot-friendly atlas display assets from WorldSpatialModel (M17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.export.pngutil import write_png_rgb, write_png_rgba
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult
from worldsim.spatial.model import WorldSpatialModel
from worldsim.spatial.raster_store import RasterStore


def _nearest_uint8(src: NDArray[np.uint8], height: int, width: int) -> NDArray[np.uint8]:
    arr = np.asarray(src)
    sh, sw = arr.shape[:2]
    rr = np.minimum((np.arange(height) * sh / max(height, 1)).astype(int), sh - 1)
    cc = np.minimum((np.arange(width) * sw / max(width, 1)).astype(int), sw - 1)
    return np.asarray(arr[rr][:, cc], dtype=np.uint8)


def _flow_direction_rgb(
    flow_direction: NDArray[np.uint8],
    river_mask: NDArray[np.bool_] | None,
    ocean: NDArray[np.bool_],
) -> NDArray[np.uint8]:
    """Pack D8 code in R; river preference mask in G; ocean = 0."""
    d8 = np.asarray(flow_direction, dtype=np.uint8)
    out = np.zeros((*d8.shape, 3), dtype=np.uint8)
    land = ~np.asarray(ocean, dtype=np.bool_)
    out[land, 0] = d8[land]
    if river_mask is not None:
        riv = np.asarray(river_mask, dtype=np.bool_) & land
        out[riv, 1] = 255
    return out


def _norm_uint8(field: NDArray[np.floating], *, lo: float | None = None, hi: float | None = None) -> NDArray[np.uint8]:
    arr = np.asarray(field, dtype=np.float64)
    vmin = float(np.nanmin(arr)) if lo is None else lo
    vmax = float(np.nanmax(arr)) if hi is None else hi
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return np.zeros(arr.shape, dtype=np.uint8)
    t = np.clip((arr - vmin) / (vmax - vmin), 0.0, 1.0)
    return (t * 255.0).astype(np.uint8)


def _elevation_rgb(elev: NDArray[np.floating], ocean: NDArray[np.bool_]) -> NDArray[np.uint8]:
    land = ~ocean
    out = np.zeros((*elev.shape, 3), dtype=np.uint8)
    if np.any(ocean):
        bath = _norm_uint8(elev, lo=float(np.nanmin(elev[ocean])), hi=0.0) if np.any(ocean) else np.zeros_like(elev, dtype=np.uint8)
        out[ocean, 0] = (bath[ocean] // 3).astype(np.uint8)
        out[ocean, 1] = (40 + bath[ocean] // 2).astype(np.uint8)
        out[ocean, 2] = (90 + bath[ocean] // 2).astype(np.uint8)
    if np.any(land):
        g = _norm_uint8(elev, lo=0.0, hi=float(np.nanpercentile(elev[land], 98)))
        out[land, 0] = (40 + g[land] // 3).astype(np.uint8)
        out[land, 1] = (80 + g[land] // 2).astype(np.uint8)
        out[land, 2] = (40 + g[land] // 4).astype(np.uint8)
    return out


def _temp_rgb(temp: NDArray[np.floating]) -> NDArray[np.uint8]:
    t = _norm_uint8(temp, lo=-20.0, hi=35.0).astype(np.float64) / 255.0
    rgb = np.zeros((*temp.shape, 3), dtype=np.uint8)
    rgb[..., 0] = (40 + 200 * t).astype(np.uint8)
    rgb[..., 1] = (60 + 100 * (1.0 - np.abs(t - 0.5) * 2)).astype(np.uint8)
    rgb[..., 2] = (180 * (1.0 - t)).astype(np.uint8)
    return rgb


def _precip_rgb(precip: NDArray[np.floating]) -> NDArray[np.uint8]:
    # Absolute scale in moisture proxy units / month. Per-frame min–max hid real
    # knob changes (wetter worlds looked identical after stretch).
    p = _norm_uint8(precip, lo=0.0, hi=3.0).astype(np.float64) / 255.0
    rgb = np.zeros((*precip.shape, 3), dtype=np.uint8)
    rgb[..., 0] = (20 + 40 * (1.0 - p)).astype(np.uint8)
    rgb[..., 1] = (40 + 160 * p).astype(np.uint8)
    rgb[..., 2] = (60 + 180 * p).astype(np.uint8)
    return rgb


def _holdridge_rgb(zones: NDArray[np.integer]) -> NDArray[np.uint8]:
    z = np.asarray(zones)
    # Deterministic palette from zone id
    rgb = np.zeros((*z.shape, 3), dtype=np.uint8)
    rgb[..., 0] = ((z * 37) % 200 + 30).astype(np.uint8)
    rgb[..., 1] = ((z * 91) % 200 + 30).astype(np.uint8)
    rgb[..., 2] = ((z * 17) % 200 + 30).astype(np.uint8)
    ocean = z < 10
    rgb[ocean] = (20, 40, 90)
    return rgb


def _draw_hex_overlay(
    width: int,
    height: int,
    hex_grid: HexAnalysisResult,
    *,
    out_w: int,
    out_h: int,
) -> NDArray[np.uint8]:
    """Flat-top hex outline overlay (RGBA) — Milestone A7 (Voronoi / shared edges)."""
    from worldsim.spatial.hex_grid.layout import hex_id, hex_vertices_xy

    rgba = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    spec = hex_grid.spec
    color = (220, 220, 240, 160)

    def _plot(px: int, py: int) -> None:
        if 0 <= py < out_h:
            rgba[py, px % out_w] = color

    def _line(x0: float, y0: float, x1: float, y1: float) -> None:
        if abs(x1 - x0) > 0.5:
            return
        p0x = x0 * out_w
        p0y = (1.0 - y0) * 0.5 * out_h
        p1x = x1 * out_w
        p1y = (1.0 - y1) * 0.5 * out_h
        steps = max(1, int(np.hypot(p1x - p0x, p1y - p0y)))
        for s in range(steps + 1):
            t = s / steps
            _plot(int(round(p0x + (p1x - p0x) * t)), int(round(p0y + (p1y - p0y) * t)))

    for r in range(spec.height):
        for q in range(spec.width):
            verts = hex_vertices_xy(q, r, width=spec.width, height=spec.height)
            for i in range(6):
                x0, y0 = verts[i]
                x1, y1 = verts[(i + 1) % 6]
                _line(x0, y0, x1, y1)
    _ = width, height, hex_grid
    return rgba


def export_atlas_display(
    model: WorldSpatialModel,
    directory: Path,
    *,
    months: int = 12,
) -> dict[str, Any]:
    """Write PNG/JSON atlas assets under ``directory`` for Godot ingestion."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rasters: RasterStore = model.rasters
    elev = np.asarray(rasters.get("climate/elevation_m"), dtype=np.float64)
    ocean = np.asarray(rasters.get("climate/ocean_mask")).astype(bool)
    h, w = elev.shape

    write_png_rgb(directory / "elevation.png", _elevation_rgb(elev, ocean))
    write_png_rgb(directory / "bathymetry.png", _elevation_rgb(elev, np.ones_like(ocean)))
    # B4 fill/clip SoT: opaque land / black ocean (avoids Godot triangulating complex rings).
    land_mask_rgb = np.zeros((h, w, 3), dtype=np.uint8)
    land_mask_rgb[~ocean] = 255
    write_png_rgb(directory / "land_mask.png", land_mask_rgb)

    if rasters.has("hydrology/flow_direction"):
        d8 = np.asarray(rasters.get("hydrology/flow_direction"), dtype=np.uint8)
        riv = None
        if rasters.has("hydrology/river_mask"):
            riv = np.asarray(rasters.get("hydrology/river_mask")).astype(bool)
        if d8.shape != (h, w):
            d8 = _nearest_uint8(d8, h, w)
            if riv is not None and riv.shape != (h, w):
                riv = _nearest_uint8(riv.astype(np.uint8), h, w).astype(bool)
        write_png_rgb(
            directory / "flow_direction.png",
            _flow_direction_rgb(d8, riv, ocean),
        )

    temp = np.asarray(rasters.get("climate/temperature_c"), dtype=np.float64)
    precip = np.asarray(rasters.get("moisture/precipitation"), dtype=np.float64)
    n_months = min(months, temp.shape[0], precip.shape[0])
    for m in range(n_months):
        write_png_rgb(directory / f"temperature_{m+1:02d}.png", _temp_rgb(temp[m]))
        write_png_rgb(directory / f"precipitation_{m+1:02d}.png", _precip_rgb(precip[m]))

    if rasters.has("ecology/holdridge_zone_id"):
        write_png_rgb(
            directory / "holdridge.png",
            _holdridge_rgb(rasters.get("ecology/holdridge_zone_id")),
        )

    # Vectors as JSON FeatureCollections (Godot-friendly).
    # B6: simplify + Chaikin on rivers/coast (presentation); raster SoT unchanged.
    from worldsim.export.stroke_smooth import smooth_open_polyline, vertex_count

    river_feats = []
    riv_verts_before = 0
    riv_verts_after = 0
    for s in model.vectors.rivers.segments:
        geom = [(float(x), float(y)) for x, y in s.geometry]
        riv_verts_before += len(geom)
        pieces = smooth_open_polyline(geom)
        if not pieces:
            pieces = [geom] if len(geom) >= 2 else []
        riv_verts_after += vertex_count(pieces)
        for pi, piece in enumerate(pieces):
            river_feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": s.id if pi == 0 else f"{s.id}_{pi}",
                        "strahler_order": s.strahler_order,
                        "mean_discharge": s.mean_discharge,
                        "basin_id": s.basin_id,
                        "monthly_discharge": list(s.monthly_discharge),
                        "from_lake_id": s.from_lake_id,
                        "to_lake_id": s.to_lake_id,
                        "parent_segment_id": s.id,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[x, y] for x, y in piece],
                    },
                }
            )
    rivers = {"type": "FeatureCollection", "features": river_feats}

    coast_feats = []
    coast_verts_before = 0
    coast_verts_after = 0
    for f in model.vectors.coastline:
        geom = [(float(x), float(y)) for x, y in f.geometry]
        coast_verts_before += len(geom)
        pieces = smooth_open_polyline(geom)
        if not pieces:
            pieces = [geom] if len(geom) >= 2 else []
        coast_verts_after += vertex_count(pieces)
        for pi, piece in enumerate(pieces):
            coast_feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": f.id if pi == 0 else f"{f.id}_{pi}",
                        "water_body_id": f.water_body_id,
                        "parent_coast_id": f.id,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[x, y] for x, y in piece],
                    },
                }
            )
    coastline = {"type": "FeatureCollection", "features": coast_feats}
    lakes = {
        "type": "FeatureCollection",
        "features": [],
    }
    from worldsim.export.stroke_smooth import smooth_closed_ring

    for lake in model.vectors.lakes:
        if len(lake.polygon) < 4:
            continue
        ring = [(float(x), float(y)) for x, y in lake.polygon]
        smoothed = smooth_closed_ring(ring)
        lakes["features"].append(
            {
                "type": "Feature",
                "properties": {
                    "id": lake.id,
                    "surface_elevation": lake.surface_elevation,
                    "closed_basin": lake.closed_basin,
                    "area_cells": lake.area_cells,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[x, y] for x, y in smoothed]],
                },
            }
        )
    (directory / "rivers.geojson").write_text(json.dumps(rivers) + "\n", encoding="utf-8")
    (directory / "coastline.geojson").write_text(
        json.dumps(coastline) + "\n", encoding="utf-8"
    )
    (directory / "lakes.geojson").write_text(json.dumps(lakes) + "\n", encoding="utf-8")

    from worldsim.physical.vectorize.land import (
        extract_land_polygons,
        land_cell_recall,
        land_coverage_score,
        land_polygons_to_geojson,
    )

    land_polys = extract_land_polygons(ocean)
    land_geo = land_polygons_to_geojson(land_polys)
    (directory / "land.geojson").write_text(
        json.dumps(land_geo, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    land_diag = {
        "polygon_count": len(land_polys),
        "land_fraction_raster": float(np.mean(~ocean)),
        "coverage_score": land_coverage_score(land_polys, ocean),
        "land_cell_recall": land_cell_recall(land_polys, ocean),
        "vertex_count": int(sum(max(len(p.ring) - 1, 0) for p in land_polys)),
    }
    (directory / "land_polygons_diagnostics.json").write_text(
        json.dumps(land_diag, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    hex_grid = model.hex_grid
    write_png_rgba(
        directory / "hex_overlay.png",
        _draw_hex_overlay(w, h, hex_grid, out_w=w, out_h=h),
    )
    hex_meta = {
        "width": hex_grid.spec.width,
        "height": hex_grid.spec.height,
        "n_cells": hex_grid.n_cells,
        "orientation": hex_grid.spec.orientation,
    }
    (directory / "hex_grid.json").write_text(
        json.dumps(hex_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Compact hex cache for inspector (avoid huge sparse river_ids lists in JSON)
    river_nonempty = {
        str(i): ids
        for i, ids in enumerate(hex_grid.river_ids)
        if ids
    }
    hex_env = {
        "center_x": [float(v) for v in hex_grid.center_x.tolist()],
        "center_y": [float(v) for v in hex_grid.center_y.tolist()],
        "cell_count": [int(v) for v in hex_grid.cell_count.tolist()],
        "land_fraction": [float(v) for v in hex_grid.land_fraction.tolist()],
        "ocean_fraction": [float(v) for v in hex_grid.ocean_fraction.tolist()],
        "lake_fraction": [float(v) for v in hex_grid.lake_fraction.tolist()],
        "elevation_mean": [float(v) for v in hex_grid.elevation_mean.tolist()],
        "temperature_annual_c": [
            float(v) for v in np.mean(hex_grid.temperature_mean, axis=1).tolist()
        ],
        "precipitation_annual": [
            float(v) for v in np.sum(hex_grid.precipitation_mean, axis=1).tolist()
        ],
        "holdridge_dominant": [int(v) for v in hex_grid.holdridge_dominant.tolist()],
        "permeability_mean": [float(v) for v in hex_grid.permeability_mean.tolist()],
        "river_ids_nonempty": river_nonempty,
    }
    (directory / "hex_environment.json").write_text(
        json.dumps(hex_env, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    from worldsim.physical.ecology.holdridge import build_zone_legend

    (directory / "holdridge_zone_legend.json").write_text(
        json.dumps(build_zone_legend(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    meta: dict[str, Any] = {
        "schema": "atlas_display_v1",
        "raster_width": w,
        "raster_height": h,
        "months": n_months,
        "map_modes": [
            "elevation",
            "bathymetry",
            "temperature",
            "precipitation",
            "holdridge",
        ],
        "default_mode": "elevation",
        "hex_n_cells": hex_grid.n_cells,
        "files": {
            "elevation": "elevation.png",
            "bathymetry": "bathymetry.png",
            "holdridge": "holdridge.png",
            "hex_overlay": "hex_overlay.png",
            "rivers": "rivers.geojson",
            "coastline": "coastline.geojson",
            "lakes": "lakes.geojson",
            "land": "land.geojson",
            "land_mask": "land_mask.png",
            "flow_direction": "flow_direction.png",
            "land_polygons_diagnostics": "land_polygons_diagnostics.json",
            "hex_grid": "hex_grid.json",
            "hex_environment": "hex_environment.json",
            "holdridge_zone_legend": "holdridge_zone_legend.json",
        },
        "stroke_smooth": {
            "river_vertices_before": riv_verts_before,
            "river_vertices_after": riv_verts_after,
            "coast_vertices_before": coast_verts_before,
            "coast_vertices_after": coast_verts_after,
            "simplify_eps": 0.0012,
            "chaikin_iters": 2,
        },
    }
    (directory / "atlas_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return meta
