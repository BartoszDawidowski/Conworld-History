"""Physical channel mask and perennial / seasonal / wadi states (CR-7 / C2)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

CHANNEL_NONE = 0
CHANNEL_WADI = 1
CHANNEL_SEASONAL = 2
CHANNEL_PERENNIAL = 3

CHANNEL_STATE_NAME = {
    CHANNEL_NONE: "none",
    CHANNEL_WADI: "wadi",
    CHANNEL_SEASONAL: "seasonal",
    CHANNEL_PERENNIAL: "perennial",
}


def effective_channel_min_cells(
    *,
    cell_area_km2: float,
    river_min_catchment_km2: float | None,
    river_min_accumulation_cells: int,
) -> tuple[int, dict[str, Any]]:
    """Physical catchment floor in cells (addendum §5.2).

    ``effective_min_cells = max(ceil(km² / cell_area), accumulation_cells)``.
    A catchment smaller than one cell is still representable as one cell, but
    diagnostics must report that the km² floor is below grid resolution.
    """
    area = max(float(cell_area_km2), 1e-12)
    acc_floor = max(int(river_min_accumulation_cells), 1)
    catchment_km2: float | None
    from_area = 1
    smaller_than_cell = False
    if river_min_catchment_km2 is not None and float(river_min_catchment_km2) > 0.0:
        catchment_km2 = float(river_min_catchment_km2)
        from_area = max(1, int(math.ceil(catchment_km2 / area)))
        smaller_than_cell = catchment_km2 < area
    else:
        catchment_km2 = None
    effective = max(from_area, acc_floor)
    return effective, {
        "river_min_catchment_km2": catchment_km2,
        "cell_area_km2": float(area),
        "river_min_accumulation_cells": acc_floor,
        "catchment_cells_from_km2": int(from_area),
        "effective_min_cells": int(effective),
        "catchment_smaller_than_cell": bool(smaller_than_cell),
    }


def river_water_fraction(
    channel_mask: NDArray[np.bool_],
    channel_length_km: NDArray[np.floating],
    *,
    cell_area_km2: float,
    width_m: NDArray[np.floating] | float,
) -> NDArray[np.float64]:
    """Fractional river-water area in each cell (width × length / cell area)."""
    mask = np.asarray(channel_mask, dtype=np.bool_)
    length = np.maximum(np.asarray(channel_length_km, dtype=np.float64), 0.0)
    width = np.maximum(np.asarray(width_m, dtype=np.float64), 0.0)
    water_km2 = (width / 1000.0) * length
    frac = water_km2 / max(float(cell_area_km2), 1e-12)
    return np.where(mask, np.clip(frac, 0.0, 1.0), 0.0)


def channel_width_m_from_discharge(
    discharge_m3s: NDArray[np.floating],
    channel_mask: NDArray[np.bool_],
    *,
    coeff: float = 8.0,
    max_width_m: float = 400.0,
) -> NDArray[np.float64]:
    """Reduced-order width from effective Q; dry channels contribute no area."""
    q = np.maximum(np.asarray(discharge_m3s, dtype=np.float64), 0.0)
    width = np.clip(float(coeff) * np.sqrt(q), 0.0, float(max_width_m))
    return np.where(np.asarray(channel_mask, dtype=np.bool_), width, 0.0)


def physical_channel_mask(
    flow_accumulation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    min_cells: int,
) -> NDArray[np.bool_]:
    """Catchment-floor network (no display quantile)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    acc = np.asarray(flow_accumulation, dtype=np.float64)
    return (~ocean) & (acc >= float(max(int(min_cells), 1)))


def display_channel_candidates(
    physical_mask: NDArray[np.bool_],
    flow_accumulation: NDArray[np.floating],
    *,
    fraction: float,
) -> NDArray[np.bool_]:
    """LOD subset of the physical network (annex §11.5: quantile after floor)."""
    physical = np.asarray(physical_mask, dtype=np.bool_)
    acc = np.asarray(flow_accumulation, dtype=np.float64)
    if not np.any(physical):
        return np.zeros(physical.shape, dtype=bool)
    frac = float(np.clip(fraction, 0.0, 1.0))
    if frac >= 1.0:
        return physical.copy()
    samples = acc[physical]
    thr = float(np.quantile(samples, 1.0 - frac)) if samples.size else 0.0
    return physical & (acc >= thr)


def classify_channel_states(
    monthly_q_m3s: NDArray[np.floating],
    network_mask: NDArray[np.bool_],
    *,
    q_min_m3s: float = 0.05,
    perennial_min_months: int = 8,
    seasonal_min_months: int = 3,
) -> tuple[NDArray[np.uint8], dict[str, Any]]:
    """Assign wadi / seasonal / perennial on a physical or display network."""
    q = np.asarray(monthly_q_m3s, dtype=np.float64)
    if q.ndim != 3:
        raise ValueError("monthly_q_m3s must be [months, y, x]")
    network = np.asarray(network_mask, dtype=np.bool_)
    floor = max(float(q_min_m3s), 0.0)
    wet = np.sum(q > floor, axis=0)
    perennial_n = max(int(perennial_min_months), 1)
    seasonal_n = max(int(seasonal_min_months), 1)
    state = np.zeros(network.shape, dtype=np.uint8)
    active = network & (np.max(q, axis=0) > floor)
    state[active & (wet >= perennial_n)] = CHANNEL_PERENNIAL
    state[active & (wet >= seasonal_n) & (wet < perennial_n)] = CHANNEL_SEASONAL
    state[active & (wet < seasonal_n)] = CHANNEL_WADI
    return state, {
        "channel_q_min_m3s": floor,
        "channel_perennial_min_months": perennial_n,
        "channel_seasonal_min_months": seasonal_n,
        "channel_perennial_count": int(np.count_nonzero(state == CHANNEL_PERENNIAL)),
        "channel_seasonal_count": int(np.count_nonzero(state == CHANNEL_SEASONAL)),
        "channel_wadi_count": int(np.count_nonzero(state == CHANNEL_WADI)),
    }
