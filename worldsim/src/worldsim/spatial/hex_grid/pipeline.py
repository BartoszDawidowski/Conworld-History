"""Milestone 15 — analytical hex grid orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.pipeline import (
    ClimateResult,
    climate_grid_land_elevation,
    downsample_mean,
)
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
    unique_positive_ids_per_hex,
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

_OPTIONAL_HEX_ARRAYS: tuple[str, ...] = (
    "mountain_score_mean",
    "plateau_score_mean",
    "mountain_terrain_fraction",
    "mountain_range_fraction",
    "plateau_context_fraction",
    "plateau_object_fraction",
    "context_dominant",
    "local_form_dominant",
    "terrain_barrier_strength",
    "biome_v2_dominant",
    "frost_months_mean",
    "growing_season_months_mean",
    "water_deficit_mm_mean",
    "soil_state_dominant",
    "local_relief_mean_m",
    "slope_mean_deg",
    "temperature_annual_c",
    "precipitation_annual_mm",
    "permanent_water_fraction",
    "seasonal_water_fraction",
    "perennial_river_fraction",
    "seasonal_river_fraction",
    "wadi_fraction",
    "mean_effective_discharge",
)

_INT_OPTIONAL = {
    "context_dominant",
    "local_form_dominant",
    "biome_v2_dominant",
    "soil_state_dominant",
}


def _optional_hex_array(env: Any, name: str) -> NDArray[Any] | None:
    if name not in env.files:
        return None
    dtype = np.int32 if name in _INT_OPTIONAL else np.float64
    return np.asarray(env[name], dtype=dtype)


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
    # C8 landform / water aggregates (optional)
    mountain_score_mean: NDArray[np.float64] | None = None
    plateau_score_mean: NDArray[np.float64] | None = None
    mountain_terrain_fraction: NDArray[np.float64] | None = None
    mountain_range_fraction: NDArray[np.float64] | None = None
    plateau_context_fraction: NDArray[np.float64] | None = None
    plateau_object_fraction: NDArray[np.float64] | None = None
    context_dominant: NDArray[np.int32] | None = None
    local_form_dominant: NDArray[np.int32] | None = None
    terrain_barrier_strength: NDArray[np.float64] | None = None
    mountain_range_ids: list[list[int]] | None = None
    plateau_ids: list[list[int]] | None = None
    basin_ids: list[list[int]] | None = None
    biome_v2_dominant: NDArray[np.int32] | None = None
    frost_months_mean: NDArray[np.float64] | None = None
    growing_season_months_mean: NDArray[np.float64] | None = None
    water_deficit_mm_mean: NDArray[np.float64] | None = None
    soil_state_dominant: NDArray[np.int32] | None = None
    local_relief_mean_m: NDArray[np.float64] | None = None
    slope_mean_deg: NDArray[np.float64] | None = None
    temperature_annual_c: NDArray[np.float64] | None = None
    precipitation_annual_mm: NDArray[np.float64] | None = None
    permanent_water_fraction: NDArray[np.float64] | None = None
    seasonal_water_fraction: NDArray[np.float64] | None = None
    perennial_river_fraction: NDArray[np.float64] | None = None
    seasonal_river_fraction: NDArray[np.float64] | None = None
    wadi_fraction: NDArray[np.float64] | None = None
    mean_effective_discharge: NDArray[np.float64] | None = None

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
        for name in _OPTIONAL_HEX_ARRAYS:
            arr = getattr(self, name)
            if arr is not None:
                payload[name] = arr
        np.savez_compressed(directory / "hex_environment.npz", **payload)
        refs = {
            "river_ids": self.river_ids,
            "lake_ids": self.lake_ids,
            "coastline_segment_ids": self.coastline_segment_ids,
        }
        if self.mountain_range_ids is not None:
            refs["mountain_range_ids"] = self.mountain_range_ids
            refs["plateau_ids"] = self.plateau_ids
        if self.basin_ids is not None:
            refs["basin_ids"] = self.basin_ids
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
        result = cls(
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
            mountain_range_ids=list(refs["mountain_range_ids"])
            if "mountain_range_ids" in refs
            else None,
            plateau_ids=list(refs["plateau_ids"]) if "plateau_ids" in refs else None,
            basin_ids=list(refs["basin_ids"]) if "basin_ids" in refs else None,
            **{
                name: _optional_hex_array(env, name) for name in _OPTIONAL_HEX_ARRAYS
            },
        )
        # Legacy caches stored score means as *_fraction.
        if result.mountain_score_mean is None and "mountain_fraction" in env.files:
            result.mountain_score_mean = np.asarray(env["mountain_fraction"], dtype=np.float64)
        if result.plateau_score_mean is None and "plateau_fraction" in env.files:
            result.plateau_score_mean = np.asarray(env["plateau_fraction"], dtype=np.float64)
        return result


def _lake_period_maps(hydrology: HydrologyResult) -> tuple[NDArray[np.float64] | None, NDArray[np.float64] | None]:
    """Permanent vs seasonal liquid fraction rasters at hydrology resolution."""
    frac = getattr(hydrology, "water_fraction_mean", None)
    lid = getattr(hydrology, "lake_id", None)
    if frac is None or lid is None or not np.asarray(lid).size:
        return None, None
    wf = np.asarray(frac, dtype=np.float64)
    ids = np.asarray(lid, dtype=np.int32)
    if wf.shape != ids.shape:
        return None, None
    recs = list(getattr(hydrology, "lake_records", None) or [])
    max_id = int(ids.max()) if ids.size else 0
    code = np.zeros(max_id + 1, dtype=np.uint8)
    for rec in recs:
        i = int(rec.get("lake_id") or rec.get("id") or 0)
        if i <= 0 or i > max_id:
            continue
        hp = str(rec.get("hydroperiod") or "")
        if hp == "permanent":
            code[i] = 1
        elif hp in ("seasonal", "ephemeral_or_dry"):
            code[i] = 2
    if recs:
        cls = code[np.clip(ids, 0, max_id)]
        perm = np.where(cls == 1, wf, 0.0)
        seas = np.where(cls == 2, wf, 0.0)
    else:
        perm = wf.copy()
        seas = np.zeros_like(wf)
    return perm, seas


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
        frac_src = getattr(hydrology, "water_fraction_mean", None)
        if frac_src is not None and np.asarray(frac_src).size:
            lake_c = downsample_mean(
                np.asarray(frac_src, dtype=np.float64),
                climate.extent.width,
                climate.extent.height,
            )
            lake_mean, _, _, _, _ = aggregate_scalar(lake_c, hex_of, n_hex=n)
            lake_frac = np.clip(lake_mean, 0.0, 1.0)
        else:
            from worldsim.physical.climate.pipeline import downsample_mode_bool

            lake_c = downsample_mode_bool(
                hydrology.lake_mask, climate.extent.width, climate.extent.height
            )
            lake_frac = aggregate_fraction(lake_c, hex_of, n_hex=n)

    if elevation_terrain_m is not None:
        src = np.asarray(elevation_terrain_m, dtype=np.float64)
        if hydrology is not None and hydrology.ocean_mask.shape == src.shape:
            terrain_ocean = hydrology.ocean_mask
        else:
            terrain_ocean = src < 0.0
        elev = climate_grid_land_elevation(
            src,
            terrain_ocean,
            climate.extent.width,
            climate.extent.height,
            climate_ocean_mask=ocean,
            ocean_elevation_m=climate.elevation_m,
        )
    else:
        elev = climate.elevation_m

    elev_mean, elev_min, elev_max, elev_std, land_counts = aggregate_scalar(
        elev, hex_of, n_hex=n, mask=land
    )
    _, _, _, _, counts = aggregate_scalar(elev, hex_of, n_hex=n)
    # Ocean-only / uncovered hexes: land elevation is no-data, not zero.
    elev_mean = np.where(land_counts > 0, elev_mean, np.nan)
    elev_min = np.where(land_counts > 0, elev_min, np.nan)
    elev_max = np.where(land_counts > 0, elev_max, np.nan)
    elev_std = np.where(land_counts > 0, elev_std, np.nan)
    local_relief = np.where(land_counts > 0, elev_max - elev_min, np.nan)

    from worldsim.spatial.hex_grid.contract import resample_nearest
    from worldsim.spatial.metrics import EARTH_RADIUS_KM, grid_metrics

    radius_km = float(climate.diagnostics.get("planet_radius_km", EARTH_RADIUS_KM))
    gm = grid_metrics(cw, ch, radius_km=radius_km)
    slope_ratio = gm.metric_slope(elev)
    slope_deg = np.degrees(np.arctan(np.asarray(slope_ratio, dtype=np.float64)))
    slope_mean, _, _, _, _ = aggregate_scalar(slope_deg, hex_of, n_hex=n, mask=land)
    slope_mean = np.where(land_counts > 0, slope_mean, np.nan)

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
    perm = np.where(land_counts > 0, perm, np.nan)

    biome_dom = frost_mean = grow_mean = deficit_mean = soil_dom = None
    if ecology.biome_v2_class is not None:
        b_all = dominant_int(ecology.biome_v2_class.astype(np.int32), hex_of, n_hex=n)
        b_land = dominant_int(
            ecology.biome_v2_class.astype(np.int32), hex_of, n_hex=n, mask=land
        )
        biome_dom = np.where(land_frac >= 0.05, b_land, b_all).astype(np.int32)
        biome_dom = np.where(counts > 0, biome_dom, np.int32(-1))
        frost_mean, _, _, _, _ = aggregate_scalar(
            ecology.frost_months.astype(np.float64), hex_of, n_hex=n, mask=land
        )
        grow_mean, _, _, _, _ = aggregate_scalar(
            ecology.growing_season_months.astype(np.float64),
            hex_of,
            n_hex=n,
            mask=land,
        )
        deficit_mean, _, _, _, _ = aggregate_scalar(
            ecology.water_deficit_mm.astype(np.float64), hex_of, n_hex=n, mask=land
        )
        frost_mean = np.where(land_counts > 0, frost_mean, np.nan)
        grow_mean = np.where(land_counts > 0, grow_mean, np.nan)
        deficit_mean = np.where(land_counts > 0, deficit_mean, np.nan)
        if ecology.soil_state is not None:
            soil_dom = dominant_int(
                ecology.soil_state.astype(np.int32), hex_of, n_hex=n, mask=land
            )
            soil_dom = np.where(land_counts > 0, soil_dom, np.int32(-1))

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
        if counts[hid] < 1 or not np.isfinite(elev_mean[hid]):
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

    # C8 landform aggregates: score mean ≠ terrain/object fraction
    mountain_score_mean = plateau_score_mean = barrier = None
    mountain_terrain_fraction = mountain_range_fraction = None
    plateau_context_fraction = plateau_object_fraction = None
    context_dom = local_form_dom = None
    mtn_ids: list[list[int]] | None = None
    plat_ids: list[list[int]] | None = None
    if landforms is not None and getattr(landforms, "mountain_score_u8", None) is not None:
        from worldsim.physical.landforms.classify import BroadContext

        diag = getattr(landforms, "diagnostics", None) or {}
        mtn_thr = float(diag.get("mountain_score_threshold", 0.60)) if isinstance(diag, dict) else 0.60
        mscore = resample_nearest(
            landforms.mountain_score_u8.astype(np.float64) / 255.0, ch, cw
        )
        pscore = resample_nearest(
            landforms.plateau_score_u8.astype(np.float64) / 255.0, ch, cw
        )
        mountain_score_mean, _, _, _, _ = aggregate_scalar(
            mscore, hex_of, n_hex=n, mask=land
        )
        plateau_score_mean, _, _, _, _ = aggregate_scalar(
            pscore, hex_of, n_hex=n, mask=land
        )
        mountain_score_mean = np.where(land_counts > 0, mountain_score_mean, np.nan)
        plateau_score_mean = np.where(land_counts > 0, plateau_score_mean, np.nan)
        mountain_terrain_fraction = aggregate_fraction(
            (mscore >= mtn_thr) & land, hex_of, n_hex=n
        )
        # Land-normalised fractions: share of land cells, not of the whole hex.
        mountain_terrain_fraction = np.where(
            land_frac > 0.0, mountain_terrain_fraction / np.maximum(land_frac, 1e-12), np.nan
        )
        ctx = resample_nearest(landforms.context_id, ch, cw).astype(np.int32)
        loc = resample_nearest(landforms.local_form_id, ch, cw).astype(np.int32)
        context_dom = dominant_int(ctx, hex_of, n_hex=n, mask=land)
        local_form_dom = dominant_int(loc, hex_of, n_hex=n, mask=land)
        context_dom = np.where(land_counts > 0, context_dom, np.int32(-1))
        local_form_dom = np.where(land_counts > 0, local_form_dom, np.int32(-1))
        plateau_context_fraction = aggregate_fraction(
            (ctx == int(BroadContext.PLATEAU)) & land, hex_of, n_hex=n
        )
        plateau_context_fraction = np.where(
            land_frac > 0.0,
            plateau_context_fraction / np.maximum(land_frac, 1e-12),
            np.nan,
        )
        rid = resample_nearest(landforms.mountain_range_id, ch, cw)
        pid = resample_nearest(landforms.plateau_id, ch, cw)
        mountain_range_fraction = aggregate_fraction((rid > 0) & land, hex_of, n_hex=n)
        mountain_range_fraction = np.where(
            land_frac > 0.0,
            mountain_range_fraction / np.maximum(land_frac, 1e-12),
            np.nan,
        )
        plateau_object_fraction = aggregate_fraction((pid > 0) & land, hex_of, n_hex=n)
        plateau_object_fraction = np.where(
            land_frac > 0.0,
            plateau_object_fraction / np.maximum(land_frac, 1e-12),
            np.nan,
        )
        barrier = np.where(land_counts > 0, np.clip(mountain_score_mean * 0.85, 0.0, 1.0), np.nan)
        mtn_ids = unique_positive_ids_per_hex(rid, hex_of, n_hex=n)
        plat_ids = unique_positive_ids_per_hex(pid, hex_of, n_hex=n)

    precip_scale = float(ecology.diagnostics.get("precip_scale_mm", 200.0))
    temp_annual = np.mean(temp, axis=1)
    precip_annual = np.sum(precip, axis=1) * precip_scale
    temp_annual = np.where(counts > 0, temp_annual, np.nan)
    precip_annual = np.where(counts > 0, precip_annual, np.nan)

    perm_water = seas_water = None
    perennial_frac = seasonal_frac = wadi_frac = None
    mean_q = None
    basin_ids: list[list[int]] | None = None
    if hydrology is not None:
        from worldsim.physical.hydrology.channels import (
            CHANNEL_PERENNIAL,
            CHANNEL_SEASONAL,
            CHANNEL_WADI,
        )

        perm_src, seas_src = _lake_period_maps(hydrology)
        if perm_src is not None:
            perm_c = downsample_mean(perm_src, cw, ch)
            seas_c = downsample_mean(seas_src, cw, ch)
            perm_water, _, _, _, _ = aggregate_scalar(perm_c, hex_of, n_hex=n)
            seas_water, _, _, _, _ = aggregate_scalar(seas_c, hex_of, n_hex=n)
            perm_water = np.where(counts > 0, np.clip(perm_water, 0.0, 1.0), np.nan)
            seas_water = np.where(counts > 0, np.clip(seas_water, 0.0, 1.0), np.nan)
        ch_state = getattr(hydrology, "channel_state", None)
        if ch_state is not None and np.asarray(ch_state).size:
            st = resample_nearest(np.asarray(ch_state), ch, cw)
            perennial_frac = aggregate_fraction(st == CHANNEL_PERENNIAL, hex_of, n_hex=n)
            seasonal_frac = aggregate_fraction(st == CHANNEL_SEASONAL, hex_of, n_hex=n)
            wadi_frac = aggregate_fraction(st == CHANNEL_WADI, hex_of, n_hex=n)
            perennial_frac = np.where(counts > 0, perennial_frac, np.nan)
            seasonal_frac = np.where(counts > 0, seasonal_frac, np.nan)
            wadi_frac = np.where(counts > 0, wadi_frac, np.nan)
            q_src = getattr(hydrology, "river_discharge_proxy", None)
            if q_src is not None and np.asarray(q_src).size:
                q = resample_nearest(np.asarray(q_src, dtype=np.float64), ch, cw)
                channel = st > 0
                mean_q, _, _, _, q_counts = aggregate_scalar(
                    q, hex_of, n_hex=n, mask=channel
                )
                mean_q = np.where(q_counts > 0, mean_q, np.nan)
        bid = getattr(hydrology, "basin_id", None)
        if bid is not None and np.asarray(bid).size:
            basin_ids = unique_positive_ids_per_hex(
                resample_nearest(np.asarray(bid), ch, cw), hex_of, n_hex=n
            )

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
        "landforms_aggregated": mountain_score_mean is not None,
        "precip_scale_mm": precip_scale,
        "precipitation_annual_unit": "mm_declared_proxy",
        "hex_contract": "c8",
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
        mountain_score_mean=mountain_score_mean,
        plateau_score_mean=plateau_score_mean,
        mountain_terrain_fraction=mountain_terrain_fraction,
        mountain_range_fraction=mountain_range_fraction,
        plateau_context_fraction=plateau_context_fraction,
        plateau_object_fraction=plateau_object_fraction,
        context_dominant=context_dom,
        local_form_dominant=local_form_dom,
        terrain_barrier_strength=barrier,
        mountain_range_ids=mtn_ids,
        plateau_ids=plat_ids,
        basin_ids=basin_ids,
        biome_v2_dominant=biome_dom,
        frost_months_mean=frost_mean,
        growing_season_months_mean=grow_mean,
        water_deficit_mm_mean=deficit_mean,
        soil_state_dominant=soil_dom,
        local_relief_mean_m=local_relief,
        slope_mean_deg=slope_mean,
        temperature_annual_c=temp_annual,
        precipitation_annual_mm=precip_annual,
        permanent_water_fraction=perm_water,
        seasonal_water_fraction=seas_water,
        perennial_river_fraction=perennial_frac,
        seasonal_river_fraction=seasonal_frac,
        wadi_fraction=wadi_frac,
        mean_effective_discharge=mean_q,
    )
