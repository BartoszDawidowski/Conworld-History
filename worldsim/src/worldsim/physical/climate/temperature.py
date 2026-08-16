"""Base monthly surface temperature from insolation, lapse, and inertia."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask


def continentality_factor(
    ocean_mask: NDArray[np.bool_],
    *,
    scale_cells: float = 24.0,
) -> NDArray[np.float64]:
    """0 at coast/ocean → ~1 deep inland (distance into land from ocean)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    if not np.any(ocean) or not np.any(land):
        return np.zeros(ocean.shape, dtype=np.float64)
    dist, _, _ = cylindrical_distance_to_mask(ocean)
    inland = np.where(land, dist, 0.0)
    return 1.0 - np.exp(-inland / max(scale_cells, 1e-6))


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
    """
    insol = np.asarray(insolation, dtype=np.float64)
    lat = np.asarray(latitude_rad, dtype=np.float64)
    elev_km = np.asarray(elevation_m, dtype=np.float64) / 1000.0
    ocean = np.asarray(ocean_mask, dtype=np.bool_)

    # Latitude baseline: tropics warm, poles cold (even with equal insolation mean).
    lat_term = -18.0 * (np.sin(lat) ** 2)
    elev_term = -lapse_rate_c_per_km * np.maximum(elev_km, 0.0)

    # Ocean slightly warmer mean (SST bias) at sea level.
    ocean_bias = np.where(ocean, 1.5, 0.0)

    # Broadcast spatial terms across months.
    months = insol.shape[0]
    spatial = lat_term + elev_term + ocean_bias
    t_eq = base_temp_c + insolation_scale_c * (insol - 0.30) + spatial[np.newaxis, :, :]

    # Crude ice/snow albedo: chill further when already cold on land.
    cold = t_eq < -5.0
    land = ~ocean
    albedo_extra = np.where(cold & land[np.newaxis, :, :], -4.0, 0.0)
    return t_eq + albedo_extra


def apply_thermal_inertia(
    t_eq: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    continentality: NDArray[np.floating],
    *,
    land_memory: float = 0.20,
    ocean_memory: float = 0.72,
) -> NDArray[np.float64]:
    """Blend monthly equilibrium temps with annual mean (land vs ocean inertia).

    Higher memory → weaker seasonal amplitude (oceans). Continentality increases
    land seasonal swing inland.
    """
    te = np.asarray(t_eq, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    cont = np.asarray(continentality, dtype=np.float64)
    annual = te.mean(axis=0)

    # Land memory decreases inland (more continental / reactive).
    land_mem = land_memory * (1.0 - 0.55 * cont)
    mem = np.where(ocean, ocean_memory, land_mem)

    # T = (1-m)*T_eq + m*annual  → seasonal anomaly damped by m
    return (1.0 - mem)[np.newaxis, :, :] * te + mem[np.newaxis, :, :] * annual[np.newaxis, :, :]


def build_monthly_temperature_c(
    *,
    insolation: NDArray[np.floating],
    latitude_rad: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    lapse_rate_c_per_km: float = 6.5,
    base_temp_c: float = 15.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(temperature_c[12,y,x], continentality[y,x])``."""
    cont = continentality_factor(ocean_mask)
    t_eq = equilibrium_temperature_c(
        insolation,
        latitude_rad=latitude_rad,
        elevation_m=elevation_m,
        ocean_mask=ocean_mask,
        lapse_rate_c_per_km=lapse_rate_c_per_km,
        base_temp_c=base_temp_c,
    )
    temperature = apply_thermal_inertia(t_eq, ocean_mask, cont)
    return temperature, cont
