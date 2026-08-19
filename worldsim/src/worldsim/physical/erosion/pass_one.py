"""Climate-informed first erosion pass (Milestone 10 / Stage I / CR-9)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.gates import (
    EROSION_MIN_MEAN_ABS_DELTA_M,
    EROSION_MIN_MEAN_ABS_FRAC_OF_RANGE,
)
from worldsim.physical.erosion.process_deltas import (
    ProcessDeltas,
    accumulate_conditioning_delta,
)
from worldsim.spatial.metrics import EARTH_RADIUS_KM, GridMetrics, grid_metrics

# Cell laplacian * 0.08 matched ~1 km cells (F-21). Physical kappa = that * (1000 m)².
THERMAL_KAPPA_REF_M = 1000.0


def land_elevation_delta_stats(
    before: NDArray[np.floating],
    after: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> dict[str, float | bool | int]:
    """Land-only change stats for first-pass / stream-power acceptance."""
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    d = a - b
    if not np.any(land):
        return {
            "mean_abs_delta_land_m": 0.0,
            "median_abs_delta_land_m": 0.0,
            "p90_abs_delta_land_m": 0.0,
            "max_abs_delta_land_m": 0.0,
            "elev_range_land_m": 1.0,
            "ocean_unchanged": True,
        }
    ad = np.abs(d[land])
    elev_range = float(np.ptp(b[land]))
    elev_range = max(elev_range, 1.0)
    return {
        "mean_abs_delta_land_m": float(np.mean(ad)),
        "median_abs_delta_land_m": float(np.median(ad)),
        "p90_abs_delta_land_m": float(np.percentile(ad, 90)),
        "max_abs_delta_land_m": float(np.max(ad)),
        "elev_range_land_m": elev_range,
        "ocean_unchanged": bool(np.allclose(a[ocean], b[ocean])),
    }


def erosion_nontrivial_gate(
    mean_abs_delta_m: float,
    elev_range_m: float,
) -> tuple[bool, float]:
    """Lower bound so a metric no-op cannot pass on correlation alone."""
    required = max(
        float(EROSION_MIN_MEAN_ABS_DELTA_M),
        float(EROSION_MIN_MEAN_ABS_FRAC_OF_RANGE) * max(float(elev_range_m), 1.0),
    )
    return bool(float(mean_abs_delta_m) >= required), required


def _metrics_for(
    elevation_m: NDArray[np.floating],
    *,
    planet_radius_km: float = EARTH_RADIUS_KM,
    metrics: GridMetrics | None = None,
) -> GridMetrics:
    if metrics is not None:
        return metrics
    h, w = np.asarray(elevation_m).shape
    return grid_metrics(w, h, radius_km=float(planet_radius_km))


def slope_magnitude(
    elevation_m: NDArray[np.floating],
    *,
    cell_scale_m: float | None = None,
    planet_radius_km: float = EARTH_RADIUS_KM,
    metrics: GridMetrics | None = None,
) -> NDArray[np.float64]:
    """Metric slope (rise/run) via GridMetrics. ``cell_scale_m`` is a leftover no-op."""
    _ = cell_scale_m
    gm = _metrics_for(
        elevation_m, planet_radius_km=planet_radius_km, metrics=metrics
    )
    return gm.metric_slope(elevation_m)


def _metric_laplacian(
    elev: NDArray[np.floating],
    metrics: GridMetrics,
) -> NDArray[np.float64]:
    """∇²h in m⁻¹ (second derivative wrt metres)."""
    e = np.asarray(elev, dtype=np.float64)
    dx = np.maximum(metrics.ew_spacing_km() * 1000.0, 1.0)
    dy = np.maximum(metrics.ns_spacing_km() * 1000.0, 1.0)
    east = np.roll(e, -1, axis=1)
    west = np.roll(e, 1, axis=1)
    north = np.empty_like(e)
    south = np.empty_like(e)
    north[:-1, :] = e[1:, :]
    north[-1, :] = e[-1, :]
    south[1:, :] = e[:-1, :]
    south[0, :] = e[0, :]
    dxx = (east - 2.0 * e + west) / (dx[:, None] ** 2)
    dyy = (south - 2.0 * e + north) / (dy[:, None] ** 2)
    return dxx + dyy


def condition_micro_depressions(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    max_depth_m: float = 25.0,
    passes: int = 8,
) -> NDArray[np.float64]:
    """Fill land pits shallower than ``max_depth_m`` (CR-9 / F-21).

    Deep closed basins stay; numerical fluvial pits do not.
    """
    elev = np.asarray(elevation_m, dtype=np.float64).copy()
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    cap = float(max(max_depth_m, 0.0))
    if cap <= 0.0:
        return elev

    def _neighbors(e: NDArray[np.float64]) -> NDArray[np.float64]:
        east = np.roll(e, -1, axis=1)
        west = np.roll(e, 1, axis=1)
        north = np.empty_like(e)
        south = np.empty_like(e)
        north[:-1, :] = e[1:, :]
        north[-1, :] = e[-1, :]
        south[1:, :] = e[:-1, :]
        south[0, :] = e[0, :]
        return np.minimum(np.minimum(east, west), np.minimum(north, south))

    for _ in range(max(1, int(passes))):
        nmin = _neighbors(elev)
        depth = nmin - elev
        pits = land & (depth > 1e-6) & (depth <= cap)
        if not np.any(pits):
            break
        elev = np.where(pits, nmin, elev)
        elev = np.where(land, np.maximum(elev, 0.0), elev)
    return elev


def rock_resistance_proxy(
    *,
    orogenic_potential: NDArray[np.floating] | None,
    tectonic_activity: NDArray[np.floating] | None,
    shape: tuple[int, int],
) -> NDArray[np.float64]:
    """Higher = harder rock (less erodible). Defaults to mid resistance."""
    h, w = shape
    resistance = np.full((h, w), 0.55, dtype=np.float64)
    if orogenic_potential is not None:
        oro = np.asarray(orogenic_potential, dtype=np.float64)
        oro_n = oro / (np.max(oro) + 1e-12)
        resistance = resistance + 0.35 * oro_n
    if tectonic_activity is not None:
        act = np.asarray(tectonic_activity, dtype=np.float64)
        act_n = act / (np.max(act) + 1e-12)
        # Active uplift zones resist instantaneous smoothing of macro peaks
        resistance = resistance + 0.15 * act_n
    return np.clip(resistance, 0.15, 1.0)


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


def count_land_local_minima(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> int:
    """4-neighbour strict local minima on land (drainage pits proxy)."""
    e = np.asarray(elevation_m, dtype=np.float64)
    land = ~np.asarray(ocean_mask, dtype=np.bool_)
    east = np.roll(e, -1, axis=1)
    west = np.roll(e, 1, axis=1)
    north = np.empty_like(e)
    south = np.empty_like(e)
    north[:-1, :] = e[1:, :]
    north[-1, :] = e[-1, :]
    south[1:, :] = e[:-1, :]
    south[0, :] = e[0, :]
    minima = land & (e < east) & (e < west) & (e < north) & (e < south)
    return int(np.count_nonzero(minima))


def land_roughness(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> float:
    land = ~np.asarray(ocean_mask, dtype=np.bool_)
    if not np.any(land):
        return 0.0
    lap = _laplacian_cylindrical(elevation_m)
    return float(np.std(lap[land]))


def apply_erosion_pass_one(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    annual_precip: NDArray[np.floating],
    resistance: NDArray[np.floating],
    iterations: int = 5,
    thermal_kappa: float = 0.08,
    fluvial_k: float = 8.0,
    max_step_m: float = 25.0,
    macro_blend: float = 0.35,
    planet_radius_km: float = EARTH_RADIUS_KM,
) -> tuple[NDArray[np.float64], ProcessDeltas]:
    """Return ``(dem_v1, process_deltas)`` with land-only climate-informed erosion."""
    elev0 = np.asarray(elevation_m, dtype=np.float64).copy()
    elev = elev0.copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    precip = np.maximum(np.asarray(annual_precip, dtype=np.float64), 0.0)
    if np.any(land):
        p_norm = precip / (np.percentile(precip[land], 90) + 1e-9)
    else:
        p_norm = precip
    p_norm = np.clip(p_norm, 0.0, 2.5)
    erodibility = 1.0 / np.maximum(np.asarray(resistance, dtype=np.float64), 0.15)
    gm = _metrics_for(elev, planet_radius_km=planet_radius_km)
    kappa_m2 = float(thermal_kappa) * (THERMAL_KAPPA_REF_M ** 2)
    thermal_acc = np.zeros_like(elev)
    fluvial_acc = np.zeros_like(elev)
    conditioning_acc = np.zeros_like(elev)

    def _neighbors(e: NDArray[np.float64]) -> tuple[NDArray, NDArray, NDArray, NDArray]:
        east = np.roll(e, -1, axis=1)
        west = np.roll(e, 1, axis=1)
        north = np.empty_like(e)
        south = np.empty_like(e)
        north[:-1, :] = e[1:, :]
        north[-1, :] = e[-1, :]
        south[1:, :] = e[:-1, :]
        south[0, :] = e[0, :]
        return east, west, north, south

    for _ in range(max(1, int(iterations))):
        thermal = np.clip(kappa_m2 * _metric_laplacian(elev, gm), -max_step_m, max_step_m)
        thermal = np.where(land, thermal, 0.0)
        thermal_acc += thermal
        slope = slope_magnitude(elev, metrics=gm)
        fluvial = np.clip(
            -fluvial_k * p_norm * slope * erodibility, -max_step_m, 0.0
        )
        fluvial = np.where(land, fluvial, 0.0)
        fluvial_acc += fluvial
        before = elev.copy()
        elev = elev + thermal + fluvial
        east, west, north, south = _neighbors(elev)
        nmin = np.minimum(np.minimum(east, west), np.minimum(north, south))
        elev = np.where(land & (elev < nmin), 0.5 * (elev + nmin), elev)
        conditioning_acc = accumulate_conditioning_delta(
            before, elev, conditioning_acc, land_mask=land
        )
        elev = np.where(land, np.maximum(elev, 0.0), elev0)
        elev = np.where(land, (1.0 - macro_blend) * elev + macro_blend * elev0, elev0)

    elev = np.where(ocean, elev0, elev)
    elev = np.where(land, np.maximum(elev, 0.0), elev)
    for _ in range(2):
        before = elev.copy()
        east, west, north, south = _neighbors(elev)
        nmin = np.minimum(np.minimum(east, west), np.minimum(north, south))
        elev = np.where(land & (elev + 1e-6 < nmin), nmin, elev)
        elev = np.where(land, np.maximum(elev, 0.0), elev0)
        conditioning_acc = accumulate_conditioning_delta(
            before, elev, conditioning_acc, land_mask=land
        )

    deltas = ProcessDeltas.zeros(elev.shape)
    deltas.merge_first_pass(
        thermal=thermal_acc,
        first_fluvial=fluvial_acc,
        conditioning=conditioning_acc,
    )
    return elev, deltas
