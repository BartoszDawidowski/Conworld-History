"""C9.1.4 — BiomeV2 NON_GROWING is not Growing–Moist; wetland ≠ saturated soil."""

from __future__ import annotations

import numpy as np

from worldsim.physical.ecology.biome_v2 import (
    BIOME_V2_DISPLAY_CLASSES,
    BiomeV2Class,
    ThermalRegime,
    classify_biome_v2,
)


def _balanced_precip(temp: np.ndarray, scale: float = 200.0) -> np.ndarray:
    n_m = float(temp.shape[0])
    pet_m = 58.93 * np.clip(temp, 0.0, 30.0) / n_m
    return pet_m / scale


def test_non_growing_land_is_never_growing_moist() -> None:
    h, w = 4, 6
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 2.0)  # above frost, below growing (5 °C)
    precip = np.full((12, h, w), 0.4)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=np.full((h, w), 0.9),
    )
    land = ~ocean
    assert np.all(out["growing_season_months"][land] == 0)
    assert np.all(out["thermal_regime_id"][land] == int(ThermalRegime.NON_GROWING))
    assert np.all(out["biome_v2_class"][land] != int(BiomeV2Class.GROWING_MOIST))
    assert np.all(out["biome_v2_class"][land] != int(BiomeV2Class.GROWING_DEFICIT))
    assert np.all(out["biome_v2_class"][land] != int(BiomeV2Class.WETLAND))
    assert int(out["diagnostics"]["growing_moist_zero_growing_months"]) == 0


def test_saturated_soil_is_wetland_potential_not_map_class() -> None:
    h, w = 4, 4
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 14.0)
    precip = _balanced_precip(temp) * 1.2
    soil = np.full((12, h, w), 0.9)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
    )
    assert float(out["diagnostics"]["wetland_potential_land_fraction"]) == 1.0
    assert float(out["diagnostics"]["wetland_land_fraction"]) == 0.0
    assert np.all(out["biome_v2_class"] == int(BiomeV2Class.GROWING_MOIST))


def test_true_wetland_needs_inundation_low_slope_and_water_neighbour() -> None:
    h, w = 6, 8
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 14.0)
    precip = _balanced_precip(temp) * 1.2
    soil = np.full((12, h, w), 0.9)
    frac = np.zeros((h, w))
    frac[2:4, 3:6] = 0.4
    lake = np.zeros((h, w), dtype=bool)
    lake[2, 2] = True
    river = np.zeros((h, w), dtype=bool)
    river[3, 5] = True
    slope = np.full((h, w), 0.2)
    slope[2:4, 3:6] = 0.005
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
        water_fraction=frac,
        lake_mask=lake,
        river_mask=river,
        slope=slope,
    )
    klass = out["biome_v2_class"]
    assert np.any(klass == int(BiomeV2Class.WETLAND))
    assert float(out["diagnostics"]["wetland_land_fraction"]) < 0.5
    # Arid/frost cannot be painted wetland by soil alone: freeze a corner.
    temp_f = temp.copy()
    temp_f[:, 0, :] = -8.0
    frozen = classify_biome_v2(
        temperature_c=temp_f,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
        water_fraction=frac,
        lake_mask=lake,
        river_mask=river,
        slope=slope,
    )
    assert np.all(
        frozen["biome_v2_class"][0, :] != int(BiomeV2Class.WETLAND)
    )


def test_legend_wetland_label_matches_map_class() -> None:
    assert BIOME_V2_DISPLAY_CLASSES[6]["key"] == "wetland"
    assert BIOME_V2_DISPLAY_CLASSES[6]["label"] == "Wetland"
    assert BIOME_V2_DISPLAY_CLASSES[3]["label"] == "Growing — moist"
