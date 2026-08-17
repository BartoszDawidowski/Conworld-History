"""Milestone 5 terrain/ocean pipeline orchestration."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.baseline import TectonicsExtendedResult
from worldsim.physical.tectonics.interpretation import (
    TectonicsInterpretationResult,
    cylindrical_distance_to_mask,
)
from worldsim.physical.terrain.bathymetry import shape_bathymetry
from worldsim.physical.terrain.coastline import (
    CoastlineFeature,
    extract_coastline_segments,
    save_coastline_geojson_like,
)
from worldsim.physical.terrain.elevation import raw_to_elevation_m_with_diagnostics
from worldsim.physical.terrain.refine import refine_terrain, upsample_mask_field
from worldsim.physical.terrain.sealevel import (
    calibrate_sea_level,
    measured_ocean_fraction,
    ocean_mask_from_sea_level,
)
from worldsim.physical.terrain.waterbodies import (
    label_water_bodies,
    ocean_basin_ids,
)
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent


@dataclass(frozen=True)
class TerrainParams:
    width: int
    height: int
    ocean_fraction_target: float = 0.71
    detail_amplitude: float = 0.08
    land_scale_m: float = 6000.0
    ocean_scale_m: float = 5000.0
    orogeny_boost: float = 0.05
    activity_relief: float = 0.25
    boundary_relief: float = 0.35
    # PR-2 / CR-5 hypsometry (packaged default: power_tail_v2)
    hypsometry_mode: str = "power_tail_v2"
    hypsometry_anchor_quantile: float = 0.95
    hypsometry_anchor_elevation_m: float = 3000.0
    hypsometry_body_exponent: float = 1.5
    hypsometry_max_elevation_m: float | None = None
    hypsometry_tail_softness: float = 1.0


@dataclass
class TerrainOceanResult:
    extent: SpatialExtent
    elevation_m: NDArray[np.float64]
    ocean_mask: NDArray[np.bool_]
    ocean_depth_m: NDArray[np.float64]
    shelf_mask: NDArray[np.bool_]
    water_body_id: NDArray[np.int32]
    ocean_basin_id: NDArray[np.int32]
    coast_distance: NDArray[np.float64]
    sea_level_raw: float
    ocean_fraction: float
    coastline_features: list[CoastlineFeature]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "terrain_ocean.npz",
            elevation_m=self.elevation_m,
            ocean_mask=self.ocean_mask.astype(np.uint8),
            ocean_depth_m=self.ocean_depth_m,
            shelf_mask=self.shelf_mask.astype(np.uint8),
            water_body_id=self.water_body_id,
            ocean_basin_id=self.ocean_basin_id,
            coast_distance=self.coast_distance,
        )
        save_coastline_geojson_like(
            self.coastline_features, directory / "coastline_prototype.geojson"
        )
        (directory / "terrain_ocean_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_terrain_ocean(
    *,
    tectonics: TectonicsExtendedResult,
    interpretation: TectonicsInterpretationResult | None,
    params: TerrainParams,
    detail_seed: int,
    reporter: ProgressReporter | None = None,
) -> TerrainOceanResult:
    if reporter is not None:
        reporter.stage_started("terrain")
        reporter.progress("terrain", 0.05)

    dist = interpretation.distance_to_boundary if interpretation else None
    activity = interpretation.tectonic_activity if interpretation else None
    volcanic = interpretation.volcanic_potential if interpretation else None
    orogenic = interpretation.orogenic_potential if interpretation else None
    subduction = interpretation.subduction_potential if interpretation else None
    divergence = interpretation.divergence_strength if interpretation else None

    refined_raw = refine_terrain(
        elevation_raw=tectonics.elevation_raw,
        distance_to_boundary=dist,
        tectonic_activity=activity,
        volcanic_potential=volcanic,
        orogenic_potential=orogenic,
        out_width=params.width,
        out_height=params.height,
        detail_seed=detail_seed,
        detail_amplitude=params.detail_amplitude,
        orogeny_boost=params.orogeny_boost,
        activity_relief=params.activity_relief,
        boundary_relief=params.boundary_relief,
    )
    if reporter is not None:
        reporter.progress("terrain", 0.35)

    sea_level_raw = calibrate_sea_level(
        refined_raw, ocean_fraction_target=params.ocean_fraction_target
    )
    ocean_mask = ocean_mask_from_sea_level(refined_raw, sea_level_raw)
    ocean_mask_before = ocean_mask.copy()
    land_components_before, land_count_before = label_water_bodies(~ocean_mask)

    elevation_m, hyps_diag = raw_to_elevation_m_with_diagnostics(
        refined_raw,
        sea_level_raw,
        land_scale_m=params.land_scale_m,
        ocean_scale_m=params.ocean_scale_m,
        ocean_mask=ocean_mask,
        hypsometry_mode=params.hypsometry_mode,
        hypsometry_anchor_quantile=params.hypsometry_anchor_quantile,
        hypsometry_anchor_elevation_m=params.hypsometry_anchor_elevation_m,
        hypsometry_body_exponent=params.hypsometry_body_exponent,
        hypsometry_max_elevation_m=params.hypsometry_max_elevation_m,
        hypsometry_tail_softness=params.hypsometry_tail_softness,
    )

    # Land transform must not alter ocean_mask / land components.
    _land_ids_after, land_count_after = label_water_bodies(~ocean_mask)
    del land_components_before

    # Rank-order check on land raw u vs land metres (ties ignored).
    land = ~ocean_mask
    rank_ok = True
    if np.count_nonzero(land) >= 2:
        u = np.maximum(refined_raw[land] - sea_level_raw, 0.0)
        z = elevation_m[land]
        rng = np.random.default_rng(0)
        n = int(u.size)
        sample = rng.choice(n, size=min(4096, n), replace=False)
        uu = u[sample]
        zz = z[sample]
        order_u = np.argsort(uu, kind="mergesort")
        order_z = np.argsort(zz, kind="mergesort")
        ru = np.empty_like(uu)
        rz = np.empty_like(zz)
        ru[order_u] = np.arange(uu.size, dtype=np.float64)
        rz[order_z] = np.arange(zz.size, dtype=np.float64)
        if float(np.std(ru)) > 0 and float(np.std(rz)) > 0:
            corr = float(np.corrcoef(ru, rz)[0, 1])
            rank_ok = corr > 0.999

    land = ~ocean_mask
    if np.any(land) and np.any(ocean_mask):
        dist_land, _, _ = cylindrical_distance_to_mask(land)
        coast_distance = np.where(ocean_mask, dist_land, 0.0)
    else:
        coast_distance = np.zeros_like(elevation_m)

    subduction_h = (
        upsample_mask_field(subduction, params.width, params.height)
        if subduction is not None
        else None
    )
    divergence_h = (
        upsample_mask_field(divergence, params.width, params.height)
        if divergence is not None
        else None
    )

    elevation_m, ocean_depth_m, shelf_mask = shape_bathymetry(
        elevation_m=elevation_m,
        ocean_mask=ocean_mask,
        coast_distance=coast_distance,
        subduction_potential=subduction_h,
        divergence_strength=divergence_h,
    )
    if reporter is not None:
        reporter.progress("terrain", 0.65)

    water_body_id, body_count = label_water_bodies(ocean_mask)
    ocean_basin_id = ocean_basin_ids(water_body_id)
    coastline = extract_coastline_segments(
        ocean_mask, water_body_id, max_features=200_000
    )
    ocean_fraction = measured_ocean_fraction(ocean_mask)

    seam_gap = float(np.mean(np.abs(elevation_m[:, 0] - elevation_m[:, -1])))
    elev_range = float(np.ptp(elevation_m)) + 1e-12
    land_elev = elevation_m[land] if np.any(land) else np.array([], dtype=np.float64)
    if land_elev.size:
        qs = (10, 25, 50, 75, 90, 95, 99)
        land_hyp = {
            "land_cells": int(land_elev.size),
            "mean_m": float(land_elev.mean()),
            "max_m": float(land_elev.max()),
            "min_m": float(land_elev.min()),
            **{f"p{q}": float(np.percentile(land_elev, q)) for q in qs},
            "frac_above_1km": float(np.mean(land_elev > 1000.0)),
            "frac_above_2km": float(np.mean(land_elev > 2000.0)),
            "frac_above_3km": float(np.mean(land_elev > 3000.0)),
            "frac_above_5km": float(np.mean(land_elev > 5000.0)),
            "frac_above_7km": float(np.mean(land_elev > 7000.0)),
            "frac_below_200m": float(np.mean(land_elev < 200.0)),
            "frac_below_500m": float(np.mean(land_elev < 500.0)),
        }
    else:
        land_hyp = {"land_cells": 0}

    diagnostics = {
        "width": params.width,
        "height": params.height,
        "sea_level_raw": sea_level_raw,
        "ocean_fraction_target": params.ocean_fraction_target,
        "ocean_fraction_measured": ocean_fraction,
        "water_body_count": body_count,
        "coastline_feature_count": len(coastline),
        "seam_gap_m": seam_gap,
        "seam_gap_relative": seam_gap / elev_range,
        "elevation_min_m": float(np.min(elevation_m)),
        "elevation_max_m": float(np.max(elevation_m)),
        "shelf_fraction": float(np.mean(shelf_mask)),
        "hypsometry": hyps_diag,
        "land_hypsometry": land_hyp,
        "land_component_count_before": int(land_count_before),
        "land_component_count_after": int(land_count_after),
        "land_components_unchanged": bool(land_count_before == land_count_after),
        "ocean_mask_unchanged": bool(np.array_equal(ocean_mask, ocean_mask_before)),
        "rank_order_ok": bool(rank_ok),
    }
    if reporter is not None:
        reporter.progress("terrain", 1.0)
        reporter.stage_complete("terrain")

    return TerrainOceanResult(
        extent=SpatialExtent.from_shape(params.width, params.height),
        elevation_m=elevation_m,
        ocean_mask=ocean_mask,
        ocean_depth_m=ocean_depth_m,
        shelf_mask=shelf_mask,
        water_body_id=water_body_id,
        ocean_basin_id=ocean_basin_id,
        coast_distance=coast_distance,
        sea_level_raw=sea_level_raw,
        ocean_fraction=ocean_fraction,
        coastline_features=coastline,
        diagnostics=diagnostics,
    )


def benchmark_terrain_resolutions(
    *,
    tectonics: TectonicsExtendedResult,
    interpretation: TectonicsInterpretationResult | None,
    detail_seed: int,
    candidates: tuple[tuple[int, int], ...] = ((4096, 2048), (2048, 1024)),
    ocean_fraction_target: float = 0.71,
    memory_budget_bytes: int = 2_000_000_000,
) -> dict[str, Any]:
    """Compare candidate terrain resolutions and recommend production size."""
    rows: list[dict[str, Any]] = []
    for width, height in candidates:
        field_bytes = width * height * 8
        estimated_bytes = field_bytes * 10
        t0 = time.perf_counter()
        run_full = estimated_bytes <= memory_budget_bytes
        timing_s: float | None
        diagnostics = None
        if run_full:
            result = build_terrain_ocean(
                tectonics=tectonics,
                interpretation=interpretation,
                params=TerrainParams(
                    width=width,
                    height=height,
                    ocean_fraction_target=ocean_fraction_target,
                ),
                detail_seed=detail_seed,
            )
            timing_s = time.perf_counter() - t0
            diagnostics = result.diagnostics
        else:
            _ = refine_terrain(
                elevation_raw=tectonics.elevation_raw,
                distance_to_boundary=(
                    interpretation.distance_to_boundary if interpretation else None
                ),
                out_width=width,
                out_height=height,
                detail_seed=detail_seed,
            )
            timing_s = time.perf_counter() - t0
        rows.append(
            {
                "width": width,
                "height": height,
                "estimated_bytes": estimated_bytes,
                "within_memory_budget": run_full,
                "seconds": timing_s,
                "diagnostics": diagnostics,
            }
        )

    viable = [r for r in rows if r["within_memory_budget"]]
    if viable:
        chosen = max(viable, key=lambda r: r["width"] * r["height"])
    else:
        chosen = min(rows, key=lambda r: r["estimated_bytes"])

    return {
        "memory_budget_bytes": memory_budget_bytes,
        "candidates": rows,
        "production_resolution": [chosen["width"], chosen["height"]],
        "rationale": (
            "Selected highest full-pipeline resolution within memory budget "
            f"({memory_budget_bytes} bytes estimated working set)."
        ),
    }
