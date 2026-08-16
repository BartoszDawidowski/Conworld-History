"""Soil / permeability proxies (Milestone 14 / Stage M)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def build_soil_layers(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    annual_precipitation: NDArray[np.floating],
    slope: NDArray[np.floating] | None = None,
    lake_mask: NDArray[np.bool_] | None = None,
) -> dict[str, NDArray]:
    """First-order physical soil proxies (no technological assumptions)."""
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    precip = np.maximum(np.asarray(annual_precipitation, dtype=np.float64), 0.0)
    if slope is None:
        # crude slope from elev gradients
        gx = 0.5 * (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1))
        gy = np.zeros_like(elev)
        gy[1:-1, :] = 0.5 * (elev[2:, :] - elev[:-2, :])
        slope_m = np.hypot(gx, gy) / 1000.0
    else:
        slope_m = np.asarray(slope, dtype=np.float64)

    # Permeability: higher on coarse/steep uplands, lower in wet flats
    p_norm = precip / (np.percentile(precip[land], 90) + 1e-9) if np.any(land) else precip
    p_norm = np.clip(p_norm, 0.0, 2.0)
    elev_n = np.clip(elev / (np.percentile(elev[land], 90) + 1e-9), 0.0, 2.0) if np.any(land) else elev * 0.0
    slope_n = np.clip(slope_m / (np.percentile(slope_m[land], 90) + 1e-9), 0.0, 2.0) if np.any(land) else slope_m * 0.0
    permeability = np.clip(0.25 + 0.35 * elev_n + 0.30 * slope_n - 0.20 * p_norm, 0.05, 1.0)
    permeability = np.where(land, permeability, 0.0)

    # Soil depth: thicker in lowlands / wetter; thinner on steep high ground
    soil_depth = np.clip(2.5 + 1.5 * p_norm - 1.2 * slope_n - 0.8 * elev_n, 0.1, 5.0)
    soil_depth = np.where(land, soil_depth, 0.0)

    # Soil moisture proxy (relative): wet climates + low permeability retain more
    soil_moisture = np.clip(0.15 + 0.55 * p_norm * (1.1 - 0.5 * permeability), 0.0, 1.0)
    soil_moisture = np.where(land, soil_moisture, 0.0)
    if lake_mask is not None:
        lakes = np.asarray(lake_mask, dtype=np.bool_)
        soil_moisture = np.where(lakes & land, np.maximum(soil_moisture, 0.85), soil_moisture)

    # Fertility proxy: moderate moisture + depth, penalize extremes / alpine
    fertility = np.clip(
        0.2 + 0.35 * soil_depth / 5.0 + 0.35 * soil_moisture - 0.25 * np.abs(p_norm - 0.8),
        0.0,
        1.0,
    )
    fertility = np.where(land, fertility, 0.0)

    # Erosion risk: steep + wet + shallow soils
    erosion_risk = np.clip(0.15 + 0.45 * slope_n + 0.25 * p_norm - 0.20 * soil_depth / 5.0, 0.0, 1.0)
    erosion_risk = np.where(land, erosion_risk, 0.0)

    return {
        "permeability": permeability.astype(np.float64),
        "soil_depth": soil_depth.astype(np.float64),
        "soil_moisture": soil_moisture.astype(np.float64),
        "fertility_proxy": fertility.astype(np.float64),
        "erosion_risk": erosion_risk.astype(np.float64),
    }
