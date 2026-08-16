"""SST from climate temperature + current / boundary coupling (Milestone 8 / B1)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask


def _ocean_gradient_x(
    field: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> NDArray[np.float64]:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    f = np.asarray(field, dtype=np.float64)
    # Replace land with local ocean mean proxy via masking neighbors
    right = np.roll(f, -1, axis=1)
    left = np.roll(f, 1, axis=1)
    r_ok = np.roll(ocean, -1, axis=1)
    l_ok = np.roll(ocean, 1, axis=1)
    right = np.where(r_ok, right, f)
    left = np.where(l_ok, left, f)
    g = 0.5 * (right - left)
    g[~ocean] = 0.0
    return g


def _ocean_gradient_y(
    field: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> NDArray[np.float64]:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    f = np.asarray(field, dtype=np.float64)
    g = np.zeros_like(f)
    # Interior
    up_ok = ocean[2:, :] & ocean[1:-1, :] & ocean[:-2, :]
    g[1:-1, :] = 0.5 * (f[2:, :] - f[:-2, :])
    g[1:-1, :] = np.where(up_ok, g[1:-1, :], 0.0)
    g[~ocean] = 0.0
    return g


def build_monthly_sst(
    *,
    temperature_c: NDArray[np.floating],
    current_u: NDArray[np.floating],
    current_v: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    western: NDArray[np.bool_],
    eastern: NDArray[np.bool_],
    latitude_deg: NDArray[np.floating],
    western_warm_c: float = 2.2,
    eastern_cool_c: float = 1.8,
    advection_scale: float = 0.12,
) -> NDArray[np.float64]:
    """Monthly SST (°C). Land cells are NaN."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    temp = np.asarray(temperature_c, dtype=np.float64)
    cu = np.asarray(current_u, dtype=np.float64)
    cv = np.asarray(current_v, dtype=np.float64)
    lat = np.asarray(latitude_deg, dtype=np.float64)
    n, h, w = temp.shape
    sst = np.full((n, h, w), np.nan, dtype=np.float64)

    abs_lat = np.abs(lat)
    subtrop = np.clip((abs_lat - 10.0) / 10.0, 0.0, 1.0) * np.clip(
        (45.0 - abs_lat) / 10.0, 0.0, 1.0
    )
    w_anom = western_warm_c * subtrop * western.astype(np.float64)
    e_anom = -eastern_cool_c * subtrop * eastern.astype(np.float64)

    for m in range(n):
        base = temp[m].copy()
        field = base + w_anom + e_anom
        # Advective adjustment along currents (warm water downstream)
        dtx = _ocean_gradient_x(field, ocean)
        dty = _ocean_gradient_y(field, ocean)
        adv = -advection_scale * (cu[m] * dtx + cv[m] * dty)
        # Bound advection
        adv = np.clip(adv, -3.0, 3.0)
        month = field + adv
        month[~ocean] = np.nan
        sst[m] = month
    return sst


def inland_sst_blend_weight(
    ocean_mask: NDArray[np.bool_],
    *,
    mix: float = 0.35,
    inland_decay_cells: float = 16.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int32], NDArray[np.int32]]:
    """Per-cell blend weight toward nearest-ocean SST (0 far inland).

    Coast land (distance 1) gets ``mix``; weight decays as
    ``mix * exp(-(dist-1) / inland_decay_cells)``.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    dist, nearest_i, nearest_j = cylindrical_distance_to_mask(ocean)
    land = ~ocean
    decay = max(float(inland_decay_cells), 1e-6)
    weight = np.zeros(ocean.shape, dtype=np.float64)
    inland_dist = np.maximum(dist - 1.0, 0.0)
    weight[land] = float(mix) * np.exp(-inland_dist[land] / decay)
    weight = np.where(land, weight, 0.0)
    return weight, dist, nearest_i, nearest_j


def couple_temperature_with_sst_inland(
    *,
    temperature_c: NDArray[np.floating],
    sst_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    mix: float = 0.35,
    inland_decay_cells: float = 16.0,
) -> tuple[NDArray[np.float64], dict[str, float]]:
    """Ocean ← SST; land ← base T blended toward nearest SST with inland decay.

    Replaces coast-only mixing so currents influence biomes beyond the shoreline.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    temp = np.asarray(temperature_c, dtype=np.float64)
    sst = np.asarray(sst_c, dtype=np.float64)
    n = temp.shape[0]
    weight, dist, nearest_i, nearest_j = inland_sst_blend_weight(
        ocean, mix=mix, inland_decay_cells=inland_decay_cells
    )
    land = ~ocean
    out = temp.copy()

    ni = nearest_i
    nj = nearest_j
    valid_land = land & (ni >= 0) & (nj >= 0)

    for m in range(n):
        nearest_sst = np.full(ocean.shape, np.nan, dtype=np.float64)
        if np.any(valid_land):
            nearest_sst[valid_land] = sst[m, nj[valid_land], ni[valid_land]]
        blend = valid_land & np.isfinite(nearest_sst) & (weight > 0.0)
        w = weight
        out[m] = np.where(
            blend,
            (1.0 - w) * temp[m] + w * nearest_sst,
            out[m],
        )
        out[m] = np.where(
            ocean,
            np.where(np.isfinite(sst[m]), sst[m], temp[m]),
            out[m],
        )

    delta = out - temp
    coast = land & (dist <= 1.5)
    deep = land & (dist >= max(float(inland_decay_cells), 1.0))
    diagnostics = {
        "sst_mix": float(mix),
        "inland_decay_cells": float(inland_decay_cells),
        "land_temp_delta_mean_abs": float(np.mean(np.abs(delta[:, land])))
        if np.any(land)
        else 0.0,
        "coast_temp_delta_mean_abs": float(np.mean(np.abs(delta[:, coast])))
        if np.any(coast)
        else 0.0,
        "deep_inland_temp_delta_mean_abs": float(np.mean(np.abs(delta[:, deep])))
        if np.any(deep)
        else 0.0,
        "mean_land_blend_weight": float(np.mean(weight[land])) if np.any(land) else 0.0,
    }
    return out, diagnostics


def couple_coastal_temperature(
    *,
    temperature_c: NDArray[np.floating],
    sst_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    mix: float = 0.35,
    inland_decay_cells: float = 16.0,
) -> NDArray[np.float64]:
    """Backward-compatible wrapper → inland SST coupling (Plan B1)."""
    coupled, _ = couple_temperature_with_sst_inland(
        temperature_c=temperature_c,
        sst_c=sst_c,
        ocean_mask=ocean_mask,
        mix=mix,
        inland_decay_cells=inland_decay_cells,
    )
    return coupled
