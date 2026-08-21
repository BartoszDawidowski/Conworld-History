"""PC4 — process-specific erosion deltas and acceptance gates."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.process_deltas import ProcessDeltas

EROSION_MIN_MEAN_ABS_DELTA_M = 1.0
EROSION_MIN_MEAN_ABS_FRAC_OF_RANGE = 0.0005
HILLSLOPE_EROSION_MIN_MEAN_ABS_DELTA_M = EROSION_MIN_MEAN_ABS_DELTA_M
HILLSLOPE_EROSION_MIN_FRAC_OF_RANGE = EROSION_MIN_MEAN_ABS_FRAC_OF_RANGE
FLUVIAL_CORRIDOR_MIN_MEAN_ABS_DELTA_M = 0.5
FLUVIAL_CORRIDOR_MIN_FRAC_OF_RANGE = 0.0003


def domain_mean_abs_delta(
    delta: NDArray[np.floating],
    domain_mask: NDArray[np.bool_],
    ocean_mask: NDArray[np.bool_],
) -> float:
    land = ~np.asarray(ocean_mask, dtype=bool)
    domain = np.asarray(domain_mask, dtype=bool) & land
    d = np.abs(np.asarray(delta, dtype=np.float64))
    if not np.any(domain):
        return 0.0
    return float(np.mean(d[domain]))


def erosion_nontrivial_gate(
    mean_abs_delta_m: float,
    elev_range_m: float,
    *,
    min_abs_m: float = EROSION_MIN_MEAN_ABS_DELTA_M,
    min_frac_of_range: float = EROSION_MIN_MEAN_ABS_FRAC_OF_RANGE,
) -> tuple[bool, float]:
    required = max(
        float(min_abs_m),
        float(min_frac_of_range) * max(float(elev_range_m), 1.0),
    )
    return bool(float(mean_abs_delta_m) >= required), required


def hillslope_erosion_gate(
    mean_abs_delta_m: float,
    elev_range_m: float,
) -> tuple[bool, float]:
    return erosion_nontrivial_gate(
        mean_abs_delta_m,
        elev_range_m,
        min_abs_m=HILLSLOPE_EROSION_MIN_MEAN_ABS_DELTA_M,
        min_frac_of_range=HILLSLOPE_EROSION_MIN_FRAC_OF_RANGE,
    )


def fluvial_corridor_erosion_gate(
    mean_abs_delta_m: float,
    elev_range_m: float,
) -> tuple[bool, float]:
    return erosion_nontrivial_gate(
        mean_abs_delta_m,
        elev_range_m,
        min_abs_m=FLUVIAL_CORRIDOR_MIN_MEAN_ABS_DELTA_M,
        min_frac_of_range=FLUVIAL_CORRIDOR_MIN_FRAC_OF_RANGE,
    )


def process_delta_stats(
    deltas: ProcessDeltas,
    ocean_mask: NDArray[np.bool_],
    *,
    geomorphic_mask: NDArray[np.bool_] | None = None,
    elev_range_m: float,
    elev_before_m: NDArray[np.floating] | None = None,
    elev_after_m: NDArray[np.floating] | None = None,
) -> dict[str, float | bool]:
    land = ~np.asarray(ocean_mask, dtype=bool)
    hillslope = deltas.thermal_or_hillslope_delta_m + deltas.first_fluvial_delta_m
    hillslope_mean = domain_mean_abs_delta(hillslope, land, ocean_mask)
    conditioning_mean = domain_mean_abs_delta(
        deltas.conditioning_or_pit_fill_delta_m, land, ocean_mask
    )
    erosion_mean = domain_mean_abs_delta(deltas.total_erosion_delta_m, land, ocean_mask)
    corridor_mean = 0.0
    if geomorphic_mask is not None and np.any(geomorphic_mask):
        corridor_mean = domain_mean_abs_delta(
            deltas.final_stream_power_delta_m,
            geomorphic_mask,
            ocean_mask,
        )
    hillslope_ok, hillslope_required = hillslope_erosion_gate(
        hillslope_mean, elev_range_m
    )
    fluvial_ok, fluvial_required = fluvial_corridor_erosion_gate(
        corridor_mean, elev_range_m
    )
    # Component identity: erosion + conditioning = total DEM adjustment.
    adj = deltas.total_dem_adjustment_m
    rebuilt = deltas.total_erosion_delta_m + deltas.conditioning_or_pit_fill_delta_m
    if np.any(land):
        max_comp_err = float(np.max(np.abs(adj[land] - rebuilt[land])))
    else:
        max_comp_err = 0.0
    dem_identity_ok = max_comp_err <= 1e-6
    dem_change_err = 0.0
    if elev_before_m is not None and elev_after_m is not None and np.any(land):
        actual = (
            np.asarray(elev_after_m, dtype=np.float64)
            - np.asarray(elev_before_m, dtype=np.float64)
        )
        dem_change_err = float(np.max(np.abs(actual[land] - adj[land])))
        dem_identity_ok = dem_identity_ok and dem_change_err <= 1e-6
    return {
        "hillslope_mean_abs_delta_m": hillslope_mean,
        "conditioning_mean_abs_delta_m": conditioning_mean,
        "erosion_mean_abs_delta_m": erosion_mean,
        "fluvial_corridor_mean_abs_delta_m": corridor_mean,
        "hillslope_erosion_min_mean_abs_delta_m": hillslope_required,
        "fluvial_corridor_min_mean_abs_delta_m": fluvial_required,
        "hillslope_erosion_ok": hillslope_ok,
        "fluvial_corridor_erosion_ok": fluvial_ok,
        "conditioning_separate_ok": True,
        "conditioning_excluded_from_erosion_acceptance": True,
        "erosion_delta_identity_max_abs_err_m": max(max_comp_err, dem_change_err),
        "erosion_delta_identity_ok": bool(dem_identity_ok),
    }
