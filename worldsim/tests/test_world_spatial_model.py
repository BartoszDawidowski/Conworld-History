from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.config import load_planet_config, default_config_path
from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ecology import EcologyParams, build_ecology
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.terrain.coastline import CoastlineFeature
from worldsim.physical.vectorize.indexes import SpatialIndex, build_spatial_index
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.physical.vectorize.rivers import RiverNetwork, RiverSegment
from worldsim.spatial.hex_grid import build_hex_analysis_grid
from worldsim.spatial.hex_grid.layout import hex_center_xy
from worldsim.spatial.manifest import WORLD_MODEL_SCHEMA_VERSION
from worldsim.spatial.model import WorldSpatialModel, build_world_spatial_model


def _small_bundle():
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
    ecology = build_ecology(
        climate=climate,
        moisture=moisture,
        elevation_terrain_m=terrain.elevation_m,
        params=EcologyParams(),
    )
    # Minimal vectors + one synthetic river for mask rebuild / bbox
    extent = climate.extent
    x0, y0 = hex_center_xy(2, 2, width=32, height=16)
    x1, y1 = hex_center_xy(3, 2, width=32, height=16)
    seg = RiverSegment(
        id=1,
        from_node=1,
        to_node=2,
        geometry=[(x0, y0), (x1, y1)],
        strahler_order=1,
        mean_discharge=1.0,
        monthly_discharge=[1.0] * 12,
        basin_id=1,
        length=0.01,
    )
    coast = [
        CoastlineFeature(
            id=10,
            geometry=[(0.1, 0.0), (0.2, 0.0)],
            water_body_id=0,
        )
    ]
    rivers = RiverNetwork(nodes=[], segments=[seg])
    index = build_spatial_index(coastline=coast, river_network=rivers, lakes=[])
    vectors = VectorGeographyResult(
        extent=extent,
        coastline=coast,
        rivers=rivers,
        lakes=[],
        basins=[],
        spatial_index=index,
        diagnostics={"acceptance_ok": True},
    )
    hex_grid = build_hex_analysis_grid(
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        vectors=vectors,
        elevation_terrain_m=terrain.elevation_m,
        width=32,
        height=16,
    )
    config = load_planet_config(default_config_path())
    model = build_world_spatial_model(
        config=config,
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        vectors=vectors,
        hex_grid=hex_grid,
        elevation_terrain_m=terrain.elevation_m,
        master_seed=111,
    )
    return model, climate, moisture, ecology


def test_world_round_trip(tmp_path: Path) -> None:
    model, _c, _m, _e = _small_bundle()
    root = tmp_path / "world"
    model.save(root)
    assert (root / "manifest.json").is_file()
    assert (root / "physical" / "rasters" / "layers.json").is_file()
    assert (root / "physical" / "vectors" / "river_network.json").is_file()
    assert (root / "physical" / "analysis_grid" / "hex_environment.npz").is_file()

    loaded = WorldSpatialModel.load(root)
    assert loaded.manifest.world_model_schema_version == WORLD_MODEL_SCHEMA_VERSION
    assert loaded.hex_grid.n_cells == model.hex_grid.n_cells
    assert np.allclose(
        loaded.rasters.get("climate/elevation_m"),
        model.rasters.get("climate/elevation_m"),
    )
    assert np.allclose(
        loaded.hex_grid.land_fraction, model.hex_grid.land_fraction
    )
    for key in (
        "ecology/biome_v2_class",
        "ecology/frost_months",
        "ecology/growing_season_months",
        "ecology/water_deficit_mm",
        "ecology/soil_state",
        "ecology/thermal_regime_id",
        "ecology/moisture_regime_id",
    ):
        assert loaded.rasters.has(key)
        assert np.array_equal(loaded.rasters.get(key), model.rasters.get(key))
    assert loaded.hex_grid.biome_v2_dominant is not None
    assert np.array_equal(
        loaded.hex_grid.biome_v2_dominant, model.hex_grid.biome_v2_dominant
    )
    assert len(loaded.vectors.rivers.segments) == 1
    assert loaded.vectors.rivers.segments[0].id == 1


def test_query_api_without_godot() -> None:
    model, climate, _m, _e = _small_bundle()
    # Pick a climate cell centre
    x, y = climate.extent.cell_center_xy(10, 8)
    env = model.environment_at(x, y)
    assert "hex_id" in env
    assert "elevation_m" in env
    elev = model.sample_elevation(x, y)
    assert abs(elev - env["elevation_m"]) < 1e-9
    t0 = model.sample_climate(x, y, 0)
    assert np.isfinite(t0)
    hid = model.hex_at(x, y)
    he = model.hex_environment(hid)
    assert he["hex_id"] == hid
    assert "biome_v2_dominant" in he
    assert "frost_months_mean" in he
    assert env.get("biome_v2_hex") == he["biome_v2_dominant"]
    neigh = model.neighbour_hexes(hid)
    assert len(neigh) == 6
    rivers = model.rivers_in_bbox(0.0, -1.0, 1.0, 1.0)
    assert 1 in rivers
    dist = model.coast_distance(0.15, 0.0)
    assert np.isfinite(dist)


def test_caches_rebuildable() -> None:
    model, _c, _m, _e = _small_bundle()
    original = model.hex_grid.river_edge_mask.copy()
    model.hex_grid.river_edge_mask[:] = 0
    rebuilt = model.rebuild_river_edge_mask()
    assert np.array_equal(rebuilt, original)
    # Spatial index rebuild keeps river queryability
    model.vectors.spatial_index = SpatialIndex(nx=8, ny=4)
    model.rebuild_spatial_index()
    assert len(model.vectors.spatial_index.buckets) >= 1
