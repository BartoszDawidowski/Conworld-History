from __future__ import annotations

from pathlib import Path

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.erosion import ErosionParams, build_erosion_pass_one
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.vectorize import build_vector_geography
from worldsim.physical.vectorize.rivers import topology_valid


def _small_hydro_stack():
    tectonics = run_pyplatec_extended(
        seed=91,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=7,
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
    erosion = build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(iterations=3),
    )
    hydrology = build_hydrology(
        erosion=erosion, moisture=moisture, params=HydrologyParams()
    )
    return terrain, hydrology


def test_vectors_from_small_world(tmp_path: Path) -> None:
    terrain, hydrology = _small_hydro_stack()
    vectors = build_vector_geography(hydrology=hydrology, terrain=terrain)
    assert len(vectors.coastline) > 0
    assert len(vectors.rivers.segments) > 0
    assert topology_valid(vectors.rivers)
    assert vectors.diagnostics["river_topology_valid"] is True
    assert vectors.diagnostics["hex_independent"] is True
    assert vectors.diagnostics["acceptance_ok"] is True
    vectors.save(tmp_path / "vectors")
    assert (tmp_path / "vectors" / "coastline.geojson").is_file()
    assert (tmp_path / "vectors" / "rivers.geojson").is_file()
    assert (tmp_path / "vectors" / "river_network.json").is_file()
    assert (tmp_path / "vectors" / "spatial_index.json").is_file()


def test_spatial_index_query() -> None:
    terrain, hydrology = _small_hydro_stack()
    vectors = build_vector_geography(hydrology=hydrology, terrain=terrain)
    seg = vectors.rivers.segments[0]
    x, y = seg.geometry[0]
    hits = vectors.spatial_index.query_point(x, y)
    assert any(h[0] == "river_segment" for h in hits)
