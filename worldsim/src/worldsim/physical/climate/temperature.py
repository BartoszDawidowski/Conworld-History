"""Base monthly surface temperature from insolation, lapse, and inertia."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask
from worldsim.spatial.metrics import EARTH_RADIUS_KM, GridMetrics, grid_metrics


def continentality_factor(
    ocean_mask: NDArray[np.bool_],
    *,
    scale_cells: float | None = None,
    scale_km: float | None = None,
    metrics: GridMetrics | None = None,
) -> NDArray[np.float64]:
    """0 at coast/ocean → ~1 deep inland (distance into land from ocean).

    Prefer ``scale_km`` + ``metrics`` (PR-3). ``scale_cells`` remains for
    legacy call sites and tests.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    if not np.any(ocean) or not np.any(land):
        return np.zeros(ocean.shape, dtype=np.float64)

    if scale_km is not None:
        if metrics is None:
            metrics = grid_metrics(ocean.shape[1], ocean.shape[0])
        dist_km = metrics.distance_to_mask_km(ocean, connectivity=4)
        inland = np.where(land, dist_km, 0.0)
        scale = max(float(scale_km), 1e-6)
        return 1.0 - np.exp(-inland / scale)

    # Legacy cell-distance path
    dist, _, _ = cylindrical_distance_to_mask(ocean)
    inland = np.where(land, dist, 0.0)
    cells = float(scale_cells if scale_cells is not None else 24.0)
    return 1.0 - np.exp(-inland / max(cells, 1e-6))


def equilibrium_temperature_c(
    insolation: NDArray[np.floating],
    *,
    latitude_rad: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    lapse_rate_c_per_km: float = 6.5,
    base_temp_c: float = 15.0,
    insolation_scale_c: float = 45.0,
) -> NDArray[np.float64]:
    """Instantaneous equilibrium temperature before thermal inertia (°C).

    Shape: ``insolation`` is ``[months, y, x]``; returns same shape.
    Owner: climate (includes lapse from the elevation field passed in).
    """
    insol = np.asarray(insolation, dtype=np.float64)
    lat = np.asarray(latitude_rad, dtype=np.float64)
    elev_km = np.asarray(elevation_m, dtype=np.float64) / 1000.0
    ocean = np.asarray(ocean_mask, dtype=np.bool_)

    lat_term = -18.0 * (np.sin(lat) ** 2)
    elev_term = -lapse_rate_c_per_km * np.maximum(elev_km, 0.0)
    ocean_bias = np.where(ocean, 1.5, 0.0)

    spatial = lat_term + elev_term + ocean_bias
    t_eq = base_temp_c + insolation_scale_c * (insol - 0.30) + spatial[np.newaxis, :, :]

    cold = t_eq < -5.0
    land = ~ocean
    albedo_extra = np.where(cold & land[np.newaxis, :, :], -4.0, 0.0)
    return t_eq + albedo_extra


