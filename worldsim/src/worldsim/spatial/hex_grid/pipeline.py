"""Milestone 15 — analytical hex grid orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.pipeline import ClimateResult, downsample_mean
from worldsim.physical.ecology.pipeline import EcologyResult
from worldsim.physical.hydrology.pipeline import HydrologyResult
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.hex_grid.aggregate import (
    aggregate_fraction,
    aggregate_monthly,
    aggregate_scalar,
    build_hex_of_climate_cells,
    dominant_int,
)
from worldsim.spatial.hex_grid.intersections import (
    coastline_ids_per_hex,
    lake_ids_per_hex,
    river_edge_mask,
    river_ids_per_hex,
)
from worldsim.spatial.hex_grid.layout import (
    HEX_LAYOUT_ALGORITHM_VERSION,
    HexGridSpec,
    all_hex_centers,
    hex_id,
    hex_latitudes_deg,
    neighbour_matrix,
    neighbours,
)


@dataclass
class HexAnalysisResult:
    spec: HexGridSpec
    center_x: NDArray[np.float64]
    center_y: NDArray[np.float64]
    latitude_deg: NDArray[np.float64]
    neighbours: NDArray[np.int32]
    land_fraction: NDArray[np.float64]
    ocean_fraction: NDArray[np.float64]
    lake_fraction: NDArray[np.float64]
    cell_count: NDArray[np.int32]
    elevation_mean: NDArray[np.float64]
    elevation_min: NDArray[np.float64]
    elevation_max: NDArray[np.float64]
    elevation_std: NDArray[np.float64]
    temperature_mean: NDArray[np.float64]  # [n, 12]
    precipitation_mean: NDArray[np.float64]  # [n, 12]
    humidity_mean: NDArray[np.float64]  # [n, 12]
    holdridge_dominant: NDArray[np.int32]
    permeability_mean: NDArray[np.float64]
    river_ids: list[list[int]]
    lake_ids: list[list[int]]
    coastline_segment_ids: list[list[int]]
    river_edge_mask: NDArray[np.uint8]
    diagnostics: dict[str, Any]
    # PR-9 landform aggregates (optional; zeros if analysis absent)
    mountain_fraction: NDArray[np.float64] | None = None
    plateau_fraction: NDArray[np.float64] | None = None
    context_dominant: NDArray[np.int32] | None = None
    terrain_barrier_strength: NDArray[np.float64] | None = None
    mountain_range_ids: list[list[int]] | None = None
    plateau_ids: list[list[int]] | None = None

    @property
    def n_cells(self) -> int:
        return self.spec.n_cells

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "latitude_deg": self.latitude_deg,
            "neighbours": self.neighbours,
            "land_fraction": self.land_fraction,
            "ocean_fraction": self.ocean_fraction,
            "lake_fraction": self.lake_fraction,
            "cell_count": self.cell_count,
            "elevation_mean": self.elevation_mean,
            "elevation_min": self.elevation_min,
            "elevation_max": self.elevation_max,
            "elevation_std": self.elevation_std,
            "temperature_mean": self.temperature_mean,
            "precipitation_mean": self.precipitation_mean,
            "humidity_mean": self.humidity_mean,
            "holdridge_dominant": self.holdridge_dominant,
            "permeability_mean": self.permeability_mean,
            "river_edge_mask": self.river_edge_mask,
        }
        if self.mountain_fraction is not None:
            payload["mountain_fraction"] = self.mountain_fraction
            payload["plateau_fraction"] = self.plateau_fraction
            payload["context_dominant"] = self.context_dominant
            payload["terrain_barrier_strength"] = self.terrain_barrier_strength
        np.savez_compressed(directory / "hex_environment.npz", **payload)
        refs = {
            "river_ids": self.river_ids,
            "lake_ids": self.lake_ids,
            "coastline_segment_ids": self.coastline_segment_ids,
        }
        if self.mountain_range_ids is not None:
            refs["mountain_range_ids"] = self.mountain_range_ids
            refs["plateau_ids"] = self.plateau_ids
        (directory / "hex_object_refs.json").write_text(
            json.dumps(refs, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (directory / "hex_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> HexAnalysisResult:
        env = np.load(directory / "hex_environment.npz")
        refs = json.loads((directory / "hex_object_refs.json").read_text(encoding="utf-8"))
        diag_path = directory / "hex_diagnostics.json"
        diagnostics = (
            json.loads(diag_path.read_text(encoding="utf-8"))
            if diag_path.is_file()
            else {}
        )
        n = int(env["center_x"].shape[0])
        # Infer width/height from diagnostics or square-ish default
        width = int(diagnostics.get("width", 0))
        height = int(diagnostics.get("height", 0))
        if width <= 0 or height <= 0 or width * height != n:
            # Neighbour wrap implies width; try common production size
            if n == 32768:
                width, height = 256, 128
            else:
                # factor n ≈ w*h with w=2h typical
                height = int(round((n / 2) ** 0.5))
                width = n // max(height, 1)
                while width * height != n and height > 1:
                    height -= 1
                    width = n // height
        return cls(
            spec=HexGridSpec(width=width, height=height, orientation="flat_top"),
            center_x=np.asarray(env["center_x"], dtype=np.float64),
            center_y=np.asarray(env["center_y"], dtype=np.float64),
            latitude_deg=np.asarray(env["latitude_deg"], dtype=np.float64),
            neighbours=np.asarray(env["neighbours"], dtype=np.int32),
            land_fraction=np.asarray(env["land_fraction"], dtype=np.float64),
            ocean_fraction=np.asarray(env["ocean_fraction"], dtype=np.float64),
            lake_fraction=np.asarray(env["lake_fraction"], dtype=np.float64),
            cell_count=(
                np.asarray(env["cell_count"], dtype=np.int32)
                if "cell_count" in env.files
                # Legacy caches predate cell_count; hexes already have aggregates.
                else np.ones(n, dtype=np.int32)
            ),
            elevation_mean=np.asarray(env["elevation_mean"], dtype=np.float64),
            elevation_min=np.asarray(env["elevation_min"], dtype=np.float64),
            elevation_max=np.asarray(env["elevation_max"], dtype=np.float64),
            elevation_std=np.asarray(env["elevation_std"], dtype=np.float64),
            temperature_mean=np.asarray(env["temperature_mean"], dtype=np.float64),
            precipitation_mean=np.asarray(env["precipitation_mean"], dtype=np.float64),
            humidity_mean=np.asarray(env["humidity_mean"], dtype=np.float64),
            holdridge_dominant=np.asarray(env["holdridge_dominant"], dtype=np.int32),
            permeability_mean=np.asarray(env["permeability_mean"], dtype=np.float64),
            river_ids=list(refs.get("river_ids", [])),
            lake_ids=list(refs.get("lake_ids", [])),
            coastline_segment_ids=list(refs.get("coastline_segment_ids", [])),
            river_edge_mask=np.asarray(env["river_edge_mask"], dtype=np.uint8),
            diagnostics=diagnostics,
            mountain_fraction=(
                np.asarray(env["mountain_fraction"], dtype=np.float64)
                if "mountain_fraction" in env.files
                else None
            ),
            plateau_fraction=(
                np.asarray(env["plateau_fraction"], dtype=np.float64)
                if "plateau_fraction" in env.files
                else None
            ),
            context_dominant=(
                np.asarray(env["context_dominant"], dtype=np.int32)
                if "context_dominant" in env.files
                else None
            ),
            terrain_barrier_strength=(
                np.asarray(env["terrain_barrier_strength"], dtype=np.float64)
                if "terrain_barrier_strength" in env.files
                else None
            ),
            mountain_range_ids=list(refs["mountain_range_ids"])
            if "mountain_range_ids" in refs
            else None,
            plateau_ids=list(refs["plateau_ids"]) if "plateau_ids" in refs else None,
        )


def build_hex_analysis_grid(
    *,
    climate: ClimateResult,
    moisture: MoistureResult,
    ecology: EcologyResult,
    hydrology: HydrologyResult | None = None,
    vectors: VectorGeographyResult | None = None,
    elevation_terrain_m: NDArray[np.floating] | None = None,
    landforms: Any | None = None,
    width: int = 256,
    height: int = 128,
    reporter: ProgressReporter | None = None,
) -> HexAnalysisResult:
    if reporter is not None:
        reporter.stage_started("hex")
        reporter.progress("hex", 0.05)

    spec = HexGridSpec(width=width, height=height, orientation="flat_top")
    # Never denser than climate grid — otherwise most hexes get zero samples
    # (Quick profile used to pair climate 128×64 with analysis 256×128).
    cw, ch = int(climate.extent.width), int(climate.extent.height)
    if spec.width > cw or spec.height > ch:
        width = min(spec.width, cw)
        height = min(spec.height, ch)
        spec = HexGridSpec(width=width, height=height, orientation="flat_top")
    n = spec.n_cells
    cx, cy = all_hex_centers(spec)
    lat = hex_latitudes_deg(spec)
    neigh = neighbour_matrix(spec)

    if reporter is not None:
        reporter.progress("hex", 0.15)

    hex_of = build_hex_of_climate_cells(climate.extent, spec)
    ocean = climate.ocean_mask
    land = ~ocean

    ocean_frac = aggregate_fraction(ocean, hex_of, n_hex=n)
    land_frac = aggregate_fraction(land, hex_of, n_hex=n)

    lake_frac = np.zeros(n, dtype=np.float64)
    if hydrology is not None:
        # downsample lake mask to climate grid then aggregate
        from worldsim.physical.climate.pipeline import downsample_mode_bool

        lake_c = downsample_mode_bool(
            hydrology.lake_mask, climate.extent.width, climate.extent.height
        )
        lake_frac = aggregate_fraction(lake_c, hex_of, n_hex=n)

    if elevation_terrain_m is not None:
        elev = downsample_mean(
            np.asarray(elevation_terrain_m, dtype=np.float64),
            climate.extent.width,
            climate.extent.height,
        )
        elev = np.where(ocean, climate.elevation_m, elev)
    else:
        elev = climate.elevation_m

    elev_mean, elev_min, elev_max, elev_std, _ = aggregate_scalar(
        elev, hex_of, n_hex=n, mask=land
    )
    # For ocean-only hexes, fill elev from all cells
    elev_all_mean, elev_all_min, elev_all_max, elev_all_std, counts = aggregate_scalar(
        elev, hex_of, n_hex=n
    )
    empty_land = ~np.isfinite(elev_mean)
    elev_mean = np.where(empty_land, elev_all_mean, elev_mean)
    elev_min = np.where(empty_land, elev_all_min, elev_min)
    elev_max = np.where(empty_land, elev_all_max, elev_max)
    elev_std = np.where(empty_land, elev_all_std, elev_std)

    if reporter is not None:
        reporter.progress("hex", 0.45)

    temp = aggregate_monthly(climate.temperature_c, hex_of, n_hex=n)
    precip = aggregate_monthly(moisture.precipitation, hex_of, n_hex=n)
    humid = aggregate_monthly(moisture.humidity, hex_of, n_hex=n)
    # Prefer land-cell mode so coastal hexes are not labeled Ocean when mostly land.
    hold_all = dominant_int(ecology.holdridge_zone_id, hex_of, n_hex=n)
    hold_land = dominant_int(
        ecology.holdridge_zone_id, hex_of, n_hex=n, mask=land
    )
    hold = np.where(land_frac >= 0.05, hold_land, hold_all).astype(np.int32)
    # Hexes with no climate cells (e.g. Quick 128×64 climate vs 256×128 hex) → no data
    hold = np.where(counts > 0, hold, np.int32(-1))
    perm, _, _, _, _ = aggregate_scalar(ecology.permeability, hex_of, n_hex=n, mask=land)

    if reporter is not None:
        reporter.progress("hex", 0.7)

    if vectors is not None:
        riv_ids = river_ids_per_hex(vectors.rivers.segments, spec)
        lake_ids = lake_ids_per_hex(vectors.lakes, spec)
        coast_ids = coastline_ids_per_hex(vectors.coastline, spec)
        edge_mask = river_edge_mask(vectors.rivers.segments, spec)
    else:
        riv_ids = [[] for _ in range(n)]
        lake_ids = [[] for _ in range(n)]
        coast_ids = [[] for _ in range(n)]
        edge_mask = np.zeros(n, dtype=np.uint8)

    # Diagnostics / acceptance
    # E–W wrap: q=0 west neighbour is q=width-1
    q0_west = neighbours(0, height // 2, width=width, height=height)[4]  # W index
    ew_wrap_ok = q0_west is not None and (q0_west % width) == (width - 1)
    # N–S: northern row has no NE/N-ish — check any None among northish edges
    north_neigh = neighbours(1, 0, width=width, height=height)
    ns_nowrap_ok = any(n is None for n in north_neigh)

    # Cache vs raster: mean ocean fraction should match global ocean mean within tol
    global_ocean = float(np.mean(ocean))
    hex_ocean = float(np.mean(ocean_frac))
    frac_ok = abs(hex_ocean - global_ocean) < 0.08

    # Sample elev consistency: hex mean near climate elev at hex centre
    sample_ok = True
    rng = np.random.default_rng(0)
    sample_ids = rng.choice(n, size=min(64, n), replace=False)
    err = []
    for hid in sample_ids:
        if counts[hid] < 1:
            continue
        # climate cell at hex centre
        from worldsim.spatial.coordinates import wrap_x

        x, y = float(cx[hid]), float(cy[hid])
        ci = int(
            np.clip(
                np.floor(wrap_x(x) * climate.extent.width),
                0,
                climate.extent.width - 1,
            )
        )
        cj = int(
            np.clip(
                np.floor((1.0 - y) * 0.5 * climate.extent.height),
                0,
                climate.extent.height - 1,
            )
        )
        err.append(abs(float(elev_mean[hid]) - float(elev[cj, ci])))
    if err:
        sample_ok = float(np.mean(err)) < max(50.0, 0.15 * float(np.nanstd(elev)))

    topology_ok = bool(ew_wrap_ok and ns_nowrap_ok and n == width * height)
    # Production default is 256×128; smaller grids are allowed in unit tests.
    production_size_ok = n == 32768

    # PR-9 landform aggregates (climate-grid landform rasters → hex)
    mountain_frac = plateau_frac = barrier = None
    context_dom = None
    mtn_ids: list[list[int]] | None = None
    plat_ids: list[list[int]] | None = None
    if landforms is not None and getattr(landforms, "mountain_score_u8", None) is not None:
        from worldsim.physical.climate.pipeline import downsample_mean as _ds

        cw, ch = climate.extent.width, climate.extent.height
        mscore = _ds(
            landforms.mountain_score_u8.astype(np.float64) / 255.0, cw, ch
        )
        pscore = _ds(
            landforms.plateau_score_u8.astype(np.float64) / 255.0, cw, ch
        )
        mountain_frac, _, _, _, _ = aggregate_scalar(mscore, hex_of, n_hex=n, mask=land)
        plateau_frac, _, _, _, _ = aggregate_scalar(pscore, hex_of, n_hex=n, mask=land)
        ctx = landforms.context_id
        if ctx.shape != (ch, cw):
            # nearest downsample
            y_idx = (np.arange(ch) * ctx.shape[0] / ch).astype(np.int32)
            x_idx = (np.arange(cw) * ctx.shape[1] / cw).astype(np.int32)
            ctx = ctx[y_idx][:, x_idx]
        context_dom = dominant_int(ctx.astype(np.int32), hex_of, n_hex=n, mask=land)
        barrier = np.clip(mountain_frac * 0.85 + (1.0 - land_frac) * 0.0, 0.0, 1.0)
        # Intersecting object IDs: unique positive IDs per hex from downsampled maps
        rid = landforms.mountain_range_id
        pid = landforms.plateau_id
        if rid.shape != (ch, cw):
            y_idx = (np.arange(ch) * rid.shape[0] / ch).astype(np.int32)
            x_idx = (np.arange(cw) * rid.shape[1] / cw).astype(np.int32)
            rid = rid[y_idx][:, x_idx]
            pid = pid[y_idx][:, x_idx]
        mtn_ids = [[] for _ in range(n)]
        plat_ids = [[] for _ in range(n)]
        for j in range(ch):
            for i in range(cw):
                hid = int(hex_of[j, i])
                if hid < 0 or hid >= n:
                    continue
                r = int(rid[j, i])
                p = int(pid[j, i])
                if r > 0 and r not in mtn_ids[hid]:
                    mtn_ids[hid].append(r)
                if p > 0 and p not in plat_ids[hid]:
                    plat_ids[hid].append(p)

    # PR-1 layout invariants (cheap; always recorded)
    abs_y = np.abs(cy)
    no_pole_clip = bool(np.all(abs_y < 1.0 - 1e-12))
    mean_lat = float(np.mean(lat))
    row_y = np.empty(height, dtype=np.float64)
    for r in range(height):
        ys = [float(cy[hex_id(q, r, width=width)]) for q in range(width)]
        row_y[r] = float(np.mean(ys))
    mirror_err = [
        abs(float(row_y[r] + row_y[height - 1 - r])) for r in range(height // 2)
    ]
    ns_mirror_ok = bool(max(mirror_err) < 0.02) if mirror_err else True
    mean_lat_ok = bool(abs(mean_lat) < 0.25)

    diagnostics: dict[str, Any] = {
        "width": width,
        "height": height,
        "n_cells": n,
        "hex_layout_algorithm_version": HEX_LAYOUT_ALGORITHM_VERSION,
        "exact_32768": production_size_ok,
        "ew_wrap_ok": bool(ew_wrap_ok),
        "ns_nowrap_ok": bool(ns_nowrap_ok),
        "no_pole_clip_ok": no_pole_clip,
        "mean_latitude_deg": mean_lat,
        "mean_latitude_ok": mean_lat_ok,
        "ns_mirror_ok": ns_mirror_ok,
        "ocean_fraction_global": global_ocean,
        "ocean_fraction_hex_mean": hex_ocean,
        "fraction_consistency_ok": frac_ok,
        "elevation_sample_consistency_ok": sample_ok,
        "hexes_with_samples": int(np.count_nonzero(counts > 0)),
        "acceptance_ok": bool(
            topology_ok
            and frac_ok
            and sample_ok
            and no_pole_clip
            and mean_lat_ok
            and ns_mirror_ok
        ),
        "production_acceptance_ok": bool(
            topology_ok
            and production_size_ok
            and frac_ok
            and sample_ok
            and no_pole_clip
            and mean_lat_ok
            and ns_mirror_ok
        ),
        "landforms_aggregated": mountain_frac is not None,
    }

    if reporter is not None:
        reporter.progress("hex", 1.0)
        reporter.stage_complete("hex")

    return HexAnalysisResult(
        spec=spec,
        center_x=cx,
        center_y=cy,
        latitude_deg=lat,
        neighbours=neigh,
        land_fraction=land_frac,
        ocean_fraction=ocean_frac,
        lake_fraction=lake_frac,
        cell_count=counts.astype(np.int32),
        elevation_mean=elev_mean,
        elevation_min=elev_min,
        elevation_max=elev_max,
        elevation_std=elev_std,
        temperature_mean=temp,
        precipitation_mean=precip,
        humidity_mean=humid,
        holdridge_dominant=hold,
        permeability_mean=perm,
        river_ids=riv_ids,
        lake_ids=lake_ids,
        coastline_segment_ids=coast_ids,
        river_edge_mask=edge_mask,
        diagnostics=diagnostics,
        mountain_fraction=mountain_frac,
        plateau_fraction=plateau_frac,
        context_dominant=context_dom,
        terrain_barrier_strength=barrier,
        mountain_range_ids=mtn_ids,
        plateau_ids=plat_ids,
    )
