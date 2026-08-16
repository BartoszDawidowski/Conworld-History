"""Climate-informed first erosion pass (Milestone 10 / Stage I)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import elevation_gradients_cylindrical


def slope_magnitude(
    elevation_m: NDArray[np.floating],
    *,
    cell_scale_m: float = 1000.0,
) -> NDArray[np.float64]:
    """Dimensionless-ish slope from cylindrical elevation gradients."""
    gx, gy = elevation_gradients_cylindrical(elevation_m)
    return np.hypot(gx, gy) / max(float(cell_scale_m), 1.0)


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
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(dem_v1, erosion_delta_m)`` with land-only climate-informed erosion.

    Combines mild thermal diffusion (artefact reduction), precip×slope incision,
    and pit filling for drainage tendency. Macro-relief is anchored by blending
    back toward the original DEM each step.
    """
    elev0 = np.asarray(elevation_m, dtype=np.float64).copy()
    elev = elev0.copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    precip = np.asarray(annual_precip, dtype=np.float64)
    precip = np.maximum(precip, 0.0)
    if np.any(land):
        p_norm = precip / (np.percentile(precip[land], 90) + 1e-9)
    else:
        p_norm = precip
    p_norm = np.clip(p_norm, 0.0, 2.5)
    resist = np.asarray(resistance, dtype=np.float64)
    erodibility = 1.0 / np.maximum(resist, 0.15)

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
        # Thermal diffusion — reduces checkerboard / noise
        lap = _laplacian_cylindrical(elev)
        thermal = np.clip(thermal_kappa * lap, -max_step_m, max_step_m)

        slope = slope_magnitude(elev)
        fluvial = np.clip(
            -fluvial_k * p_norm * slope * erodibility, -max_step_m, 0.0
        )

        delta = thermal + fluvial
        delta = np.where(land, delta, 0.0)
        elev = elev + delta

        # Pit fill: raise strict land minima toward lowest neighbour
        east, west, north, south = _neighbors(elev)
        nmin = np.minimum(np.minimum(east, west), np.minimum(north, south))
        pits = land & (elev < nmin)
        elev = np.where(pits, 0.5 * (elev + nmin), elev)

        # Keep land above sea level; leave ocean unchanged
        elev = np.where(land, np.maximum(elev, 0.0), elev0)
        # Anchor macro-relief toward original DEM
        elev = np.where(land, (1.0 - macro_blend) * elev + macro_blend * elev0, elev0)

    elev = np.where(ocean, elev0, elev)
    elev = np.where(land, np.maximum(elev, 0.0), elev)
    # Final pit-fill pass without re-blending (drainage quality)
    for _ in range(2):
        east, west, north, south = _neighbors(elev)
        nmin = np.minimum(np.minimum(east, west), np.minimum(north, south))
        pits = land & (elev + 1e-6 < nmin)
        elev = np.where(pits, nmin, elev)
        elev = np.where(land, np.maximum(elev, 0.0), elev0)

    delta_m = elev - elev0
    return elev, delta_m
