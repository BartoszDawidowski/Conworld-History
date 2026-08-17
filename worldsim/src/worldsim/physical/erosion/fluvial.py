"""Fluvial (stream-power) second erosion pass (Milestone 13)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.metrics import EARTH_RADIUS_KM

from worldsim.physical.erosion.pass_one import (
    THERMAL_KAPPA_REF_M,
    _metric_laplacian,
    _metrics_for,
    condition_micro_depressions,
    slope_magnitude,
)


def river_influence_mask(
    river_mask: NDArray[np.bool_],
    *,
    halo: int = 2,
) -> NDArray[np.float64]:
    """1 on rivers, decaying weight in a small halo (floodplain)."""
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


def apply_fluvial_erosion(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    river_mask: NDArray[np.bool_],
    discharge_proxy: NDArray[np.floating],
    resistance: NDArray[np.floating],
    iterations: int = 4,
    stream_power_k: float = 12.0,
    max_step_m: float = 30.0,
    macro_blend: float = 0.40,
    deposit_frac: float = 0.25,
    planet_radius_km: float = EARTH_RADIUS_KM,
    micro_fill_max_depth_m: float = 25.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Incise along rivers; deposit a fraction on nearby low slopes.

    Returns ``(elevation_v2, delta_m)``. Ocean bathymetry is unchanged.
    After incision, shallow numerical pits are filled (CR-9 / F-21).
    """
    elev0 = np.asarray(elevation_m, dtype=np.float64).copy()
    elev = elev0.copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    riv_w = river_influence_mask(river_mask, halo=2)
    q = np.asarray(discharge_proxy, dtype=np.float64)
    q = np.where(land, np.maximum(q, 0.0), 0.0)
    if np.any(land & (q > 0)):
        q_norm = q / (np.percentile(q[land & (q > 0)], 90) + 1e-9)
    else:
        q_norm = q
    q_norm = np.clip(q_norm, 0.0, 3.0)
    erodibility = 1.0 / np.maximum(np.asarray(resistance, dtype=np.float64), 0.15)
    gm = _metrics_for(elev, planet_radius_km=planet_radius_km)
    kappa_m2 = 0.04 * (THERMAL_KAPPA_REF_M ** 2)

    for _ in range(max(1, int(iterations))):
        slope = slope_magnitude(elev, metrics=gm)
        incision = (
            -stream_power_k
            * (q_norm**0.5)
            * (slope**0.8)
            * erodibility
            * riv_w
        )
        incision = np.clip(incision, -max_step_m, 0.0)
        incision = np.where(land, incision, 0.0)

        lap = _metric_laplacian(elev, gm)
        thermal = np.clip(kappa_m2 * lap, -0.5 * max_step_m, 0.5 * max_step_m)
        thermal = np.where(land, thermal, 0.0)

        elev = elev + incision + thermal

        removed = np.where(incision < 0.0, -incision, 0.0)
        mass = float(removed.sum())
        if mass > 0.0 and np.any(land):
            low = land & (slope < np.percentile(slope[land], 35)) & (riv_w > 0.2)
            if np.any(low):
                deposit = np.zeros_like(elev)
                deposit[low] = deposit_frac * mass / float(np.count_nonzero(low))
                deposit = np.clip(deposit, 0.0, max_step_m)
                elev = elev + deposit

        elev = np.where(land, np.maximum(elev, 0.0), elev0)
        elev = np.where(land, (1.0 - macro_blend) * elev + macro_blend * elev0, elev0)

    elev = np.where(ocean, elev0, elev)
    elev = np.where(land, np.maximum(elev, 0.0), elev)
    elev = condition_micro_depressions(
        elev, ocean, max_depth_m=float(micro_fill_max_depth_m)
    )
    elev = np.where(ocean, elev0, elev)
    return elev, elev - elev0
