"""River mask, discharge proxy, and lake detection (Milestone 11 / Plan B7)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.terrain.waterbodies import label_water_bodies

# ArcGIS D8 → (dr, dc); E–W wraps at caller.
_D8_DELTAS: dict[int, tuple[int, int]] = {
    1: (0, 1),
    2: (1, 1),
    4: (1, 0),
    8: (1, -1),
    16: (0, -1),
    32: (-1, -1),
    64: (-1, 0),
    128: (-1, 1),
}


def river_mask_from_accumulation(
    flow_accumulation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    fraction: float = 0.02,
    min_cells: int = 8,
) -> NDArray[np.bool_]:
    """Cells with high upstream area (land only)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    acc = np.asarray(flow_accumulation, dtype=np.float64)
    land = ~ocean
    if not np.any(land):
        return np.zeros(acc.shape, dtype=bool)
    thr = float(np.quantile(acc[land], 1.0 - fraction))
    thr = max(thr, float(min_cells))
    return land & (acc >= thr)


def _land_quantile(values: NDArray[np.floating], land: NDArray[np.bool_], q: float) -> float:
    samples = np.asarray(values, dtype=np.float64)[land]
    if samples.size == 0:
        return 0.0
    q = float(np.clip(q, 0.0, 1.0))
    return float(np.quantile(samples, q))


def propagate_downstream_on_mask(
    seeds: NDArray[np.bool_],
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
    *,
    limit_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.bool_]:
    """Mark every ``limit_mask`` cell reachable by following D8 from ``seeds``."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    d8 = np.asarray(flow_direction, dtype=np.uint8)
    h, w = ocean.shape
    limit = (
        np.asarray(limit_mask, dtype=np.bool_)
        if limit_mask is not None
        else (~ocean)
    )
    kept = np.asarray(seeds, dtype=np.bool_) & limit & ~ocean
    stack = list(map(tuple, np.argwhere(kept)))
    while stack:
        r, c = stack.pop()
        code = int(d8[r, c])
        if code not in _D8_DELTAS:
            continue
        dr, dc = _D8_DELTAS[code]
        nr, nc = int(r + dr), int(c + dc) % w
        if nr < 0 or nr >= h or ocean[nr, nc]:
            continue
        if not limit[nr, nc] or kept[nr, nc]:
            continue
        kept[nr, nc] = True
        stack.append((nr, nc))
    return kept


def gate_river_mask_by_discharge(
    candidate_mask: NDArray[np.bool_],
    discharge_proxy: NDArray[np.floating],
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
    *,
    candidate_quantile: float = 0.50,
    min_effective_discharge: float | None = None,
    inherit_downstream: bool = False,
) -> tuple[NDArray[np.bool_], dict[str, Any]]:
    """Keep river candidates with sufficient effective Q (PR-6).

    Default: **no** downstream inheritance — cells with Q below the physical
    threshold stay dry even if a wet seed exists upstream (wadi extinction).
    Nil-like corridors survive only where effective Q remains above threshold.

    ``inherit_downstream=True`` restores the legacy Plan B7 behaviour (tests /
    display experiments only).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    candidate = np.asarray(candidate_mask, dtype=np.bool_) & ~ocean
    q = np.asarray(discharge_proxy, dtype=np.float64)
    before = int(np.count_nonzero(candidate))
    if before == 0:
        return candidate.copy(), {
            "river_cells_before_gate": before,
            "river_cells_after_gate": before,
            "river_discharge_threshold": 0.0,
            "river_seed_cells": 0,
            "river_gate_candidate_quantile": float(candidate_quantile),
            "river_inherit_downstream": bool(inherit_downstream),
        }
    if min_effective_discharge is not None:
        thr = max(float(min_effective_discharge), 0.0)
    else:
        thr = max(_land_quantile(q, candidate, candidate_quantile), 1e-9)
    seeds = candidate & (q >= thr)
    if inherit_downstream:
        gated = propagate_downstream_on_mask(
            seeds, flow_direction, ocean, limit_mask=candidate
        )
        gated |= seeds
    else:
        gated = seeds
    after = int(np.count_nonzero(gated))
    return gated, {
        "river_cells_before_gate": before,
        "river_cells_after_gate": after,
        "river_discharge_threshold": thr,
        "river_seed_cells": int(np.count_nonzero(seeds)),
        "river_gate_candidate_quantile": float(candidate_quantile),
        "river_inherit_downstream": bool(inherit_downstream),
        "river_min_effective_discharge": (
            float(min_effective_discharge)
            if min_effective_discharge is not None
            else None
        ),
    }


