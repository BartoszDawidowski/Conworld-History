"""Stage G — reduced ocean circulation (Milestone 8).

Basin-constrained monthly currents from wind stress, Coriolis/Ekman,
boundary currents and equatorial flow. Currents MUST NOT cross land.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.terrain.waterbodies import label_water_bodies, ocean_basin_ids
from worldsim.spatial.metrics import EARTH_RADIUS_KM, GridMetrics, grid_metrics


def basin_ids_on_mask(ocean_mask: NDArray[np.bool_]) -> NDArray[np.int32]:
    """Label connected ocean basins on the climate-resolution mask."""
    bodies, _ = label_water_bodies(ocean_mask)
    return ocean_basin_ids(bodies, min_fraction=0.01)


def western_eastern_boundary_masks(
    ocean_mask: NDArray[np.bool_],
    *,
    width_cells: int | None = None,
    width_km: float | None = None,
    metrics: GridMetrics | None = None,
    planet_radius_km: float = EARTH_RADIUS_KM,
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """Ocean strips adjacent to land on the west / east (cylindrical).

    Prefer ``width_km`` + metrics (PR-3). ``width_cells`` remains for legacy.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    if width_km is not None:
        if metrics is None:
            metrics = grid_metrics(w, h, radius_km=planet_radius_km)
        cells = metrics.cells_from_km_ew(float(width_km), metrics.height // 2)
        n_cells = max(1, int(round(cells)))
    else:
        n_cells = max(1, int(width_cells if width_cells is not None else 3))

    western = np.zeros(ocean.shape, dtype=np.bool_)
    eastern = np.zeros(ocean.shape, dtype=np.bool_)
    # Seed: ocean cell with land immediately west / east
    western |= ocean & ~np.roll(ocean, 1, axis=1)
    eastern |= ocean & ~np.roll(ocean, -1, axis=1)
    # Grow into the basin (eastward from west coast, westward from east)
    for _ in range(max(0, n_cells - 1)):
        western |= ocean & np.roll(western, -1, axis=1)
        eastern |= ocean & np.roll(eastern, 1, axis=1)
    # Prefer western label if both (narrow seas)
    eastern &= ~western
    return western, eastern


def _smooth_ocean_field(
    field: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    passes: int = 1,
) -> NDArray[np.float64]:
    """Neighbor average that ignores land (keeps zeros on land)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    out = np.asarray(field, dtype=np.float64).copy()
    out[~ocean] = 0.0
    for _ in range(passes):
        acc = np.zeros_like(out)
        wsum = np.zeros_like(out)
        for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)):
            if di == 0:
                shifted = out
                mask = ocean
                if dj != 0:
                    shifted = np.roll(out, -dj, axis=0)
                    mask = np.roll(ocean, -dj, axis=0)
                    if dj > 0:
                        shifted[-dj:, :] = 0.0
                        mask[-dj:, :] = False
                    else:
                        shifted[:-dj, :] = 0.0
                        mask[:-dj, :] = False
            else:
                shifted = np.roll(out, -di, axis=1)
                mask = np.roll(ocean, -di, axis=1)
            acc += np.where(mask, shifted, 0.0)
            wsum += mask.astype(np.float64)
        nxt = np.divide(acc, wsum, out=np.zeros_like(acc), where=wsum > 0)
        nxt[~ocean] = 0.0
        out = nxt
    return out


def currents_for_month(
    *,
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    latitude_deg: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    basin_id: NDArray[np.integer],
    western: NDArray[np.bool_],
    eastern: NDArray[np.bool_],
    depth_m: NDArray[np.floating] | None = None,
    wind_to_current: float = 0.035,
    ekman_frac: float = 0.55,
    equatorial_speed: float = 0.45,
    wbc_speed: float = 0.85,
    ebc_speed: float = 0.45,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """One month of surface currents (m/s proxy). Zero on land / tiny basins."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    active = ocean & (np.asarray(basin_id) > 0)
    lat = np.asarray(latitude_deg, dtype=np.float64)
    lat_r = np.radians(lat)
    wu = np.asarray(wind_u, dtype=np.float64)
    wv = np.asarray(wind_v, dtype=np.float64)

    # Direct wind drag + Ekman (NH: transport to the right of wind)
    fsign = np.sign(np.sin(lat_r))
    fsign = np.where(fsign == 0.0, 1.0, fsign)
    u_drag = wind_to_current * (1.0 - ekman_frac) * wu
    v_drag = wind_to_current * (1.0 - ekman_frac) * wv
    u_ek = wind_to_current * ekman_frac * fsign * wv
    v_ek = -wind_to_current * ekman_frac * fsign * wu

    # Equatorial currents: westward under trades
    eq_w = np.exp(-0.5 * (lat / 8.0) ** 2)
    u_eq = -equatorial_speed * eq_w

    # Subtropical gyre boundary currents
    abs_lat = np.abs(lat)
    subtrop = np.clip((abs_lat - 12.0) / 8.0, 0.0, 1.0) * np.clip(
        (42.0 - abs_lat) / 8.0, 0.0, 1.0
    )
    # Poleward on western boundary, equatorward on eastern
    poleward = np.sign(lat)
    poleward = np.where(poleward == 0.0, 0.0, poleward)
    v_wbc = wbc_speed * subtrop * poleward * western.astype(np.float64)
    v_ebc = -ebc_speed * subtrop * poleward * eastern.astype(np.float64)
    # Weak zonal return: westward in lower subtropics, eastward in higher
    u_gyre = 0.25 * subtrop * np.where(abs_lat < 28.0, -1.0, 0.6)

    # Polar damping
    polar = np.clip((abs_lat - 55.0) / 20.0, 0.0, 1.0)
    damp = 1.0 - 0.75 * polar

    # Shallow shelf damping (optional)
    if depth_m is not None:
        depth = np.asarray(depth_m, dtype=np.float64)
        shelf = np.clip(depth / 200.0, 0.15, 1.0)
    else:
        shelf = 1.0

    u = (u_drag + u_ek + u_eq + u_gyre) * damp * shelf
    v = (v_drag + v_ek + v_wbc + v_ebc) * damp * shelf

    u = np.where(active, u, 0.0)
    v = np.where(active, v, 0.0)
    u = _smooth_ocean_field(u, active, passes=1)
    v = _smooth_ocean_field(v, active, passes=1)
    # Hard land mask after smoothing
    u = np.where(ocean, u, 0.0)
    v = np.where(ocean, v, 0.0)
    # Non-basin lakes: keep tiny residual wind drag only, still no land cross
    lakes = ocean & ~active
    if np.any(lakes):
        u = np.where(lakes, 0.15 * wind_to_current * wu, u)
        v = np.where(lakes, 0.15 * wind_to_current * wv, v)
        u = np.where(ocean, u, 0.0)
        v = np.where(ocean, v, 0.0)
    return u, v


def build_monthly_currents(
    *,
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    latitude_deg: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating] | None = None,
    months: int | None = None,
    boundary_width_km: float | None = None,
    boundary_width_cells: int | None = None,
    metrics: GridMetrics | None = None,
    planet_radius_km: float = EARTH_RADIUS_KM,
) -> dict[str, NDArray]:
    """Return monthly ``current_u``, ``current_v`` plus basin/boundary masks."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    wu = np.asarray(wind_u, dtype=np.float64)
    wv = np.asarray(wind_v, dtype=np.float64)
    n = int(months if months is not None else wu.shape[0])
    h, w = ocean.shape
    basin = basin_ids_on_mask(ocean)
    if metrics is None and boundary_width_km is not None:
        metrics = grid_metrics(w, h, radius_km=planet_radius_km)
    western, eastern = western_eastern_boundary_masks(
        ocean,
        width_km=boundary_width_km,
        width_cells=boundary_width_cells,
        metrics=metrics,
        planet_radius_km=planet_radius_km,
    )

    depth = None
    if elevation_m is not None:
        elev = np.asarray(elevation_m, dtype=np.float64)
        depth = np.where(ocean, np.maximum(0.0, -elev), 0.0)

    current_u = np.empty((n, h, w), dtype=np.float64)
    current_v = np.empty((n, h, w), dtype=np.float64)
    for m in range(n):
        cu, cv = currents_for_month(
            wind_u=wu[m],
            wind_v=wv[m],
            latitude_deg=latitude_deg,
            ocean_mask=ocean,
            basin_id=basin,
            western=western,
            eastern=eastern,
            depth_m=depth,
        )
        current_u[m] = cu
        current_v[m] = cv

    return {
        "current_u": current_u,
        "current_v": current_v,
        "ocean_basin_id": basin,
        "western_boundary": western,
        "eastern_boundary": eastern,
    }
