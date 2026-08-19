"""CR-9 / C6 — seasonal BiomeV2 on the climate grid (Holdridge stays annual)."""

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


class ThermalRegime(IntEnum):
    OCEAN = 0
    ICE = 1
    FROST_SEASONAL = 2
    GROWING = 3
    NON_GROWING = 4


class MoistureRegime(IntEnum):
    OCEAN = 0
    ARID = 1
    DEFICIT = 2
    MOIST = 3
    WET = 4


CLASS_NAMES = {int(v): v.name.lower() for v in BiomeV2Class}
CLASS_DISPLAY_NAMES: dict[int, str] = {
    int(BiomeV2Class.OCEAN): "ocean",
    int(BiomeV2Class.ICE): "ice_climate_potential",
    int(BiomeV2Class.FROST_SEASONAL): "frost_seasonal",
    int(BiomeV2Class.GROWING_MOIST): "growing_moist",
    int(BiomeV2Class.GROWING_DEFICIT): "growing_deficit",
    int(BiomeV2Class.ARID): "arid",
    int(BiomeV2Class.WETLAND): "wetland",
}
THERMAL_NAMES = {int(v): v.name.lower() for v in ThermalRegime}
MOISTURE_NAMES = {int(v): v.name.lower() for v in MoistureRegime}

# Growing-season mean of monthly store; wetland uses this, not a last-month snapshot.
SOIL_MOISTURE_STATISTIC = "soil_moisture_growing_mean"


def soil_moisture_growing_mean(
    soil_moisture: NDArray[np.floating] | None,
    temperature_c: NDArray[np.floating],
    *,
    growing_c: float = 5.0,
    shape2d: tuple[int, int] | None = None,
) -> NDArray[np.float64]:
    """Climatological soil wetness: growing-season mean, or a provided 2-D climatology.

    A 3-D ``[months, y, x]`` field is averaged only over months with
    ``T > growing_c``. Cells with no growing month fall back to the annual mean.
    A 2-D field is treated as an already-named climatology, not as December.
    """
    temp = np.asarray(temperature_c, dtype=np.float64)
    if shape2d is None:
        shape2d = (int(temp.shape[1]), int(temp.shape[2])) if temp.ndim == 3 else temp.shape[-2:]
    h, w = int(shape2d[0]), int(shape2d[1])
    if soil_moisture is None:
        return np.zeros((h, w), dtype=np.float64)
    soil = np.clip(np.asarray(soil_moisture, dtype=np.float64), 0.0, 1.0)
    if soil.ndim == 2:
        if soil.shape != (h, w):
            raise ValueError("2-D soil_moisture must match the climate-grid shape")
        return soil
    if soil.ndim != 3:
        raise ValueError("soil_moisture must be 2-D climatology or monthly [months, y, x]")
    if soil.shape[1:] != (h, w) or soil.shape[0] != temp.shape[0]:
        raise ValueError("monthly soil_moisture must match temperature_c")
    growing = temp > float(growing_c)
    weight = growing.astype(np.float64)
    numer = np.sum(soil * weight, axis=0)
    denom = np.sum(weight, axis=0)
    annual = np.mean(soil, axis=0)
    return np.where(denom > 0.0, numer / np.maximum(denom, 1e-12), annual)


