"""Continuous scores and discrete semantic layers (PR-9A/B)."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.landforms.params import LandformParams


class BroadContext(IntEnum):
    OCEAN = 0
    PLAIN = 1
    UPLAND = 2
    PLATEAU = 3
    BASIN = 4


class LocalForm(IntEnum):
    OCEAN = 0
    FLAT = 1
    SUMMIT = 2
    RIDGE = 3
    SHOULDER = 4
    SLOPE = 5
    FOOTSLOPE = 6
    VALLEY = 7
    DEPRESSION = 8
    ESCARPMENT = 9


class Provenance(IntEnum):
    UNKNOWN = 0
    OROGENIC = 1
    VOLCANIC = 2
    RIFT_RELATED = 3
    RESIDUAL_OR_ERODED = 4
    MIXED = 5


CONTEXT_NAMES = {int(v): v.name.lower() for v in BroadContext}
LOCAL_FORM_NAMES = {int(v): v.name.lower() for v in LocalForm}
PROVENANCE_NAMES = {int(v): v.name.lower() for v in Provenance}


def _norm(x: NDArray[np.floating], scale: float) -> NDArray[np.float64]:
    return np.clip(np.asarray(x, dtype=np.float64) / max(float(scale), 1e-6), 0.0, 1.0)


def compute_scores(
    metrics: dict[str, NDArray[np.float64]],
    ocean_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    *,
    params: LandformParams,
) -> dict[str, NDArray[np.float64]]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    elev = np.asarray(elevation_m, dtype=np.float64)
    relief_f = metrics["relief_fine"]
    relief_m = metrics["relief_meso"]
    relief_a = metrics["relief_macro"]
    rough_m = metrics["roughness_meso"]
    slope = metrics["slope"]
    flat = metrics["flatness_meso"]
    mean_macro = metrics["mean_elev_macro"]

    # Mountain: meso relief + ruggedness + prominence. Scales chosen so
    # typical hills stay below ~0.55 and orogens exceed 0.60 (CR-9 / F-13).
    mean_slope_m = metrics["mean_slope_meso"]
    tpi_abs = np.abs(metrics["tpi_fine"])
    mountain = (
        0.18 * _norm(relief_f, 800.0)
        + 0.30 * _norm(relief_m, 1500.0)
        + 0.16 * _norm(rough_m, 450.0)
        + 0.12 * _norm(mean_slope_m, 0.04)
        + 0.24 * _norm(tpi_abs, 300.0)
    )
    # Flat interiors drop; summits (high |TPI|) keep score even if metric slope is tiny.
    flat_pen = np.clip(flat - 0.40, 0.0, 1.0) * np.clip(1.0 - tpi_abs / 120.0, 0.0, 1.0)
    mountain = mountain * (1.0 - 0.40 * flat_pen)

    # Lowland reference: lower quantile of land elevation
    if np.any(land):
        lowland = float(np.percentile(elev[land], 25))
    else:
        lowland = 0.0
    elev_above_lowland = np.maximum(elev - lowland, 0.0)
    elev_above_macro = np.maximum(elev - mean_macro, 0.0)
    # Plateau: elevated, flat, low fine relief (flatness is required)
    plateau = (
        0.35 * _norm(elev_above_lowland, 500.0)
        + 0.25 * _norm(elev_above_macro, 300.0)
        + 0.10 * (1.0 - _norm(relief_f, 400.0))
    ) * (0.25 + 0.75 * flat)
    plateau = plateau * (1.0 - 0.5 * _norm(relief_m, 900.0))
    # Hills: moderate meso relief without mountain intensity
    hill = (
        0.45 * _norm(relief_m, 500.0)
        + 0.30 * _norm(slope, 0.10)
        + 0.25 * (1.0 - mountain)
    )
    mountain = np.where(ocean, 0.0, np.clip(mountain, 0.0, 1.0))
    plateau = np.where(ocean, 0.0, np.clip(plateau, 0.0, 1.0))
    hill = np.where(ocean, 0.0, np.clip(hill, 0.0, 1.0))
    stack = np.stack([mountain, plateau, hill], axis=0)
    order = np.sort(stack, axis=0)
    conf = np.where(ocean, 0.0, np.clip(order[-1] - order[-2], 0.0, 1.0))
    _ = relief_a
    _ = params
    return {
        "mountain_score": mountain,
        "plateau_score": plateau,
        "hill_score": hill,
        "confidence": conf,
    }


def _laplacian_cylindrical(elev: NDArray[np.floating]) -> NDArray[np.float64]:
    e = np.asarray(elev, dtype=np.float64)
    east = np.roll(e, -1, axis=1)
    west = np.roll(e, 1, axis=1)
    north = np.empty_like(e)
    south = np.empty_like(e)
    north[:-1, :] = e[1:, :]
    north[-1, :] = e[-1, :]
    south[1:, :] = e[:-1, :]
    south[0, :] = e[0, :]
    return east + west + north + south - 4.0 * e


def _max_neighbor_drop(elev: NDArray[np.floating]) -> NDArray[np.float64]:
    """Largest elevation drop from a cell to any of its 8 neighbours (m)."""
    e = np.asarray(elev, dtype=np.float64)
    east = np.roll(e, -1, axis=1)
    west = np.roll(e, 1, axis=1)
    north = np.vstack([e[:1], e[:-1]])
    south = np.vstack([e[1:], e[-1:]])
    neigh = [
        east,
        west,
        north,
        south,
        np.roll(north, -1, axis=1),
        np.roll(north, 1, axis=1),
        np.roll(south, -1, axis=1),
        np.roll(south, 1, axis=1),
    ]
    return e - np.minimum.reduce(neigh)


def _dilate_cylindrical(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    m = np.asarray(mask, dtype=bool)
    out = m.copy()
    out |= np.roll(m, -1, axis=1)
    out |= np.roll(m, 1, axis=1)
    out[:-1] |= m[1:]
    out[1:] |= m[:-1]
    out[:-1] |= np.roll(m[1:], -1, axis=1)
    out[:-1] |= np.roll(m[1:], 1, axis=1)
    out[1:] |= np.roll(m[:-1], -1, axis=1)
    out[1:] |= np.roll(m[:-1], 1, axis=1)
    return out


def classify_layers(
    metrics: dict[str, NDArray[np.float64]],
    scores: dict[str, NDArray[np.float64]],
    ocean_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    *,
    params: LandformParams,
    orogenic: NDArray[np.floating] | None = None,
    tectonic_activity: NDArray[np.floating] | None = None,
) -> dict[str, NDArray]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    elev = np.asarray(elevation_m, dtype=np.float64)
    slope = metrics["slope"]
    tpi_f = metrics["tpi_fine"]
    relief_f = metrics["relief_fine"]
    flat = metrics["flatness_meso"]
    mountain = scores["mountain_score"]
    plateau = scores["plateau_score"]
    mtn_thr = float(params.mountain_score_threshold)
    elev_above_sea = np.maximum(elev, 0.0)

    context = np.full(ocean.shape, int(BroadContext.OCEAN), dtype=np.uint8)
    basin = land & (metrics["tpi_macro"] < -150.0)
    plat = (
        land
        & (plateau >= params.plateau_score_threshold)
        & (flat > 0.40)
        & (elev_above_sea > 250.0)
        & (relief_f < 350.0)
        & (mountain < mtn_thr)
    )
    upland = land & ~plat & (elev_above_sea > 150.0) & (mountain < mtn_thr)
    plain = land & ~plat & ~upland & ~basin
    context[plain] = int(BroadContext.PLAIN)
    context[upland] = int(BroadContext.UPLAND)
    context[plat] = int(BroadContext.PLATEAU)
    context[basin] = int(BroadContext.BASIN)

    lap = _laplacian_cylindrical(elev)
    drop = _max_neighbor_drop(elev)
    convex = lap < -25.0
    concave = lap > 25.0
    tpi_scale = np.maximum(relief_f, 80.0)
    tpi_n = tpi_f / tpi_scale

    local = np.full(ocean.shape, int(LocalForm.OCEAN), dtype=np.uint8)
    local[land] = int(LocalForm.SLOPE)
    local[land & (slope < params.flat_slope) & (np.abs(tpi_n) < 0.12)] = int(
        LocalForm.FLAT
    )
    local[land & (tpi_n < -0.08) & concave] = int(LocalForm.FOOTSLOPE)
    local[land & (tpi_n > 0.08) & convex] = int(LocalForm.SHOULDER)
    local[land & (tpi_n < -0.22) & concave] = int(LocalForm.VALLEY)
    local[land & (tpi_n < -0.35) & (slope < 0.08)] = int(LocalForm.DEPRESSION)
    local[land & (tpi_n > 0.18) & (slope >= 0.02)] = int(LocalForm.RIDGE)
    local[land & (tpi_n > 0.32) & convex & (slope < 0.12)] = int(LocalForm.SUMMIT)

    plat_mask = context == int(BroadContext.PLATEAU)
    plat_rim = plat_mask & _dilate_cylindrical(~plat_mask)
    plat_interior = plat_mask & ~plat_rim
    near_plat = _dilate_cylindrical(_dilate_cylindrical(plat_mask))
    low_side = ((elev_above_sea < 220.0) & land) | ocean
    step = (
        land
        & convex
        & (drop >= 80.0)
        & (elev_above_sea > 250.0)
        & _dilate_cylindrical(low_side)
        & ~plat_interior
    )
    esc = (land & ~plat_interior & near_plat & (drop >= 80.0)) | step
    esc = esc | (
        plat_rim
        & ((drop >= 80.0) | (slope >= params.escarpment_slope))
    )
    if np.any(land):
        drop_cut = float(np.quantile(drop[land], 0.98))
        lap_cut = float(np.quantile(np.abs(lap)[land], 0.90))
        extra = (
            land
            & ~plat_mask
            & (drop >= max(drop_cut, 250.0))
            & (np.abs(lap) >= lap_cut)
            & (mountain < mtn_thr)
            & _dilate_cylindrical((slope < params.flat_slope) & land)
        )
        esc = esc | extra
    local[esc] = int(LocalForm.ESCARPMENT)
    # Interior of a plateau stays interior (flat/slope/etc.), never escarpment.
    local[plat_interior] = np.where(
        local[plat_interior] == int(LocalForm.ESCARPMENT),
        np.where(
            slope[plat_interior] < params.flat_slope,
            int(LocalForm.FLAT),
            int(LocalForm.SLOPE),
        ),
        local[plat_interior],
    )

    prov = np.full(ocean.shape, int(Provenance.UNKNOWN), dtype=np.uint8)
    if orogenic is not None and tectonic_activity is not None:
        oro = np.asarray(orogenic, dtype=np.float64)
        act = np.asarray(tectonic_activity, dtype=np.float64)
        prov[land & (oro > 0.45)] = int(Provenance.OROGENIC)
        prov[land & (act > 0.55) & (oro <= 0.45)] = int(Provenance.RIFT_RELATED)
        both = land & (oro > 0.35) & (act > 0.35)
        prov[both] = int(Provenance.MIXED)
        residual = land & (mountain > 0.4) & (oro < 0.2) & (act < 0.2)
        prov[residual] = int(Provenance.RESIDUAL_OR_ERODED)

    return {
        "context_id": context,
        "local_form_id": local,
        "provenance_id": prov,
    }


def legend_payload() -> dict[str, Any]:
    return {
        "broad_context": CONTEXT_NAMES,
        "local_form": LOCAL_FORM_NAMES,
        "provenance": PROVENANCE_NAMES,
    }


class DisplayLandform(IntEnum):
    """Presentation-only landform class. Canonical context/objects stay independent."""

    OCEAN = 0
    PLAIN = 1
    UPLAND = 2
    MOUNTAIN = 3
    PLATEAU = 4
    BASIN = 5


DISPLAY_LANDFORM_NAMES = {int(v): v.name.lower() for v in DisplayLandform}
LANDFORM_LEGEND_SCHEMA = "landform_legend_v1"
LANDFORM_DISPLAY_CLASSES: dict[int, dict[str, str]] = {
    0: {"key": "ocean", "label": "Ocean", "color": "#17365D"},
    1: {"key": "plain", "label": "Plain", "color": "#D8D0AA"},
    2: {"key": "upland_or_hills", "label": "Upland / hills", "color": "#A99063"},
    3: {"key": "mountain", "label": "Mountain", "color": "#736357"},
    4: {"key": "plateau", "label": "Plateau", "color": "#B87855"},
    5: {"key": "basin", "label": "Basin", "color": "#8E9E78"},
}
DISPLAY_LANDFORM_PRIORITY = (
    "ocean",
    "mountain_range_object",
    "plateau_object_or_context",
    "basin",
    "upland",
    "plain",
)


def derive_display_landform_id(
    context_id: NDArray[np.integer],
    *,
    mountain_range_id: NDArray[np.integer] | None = None,
    plateau_id: NDArray[np.integer] | None = None,
    ocean_mask: NDArray[np.bool_] | None = None,
) -> tuple[NDArray[np.uint8], dict[str, Any]]:
    """Derived exclusive display class. Does not mutate canonical layers."""
    ctx = np.asarray(context_id, dtype=np.int32)
    display = np.full(ctx.shape, int(DisplayLandform.PLAIN), dtype=np.uint8)
    display[ctx == int(BroadContext.UPLAND)] = int(DisplayLandform.UPLAND)
    display[ctx == int(BroadContext.BASIN)] = int(DisplayLandform.BASIN)
    plat_obj = (
        np.asarray(plateau_id, dtype=np.int32) > 0
        if plateau_id is not None
        else np.zeros(ctx.shape, dtype=bool)
    )
    display[(ctx == int(BroadContext.PLATEAU)) | plat_obj] = int(DisplayLandform.PLATEAU)
    range_obj = (
        np.asarray(mountain_range_id, dtype=np.int32) > 0
        if mountain_range_id is not None
        else np.zeros(ctx.shape, dtype=bool)
    )
    display[range_obj] = int(DisplayLandform.MOUNTAIN)
    ocean = (
        np.asarray(ocean_mask, dtype=bool)
        if ocean_mask is not None
        else ctx == int(BroadContext.OCEAN)
    )
    display[ocean | (ctx == int(BroadContext.OCEAN))] = int(DisplayLandform.OCEAN)
    overlap = int(np.count_nonzero(range_obj & plat_obj & ~ocean))
    diag = {
        "derived": True,
        "priority": list(DISPLAY_LANDFORM_PRIORITY),
        "range_plateau_overlap_cells": overlap,
    }
    return display, diag


def landform_display_legend() -> dict[str, Any]:
    def _named(src: dict[int, str]) -> dict[str, dict[str, str]]:
        return {str(i): {"key": name, "label": name.replace("_", " ")} for i, name in src.items()}

    return {
        "schema": LANDFORM_LEGEND_SCHEMA,
        "title": "Landforms",
        "derived": True,
        "priority": list(DISPLAY_LANDFORM_PRIORITY),
        "ocean_composite_note": (
            "Ocean cells use the ordinary bathymetry background in the land-composite shader."
        ),
        "display_classes": {str(i): dict(v) for i, v in LANDFORM_DISPLAY_CLASSES.items()},
        "broad_context": _named(CONTEXT_NAMES),
        "local_form": _named(LOCAL_FORM_NAMES),
        "provenance": _named(PROVENANCE_NAMES),
        "object_styles": {
            "mountain_range": {"color": "#4A372C", "width_px": 1.25},
            "ridge": {"color": "#3A322C", "width_px": 0.95},
            "plateau_fill": {"color": "#B87855", "alpha": 0.12},
            "plateau_rim": {"color": "#C45C28", "width_px": 1.25},
            "selection": {"color": "#F2B847", "width_px": 2.0},
        },
    }
