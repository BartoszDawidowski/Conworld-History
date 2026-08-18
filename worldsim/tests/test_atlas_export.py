from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from worldsim.config import default_config_path, load_planet_config
from worldsim.export import export_atlas_display
from worldsim.export.pngutil import write_png_rgb
from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ecology import EcologyParams, build_ecology
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.terrain.coastline import CoastlineFeature
from worldsim.physical.vectorize.indexes import build_spatial_index
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.physical.vectorize.rivers import RiverNetwork
from worldsim.spatial.hex_grid import build_hex_analysis_grid
from worldsim.spatial.model import build_world_spatial_model


def _model():
    tectonics = run_pyplatec_extended(
        seed=42, width=64, height=32, params=PyPlatecParams(num_plates=5)
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=3,
    )
    climate = build_base_climate(terrain=terrain, params=ClimateParams(width=64, height=32))
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
    coast = [CoastlineFeature(id=1, geometry=[(0.0, 0.0), (0.2, 0.0)], water_body_id=0)]
    rivers = RiverNetwork(nodes=[], segments=[])
    vectors = VectorGeographyResult(
        extent=climate.extent,
        coastline=coast,
        rivers=rivers,
        lakes=[],
        basins=[],
        spatial_index=build_spatial_index(
            coastline=coast, river_network=rivers, lakes=[]
        ),
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
    return build_world_spatial_model(
        config=config,
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        vectors=vectors,
        hex_grid=hex_grid,
        elevation_terrain_m=terrain.elevation_m,
        master_seed=42,
    )


def test_png_roundtrip(tmp_path: Path) -> None:
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[..., 0] = 255
    path = tmp_path / "t.png"
    write_png_rgb(path, rgb)
    assert path.is_file()
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_atlas_display_export(tmp_path: Path) -> None:
    model = _model()
    out = tmp_path / "atlas_display"
    meta = export_atlas_display(model, out)
    assert meta["schema"] == "atlas_display_v2"
    assert (out / "atlas_meta.json").is_file()
    assert (out / "elevation.png").is_file()
    assert (out / "temperature_01.png").is_file()
    assert (out / "rivers.geojson").is_file()
    assert (out / "coastline.geojson").is_file()
    assert (out / "land.geojson").is_file()
    assert (out / "land_mask.png").is_file()
    assert (out / "land_polygons_diagnostics.json").is_file()
    land = json.loads((out / "land.geojson").read_text(encoding="utf-8"))
    assert land["type"] == "FeatureCollection"
    assert len(land["features"]) >= 1
    assert meta["files"]["land"] == "land.geojson"
    assert meta["files"]["land_mask"] == "land_mask.png"
    assert (out / "hex_overlay.png").is_file()
    assert (out / "hex_environment.json").is_file()
    assert (out / "holdridge_zone_legend.json").is_file()
    legend = json.loads((out / "holdridge_zone_legend.json").read_text(encoding="utf-8"))
    assert legend["0"] == "Ocean"
    assert "Tropical moist forest" in legend.values()
    assert legend["classes"]["0"]["label"] == "Ocean"
    assert legend["classes"]["0"]["color"].startswith("#")
    assert "shaded_relief" not in meta.get("map_mode_ids", [])
    mode_ids = [
        str(m["id"]) if isinstance(m, dict) else str(m) for m in meta["map_modes"]
    ]
    assert meta["default_mode"] == "elevation"
    assert "elevation" in mode_ids
    assert "biome_v2" in mode_ids
    assert (out / "biome_v2.png").is_file()
    assert (out / "biome_v2_legend.json").is_file()
    assert (out / "inspection_grid.bin").is_file()
    assert (out / "climate_summary.json").is_file()
    assert "stroke_smooth" in meta
    assert meta["stroke_smooth"]["chaikin_iters"] == 2
    env = json.loads((out / "hex_environment.json").read_text(encoding="utf-8"))
    assert "temperature_annual_c" in env
    assert "precipitation_annual_mm" in env
    assert "precipitation_annual" in env
    assert "elevation_mean_m" in env
    assert "cell_count" in env
    assert len(env["cell_count"]) == len(env["holdridge_dominant"])


def test_hex_overlay_draws_outlines_not_crosses() -> None:
    """A7: each hex contributes an outline ring → many more lit pixels than 5-px crosses."""
    from worldsim.export.atlas_display import _draw_hex_overlay
    from worldsim.spatial.hex_grid.layout import HexGridSpec, all_hex_centers

    class _Fake:
        pass

    spec = HexGridSpec(width=16, height=8)
    xs, ys = all_hex_centers(spec)
    grid = _Fake()
    grid.spec = spec
    grid.center_x = xs
    grid.center_y = ys
    grid.n_cells = spec.n_cells
    rgba = _draw_hex_overlay(64, 32, grid, out_w=128, out_h=64)
    lit = int(np.count_nonzero(rgba[..., 3]))
    # Old crosses: ≤ n_cells * 5; outlines are much denser
    assert lit > spec.n_cells * 8
