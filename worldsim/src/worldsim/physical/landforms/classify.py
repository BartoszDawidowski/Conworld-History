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

    # Mountain: meso relief + slope + local prominence (peak/ridge TPI)
    mean_slope_m = metrics["mean_slope_meso"]
    tpi_abs = np.abs(metrics["tpi_fine"])
    mountain = (
        0.20 * _norm(relief_f, 400.0)
        + 0.35 * _norm(relief_m, 700.0)
        + 0.15 * _norm(rough_m, 250.0)
        + 0.15 * _norm(mean_slope_m, 0.12)
        + 0.15 * _norm(tpi_abs, 250.0)
    )
    # Mild flatness penalty (plateau interiors stay low; ridges keep score)
    mountain = mountain * (1.0 - 0.30 * np.clip(flat - 0.5, 0.0, 1.0))

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
    mean_slope_m = metrics["mean_slope_meso"]
    tpi_f = metrics["tpi_fine"]
    relief_f = metrics["relief_fine"]
    flat = metrics["flatness_meso"]
    mountain = scores["mountain_score"]
    plateau = scores["plateau_score"]
    if np.any(land):
        lowland = float(np.percentile(elev[land], 25))
    else:
        lowland = 0.0
    elev_above = elev - lowland

    context = np.full(ocean.shape, int(BroadContext.OCEAN), dtype=np.uint8)
    basin = land & (metrics["tpi_macro"] < -150.0)
    plat = (
        land
        & (plateau >= params.plateau_score_threshold)
        & (flat > 0.40)
        & (elev_above > 250.0)
        & (relief_f < 350.0)
        & (mountain < 0.55)
    )
    upland = land & ~plat & (elev_above > 150.0) & (mountain < 0.55)
    plain = land & ~plat & ~upland & ~basin
    context[plain] = int(BroadContext.PLAIN)
    context[upland] = int(BroadContext.UPLAND)
    context[plat] = int(BroadContext.PLATEAU)
    context[basin] = int(BroadContext.BASIN)

    local = np.full(ocean.shape, int(LocalForm.OCEAN), dtype=np.uint8)
    local[land] = int(LocalForm.SLOPE)
    local[land & (slope < params.flat_slope) & (np.abs(tpi_f) < 50.0)] = int(
        LocalForm.FLAT
    )
    local[land & (tpi_f > 80.0) & (slope < 0.15)] = int(LocalForm.SUMMIT)
    local[land & (tpi_f > 40.0) & (slope >= 0.05)] = int(LocalForm.RIDGE)
    local[land & (tpi_f < -60.0)] = int(LocalForm.VALLEY)
    local[land & (tpi_f < -120.0) & (slope < 0.08)] = int(LocalForm.DEPRESSION)
    # Escarpment: strong local elev step. Metric slope is tiny on coarse
    # planetary grids, so relief dominates the label.
    esc = land & (relief_f >= 200.0) & (
        (slope >= params.escarpment_slope)
        | (mean_slope_m >= 0.0008)
        | (relief_f >= 400.0)
    )
    local[esc] = int(LocalForm.ESCARPMENT)

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
