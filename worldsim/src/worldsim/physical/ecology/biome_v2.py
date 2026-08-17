"""CR-9 — seasonal BiomeV2 on the climate grid (Holdridge stays annual)."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray


class BiomeV2Class(IntEnum):
    OCEAN = 0
    ICE = 1
    FROST_SEASONAL = 2
    GROWING_MOIST = 3
    GROWING_DEFICIT = 4
    ARID = 5
    WETLAND = 6


CLASS_NAMES = {int(v): v.name.lower() for v in BiomeV2Class}


def classify_biome_v2(
    *,
    temperature_c: NDArray[np.floating],
    precipitation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    soil_moisture: NDArray[np.floating] | None = None,
    precip_scale_mm: float = 200.0,
    frost_c: float = 0.0,
    growing_c: float = 5.0,
) -> dict[str, NDArray | dict[str, Any]]:
    """Seasonal fields: frost months, growing season, water deficit, soil state.

    Holdridge remains the annual diagnostic; this is a parallel climate-grid
    classification (annex CR-9).
    """
    temp = np.asarray(temperature_c, dtype=np.float64)
    precip = np.maximum(np.asarray(precipitation, dtype=np.float64), 0.0)
    ocean = np.asarray(ocean_mask, dtype=bool)
    months = int(temp.shape[0])
    n_m = float(max(months, 1))

    frost_months = np.sum(temp < float(frost_c), axis=0).astype(np.int16)
    growing_months = np.sum(temp > float(growing_c), axis=0).astype(np.int16)

    # Monthly PET proxy from Holdridge annual 58.93×biotemp, split by month.
    bio_m = np.clip(temp, 0.0, 30.0)
    pet_m = 58.93 * bio_m / n_m
    precip_mm_m = precip * float(precip_scale_mm) / n_m
    deficit_m = np.maximum(0.0, pet_m - precip_mm_m)
    water_deficit_mm = deficit_m.sum(axis=0)

    if soil_moisture is not None:
        soil = np.clip(np.asarray(soil_moisture, dtype=np.float64), 0.0, 1.0)
    else:
        soil = np.zeros(ocean.shape, dtype=np.float64)
    soil_state = np.zeros(ocean.shape, dtype=np.uint8)
    soil_state[soil >= 0.25] = 1
    soil_state[soil >= 0.50] = 2
    soil_state[soil >= 0.80] = 3
    soil_state[ocean] = 0

    klass = np.full(ocean.shape, int(BiomeV2Class.GROWING_MOIST), dtype=np.uint8)
    arid = water_deficit_mm >= np.maximum(pet_m.sum(axis=0) * 0.45, 50.0)
    klass[arid] = int(BiomeV2Class.ARID)
    deficit = (~arid) & (water_deficit_mm > 20.0)
    klass[deficit] = int(BiomeV2Class.GROWING_DEFICIT)
    seasonal_frost = (frost_months >= 1) & (frost_months < months) & (growing_months >= 1)
    klass[seasonal_frost] = int(BiomeV2Class.FROST_SEASONAL)
    ice = frost_months >= months
    klass[ice] = int(BiomeV2Class.ICE)
    wetland = (soil_state >= 3) & (growing_months >= 3) & ~ice
    klass[wetland] = int(BiomeV2Class.WETLAND)
    klass[ocean] = int(BiomeV2Class.OCEAN)

    land = ~ocean
    diag: dict[str, Any] = {
        "algorithm": "biome_v2_seasonal_cr9",
        "holdridge_role": "annual_diagnostic",
        "frost_c": float(frost_c),
        "growing_c": float(growing_c),
        "mean_frost_months_land": float(frost_months[land].mean()) if np.any(land) else 0.0,
        "mean_growing_months_land": float(growing_months[land].mean())
        if np.any(land)
        else 0.0,
        "mean_water_deficit_mm_land": float(water_deficit_mm[land].mean())
        if np.any(land)
        else 0.0,
        "class_names": {str(k): v for k, v in CLASS_NAMES.items()},
    }
    return {
        "frost_months": frost_months,
        "growing_season_months": growing_months,
        "water_deficit_mm": water_deficit_mm.astype(np.float64),
        "soil_state": soil_state,
        "biome_v2_class": klass,
        "diagnostics": diag,
    }
