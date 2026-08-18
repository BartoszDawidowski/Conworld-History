"""Export Godot-friendly atlas display assets from WorldSpatialModel (M17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.export.pngutil import write_png_rgb, write_png_rgba
from worldsim.physical.hydrology.lakes_meta import LAKE_VECTOR_SCHEMA
from worldsim.physical.vectorize.lakes import lake_atlas_properties
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult
from worldsim.spatial.hex_grid.contract import HEX_CONTRACT_FIELDS, hex_environment_columns
from worldsim.spatial.model import WorldSpatialModel
from worldsim.spatial.raster_store import RasterStore

# C0: version the display contract. C9 writes structured mode descriptors.
ATLAS_DISPLAY_SCHEMA = "atlas_display_v2"


def _hex_color_rgb(color: str) -> tuple[int, int, int]:
    text = str(color).lstrip("#")
    if len(text) != 6:
        return (128, 128, 128)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def paint_categorical_rgb(
    class_ids: NDArray[np.integer],
    classes: dict[str, dict[str, Any]],
) -> NDArray[np.uint8]:
    ids = np.asarray(class_ids)
    out = np.zeros((*ids.shape, 3), dtype=np.uint8)
    for key, spec in classes.items():
        rgb = _hex_color_rgb(spec.get("color", "#808080"))
        out[ids == int(key)] = rgb
    return out


def _mode_descriptor(
    mode_id: str,
    *,
    label: str,
    icon: str,
    kind: str,
    file: str,
    legend: str | None = None,
    monthly: bool = False,
) -> dict[str, Any]:
    return {
        "id": mode_id,
        "label": label,
        "icon": icon,
        "kind": kind,
        "file": file,
        "legend": legend,
        "monthly": monthly,
    }


PRIMARY_MODE_DESCRIPTORS: tuple[dict[str, Any], ...] = (
    _mode_descriptor("elevation", label="Elevation", icon="El", kind="continuous", file="elevation.png"),
    _mode_descriptor("bathymetry", label="Bathymetry", icon="Ba", kind="continuous", file="bathymetry.png"),
    _mode_descriptor(
        "temperature",
        label="Temperature",
        icon="Te",
        kind="continuous",
        file="temperature_{month:02d}.png",
        monthly=True,
    ),
    _mode_descriptor(
        "precipitation",
        label="Precipitation",
        icon="Pr",
        kind="continuous",
        file="precipitation_{month:02d}.png",
        monthly=True,
    ),
    _mode_descriptor(
        "holdridge",
        label="Holdridge",
        icon="Ho",
        kind="categorical",
        file="holdridge.png",
        legend="holdridge_zone_legend.json",
    ),
    _mode_descriptor(
        "biome_v2",
        label="Biome V2",
        icon="B2",
        kind="categorical",
        file="biome_v2.png",
        legend="biome_v2_legend.json",
    ),
    _mode_descriptor(
        "landforms",
        label="Landforms",
        icon="Lf",
        kind="categorical",
        file="landforms.png",
        legend="landform_legend.json",
    ),
)



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
    from worldsim.physical.ecology.holdridge import holdridge_zone_rgb

    z = np.asarray(zones)
    rgb = np.zeros((*z.shape, 3), dtype=np.uint8)
    for zid in np.unique(z):
        rgb[z == zid] = holdridge_zone_rgb(int(zid))
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

    from worldsim.physical.ecology.biome_v2 import biome_v2_legend
    from worldsim.physical.landforms.classify import (
        derive_display_landform_id,
        landform_display_legend,
    )

    biome_legend = biome_v2_legend()
    if rasters.has("ecology/biome_v2_class"):
        klass = np.asarray(rasters.get("ecology/biome_v2_class"))
        if klass.shape != (h, w):
            klass = _nearest_uint8(klass.astype(np.uint8), h, w)
        write_png_rgb(
            directory / "biome_v2.png",
            paint_categorical_rgb(klass, biome_legend["classes"]),
        )

    landform_legend = landform_display_legend()
    display_overlap = 0
    if rasters.has("landforms/context_id"):
        from worldsim.spatial.hex_grid.contract import resample_nearest

        ctx = resample_nearest(np.asarray(rasters.get("landforms/context_id")), h, w)
        rid = (
            resample_nearest(np.asarray(rasters.get("landforms/mountain_range_id")), h, w)
            if rasters.has("landforms/mountain_range_id")
            else None
        )
        pid = (
            resample_nearest(np.asarray(rasters.get("landforms/plateau_id")), h, w)
            if rasters.has("landforms/plateau_id")
            else None
        )
        display_id, display_diag = derive_display_landform_id(
            ctx, mountain_range_id=rid, plateau_id=pid, ocean_mask=ocean
        )
        display_overlap = int(display_diag.get("range_plateau_overlap_cells", 0))
        write_png_rgb(
            directory / "landforms.png",
            paint_categorical_rgb(display_id, landform_legend["display_classes"]),
        )
        landform_legend["range_plateau_overlap_cells"] = display_overlap

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
                        "channel_state": s.channel_state,
                        "catchment_km2": s.catchment_km2,
                        "channel_length_km": s.channel_length_km,
                        "monthly_bed_loss": list(s.monthly_bed_loss),
                        "bed_loss_mean": s.bed_loss_mean,
                        "loss_limited": s.loss_limited,
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
        "lake_vector_schema": LAKE_VECTOR_SCHEMA,
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
                "properties": lake_atlas_properties(lake),
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

    # Compact hex cache for inspector — C8 contract names (aliases for pre-C9 Godot).
    hex_env = hex_environment_columns(hex_grid)
    hex_env["elevation_mean"] = hex_env["elevation_mean_m"]
    hex_env["precipitation_annual"] = hex_env["precipitation_annual_mm"]
    hex_env["precipitation_annual_unit"] = hex_grid.diagnostics.get(
        "precipitation_annual_unit", "mm_declared_proxy"
    )
    hex_env["precip_scale_mm"] = hex_grid.diagnostics.get("precip_scale_mm", 200.0)
    (directory / "hex_environment.json").write_text(
        json.dumps(hex_env, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    from worldsim.physical.ecology.holdridge import holdridge_display_legend
    from worldsim.export.inspection_grid import write_inspection_grid

    holdridge_legend = holdridge_display_legend()
    (directory / "holdridge_zone_legend.json").write_text(
        json.dumps(holdridge_legend, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (directory / "biome_v2_legend.json").write_text(
        json.dumps(biome_legend, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (directory / "landform_legend.json").write_text(
        json.dumps(landform_legend, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    precip_scale = float(hex_grid.diagnostics.get("precip_scale_mm", 200.0))
    write_inspection_grid(
        directory,
        temperature=hex_grid.temperature_mean,
        precipitation=hex_grid.precipitation_mean,
        humidity=hex_grid.humidity_mean,
        precip_scale_mm=precip_scale,
    )
    summary = _climate_summary(model, display_overlap=display_overlap)
    (directory / "climate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    def _write_fc(name: str, features: list[dict[str, Any]]) -> None:
        (directory / name).write_text(
            json.dumps({"type": "FeatureCollection", "features": features}) + "\n",
            encoding="utf-8",
        )

    _write_fc("mountain_ranges.geojson", list(model.vectors.mountain_ranges))
    _write_fc("mountain_ridges.geojson", list(model.vectors.mountain_ridges))
    _write_fc("plateaus.geojson", list(model.vectors.plateaus))
    _write_fc("plateau_rims.geojson", list(model.vectors.plateau_rims))

    available = [d for d in PRIMARY_MODE_DESCRIPTORS if (directory / _descriptor_file(d, 1)).is_file()]
    meta: dict[str, Any] = {
        "schema": ATLAS_DISPLAY_SCHEMA,
        "lake_vector_schema": LAKE_VECTOR_SCHEMA,
        "raster_width": w,
        "raster_height": h,
        "months": n_months,
        "map_modes": available,
        "map_mode_ids": [str(d["id"]) for d in available],
        "default_mode": "elevation",
        "hex_n_cells": hex_grid.n_cells,
        "static_modes": [str(d["id"]) for d in available if not d.get("monthly")],
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
            "biome_v2_legend": "biome_v2_legend.json",
            "landform_legend": "landform_legend.json",
            "mountain_ranges": "mountain_ranges.geojson",
            "mountain_ridges": "mountain_ridges.geojson",
            "plateaus": "plateaus.geojson",
            "plateau_rims": "plateau_rims.geojson",
            "biome_v2": "biome_v2.png",
            "landforms": "landforms.png",
            "inspection_grid": "inspection_grid.bin",
            "inspection_grid_schema": "inspection_grid.json",
            "climate_summary": "climate_summary.json",
        },
        "hex_contract_fields": list(HEX_CONTRACT_FIELDS),
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


def _descriptor_file(desc: dict[str, Any], month: int = 1) -> str:
    template = str(desc.get("file", ""))
    try:
        return template.format(month=int(month))
    except (KeyError, ValueError, IndexError):
        return template


def _climate_summary(
    model: WorldSpatialModel, *, display_overlap: int = 0
) -> dict[str, Any]:
    extra = dict(model.manifest.extra or {})
    rasters = model.rasters
    warnings: list[str] = []
    biome_ok = bool(rasters.has("ecology/biome_v2_class"))
    landforms_ok = bool(rasters.has("landforms/context_id"))
    if not biome_ok:
        warnings.append("ecology/biome_v2_class missing")
    if not landforms_ok:
        warnings.append("landforms/context_id missing")
    if display_overlap:
        warnings.append(f"range/plateau object overlap: {display_overlap} cells")
    return {
        "temperature_integrity_ok": bool(
            extra.get("temperature_integrity_ok", extra.get("climate_acceptance_ok", True))
        ),
        "moisture_spinup_ok": bool(extra.get("moisture_spinup_ok", extra.get("moisture_acceptance_ok", False))),
        "moisture_budget_ok": bool(extra.get("moisture_budget_ok", extra.get("moisture_acceptance_ok", False))),
        "hydrology_coupling_ok": bool(
            extra.get("hydrology_coupling_ok", extra.get("hydrology_acceptance_ok", False))
        ),
        "biome_v2_ok": biome_ok,
        "landforms_ok": landforms_ok,
        "overall_acceptance_ok": bool(model.manifest.acceptance_ok),
        "warnings": warnings,
    }
