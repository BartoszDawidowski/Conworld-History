"""C6 — BiomeV2 climatological wetness, axes, canonical rasters/hex."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from worldsim.physical.ecology.biome_v2 import (
    CLASS_NAMES,
    BiomeV2Class,
    MoistureRegime,
    ThermalRegime,
    classify_biome_v2,
)
from worldsim.physical.ecology.holdridge import HoldridgeOverride, classify_holdridge
from worldsim.physical.ecology.pipeline import (
    climate_liquid_lake_mask,
    climatological_soil_monthly,
)


def _balanced_precip(temp: np.ndarray, scale: float = 200.0) -> np.ndarray:
    n_m = float(temp.shape[0])
    pet_m = 58.93 * np.clip(temp, 0.0, 30.0) / n_m
    return pet_m / scale


def test_balanced_monthly_p_pet_zero_deficit() -> None:
    h, w = 4, 6
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 12.0)
    precip = _balanced_precip(temp)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        precip_scale_mm=200.0,
    )
    assert np.allclose(out["water_deficit_mm"], 0.0, atol=1e-6)


def test_month_rotation_preserves_annuals_and_rotates_monthly_deficit() -> None:
    h, w = 3, 5
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, 0] = True
    month = np.arange(12, dtype=np.float64)[:, None, None]
    temp = 8.0 + 12.0 * np.sin(2.0 * np.pi * month / 12.0)
    temp = np.broadcast_to(temp, (12, h, w)).copy()
    precip = _balanced_precip(temp)
    precip = precip * (0.4 + 0.8 * (month / 11.0))
    soil = np.linspace(0.1, 0.9, 12, dtype=np.float64)[:, None, None]
    soil = np.broadcast_to(soil, (12, h, w)).copy()

    base = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
    )
    shift = 3
    rot = classify_biome_v2(
        temperature_c=np.roll(temp, shift, axis=0),
        precipitation=np.roll(precip, shift, axis=0),
        ocean_mask=ocean,
        soil_moisture=np.roll(soil, shift, axis=0),
    )
    for key in (
        "frost_months",
        "growing_season_months",
        "water_deficit_mm",
        "precipitation_annual_mm",
        "soil_moisture_growing_mean",
        "biome_v2_class",
        "thermal_regime_id",
        "moisture_regime_id",
    ):
        assert np.allclose(base[key], rot[key]), key
    assert np.allclose(
        np.roll(base["water_deficit_monthly"], shift, axis=0),
        rot["water_deficit_monthly"],
    )


def test_wetland_requires_growing_season_climatology_not_wet_december() -> None:
    h, w = 4, 4
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 14.0)
    precip = _balanced_precip(temp) * 1.2
    soil = np.zeros((12, h, w), dtype=np.float64)
    soil[-1] = 1.0
    dry_dec = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
    )
    assert np.all(dry_dec["biome_v2_class"] != int(BiomeV2Class.WETLAND))
    assert float(dry_dec["soil_moisture_growing_mean"].mean()) < 0.25
    assert np.all(dry_dec["moisture_regime_id"] != int(MoistureRegime.WET))

    soil[:] = 0.9
    wet = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
    )
    assert np.all(wet["biome_v2_class"] == int(BiomeV2Class.WETLAND))
    assert np.all(wet["moisture_regime_id"] == int(MoistureRegime.WET))


def test_climatology_ignores_2d_last_month_hydrology_store() -> None:
    h, w = 3, 3
    moisture = SimpleNamespace(land_store=None, diagnostics={"land_store_capacity": 0.0})
    hydro = SimpleNamespace(
        soil_store=np.full((h, w), 0.99),
        soil_store_monthly=np.zeros((0,)),
        diagnostics={"soil_capacity": 1.0},
    )
    assert climatological_soil_monthly(moisture, hydro, w, h) is None

    monthly = np.zeros((12, h, w), dtype=np.float64)
    monthly[-1] = 0.99
    hydro.soil_store_monthly = monthly
    got = climatological_soil_monthly(moisture, hydro, w, h)
    assert got is not None
    assert got.shape == (12, h, w)
    assert float(got[-1].mean()) == 0.99
    assert float(got[0].mean()) == 0.0


def test_axes_keep_seasonal_frost_on_arid_land() -> None:
    h, w = 2, 3
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 12.0)
    temp[:4] = -4.0
    precip = np.full((12, h, w), 0.02)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=np.full((h, w), 0.2),
    )
    assert np.all(out["thermal_regime_id"] == int(ThermalRegime.FROST_SEASONAL))
    assert np.all(out["moisture_regime_id"] == int(MoistureRegime.ARID))
    assert np.all(out["biome_v2_class"] == int(BiomeV2Class.FROST_SEASONAL))


def test_legend_is_exactly_seven_named_classes() -> None:
    assert CLASS_NAMES == {i: BiomeV2Class(i).name.lower() for i in range(7)}
    h, w = 2, 2
    out = classify_biome_v2(
        temperature_c=np.full((12, h, w), 10.0),
        precipitation=np.full((12, h, w), 0.2),
        ocean_mask=np.zeros((h, w), dtype=bool),
    )
    assert out["diagnostics"]["legend_exact"] is True
    assert set(out["diagnostics"]["class_names"]) == {str(i) for i in range(7)}


def test_lake_override_uses_liquid_fraction_not_basin_envelope() -> None:
    h, w = 8, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :1] = True
    envelope = np.zeros((h, w), dtype=bool)
    envelope[2:6, 2:6] = True
    frac = np.zeros((h, w), dtype=np.float64)
    frac[3:5, 3:5] = 0.8
    hydro = SimpleNamespace(
        lake_mask=envelope,
        basin_envelope_id=np.where(envelope, 1, 0).astype(np.int32),
        water_fraction_mean=frac,
    )
    liquid = climate_liquid_lake_mask(hydro, w, h, min_fraction=0.05)
    assert int(np.count_nonzero(liquid)) == 4
    assert int(np.count_nonzero(envelope)) == 16
    assert np.all(liquid <= envelope)

    bio = np.full((h, w), 16.0)
    ratio = np.full((h, w), 1.0)
    elev = np.full((h, w), 80.0)
    zones_liquid, _ = classify_holdridge(
        biotemperature_c=bio,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
        lake_mask=liquid,
    )
    zones_env, _ = classify_holdridge(
        biotemperature_c=bio,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
        lake_mask=envelope,
    )
    lake_id = int(HoldridgeOverride.LAKE)
    assert int(np.count_nonzero(zones_liquid == lake_id)) == 4
    assert int(np.count_nonzero(zones_env == lake_id)) == 16
    land_zones = zones_liquid[~ocean & ~liquid]
    assert np.all(land_zones != lake_id)
    assert np.all(land_zones >= 10)


def test_holdridge_annual_view_unchanged_by_month_rotation() -> None:
    h, w = 4, 6
    ocean = np.zeros((h, w), dtype=bool)
    month = np.arange(12, dtype=np.float64)[:, None, None]
    temp = 10.0 + 8.0 * np.sin(2.0 * np.pi * month / 12.0)
    temp = np.broadcast_to(temp, (12, h, w)).copy()
    from worldsim.physical.ecology.biotemperature import (
        annual_biotemperature_c,
        pet_ratio,
    )

    bio = annual_biotemperature_c(temp)
    bio_rot = annual_biotemperature_c(np.roll(temp, 5, axis=0))
    assert np.allclose(bio, bio_rot)
    precip_annual = np.full((h, w), 4.0)
    ratio = pet_ratio(biotemperature_c=bio, annual_precipitation=precip_annual)
    elev = np.full((h, w), 100.0)
    z0, o0 = classify_holdridge(
        biotemperature_c=bio,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
    )
    z1, o1 = classify_holdridge(
        biotemperature_c=bio_rot,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
    )
    assert np.array_equal(z0, z1)
    assert np.array_equal(o0, o1)
