"""C8 — WorldSpatialModel / hex / query / atlas contract integration."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from worldsim.config import default_config_path, load_planet_config
from worldsim.export import export_atlas_display
from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ecology import EcologyParams, build_ecology
from worldsim.physical.hydrology.channels import CHANNEL_PERENNIAL, CHANNEL_SEASONAL, CHANNEL_WADI
from worldsim.physical.landforms.classify import BroadContext, LocalForm, legend_payload
from worldsim.physical.landforms.objects import MountainRange, Plateau
from worldsim.physical.landforms.pipeline import LandformResult
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.terrain.coastline import CoastlineFeature
from worldsim.physical.vectorize.basins import BasinMeta
from worldsim.physical.vectorize.indexes import build_spatial_index
from worldsim.physical.vectorize.lakes import Lake
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.physical.vectorize.rivers import RiverNetwork, RiverSegment
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.hex_grid import build_hex_analysis_grid
from worldsim.spatial.hex_grid.contract import (
    FRACTION_FIELDS,
    HEX_CONTRACT_FIELDS,
    SCORE_MEAN_FIELDS,
    column_value,
    hex_environment_record,
)
from worldsim.spatial.hex_grid.layout import hex_center_xy
from worldsim.spatial.model import (
    WorldSpatialModel,
    build_world_spatial_model,
    rebuild_hex_analysis_cache,
)


def _synthetic_landforms(ocean: np.ndarray) -> LandformResult:
    h, w = ocean.shape
    land = ~ocean
    ctx = np.zeros((h, w), dtype=np.uint8)
    loc = np.zeros((h, w), dtype=np.uint8)
    ctx[land] = int(BroadContext.PLAIN)
    loc[land] = int(LocalForm.SLOPE)
    mscore = np.zeros((h, w), dtype=np.uint8)
    pscore = np.zeros((h, w), dtype=np.uint8)
    range_id = np.zeros((h, w), dtype=np.int32)
    plat_id = np.zeros((h, w), dtype=np.int32)
    j0, j1 = max(h // 4, 2), min(h // 4 + 6, h - 2)
    i0, i1 = max(w // 4, 2), min(w // 4 + 6, w - 2)
    block = np.zeros((h, w), dtype=bool)
    block[j0:j1, i0:i1] = True
    block &= land
    if not np.any(block):
        coords = np.argwhere(land)
        for y, x in coords[:24]:
            block[int(y), int(x)] = True
    mscore[block] = 200  # 200/255 ≈ 0.78 ≥ 0.60
    range_id[block] = 7
    ctx[block] = int(BroadContext.UPLAND)
    loc[block] = int(LocalForm.RIDGE)
    p0, p1 = max(h // 2, 2), min(h // 2 + 5, h - 2)
    q0, q1 = max(w // 2, 2), min(w // 2 + 5, w - 2)
    plat = np.zeros((h, w), dtype=bool)
    plat[p0:p1, q0:q1] = True
    plat &= land & ~block
    if not np.any(plat):
        coords = np.argwhere(land & ~block)
        for y, x in coords[:16]:
            plat[int(y), int(x)] = True
    pscore[plat] = 180
    plat_id[plat] = 3
    ctx[plat] = int(BroadContext.PLATEAU)
    loc[plat] = int(LocalForm.FLAT)
    rng = MountainRange(
        id=7,
        cell_count=int(block.sum()),
        area_cells=int(block.sum()),
        area_km2=float(block.sum()),
        centroid_j=float((j0 + j1) / 2),
        centroid_i=float((i0 + i1) / 2),
        mean_elev_m=1200.0,
        max_elev_m=1800.0,
        base_elev_m=400.0,
        local_relief_m=800.0,
        orientation_deg=90.0,
        elongation=2.0,
        provenance_mode=1,
        confidence=0.8,
        crosses_ew_seam=False,
        ridge_line=[[0.3, 0.2], [0.32, 0.15]],
    )
    plateau = Plateau(
        id=3,
        cell_count=int(plat.sum()),
        area_cells=int(plat.sum()),
        area_km2=float(plat.sum()),
        centroid_j=float((p0 + p1) / 2),
        centroid_i=float((q0 + q1) / 2),
        mean_elev_m=900.0,
        base_elev_m=800.0,
        internal_relief_m=40.0,
        mean_slope=0.01,
        provenance_mode=4,
        confidence=0.7,
        crosses_ew_seam=False,
        rim_line=[[0.55, -0.1], [0.58, -0.12]],
    )
    return LandformResult(
        extent=SpatialExtent.from_shape(w, h),
        context_id=ctx,
        local_form_id=loc,
        provenance_id=np.zeros((h, w), dtype=np.uint8),
        confidence_u8=np.full((h, w), 200, dtype=np.uint8),
        mountain_score_u8=mscore,
        plateau_score_u8=pscore,
        hill_score_u8=np.zeros((h, w), dtype=np.uint8),
        mountain_range_id=range_id,
        plateau_id=plat_id,
        mountain_ranges=[rng],
        plateaus=[plateau],
        diagnostics={"mountain_score_threshold": 0.60},
    )


def _synthetic_hydrology(ocean: np.ndarray) -> SimpleNamespace:
    h, w = ocean.shape
    lake_id = np.zeros((h, w), dtype=np.int32)
    water = np.zeros((h, w), dtype=np.float64)
    channel = np.zeros((h, w), dtype=np.uint8)
    discharge = np.zeros((h, w), dtype=np.float64)
    basin = np.zeros((h, w), dtype=np.int32)
    land = ~ocean
    ys, xs = np.where(land)
    if ys.size:
        lake_id[ys[0], xs[0]] = 11
        water[ys[0], xs[0]] = 0.4
        if ys.size > 1:
            channel[ys[1], xs[1]] = CHANNEL_PERENNIAL
            discharge[ys[1], xs[1]] = 12.5
            basin[ys[1], xs[1]] = 4
        if ys.size > 2:
            channel[ys[2], xs[2]] = CHANNEL_SEASONAL
        if ys.size > 3:
            channel[ys[3], xs[3]] = CHANNEL_WADI
            lake_id[ys[3], xs[3]] = 12
            water[ys[3], xs[3]] = 0.2
    records = [
        {"id": 11, "lake_id": 11, "hydroperiod": "permanent"},
        {"id": 12, "lake_id": 12, "hydroperiod": "seasonal"},
    ]
    return SimpleNamespace(
        water_fraction_mean=water,
        river_mask=channel > 0,
        lake_mask=water > 0,
        channel_state=channel,
        river_discharge_proxy=discharge,
        basin_id=basin,
        lake_id=lake_id,
        lake_records=records,
        ocean_mask=ocean,
    )


def _bundle():
    tectonics = run_pyplatec_extended(
        seed=111, width=64, height=32, params=PyPlatecParams(num_plates=5)
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=9,
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
    landforms = _synthetic_landforms(climate.ocean_mask)
    hydrology = _synthetic_hydrology(climate.ocean_mask)
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
        basin_id=4,
        length=0.01,
    )
    lake = Lake(
        id=11,
        polygon=[(0.2, 0.1), (0.22, 0.1), (0.22, 0.08), (0.2, 0.08), (0.2, 0.1)],
        surface_elevation=12.0,
        basin_id=4,
        hydroperiod="permanent",
    )
    basin = BasinMeta(
        id=4,
        area_cells=8,
        mean_elevation_m=100.0,
        max_accumulation=20.0,
        outlet_row=1,
        outlet_col=1,
        outlet_x=0.2,
        outlet_y=0.1,
    )
    coast = [CoastlineFeature(id=10, geometry=[(0.1, 0.0), (0.2, 0.0)], water_body_id=0)]
    rivers = RiverNetwork(nodes=[], segments=[seg])
    index = build_spatial_index(coastline=coast, river_network=rivers, lakes=[lake])
    vectors = VectorGeographyResult(
        extent=climate.extent,
        coastline=coast,
        rivers=rivers,
        lakes=[lake],
        basins=[basin],
        spatial_index=index,
        diagnostics={"acceptance_ok": True},
    )
    hex_grid = build_hex_analysis_grid(
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        hydrology=hydrology,
        vectors=vectors,
        elevation_terrain_m=terrain.elevation_m,
        landforms=landforms,
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
        hydrology=hydrology,
        elevation_terrain_m=terrain.elevation_m,
        landforms=landforms,
        master_seed=111,
    )
    return model, climate, moisture, ecology, terrain, landforms, hydrology


def test_save_load_preserves_landform_products(tmp_path: Path) -> None:
    model, *_rest = _bundle()
    root = tmp_path / "world"
    model.save(root)
    loaded = WorldSpatialModel.load(root)
    for key in (
        "landforms/context_id",
        "landforms/local_form_id",
        "landforms/mountain_score",
        "landforms/mountain_range_id",
        "landforms/plateau_id",
        "hydrology/lake_id",
        "hydrology/channel_state",
    ):
        assert loaded.rasters.has(key)
        assert np.array_equal(loaded.rasters.get(key), model.rasters.get(key))
    assert loaded.vectors.mountain_ranges
    assert loaded.vectors.plateaus
    assert loaded.vectors.mountain_ridges
    assert loaded.vectors.plateau_rims
    assert loaded.hex_grid.mountain_score_mean is not None
    assert np.allclose(
        loaded.hex_grid.mountain_score_mean,
        model.hex_grid.mountain_score_mean,
        equal_nan=True,
    )
    assert loaded.hex_grid.mountain_range_ids == model.hex_grid.mountain_range_ids
    assert loaded.hex_grid.basin_ids == model.hex_grid.basin_ids


def test_rebuild_keeps_landform_aggregates() -> None:
    model, climate, moisture, ecology, terrain, landforms, hydrology = _bundle()
    before = model.hex_grid.mountain_terrain_fraction.copy()
    ids_before = [list(x) for x in model.hex_grid.mountain_range_ids]
    rebuilt = rebuild_hex_analysis_cache(
        model,
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        hydrology=hydrology,
        elevation_terrain_m=terrain.elevation_m,
        landforms=landforms,
    )
    assert rebuilt.mountain_terrain_fraction is not None
    assert np.allclose(rebuilt.mountain_terrain_fraction, before, equal_nan=True)
    assert rebuilt.mountain_range_ids == ids_before
    # Raster fallback (no live landforms argument)
    rebuilt2 = rebuild_hex_analysis_cache(
        model,
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        elevation_terrain_m=terrain.elevation_m,
    )
    assert rebuilt2.mountain_score_mean is not None
    assert any(7 in ids for ids in rebuilt2.mountain_range_ids)


def test_score_mean_is_not_a_fraction() -> None:
    model, *_rest = _bundle()
    grid = model.hex_grid
    assert grid.mountain_score_mean is not None
    assert grid.mountain_terrain_fraction is not None
    land = grid.land_fraction > 0.05
    differ = land & np.isfinite(grid.mountain_score_mean) & (
        np.abs(grid.mountain_score_mean - grid.mountain_terrain_fraction) > 0.05
    )
    assert np.any(differ)
    rec = hex_environment_record(grid, int(np.flatnonzero(differ)[0]))
    for name in FRACTION_FIELDS:
        assert name not in SCORE_MEAN_FIELDS
        assert not name.endswith("score_mean")
    assert rec["mountain_score_mean"] != rec["mountain_terrain_fraction"]


def test_ocean_only_hex_uses_null_not_zero() -> None:
    model, *_rest = _bundle()
    ocean_ids = np.where(model.hex_grid.land_fraction == 0.0)[0]
    assert ocean_ids.size
    rec = hex_environment_record(model.hex_grid, int(ocean_ids[0]))
    assert rec["land_fraction"] == 0.0
    assert rec["elevation_mean_m"] is None
    assert rec["mountain_score_mean"] is None
    assert rec["local_relief_mean_m"] is None


def test_query_matches_atlas_export_names(tmp_path: Path) -> None:
    model, *_rest = _bundle()
    out = tmp_path / "atlas_display"
    meta = export_atlas_display(model, out)
    env = json.loads((out / "hex_environment.json").read_text(encoding="utf-8"))
    hid = next(
        i
        for i, frac in enumerate(env["land_fraction"])
        if frac and frac > 0.2
    )
    query = model.hex_environment(hid)
    for name in HEX_CONTRACT_FIELDS:
        if name == "hex_id":
            continue
        assert name in env
        assert name in query
        qv = query[name]
        av = column_value(env, name, hid)
        if isinstance(qv, float) or isinstance(av, float):
            if qv is None or av is None:
                assert qv is None and av is None
            else:
                assert abs(float(qv) - float(av)) < 1e-9
        else:
            assert qv == av
    assert "mountain_fraction" not in query
    assert meta["files"]["biome_v2_legend"] == "biome_v2_legend.json"
    assert (out / "landform_legend.json").is_file()


def test_legends_cover_emitted_ids() -> None:
    model, *_rest = _bundle()
    legends = model.metadata["categorical_legends"]
    biome = model.rasters.get("ecology/biome_v2_class")
    for zid in np.unique(biome):
        assert str(int(zid)) in legends["biome_v2_class"]
    hold = model.rasters.get("ecology/holdridge_zone_id")
    for zid in np.unique(hold):
        assert str(int(zid)) in legends["holdridge_zone"]
    ctx = model.rasters.get("landforms/context_id")
    loc = model.rasters.get("landforms/local_form_id")
    for zid in np.unique(ctx):
        assert str(int(zid)) in legends["landform"]["broad_context"]
    for zid in np.unique(loc):
        assert str(int(zid)) in legends["landform"]["local_form"]
    payload = legend_payload()
    assert set(payload["broad_context"]) <= {
        int(k) for k in legends["landform"]["broad_context"]
    }


def test_object_lookups() -> None:
    model, *_rest = _bundle()
    rng = model.mountain_range(7)
    assert int(rng["properties"]["id"]) == 7
    plat = model.plateau(3)
    assert int(plat["properties"]["id"]) == 3
    riv = model.river(1)
    assert int(riv["id"]) == 1
    lake = model.lake(11)
    assert int(lake["id"]) == 11
    basin = model.basin(4)
    assert int(basin["id"]) == 4
    assert 7 in {
        i for ids in (model.hex_grid.mountain_range_ids or []) for i in ids
    }
    assert 4 in {i for ids in (model.hex_grid.basin_ids or []) for i in ids}