def apply_periodic_thermal_inertia(
    t_eq: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    continentality: NDArray[np.floating],
    *,
    tau_land_months: float = 0.55,
    tau_ocean_months: float = 2.8,
    continentality_tau_factor: float = 0.55,
    spinup_years: int = 4,
    closure_tol_c: float = 1e-4,
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """First-order periodic thermal reservoir (PR-3).

    ``T[m] = T[m-1] + alpha * (T_eq[m] - T[m-1])``
    ``alpha = 1 - exp(-dt / tau)`` with ``dt = 1`` month.

    Ocean uses a longer ``tau`` (weaker amplitude, seasonal lag). Inland land
    shortens ``tau`` with continentality. Spin-up runs until Jan→Dec closure or
    ``spinup_years`` is exhausted — no arbitrary dry January initial state in
    the reported climatology (last converged year is kept).
    """
    te = np.asarray(t_eq, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    cont = np.asarray(continentality, dtype=np.float64)
    n = int(te.shape[0])
    if n < 1:
        raise ValueError("t_eq must have at least one month")

    tau_land = float(tau_land_months) * (
        1.0 - float(continentality_tau_factor) * cont
    )
    tau_land = np.maximum(tau_land, 0.05)
    tau = np.where(ocean, float(tau_ocean_months), tau_land)
    alpha = 1.0 - np.exp(-1.0 / tau)

    # Warm start: annual mean equilibrium (not January = 0 / first month alone).
    t = te.mean(axis=0).astype(np.float64).copy()
    years = max(int(spinup_years), 1)
    closure = float("inf")
    out = np.empty_like(te)

    for _year in range(years):
        t_start = t.copy()
        for m in range(n):
            t = t + alpha * (te[m] - t)
            out[m] = t
        closure = float(np.max(np.abs(t - t_start)))
        if closure <= float(closure_tol_c):
            break

    diag = {
        "thermal_inertia": "periodic_first_order_v1",
        "tau_land_months": float(tau_land_months),
        "tau_ocean_months": float(tau_ocean_months),
        "continentality_tau_factor": float(continentality_tau_factor),
        "spinup_years": years,
        "closure_max_abs_c": closure,
        "periodic_closure_ok": bool(closure <= float(closure_tol_c) * 10.0),
    }
    return out, diag


def apply_thermal_inertia(
    t_eq: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    continentality: NDArray[np.floating],
    *,
    land_memory: float = 0.20,
    ocean_memory: float = 0.72,
    tau_land_months: float | None = None,
    tau_ocean_months: float | None = None,
) -> NDArray[np.float64]:
    """Thermal inertia. Canonical path is periodic first-order (PR-3).

    ``land_memory`` / ``ocean_memory`` are accepted for API compatibility but
    ignored when ``tau_*`` are used (defaults always use the periodic path).
    """
    # Map legacy memory knobs to approximate taus if explicitly provided alone.
    if tau_land_months is None:
        # memory m ≈ seasonal damping; higher m → longer tau
        tau_land_months = 0.35 + 1.2 * float(land_memory)
    if tau_ocean_months is None:
        tau_ocean_months = 0.8 + 2.5 * float(ocean_memory)
    out, _ = apply_periodic_thermal_inertia(
        t_eq,
        ocean_mask,
        continentality,
        tau_land_months=float(tau_land_months),
        tau_ocean_months=float(tau_ocean_months),
    )
    return out


def build_monthly_temperature_c(
    *,
    insolation: NDArray[np.floating],
    latitude_rad: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    lapse_rate_c_per_km: float = 6.5,
    base_temp_c: float = 15.0,
    continentality_scale_km: float | None = None,
    continentality_scale_cells: float | None = 24.0,
    metrics: GridMetrics | None = None,
    tau_land_months: float = 0.55,
    tau_ocean_months: float = 2.8,
    planet_radius_km: float = EARTH_RADIUS_KM,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], dict[str, Any]]:
    """Return ``(temperature_base_c, continentality, temperature_equilibrium_c, diag)``.

    ``temperature_base_c`` = equilibrium after periodic inertia (includes lapse
    from ``elevation_m``). SST coupling is applied later by ocean stage.
    """
    ocean = np.asarray(ocean_mask, dtype=bool)
    h, w = ocean.shape
    if metrics is None and continentality_scale_km is not None:
        metrics = grid_metrics(w, h, radius_km=planet_radius_km)

    cont = continentality_factor(
        ocean,
        scale_km=continentality_scale_km,
        scale_cells=continentality_scale_cells,
        metrics=metrics,
    )
    t_eq = equilibrium_temperature_c(
        insolation,
        latitude_rad=latitude_rad,
        elevation_m=elevation_m,
        ocean_mask=ocean,
        lapse_rate_c_per_km=lapse_rate_c_per_km,
        base_temp_c=base_temp_c,
    )
    temperature, inertia_diag = apply_periodic_thermal_inertia(
        t_eq,
        ocean,
        cont,
        tau_land_months=tau_land_months,
        tau_ocean_months=tau_ocean_months,
    )
    diag = {
        **inertia_diag,
        "lapse_owner": "climate_equilibrium",
        "lapse_rate_c_per_km": float(lapse_rate_c_per_km),
        "continentality_scale_km": (
            float(continentality_scale_km)
            if continentality_scale_km is not None
            else None
        ),
        "continentality_scale_cells": (
            float(continentality_scale_cells)
            if continentality_scale_cells is not None
            else None
        ),
        "temperature_state": "temperature_base_c",
    }
    return temperature, cont, t_eq, diag