def lake_mask_from_fill(
    elevation_m: NDArray[np.floating],
    dem_conditioned_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    min_depth_m: float = 2.0,
    min_cells: int = 4,
) -> tuple[NDArray[np.bool_], NDArray[np.int32], int]:
    """Lakes ≈ depressions filled during DEM conditioning (depth ≥ threshold)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    elev = np.asarray(elevation_m, dtype=np.float64)
    filled = np.asarray(dem_conditioned_m, dtype=np.float64)
    depth = np.where(ocean, 0.0, filled - elev)
    raw = (~ocean) & (depth >= min_depth_m)
    if not np.any(raw):
        return raw, np.zeros(elev.shape, dtype=np.int32), 0
    labels, count = label_water_bodies(raw)
    keep = np.zeros(elev.shape, dtype=bool)
    for lid in range(1, count + 1):
        mask = labels == lid
        if int(np.count_nonzero(mask)) >= min_cells:
            keep |= mask
        else:
            labels[mask] = 0
    lake_id = np.zeros(elev.shape, dtype=np.int32)
    n = 0
    for lid in np.unique(labels):
        if lid <= 0:
            continue
        n += 1
        lake_id[labels == lid] = n
    return keep, lake_id, n


def _lake_touches_river(
    body: NDArray[np.bool_],
    river_mask: NDArray[np.bool_],
) -> bool:
    """True if lake body overlaps a river cell or a 4-neighbour (E–W wrap)."""
    riv = np.asarray(river_mask, dtype=np.bool_)
    if np.any(body & riv):
        return True
    h, w = body.shape
    rows, cols = np.where(body)
    for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, (c + dc) % w
            if 0 <= nr < h and riv[nr, nc]:
                return True
    return False


def gate_lakes_by_water_supply(
    lake_mask: NDArray[np.bool_],
    lake_id: NDArray[np.integer],
    annual_precip: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    river_mask: NDArray[np.bool_] | None = None,
    discharge_effective: NDArray[np.floating] | None = None,
    temperature_annual_c: NDArray[np.floating] | None = None,
    precip_land_quantile: float = 0.70,
    arid_precip_land_quantile: float = 0.45,
    lake_min_mean_temp_c: float = 1.0,
    inflow_land_quantile: float = 0.75,
) -> tuple[NDArray[np.bool_], NDArray[np.int32], int, dict[str, float | int]]:
    """Keep fill-depth lakes that are liquid and climate-plausible.

    - Drop polar / ice-sheet depressions (mean annual T below ``lake_min_mean_temp_c``).
    - Rain-fed: local mean precip ≥ land precip quantile.
    - River-fed: touches gated ``river_mask`` and either local precip is not arid
      **or** effective discharge on the body is high (distant Nil-like feed).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    lakes = np.asarray(lake_mask, dtype=np.bool_) & ~ocean
    ids = np.asarray(lake_id, dtype=np.int32)
    precip = np.asarray(annual_precip, dtype=np.float64)
    land = ~ocean
    riv = (
        np.asarray(river_mask, dtype=np.bool_) & ~ocean
        if river_mask is not None
        else None
    )
    q_eff = (
        np.asarray(discharge_effective, dtype=np.float64)
        if discharge_effective is not None
        else None
    )
    temp = (
        np.asarray(temperature_annual_c, dtype=np.float64)
        if temperature_annual_c is not None
        else None
    )
    before_cells = int(np.count_nonzero(lakes))
    before_count = int(len(np.unique(ids[ids > 0])))
    empty_diag: dict[str, float | int] = {
        "lake_cells_before_gate": before_cells,
        "lake_cells_after_gate": 0,
        "lake_count_before_gate": before_count,
        "lake_count_after_gate": 0,
        "lake_precip_threshold": 0.0,
        "lake_arid_precip_threshold": 0.0,
        "lake_inflow_q_threshold": 0.0,
        "lake_min_mean_temp_c": float(lake_min_mean_temp_c),
        "lake_dropped_cold": 0,
        "lake_dropped_arid": 0,
        "lake_kept_rain": 0,
        "lake_kept_river": 0,
        "lake_kept_distant": 0,
    }
    if before_cells == 0 or not np.any(land):
        empty = np.zeros(lakes.shape, dtype=bool)
        return empty, np.zeros(lakes.shape, dtype=np.int32), 0, empty_diag

    precip_thr = _land_quantile(precip, land, precip_land_quantile)
    arid_thr = _land_quantile(precip, land, arid_precip_land_quantile)
    q_thr = (
        max(_land_quantile(q_eff, land, inflow_land_quantile), 1e-9)
        if q_eff is not None
        else 0.0
    )
    keep = np.zeros(lakes.shape, dtype=bool)
    dropped_cold = 0
    dropped_arid = 0
    kept_rain = 0
    kept_river = 0
    kept_distant = 0
    for lid in np.unique(ids):
        lid_i = int(lid)
        if lid_i <= 0:
            continue
        body = ids == lid_i
        if not np.any(body):
            continue
        if temp is not None and float(np.mean(temp[body])) < lake_min_mean_temp_c:
            dropped_cold += 1
            continue
        local_p = float(np.mean(precip[body]))
        if local_p >= precip_thr:
            keep |= body
            kept_rain += 1
            continue
        touch = riv is not None and _lake_touches_river(body, riv)
        body_q = float(np.max(q_eff[body])) if q_eff is not None else 0.0
        if touch and local_p >= arid_thr:
            keep |= body
            kept_river += 1
            continue
        if touch and body_q >= q_thr:
            keep |= body
            kept_distant += 1
            continue
        dropped_arid += 1

    new_id = np.zeros(lakes.shape, dtype=np.int32)
    n = 0
    for lid in np.unique(ids):
        lid_i = int(lid)
        if lid_i <= 0:
            continue
        body = keep & (ids == lid_i)
        if not np.any(body):
            continue
        n += 1
        new_id[body] = n
    after_cells = int(np.count_nonzero(keep))
    return keep, new_id, n, {
        "lake_cells_before_gate": before_cells,
        "lake_cells_after_gate": after_cells,
        "lake_count_before_gate": before_count,
        "lake_count_after_gate": n,
        "lake_precip_threshold": precip_thr,
        "lake_arid_precip_threshold": arid_thr,
        "lake_inflow_q_threshold": q_thr,
        "lake_min_mean_temp_c": float(lake_min_mean_temp_c),
        "lake_dropped_cold": dropped_cold,
        "lake_dropped_arid": dropped_arid,
        "lake_kept_rain": kept_rain,
        "lake_kept_river": kept_river,
        "lake_kept_distant": kept_distant,
    }
