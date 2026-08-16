"""Bathymetry shaping for ocean cells (shelves, slopes, abyss, trenches, ridges)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask


def shape_bathymetry(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    coast_distance: NDArray[np.floating] | None = None,
    subduction_potential: NDArray[np.floating] | None = None,
    divergence_strength: NDArray[np.floating] | None = None,
    shelf_width_cells: float = 12.0,
    slope_width_cells: float = 18.0,
    shelf_depth_m: float = -80.0,
    abyssal_depth_m: float = -4000.0,
    trench_extra_m: float = -2500.0,
    ridge_lift_m: float = 1200.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    """Return ``(elevation_m, ocean_depth_m, shelf_mask)``.

    Land elevations are preserved. Ocean cells are reshaped into shelf/slope/
    abyssal profiles with trench/ridge tendencies from tectonic proxies.
    """
    elev = np.asarray(elevation_m, dtype=np.float64).copy()
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if coast_distance is None:
        # Distance into ocean from coastline (land mask edge).
        land = ~ocean
        if np.any(land) and np.any(ocean):
            dist_land, _, _ = cylindrical_distance_to_mask(land)
            coast_distance = np.where(ocean, dist_land, 0.0)
        else:
            coast_distance = np.zeros_like(elev)

    d = np.asarray(coast_distance, dtype=np.float64)
    shelf = ocean & (d <= shelf_width_cells)
    slope = ocean & (d > shelf_width_cells) & (d <= shelf_width_cells + slope_width_cells)
    abyss = ocean & ~(shelf | slope)

    # Base profile by distance band.
    elev[shelf] = np.minimum(elev[shelf], 0.0) * 0.05 + shelf_depth_m * (
        0.4 + 0.6 * (d[shelf] / max(shelf_width_cells, 1e-6))
    )
    # Slope: interpolate shelf → abyssal
    t = (d[slope] - shelf_width_cells) / max(slope_width_cells, 1e-6)
    elev[slope] = shelf_depth_m * (1.0 - t) + abyssal_depth_m * t
    if np.any(abyss):
        elev[abyss] = abyssal_depth_m + 0.05 * (
            elev[abyss] - float(np.mean(elev[abyss]))
        )

    if subduction_potential is not None:
        sub = np.asarray(subduction_potential, dtype=np.float64)
        sub_n = sub / (np.max(sub) + 1e-12)
        elev[ocean] = elev[ocean] + trench_extra_m * sub_n[ocean]

    if divergence_strength is not None:
        div = np.asarray(divergence_strength, dtype=np.float64)
        div_n = div / (np.max(div) + 1e-12)
        elev[ocean] = elev[ocean] + ridge_lift_m * div_n[ocean]

    # Ensure ocean stays below sea level (0 m after calibration).
    elev[ocean] = np.minimum(elev[ocean], -1.0)
    # Land stays >= 0 after calibration step that shifts sea level to 0.
    elev[~ocean] = np.maximum(elev[~ocean], 0.0)

    ocean_depth_m = np.where(ocean, -elev, 0.0)
    return elev, ocean_depth_m, shelf