def _dilate8_ew(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """8-neighbour dilation with E–W wrap, no N–S wrap."""
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    out = np.zeros((h, w), dtype=bool)
    for dr in (-1, 0, 1):
        src = np.zeros((h, w), dtype=bool)
        if dr == 0:
            src = m
        elif dr < 0:
            src[-dr:] = m[: h + dr]
        else:
            src[: h - dr] = m[dr:]
        out |= src
        out |= np.roll(src, 1, axis=1)
        out |= np.roll(src, -1, axis=1)
    return out


def classify_biome_v2(
    *,
    temperature_c: NDArray[np.floating],
    precipitation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    soil_moisture: NDArray[np.floating] | None = None,
    precip_scale_mm: float = 200.0,
    frost_c: float = 0.0,
    growing_c: float = 5.0,
    water_fraction: NDArray[np.floating] | None = None,
    water_fraction_monthly: NDArray[np.floating] | None = None,
    lake_mask: NDArray[np.bool_] | None = None,
    river_mask: NDArray[np.bool_] | None = None,
    slope: NDArray[np.floating] | None = None,
    wetland_min_water_fraction: float = 0.10,
    wetland_max_slope: float = 0.02,
) -> dict[str, NDArray | dict[str, Any]]:
    """Seasonal fields: frost, growing season, deficit, climatological soil, axes, class.

    Holdridge remains the annual diagnostic; this is a parallel climate-grid
    classification. Display class is derived from thermal and moisture axes so a
    seven-class map does not erase seasonal frost in a dry region.
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
    # Monthly precip is already a per-month proxy; do not divide by n_m again (C0).
    precip_mm_m = precip * float(precip_scale_mm)
    deficit_m = np.maximum(0.0, pet_m - precip_mm_m)
    water_deficit_mm = deficit_m.sum(axis=0)
    precipitation_annual_mm = precip_mm_m.sum(axis=0)

    soil_gs = soil_moisture_growing_mean(
        soil_moisture,
        temp,
        growing_c=growing_c,
        shape2d=ocean.shape,
    )
    soil_state = np.zeros(ocean.shape, dtype=np.uint8)
    soil_state[soil_gs >= 0.25] = 1
    soil_state[soil_gs >= 0.50] = 2
    soil_state[soil_gs >= 0.80] = 3
    soil_state[ocean] = 0

    arid = water_deficit_mm >= np.maximum(pet_m.sum(axis=0) * 0.45, 50.0)
    deficit = (~arid) & (water_deficit_mm > 20.0)
    ice = frost_months >= months
    seasonal_frost = (frost_months >= 1) & (frost_months < months) & (growing_months >= 1)
    growing = (growing_months >= 1) & (frost_months == 0)
    wet = soil_state >= 3

    thermal = np.full(ocean.shape, int(ThermalRegime.NON_GROWING), dtype=np.uint8)
    thermal[growing] = int(ThermalRegime.GROWING)
    thermal[seasonal_frost] = int(ThermalRegime.FROST_SEASONAL)
    thermal[ice] = int(ThermalRegime.ICE)
    thermal[ocean] = int(ThermalRegime.OCEAN)

    moisture = np.full(ocean.shape, int(MoistureRegime.MOIST), dtype=np.uint8)
    moisture[arid] = int(MoistureRegime.ARID)
    moisture[deficit] = int(MoistureRegime.DEFICIT)
    moisture[wet] = int(MoistureRegime.WET)
    moisture[ocean] = int(MoistureRegime.OCEAN)

    # Never seed Growing–Moist. NON_GROWING / zero growing months stay frost.
    klass = np.full(ocean.shape, int(BiomeV2Class.FROST_SEASONAL), dtype=np.uint8)
    klass[ice] = int(BiomeV2Class.ICE)
    can_grow = (growing_months >= 1) & ~ocean & ~ice
    klass[can_grow & (moisture == int(MoistureRegime.ARID))] = int(BiomeV2Class.ARID)
    klass[can_grow & (moisture == int(MoistureRegime.DEFICIT))] = int(
        BiomeV2Class.GROWING_DEFICIT
    )
    klass[can_grow & (moisture == int(MoistureRegime.MOIST))] = int(
        BiomeV2Class.GROWING_MOIST
    )
    klass[can_grow & (moisture == int(MoistureRegime.WET))] = int(
        BiomeV2Class.GROWING_MOIST
    )
    # Seasonal frost stays visible on dry/arid land (axes, not soil paint).
    klass[thermal == int(ThermalRegime.FROST_SEASONAL)] = int(BiomeV2Class.FROST_SEASONAL)
    klass[thermal == int(ThermalRegime.NON_GROWING)] = int(BiomeV2Class.FROST_SEASONAL)
    klass[ice] = int(BiomeV2Class.ICE)

    frac = (
        np.asarray(water_fraction, dtype=np.float64)
        if water_fraction is not None and np.asarray(water_fraction).shape == ocean.shape
        else np.zeros(ocean.shape, dtype=np.float64)
    )
    if (
        water_fraction_monthly is not None
        and np.asarray(water_fraction_monthly).ndim == 3
        and np.asarray(water_fraction_monthly).shape[1:] == ocean.shape
    ):
        frac = np.maximum(frac, np.max(np.asarray(water_fraction_monthly, dtype=np.float64), axis=0))
    lakes = (
        np.asarray(lake_mask, dtype=bool)
        if lake_mask is not None and np.asarray(lake_mask).shape == ocean.shape
        else np.zeros(ocean.shape, dtype=bool)
    )
    rivers = (
        np.asarray(river_mask, dtype=bool)
        if river_mask is not None and np.asarray(river_mask).shape == ocean.shape
        else np.zeros(ocean.shape, dtype=bool)
    )
    slp = (
        np.asarray(slope, dtype=np.float64)
        if slope is not None and np.asarray(slope).shape == ocean.shape
        else np.full(ocean.shape, np.inf, dtype=np.float64)
    )
    inundated = (frac >= float(wetland_min_water_fraction)) | lakes
    near_water = _dilate8_ew(lakes | rivers)
    low_slope = slp <= float(wetland_max_slope)
    wetland_potential = wet & ~ocean
    wetland = (
        inundated
        & low_slope
        & near_water
        & (growing_months >= 3)
        & ~ice
        & ~arid
        & ~ocean
        & (thermal != int(ThermalRegime.NON_GROWING))
        & (thermal != int(ThermalRegime.FROST_SEASONAL))
        & (thermal != int(ThermalRegime.ICE))
    )
    klass[wetland] = int(BiomeV2Class.WETLAND)
    klass[ocean] = int(BiomeV2Class.OCEAN)
    growing_classes = {
        int(BiomeV2Class.GROWING_MOIST),
        int(BiomeV2Class.GROWING_DEFICIT),
    }
    bad_grow = (~ocean) & (growing_months == 0) & np.isin(klass, list(growing_classes))
    klass[bad_grow] = int(BiomeV2Class.FROST_SEASONAL)

    land = ~ocean
    legend = {str(k): v for k, v in CLASS_NAMES.items()}
    unique_classes = {int(v) for v in np.unique(klass)}
    diag: dict[str, Any] = {
        "algorithm": "biome_v2_c91_4_v1",
        "holdridge_role": "annual_diagnostic",
        "soil_moisture_statistic": SOIL_MOISTURE_STATISTIC,
        "frost_c": float(frost_c),
        "growing_c": float(growing_c),
        "mean_frost_months_land": float(frost_months[land].mean()) if np.any(land) else 0.0,
        "mean_growing_months_land": float(growing_months[land].mean())
        if np.any(land)
        else 0.0,
        "mean_water_deficit_mm_land": float(water_deficit_mm[land].mean())
        if np.any(land)
        else 0.0,
        "class_names": legend,
        "thermal_regime_names": {str(k): v for k, v in THERMAL_NAMES.items()},
        "moisture_regime_names": {str(k): v for k, v in MOISTURE_NAMES.items()},
        "legend_exact": legend == {str(i): CLASS_NAMES[i] for i in range(len(CLASS_NAMES))},
        "unique_classes_in_legend": unique_classes.issubset(set(CLASS_NAMES)),
        "soil_input_ndim": int(np.asarray(soil_moisture).ndim) if soil_moisture is not None else 0,
        "wetland_min_water_fraction": float(wetland_min_water_fraction),
        "wetland_max_slope": float(wetland_max_slope),
        "wetland_land_fraction": (
            float(np.count_nonzero(wetland) / max(int(np.count_nonzero(land)), 1))
        ),
        "wetland_potential_land_fraction": (
            float(np.count_nonzero(wetland_potential) / max(int(np.count_nonzero(land)), 1))
        ),
        "growing_moist_zero_growing_months": int(
            np.count_nonzero(
                land
                & (growing_months == 0)
                & (klass == int(BiomeV2Class.GROWING_MOIST))
            )
        ),
    }
    return {
        "frost_months": frost_months,
        "growing_season_months": growing_months,
        "water_deficit_mm": water_deficit_mm.astype(np.float64),
        "water_deficit_monthly": deficit_m.astype(np.float64),
        "precipitation_annual_mm": precipitation_annual_mm.astype(np.float64),
        "soil_moisture_growing_mean": soil_gs.astype(np.float64),
        "soil_state": soil_state,
        "thermal_regime_id": thermal,
        "moisture_regime_id": moisture,
        "biome_v2_class": klass,
        "wetland_potential": wetland_potential,
        "diagnostics": diag,
    }


# C9: Python-owned atlas palette. Godot must not invent class colours.
BIOME_V2_LEGEND_SCHEMA = "biome_v2_legend_v1"
BIOME_V2_LEGEND_TITLE = "Seasonal ecological regime (BiomeV2)"
BIOME_V2_DISPLAY_CLASSES: dict[int, dict[str, str]] = {
    0: {"key": "ocean", "label": "Ocean", "color": "#17365D"},
    1: {"key": "year_round_frost", "label": "Year-round frost", "color": "#E8F1F2"},
    2: {"key": "frost_seasonal", "label": "Seasonal frost", "color": "#8FA9B3"},
    3: {"key": "growing_moist", "label": "Growing — moist", "color": "#5E8B57"},
    4: {"key": "growing_deficit", "label": "Growing — moisture deficit", "color": "#AAA05A"},
    5: {"key": "arid", "label": "Arid", "color": "#D1A466"},
    6: {"key": "wetland", "label": "Wetland", "color": "#397A72"},
}


def biome_v2_legend() -> dict[str, Any]:
    return {
        "schema": BIOME_V2_LEGEND_SCHEMA,
        "title": BIOME_V2_LEGEND_TITLE,
        "ocean_composite_note": (
            "Ocean cells use the ordinary bathymetry background in the land-composite "
            "shader; the ocean swatch documents the class colour, not a second ocean fill."
        ),
        "classes": {str(i): dict(v) for i, v in BIOME_V2_DISPLAY_CLASSES.items()},
    }
