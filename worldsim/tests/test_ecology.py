from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ecology import EcologyParams, HoldridgeOverride, build_ecology
from worldsim.physical.ecology.biotemperature import annual_biotemperature_c, pet_ratio
from worldsim.physical.ecology.holdridge import (
    classify_holdridge,
    humanize_zone_label,
    zone_label_for_id,
)
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_climate_moisture():
    tectonics = run_pyplatec_extended(
        seed=111,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=9,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atmosphere = build_atmosphere(climate=climate, params=AtmosphereParams())
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    moisture = build_moisture(
        climate=climate, atmosphere=atmosphere, ocean=ocean, params=MoistureParams()
    )
    return climate, moisture, terrain


def test_biotemperature_nonnegative() -> None:
    t = np.array([[[-10.0, 5.0], [35.0, 0.0]]])  # 1 month
    bio = annual_biotemperature_c(t)
    assert float(bio.min()) >= 0.0
    assert float(bio.max()) <= 30.0


def test_holdridge_ocean_override() -> None:
    bio = np.full((8, 8), 15.0)
    ratio = np.full((8, 8), 1.0)
    ocean = np.zeros((8, 8), dtype=bool)
    ocean[:, :3] = True
    elev = np.full((8, 8), 100.0)
    zones, override = classify_holdridge(
        biotemperature_c=bio,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
    )
    assert np.all(zones[ocean] == int(HoldridgeOverride.OCEAN))
    assert np.all(zones[~ocean] >= 10)


def test_holdridge_inspector_labels() -> None:
    assert zone_label_for_id(0) == "Ocean"
    assert zone_label_for_id(1) == "Lake"
    assert zone_label_for_id(2) == "Permanent ice"
    assert zone_label_for_id(3) == "Alpine bare"
    # Tropical (≥24 °C) × humid → Tropical moist forest (wiki-style)
    from worldsim.physical.ecology.holdridge import life_zone_id

    assert zone_label_for_id(life_zone_id(5, 2)) == "Tropical moist forest"
    assert "Boreal" in zone_label_for_id(life_zone_id(2, 2))
    assert humanize_zone_label("boreal__humid") == "Boreal / humid"


def test_ecology_from_small_world(tmp_path: Path) -> None:
    climate, moisture, terrain = _small_climate_moisture()
    ecology = build_ecology(
        climate=climate,
        moisture=moisture,
        elevation_terrain_m=terrain.elevation_m,
        params=EcologyParams(),
    )
    assert ecology.holdridge_zone_id.shape == climate.ocean_mask.shape
    assert ecology.diagnostics["acceptance_ok"] is True
    assert ecology.diagnostics["all_cells_classified"] is True
    land = ~climate.ocean_mask
    assert np.all(ecology.permeability[land] > 0.0)
    ecology.save(tmp_path / "ecology")
    assert (tmp_path / "ecology" / "ecology.npz").is_file()
    assert (tmp_path / "ecology" / "holdridge_zone_legend.json").is_file()


def test_pet_ratio_wetter_lower() -> None:
    bio = np.full((4, 4), 20.0)
    wet = pet_ratio(biotemperature_c=bio, annual_precipitation=np.full((4, 4), 10.0))
    dry = pet_ratio(biotemperature_c=bio, annual_precipitation=np.full((4, 4), 1.0))
    assert float(wet.mean()) < float(dry.mean())
