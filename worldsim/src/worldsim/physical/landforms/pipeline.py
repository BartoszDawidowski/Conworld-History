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
    classify_layers,
    compute_scores,
    legend_payload,
)
from worldsim.physical.landforms.metrics import compute_metric_fields
from worldsim.physical.landforms.objects import (
    MountainRange,
    Plateau,
    components_to_geojson_polygons,
    extract_mountain_ranges,
    extract_plateaus,
)
from worldsim.physical.landforms.params import (
    LANDFORM_ALGORITHM_VERSION,
    LandformParams,
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

    mfields = compute_metric_fields(
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

    land = ~ocean
    if np.any(land):
        scores_finite = all(
            bool(np.all(np.isfinite(scores[k][land])))
            for k in ("mountain_score", "plateau_score", "hill_score", "confidence")
        )
    else:
        scores_finite = True
    # Structural integrity only — threshold calibration is CR-5 / PR-9E (F-13).
    structural_ok = bool(
        aw >= 8
        and ah >= 8
        and scores_finite
        and int(layers["context_id"].shape[0]) == ah
        and int(layers["context_id"].shape[1]) == aw
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
        "mountain_range_count": len(ranges),
        "plateau_count": len(plateaus),
        "mean_mountain_score_land": float(scores["mountain_score"][land].mean())
        if np.any(land)
        else 0.0,
        "mean_plateau_score_land": float(scores["plateau_score"][land].mean())
        if np.any(land)
        else 0.0,
        "seam_crossing_ranges": int(sum(1 for r in ranges if r.crosses_ew_seam)),
        "structural_ok": structural_ok,
        "calibrated": False,
        "acceptance_ok": structural_ok,
    }

    if reporter is not None:
        reporter.progress("landforms", 1.0)
        reporter.stage_complete("landforms")

    return LandformResult(
        extent=SpatialExtent(width=tw, height=th),
        context_id=up_u8(layers["context_id"]),
        local_form_id=up_u8(layers["local_form_id"]),
        provenance_id=up_u8(layers["provenance_id"]),
        confidence_u8=up_u8(to_u8(scores["confidence"])),
        mountain_score_u8=up_u8(to_u8(scores["mountain_score"])),
        plateau_score_u8=up_u8(to_u8(scores["plateau_score"])),
        hill_score_u8=up_u8(to_u8(scores["hill_score"])),
        mountain_range_id=up_i32(range_id),
        plateau_id=up_i32(plat_id),
        mountain_ranges=ranges,
        plateaus=plateaus,
        diagnostics=diagnostics,
    )
