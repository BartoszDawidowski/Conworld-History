"""LandformAnalysis orchestration (PR-9)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.pipeline import downsample_land_elevation_mean
from worldsim.physical.landforms.classify import (
    BroadContext,
    LocalForm,
    _dilate_cylindrical,
    classify_layers,
    compute_scores,
    legend_payload,
)
from worldsim.physical.landforms.gates import (
    MIN_RIDGE_COVERAGE_FRAC,
    MAX_LAND_ESCARPMENT_FRAC,
    MAX_PLATEAU_CONTEXT_ESCARPMENT_FRAC,
    landform_acceptance_gates,
    object_explosion_catastrophe,
)
from worldsim.physical.landforms.metrics import compute_metric_fields
from worldsim.physical.landforms.objects import (
    MountainRange,
    Plateau,
    components_to_geojson_polygons,
    components_to_geojson_ridges,
    components_to_geojson_rims,
    extract_mountain_ranges,
    extract_plateaus,
    plateau_rim_valid,
    ridge_geometry_ok,
)
from worldsim.physical.landforms.params import (
    LANDFORM_ALGORITHM_VERSION,
    LandformParams,
    effective_min_cells_honest,
    params_are_calibrated,
)
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics
from worldsim.spatial.resample import upsample_bilinear_cylindrical


def _dem_checksum(elevation_m: NDArray[np.floating]) -> str:
    arr = np.ascontiguousarray(np.asarray(elevation_m, dtype=np.float32))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


@dataclass
class LandformResult:
    extent: SpatialExtent
    context_id: NDArray[np.uint8]
    local_form_id: NDArray[np.uint8]
    provenance_id: NDArray[np.uint8]
    confidence_u8: NDArray[np.uint8]
    mountain_score_u8: NDArray[np.uint8]
    plateau_score_u8: NDArray[np.uint8]
    hill_score_u8: NDArray[np.uint8]
    mountain_range_id: NDArray[np.int32]
    plateau_id: NDArray[np.int32]
    mountain_ranges: list[MountainRange] = field(default_factory=list)
    plateaus: list[Plateau] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "landform_rasters.npz",
            context_id=self.context_id,
            local_form_id=self.local_form_id,
            provenance_id=self.provenance_id,
            confidence=self.confidence_u8,
            mountain_score=self.mountain_score_u8,
            plateau_score=self.plateau_score_u8,
            hill_score=self.hill_score_u8,
            mountain_range_id=self.mountain_range_id,
            plateau_id=self.plateau_id,
        )
        (directory / "landform_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "landform_legend.json").write_text(
            json.dumps(legend_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        vec_dir = directory.parent / "vectors" if directory.name == "landforms" else directory
        # Prefer sibling vectors/ when saved under final/landforms
        if (directory.parent / "vectors").is_dir() or directory.name == "landforms":
            out_vec = directory.parent / "vectors"
            out_vec.mkdir(parents=True, exist_ok=True)
        else:
            out_vec = directory
        range_feats = components_to_geojson_polygons(
            self.mountain_range_id, self.mountain_ranges, kind="mountain_range"
        )
        plat_feats = components_to_geojson_polygons(
            self.plateau_id, self.plateaus, kind="plateau"
        )
        (out_vec / "mountain_ranges.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": range_feats}) + "\n",
            encoding="utf-8",
        )
        (out_vec / "plateaus.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": plat_feats}) + "\n",
            encoding="utf-8",
        )
        ridge_feats = components_to_geojson_ridges(self.mountain_ranges)
        (out_vec / "mountain_ridges.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": ridge_feats}) + "\n",
            encoding="utf-8",
        )
        rim_feats = components_to_geojson_rims(self.plateaus)
        (out_vec / "plateau_rims.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": rim_feats}) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> LandformResult:
        rasters = np.load(directory / "landform_rasters.npz")
        diag_path = directory / "landform_diagnostics.json"
        diagnostics = (
            json.loads(diag_path.read_text(encoding="utf-8"))
            if diag_path.is_file()
            else {}
        )
        h, w = np.asarray(rasters["context_id"]).shape
        return cls(
            extent=SpatialExtent(width=w, height=h),
            context_id=np.asarray(rasters["context_id"], dtype=np.uint8),
            local_form_id=np.asarray(rasters["local_form_id"], dtype=np.uint8),
            provenance_id=np.asarray(rasters["provenance_id"], dtype=np.uint8),
            confidence_u8=np.asarray(rasters["confidence"], dtype=np.uint8),
            mountain_score_u8=np.asarray(rasters["mountain_score"], dtype=np.uint8),
            plateau_score_u8=np.asarray(rasters["plateau_score"], dtype=np.uint8),
            hill_score_u8=np.asarray(rasters["hill_score"], dtype=np.uint8),
            mountain_range_id=np.asarray(rasters["mountain_range_id"], dtype=np.int32),
            plateau_id=np.asarray(rasters["plateau_id"], dtype=np.int32),
            diagnostics=diagnostics,
        )


def build_landform_analysis(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    extent: SpatialExtent | None = None,
    analysis_width: int | None = None,
    analysis_height: int | None = None,
    orogenic_potential: NDArray[np.floating] | None = None,
    tectonic_activity: NDArray[np.floating] | None = None,
    params: LandformParams | None = None,
    reporter: ProgressReporter | None = None,
) -> LandformResult:
    """Analyse unconditioned DEM; optionally on a coarser analysis grid."""
    params = params or LandformParams()
    elev_full = np.asarray(elevation_m, dtype=np.float64)
    ocean_full = np.asarray(ocean_mask, dtype=bool)
    th, tw = elev_full.shape
    if extent is None:
        extent = SpatialExtent(width=tw, height=th)

    if not params.enabled:
        z = np.zeros((th, tw), dtype=np.uint8)
        zi = np.zeros((th, tw), dtype=np.int32)
        return LandformResult(
            extent=extent,
            context_id=z,
            local_form_id=z,
            provenance_id=z,
            confidence_u8=z,
            mountain_score_u8=z,
            plateau_score_u8=z,
            hill_score_u8=z,
            mountain_range_id=zi,
            plateau_id=zi,
            diagnostics={
                "enabled": False,
                "algorithm": LANDFORM_ALGORITHM_VERSION,
                "structural_ok": False,
                "calibrated": False,
                "acceptance_ok": False,
            },
        )

    if reporter is not None:
        reporter.stage_started("landforms")
        reporter.progress("landforms", 0.05)

    aw = int(analysis_width or tw)
    ah = int(analysis_height or th)
    aw = min(aw, tw)
    ah = min(ah, th)

    if (ah, aw) != (th, tw):
        elev, ocean = downsample_land_elevation_mean(elev_full, ocean_full, aw, ah)
    else:
        elev = elev_full
        ocean = ocean_full

    checksum = _dem_checksum(elev_full)
    metrics_grid = grid_metrics(aw, ah, radius_km=params.planet_radius_km)

    if reporter is not None:
        reporter.progress("landforms", 0.25)

    mfields, scale_windows = compute_metric_fields(
        elev,
        ocean,
        fine_radius_km=params.fine_radius_km,
        meso_radius_km=params.meso_radius_km,
        macro_radius_km=params.macro_radius_km,
        planet_radius_km=params.planet_radius_km,
        metrics=metrics_grid,
    )
    scores = compute_scores(mfields, ocean, elev, params=params)

    oro = act = None
    if orogenic_potential is not None:
        oro = np.asarray(orogenic_potential, dtype=np.float64)
        if oro.shape != elev.shape:
            oro = upsample_bilinear_cylindrical(oro, aw, ah)
    if tectonic_activity is not None:
        act = np.asarray(tectonic_activity, dtype=np.float64)
        if act.shape != elev.shape:
            act = upsample_bilinear_cylindrical(act, aw, ah)

    layers = classify_layers(
        mfields,
        scores,
        ocean,
        elev,
        params=params,
        orogenic=oro,
        tectonic_activity=act,
    )

    if reporter is not None:
        reporter.progress("landforms", 0.65)

    range_id, ranges = extract_mountain_ranges(
        mountain_score=scores["mountain_score"],
        plateau_score=scores["plateau_score"],
        elevation_m=elev,
        ocean_mask=ocean,
        provenance_id=layers["provenance_id"],
        confidence=scores["confidence"],
        relief_meso=mfields["relief_meso"],
        params=params,
        cell_area_km2=float(metrics_grid.cell_area_km2),
        tpi=mfields.get("tpi_fine"),
    )
    plat_id, plateaus = extract_plateaus(
        context_id=layers["context_id"],
        elevation_m=elev,
        ocean_mask=ocean,
        provenance_id=layers["provenance_id"],
        confidence=scores["confidence"],
        slope=mfields["slope"],
        relief_fine=mfields["relief_fine"],
        mean_elev_macro=mfields["mean_elev_macro"],
        params=params,
        cell_area_km2=float(metrics_grid.cell_area_km2),
    )

    def to_u8(x: NDArray[np.floating]) -> NDArray[np.uint8]:
        return np.clip(np.asarray(x) * 255.0, 0, 255).astype(np.uint8)

    # Upsample class maps to full DEM shape when analysis grid is coarser
    def up_u8(arr: NDArray[np.uint8]) -> NDArray[np.uint8]:
        if arr.shape == (th, tw):
            return arr
        # nearest via repeat blocks
        y_idx = (np.arange(th) * ah / th).astype(np.int32)
        x_idx = (np.arange(tw) * aw / tw).astype(np.int32)
        return arr[y_idx][:, x_idx]

    def up_i32(arr: NDArray[np.int32]) -> NDArray[np.int32]:
        if arr.shape == (th, tw):
            return arr
        y_idx = (np.arange(th) * ah / th).astype(np.int32)
        x_idx = (np.arange(tw) * aw / tw).astype(np.int32)
        return arr[y_idx][:, x_idx]

    context_full = up_u8(layers["context_id"])
    local_full = up_u8(layers["local_form_id"])
    prov_full = up_u8(layers["provenance_id"])
    conf_full = up_u8(to_u8(scores["confidence"]))
    mtn_full = up_u8(to_u8(scores["mountain_score"]))
    plat_full = up_u8(to_u8(scores["plateau_score"]))
    hill_full = up_u8(to_u8(scores["hill_score"]))
    range_full = up_i32(range_id)
    platid_full = up_i32(plat_id)

    ocean_u8 = int(BroadContext.OCEAN)
    local_ocean = int(LocalForm.OCEAN)
    context_full[ocean_full] = ocean_u8
    local_full[ocean_full] = local_ocean
    prov_full[ocean_full] = 0
    conf_full[ocean_full] = 0
    mtn_full[ocean_full] = 0
    plat_full[ocean_full] = 0
    hill_full[ocean_full] = 0
    range_full[ocean_full] = 0
    platid_full[ocean_full] = 0
    land_full = ~ocean_full
    context_full[land_full & (context_full == ocean_u8)] = int(BroadContext.PLAIN)
    local_full[land_full & (local_full == local_ocean)] = int(LocalForm.SLOPE)

    land = ~ocean
    if np.any(land):
        scores_finite = all(
            bool(np.all(np.isfinite(scores[k][land])))
            for k in ("mountain_score", "plateau_score", "hill_score", "confidence")
        )
        mountain_frac = float(
            np.mean(scores["mountain_score"][land] >= params.mountain_score_threshold)
        )
        plateau_frac = float(
            np.mean(layers["context_id"][land] == int(BroadContext.PLATEAU))
        )
        esc_frac = float(
            np.mean(layers["local_form_id"][land] == int(LocalForm.ESCARPMENT))
        )
        plat_mask = layers["context_id"] == int(BroadContext.PLATEAU)
        plat_ctx = plat_mask[land]
        if np.any(plat_ctx):
            plat_esc_frac = float(
                np.mean(
                    layers["local_form_id"][land][plat_ctx]
                    == int(LocalForm.ESCARPMENT)
                )
            )
        else:
            plat_esc_frac = 0.0
        plat_rim = plat_mask & _dilate_cylindrical(~plat_mask)
        plat_interior = plat_mask & ~plat_rim
        if np.any(plat_interior):
            plat_interior_esc_frac = float(
                np.mean(
                    layers["local_form_id"][plat_interior]
                    == int(LocalForm.ESCARPMENT)
                )
            )
        else:
            plat_interior_esc_frac = 0.0
    else:
        scores_finite = True
        mountain_frac = 0.0
        plateau_frac = 0.0
        esc_frac = 0.0
        plat_esc_frac = 0.0
        plat_interior_esc_frac = 0.0
    structural_ok = bool(
        aw >= 8
        and ah >= 8
        and scores_finite
        and int(layers["context_id"].shape[0]) == ah
        and int(layers["context_id"].shape[1]) == aw
    )
    calibrated = params_are_calibrated(params)
    mask_ok = bool(
        np.all(context_full[ocean_full] == ocean_u8)
        and np.all(context_full[land_full] != ocean_u8)
        and np.all(local_full[ocean_full] == local_ocean)
        and np.all(local_full[land_full] != local_ocean)
        and np.all(range_full[ocean_full] == 0)
        and np.all(platid_full[ocean_full] == 0)
    )
    pairs = [
        (int(w["effective_rx_cells"]), int(w["effective_ry_cells"]))
        for w in scale_windows.values()
    ]
    scales_collapsed = bool(len(set(pairs)) < len(pairs))
    local_ids = {int(v) for v in np.unique(local_full)}
    declared = set(range(int(LocalForm.OCEAN), int(LocalForm.ESCARPMENT) + 1))
    local_coverage_ok = bool(local_ids.issubset(declared) and ocean_u8 in local_ids)
    ridge_in_mask = True
    ridge_no_dup = True
    for rec in ranges:
        sel = range_id == rec.id
        chk = ridge_geometry_ok(rec.ridge_line, sel)
        ridge_in_mask = ridge_in_mask and chk["in_mask"]
        ridge_no_dup = ridge_no_dup and chk["no_consecutive_duplicates"]
    esc_alarm_ok = bool(esc_frac < MAX_LAND_ESCARPMENT_FRAC)
    plat_ctx_esc_ok = bool(plat_esc_frac < MAX_PLATEAU_CONTEXT_ESCARPMENT_FRAC)
    cell_area = float(metrics_grid.cell_area_km2)
    min_range_cells_eff, range_floor = effective_min_cells_honest(
        min_km2=params.min_range_km2,
        min_cells=params.min_range_cells,
        cell_area_km2=cell_area,
        min_component_cells=params.min_component_cells,
    )
    min_plat_cells_eff, plat_floor = effective_min_cells_honest(
        min_km2=params.min_plateau_km2,
        min_cells=params.min_plateau_cells,
        cell_area_km2=cell_area,
        min_component_cells=params.min_component_cells,
    )
    plateau_honesty_ok = bool(plat_floor["honesty_ok"]) if calibrated else True
    representability_ok = bool(plat_floor["honesty_ok"]) if calibrated else True
    interior_ok = bool(plat_interior_esc_frac < 0.15)
    eligible_ranges = [r for r in ranges if int(r.area_cells) >= int(min_range_cells_eff)]
    if eligible_ranges:
        ridge_with_line = sum(1 for r in eligible_ranges if len(r.ridge_line) >= 2)
        ridge_coverage = float(ridge_with_line) / float(len(eligible_ranges))
    else:
        ridge_coverage = 1.0
    ridge_coverage_ok = bool(ridge_coverage >= MIN_RIDGE_COVERAGE_FRAC)
    plateau_rim_ok = True
    for rec in plateaus:
        sel = plat_id == rec.id
        if not np.any(sel):
            continue
        plateau_rim_ok = plateau_rim_ok and plateau_rim_valid(
            rec.rim_line,
            sel,
            slope=mfields["slope"],
            params=params,
        )
    unresolved_mask = (
        (~ocean)
        & (scores["mountain_score"] >= params.mountain_score_threshold)
        & (range_id == 0)
    )
    unresolved_cells = int(np.count_nonzero(unresolved_mask))
    object_catastrophe = object_explosion_catastrophe(
        mountain_range_count=len(ranges),
        plateau_context_escarpment_fraction=float(plat_esc_frac),
    )
    zero_semantic_ok = bool(
        len(ranges) + len(plateaus) > 0
        or unresolved_cells > 0
        or not calibrated
    )
    gate_report = landform_acceptance_gates(
        structural_ok=structural_ok,
        calibrated=calibrated,
        mask_ok=mask_ok,
        local_coverage_ok=local_coverage_ok,
        ridge_in_mask_ok=bool(ridge_in_mask),
        ridge_no_duplicate_ok=bool(ridge_no_dup),
        plateau_honesty_ok=plateau_honesty_ok,
        plateau_interior_ok=interior_ok,
        escarpment_dominance_ok=esc_alarm_ok,
        mountain_fraction_ok=bool(
            mountain_frac <= float(params.max_mountain_land_fraction)
        ),
        mountain_fraction_alarm=bool(
            mountain_frac < 0.10 or mountain_frac > 0.30
        ),
        plateau_fraction_alarm=bool(plateau_frac < 0.01 or plateau_frac > 0.08),
        plateau_context_escarpment_ok=plat_ctx_esc_ok,
        representability_ok=representability_ok,
        ridge_coverage_ok=ridge_coverage_ok,
        plateau_rim_valid_ok=plateau_rim_ok,
        object_count_catastrophe_ok=not object_catastrophe,
        zero_semantic_objects_ok=zero_semantic_ok,
    )
    diagnostics: dict[str, Any] = {
        "enabled": True,
        "algorithm": LANDFORM_ALGORITHM_VERSION,
        "dem_checksum": checksum,
        "analysis_width": aw,
        "analysis_height": ah,
        "source_width": tw,
        "source_height": th,
        "fine_radius_km": params.fine_radius_km,
        "meso_radius_km": params.meso_radius_km,
        "macro_radius_km": params.macro_radius_km,
        "scale_windows": scale_windows,
        "scales_collapsed": scales_collapsed,
        "quick_scales_indistinguishable": bool(scales_collapsed and max(aw, ah) <= 128),
        "mountain_score_threshold": float(params.mountain_score_threshold),
        "min_range_km2": params.min_range_km2,
        "min_plateau_km2": params.min_plateau_km2,
        "min_plateau_km2_configured": (
            float(params.min_plateau_km2) if params.min_plateau_km2 is not None else None
        ),
        "cell_area_km2": cell_area,
        "min_range_cells_effective": int(min_range_cells_eff),
        "min_plateau_cells_effective": int(min_plat_cells_eff),
        "min_range_km2_representable": float(min_range_cells_eff) * cell_area,
        "min_plateau_km2_representable": float(min_plat_cells_eff) * cell_area,
        "plateau_area_floor_honesty_ok": plateau_honesty_ok,
        "min_plateau_km2_representable_ok": bool(plat_floor["representable_ok"]),
        "mountain_range_count": len(ranges),
        "mountain_system_count": int(len({int(r.system_id or r.id) for r in ranges})),
        "plateau_count": len(plateaus),
        "unresolved_mountain_candidate_cells": unresolved_cells,
        "mountain_land_fraction": mountain_frac,
        "plateau_context_land_fraction": plateau_frac,
        "escarpment_land_fraction": esc_frac,
        "plateau_context_escarpment_fraction": float(plat_esc_frac),
        "plateau_interior_escarpment_fraction": float(plat_interior_esc_frac),
        "plateau_interior_not_escarpment_ok": interior_ok,
        "mountain_fraction_alarm_band": [0.10, 0.30],
        "plateau_fraction_alarm_band": [0.01, 0.08],
        "escarpment_alarm_max": MAX_LAND_ESCARPMENT_FRAC,
        "plateau_context_escarpment_alarm_max": MAX_PLATEAU_CONTEXT_ESCARPMENT_FRAC,
        "mountain_range_catastrophe_max": 200,
        "mountain_fraction_alarm": bool(mountain_frac < 0.10 or mountain_frac > 0.30),
        "plateau_fraction_alarm": bool(plateau_frac < 0.01 or plateau_frac > 0.08),
        "escarpment_dominance_ok": esc_alarm_ok,
        "object_explosion_catastrophe": object_catastrophe,
        "ridge_coverage_fraction": float(ridge_coverage),
        "ridge_coverage_ok": ridge_coverage_ok,
        "mean_mountain_score_land": float(scores["mountain_score"][land].mean())
        if np.any(land)
        else 0.0,
        "mean_plateau_score_land": float(scores["plateau_score"][land].mean())
        if np.any(land)
        else 0.0,
        "seam_crossing_ranges": int(sum(1 for r in ranges if r.crosses_ew_seam)),
        "mask_consistency_ok": mask_ok,
        "local_form_coverage_ok": local_coverage_ok,
        "ridge_in_mask_ok": bool(ridge_in_mask),
        "ridge_no_duplicate_ok": bool(ridge_no_dup),
        "structural_ok": structural_ok,
        "calibrated": calibrated,
        "mountain_fraction_ok": bool(
            mountain_frac <= float(params.max_mountain_land_fraction)
        ),
        **gate_report,
        "ridge_centerlines": int(sum(1 for r in ranges if len(r.ridge_line) >= 2)),
        "plateau_rims": int(sum(1 for p in plateaus if len(p.rim_line) >= 2)),
    }

    if reporter is not None:
        reporter.progress("landforms", 1.0)
        reporter.stage_complete("landforms")

    return LandformResult(
        extent=SpatialExtent(width=tw, height=th),
        context_id=context_full,
        local_form_id=local_full,
        provenance_id=prov_full,
        confidence_u8=conf_full,
        mountain_score_u8=mtn_full,
        plateau_score_u8=plat_full,
        hill_score_u8=hill_full,
        mountain_range_id=range_full,
        plateau_id=platid_full,
        mountain_ranges=ranges,
        plateaus=plateaus,
        diagnostics=diagnostics,
    )
