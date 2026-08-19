"""Fluvial (stream-power) second erosion pass (Milestone 13 / PC4)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.metrics import EARTH_RADIUS_KM

from worldsim.physical.erosion.process_deltas import ProcessDeltas
from worldsim.physical.erosion.pass_one import (
    THERMAL_KAPPA_REF_M,
    _metric_laplacian,
    _metrics_for,
    condition_micro_depressions,
    slope_magnitude,
)


def geomorphic_corridor_weight(
    geomorphic_mask: NDArray[np.bool_],
    step_length_km: NDArray[np.floating],
    *,
    influence_km: float = 5.0,
) -> NDArray[np.float64]:
    """Metric km corridor around geomorphic channels (replaces fixed cell halo)."""
    geo = np.asarray(geomorphic_mask, dtype=np.bool_)
    steps = np.maximum(np.asarray(step_length_km, dtype=np.float64), 1e-9)
    dist = np.where(geo, 0.0, np.inf)
    cap = max(float(influence_km), 0.0)
    if cap <= 0.0 or not np.any(geo):
        return np.where(geo, 1.0, 0.0).astype(np.float64)

    def _shift(field: NDArray[np.float64], dr: int, dc: int) -> NDArray[np.float64]:
        if dr == 0 and dc != 0:
            return np.roll(field, -dc, axis=1)
        out = np.empty_like(field)
        if dr > 0:
            out[:-1, :] = field[1:, :]
            out[-1, :] = field[-1, :]
        else:
            out[1:, :] = field[:-1, :]
            out[0, :] = field[0, :]
        return out

    for _ in range(512):
        prev = dist.copy()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n_dist = _shift(dist, dr, dc)
            n_step = _shift(steps, dr, dc)
            dist = np.minimum(dist, n_dist + n_step)
        finite = np.isfinite(dist) & np.isfinite(prev)
        if not np.any(finite):
            break
        if float(np.max(np.abs(dist[finite] - prev[finite]))) < 1e-12:
            break

    weight = np.clip(1.0 - dist / cap, 0.0, 1.0)
    weight[geo] = 1.0
    return weight.astype(np.float64)


def apply_fluvial_erosion(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    geomorphic_channel_mask: NDArray[np.bool_] | None = None,
    discharge_proxy: NDArray[np.floating],
    resistance: NDArray[np.floating],
    step_length_km: NDArray[np.floating] | None = None,
    corridor_influence_km: float = 5.0,
    iterations: int = 4,
    stream_power_k: float = 12.0,
    max_step_m: float = 30.0,
    macro_blend: float = 0.40,
    deposit_frac: float = 0.25,
    planet_radius_km: float = EARTH_RADIUS_KM,
    micro_fill_max_depth_m: float = 25.0,
    river_mask: NDArray[np.bool_] | None = None,
) -> tuple[NDArray[np.float64], ProcessDeltas]:
    """Incise along the geomorphic corridor; deposit a fraction on nearby low slopes."""
    if geomorphic_channel_mask is None:
        if river_mask is None:
            raise ValueError("geomorphic_channel_mask is required")
        geomorphic_channel_mask = river_mask
    elev0 = np.asarray(elevation_m, dtype=np.float64).copy()
    elev = elev0.copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    gm = _metrics_for(elev, planet_radius_km=planet_radius_km)
    if step_length_km is None:
        d8 = np.full(elev.shape, 1, dtype=np.uint8)
        step_field = gm.d8_step_length_km_field(d8)
    else:
        step_field = np.maximum(np.asarray(step_length_km, dtype=np.float64), 1e-9)
    corridor = geomorphic_corridor_weight(
        geomorphic_channel_mask,
        step_field,
        influence_km=corridor_influence_km,
    )
    q = np.where(land, np.maximum(np.asarray(discharge_proxy, dtype=np.float64), 0.0), 0.0)
    if np.any(land & (q > 0)):
        q_norm = q / (np.percentile(q[land & (q > 0)], 90) + 1e-9)
    else:
        q_norm = q
    q_norm = np.clip(q_norm, 0.0, 3.0)
    erodibility = 1.0 / np.maximum(np.asarray(resistance, dtype=np.float64), 0.15)
    kappa_m2 = 0.04 * (THERMAL_KAPPA_REF_M ** 2)
    stream_acc = np.zeros_like(elev)

    for _ in range(max(1, int(iterations))):
        slope = slope_magnitude(elev, metrics=gm)
        incision = (
            -stream_power_k
            * (q_norm**0.5)
            * (slope**0.8)
            * erodibility
            * corridor
        )
        incision = np.clip(incision, -max_step_m, 0.0)
        incision = np.where(land, incision, 0.0)
        lap = _metric_laplacian(elev, gm)
        thermal = np.clip(kappa_m2 * lap, -0.5 * max_step_m, 0.5 * max_step_m)
        thermal = np.where(land, thermal, 0.0)
        step_delta = incision + thermal
        stream_acc += step_delta
        elev = elev + step_delta

        removed = np.where(incision < 0.0, -incision, 0.0)
        mass = float(removed.sum())
        if mass > 0.0 and np.any(land):
            low = land & (slope < np.percentile(slope[land], 35)) & (corridor > 0.2)
            if np.any(low):
                deposit = np.zeros_like(elev)
                deposit[low] = deposit_frac * mass / float(np.count_nonzero(low))
                deposit = np.clip(deposit, 0.0, max_step_m)
                stream_acc += deposit
                elev = elev + deposit

        elev = np.where(land, np.maximum(elev, 0.0), elev0)
        elev = np.where(land, (1.0 - macro_blend) * elev + macro_blend * elev0, elev0)

    elev = np.where(ocean, elev0, elev)
    elev = np.where(land, np.maximum(elev, 0.0), elev)
    before_cond = elev.copy()
    elev = condition_micro_depressions(
        elev, ocean, max_depth_m=float(micro_fill_max_depth_m)
    )
    elev = np.where(ocean, elev0, elev)
    conditioning = elev - before_cond
    deltas = ProcessDeltas.zeros(elev.shape)
    deltas.merge_final_fluvial(stream_power=stream_acc, conditioning=conditioning)
    return elev, deltas


def river_influence_mask(
    river_mask: NDArray[np.bool_],
    *,
    halo: int = 2,
) -> NDArray[np.float64]:
    """Deprecated fixed-cell halo — use ``geomorphic_corridor_weight`` instead."""
    riv = np.asarray(river_mask, dtype=np.bool_)
    w = riv.astype(np.float64)
    for _ in range(max(0, halo)):
        neigh = (
            np.roll(w, 1, axis=1)
            + np.roll(w, -1, axis=1)
            + np.pad(w[1:, :], ((0, 1), (0, 0)), mode="edge")
            + np.pad(w[:-1, :], ((1, 0), (0, 0)), mode="edge")
        )
        w = np.maximum(w, 0.45 * neigh)
    w = np.clip(w, 0.0, 1.0)
    w = np.where(riv, 1.0, w)
    return w
