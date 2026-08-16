from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.ecology import EcologyParams, build_ecology
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.spatial.hex_grid import (
    HexGridSpec,
    build_hex_analysis_grid,
    hex_id,
    neighbours,
)
from worldsim.spatial.hex_grid.intersections import river_edge_mask
from worldsim.spatial.hex_grid.layout import neighbour_matrix


def _small_world():
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
    return climate, moisture, ecology, terrain


def test_production_hex_count() -> None:
    spec = HexGridSpec(width=256, height=128)
    assert spec.n_cells == 32768


def test_hex_vertices_flat_top_six() -> None:
    from worldsim.spatial.hex_grid.layout import hex_vertices_xy

    verts = hex_vertices_xy(3, 4, width=32, height=16)
    assert len(verts) == 6
    assert all(0.0 <= x < 1.0 for x, _y in verts)
    edge = hex_vertices_xy(0, 4, width=32, height=16)
    assert len(edge) == 6


def test_hex_vertices_shared_with_neighbour() -> None:
    """Voronoi corners: adjacent hexes share an edge (no interstitial gap)."""
    from worldsim.spatial.hex_grid.layout import hex_vertices_xy

    w, h = 32, 16
    a = hex_vertices_xy(4, 5, width=w, height=h)
    b = hex_vertices_xy(5, 5, width=w, height=h)  # eastern neighbour (even q)

    def _key(p: tuple[float, float]) -> tuple[float, float]:
        return (round(p[0], 6), round(p[1], 6))

    shared = set(_key(p) for p in a) & set(_key(p) for p in b)
    assert len(shared) >= 2


def test_ew_wrap_and_no_ns_wrap() -> None:
    w, h = 32, 16
    # West of q=0 wraps to q=w-1
    west = neighbours(0, h // 2, width=w, height=h)[4]
    assert west is not None
    assert west % w == w - 1
    # East of q=w-1 wraps to q=0
    east = neighbours(w - 1, h // 2, width=w, height=h)[1]
    assert east is not None
    assert east % w == 0
    # Northern row has at least one missing neighbour (no N–S wrap)
    north = neighbours(2, 0, width=w, height=h)
    assert any(n is None for n in north)
    south = neighbours(2, h - 1, width=w, height=h)
    assert any(n is None for n in south)
    mat = neighbour_matrix(HexGridSpec(width=w, height=h))
    assert mat.shape == (w * h, 6)
    assert int(np.min(mat)) == -1


def test_land_fraction_matches_ocean_mask() -> None:
    climate, moisture, ecology, terrain = _small_world()
    hex_result = build_hex_analysis_grid(
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        elevation_terrain_m=terrain.elevation_m,
        width=32,
        height=16,
    )
    assert hex_result.n_cells == 32 * 16
    assert hex_result.diagnostics["ew_wrap_ok"] is True
    assert hex_result.diagnostics["ns_nowrap_ok"] is True
    assert hex_result.diagnostics["fraction_consistency_ok"] is True
    # land + ocean ≈ 1 per hex
    total = hex_result.land_fraction + hex_result.ocean_fraction
    assert float(np.max(np.abs(total - 1.0))) < 1e-9
    global_ocean = float(np.mean(climate.ocean_mask))
    assert abs(float(np.mean(hex_result.ocean_fraction)) - global_ocean) < 0.08


def test_river_edge_mask_rebuildable() -> None:
    spec = HexGridSpec(width=16, height=8)
    # Synthetic river crossing from hex A to eastern neighbour
    q, r = 3, 4
    hid = hex_id(q, r, width=spec.width)
    east = neighbours(q, r, width=spec.width, height=spec.height)[1]
    assert east is not None
    from worldsim.spatial.hex_grid.layout import hex_center_xy

    x0, y0 = hex_center_xy(q, r, width=spec.width, height=spec.height)
    qe, re = east % spec.width, east // spec.width
    x1, y1 = hex_center_xy(qe, re, width=spec.width, height=spec.height)
    seg = SimpleNamespace(id=7, geometry=[(x0, y0), (x1, y1)])
    mask = river_edge_mask([seg], spec)
    # Edge bit 1 = E
    assert mask[hid] & (1 << 1)
    assert mask[east] != 0  # reciprocal edge set


def test_hex_save_artefacts(tmp_path: Path) -> None:
    climate, moisture, ecology, terrain = _small_world()
    hex_result = build_hex_analysis_grid(
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        elevation_terrain_m=terrain.elevation_m,
        width=32,
        height=16,
    )
    out = tmp_path / "hex"
    hex_result.save(out)
    assert (out / "hex_environment.npz").is_file()
    assert (out / "hex_object_refs.json").is_file()
    assert (out / "hex_diagnostics.json").is_file()
    data = np.load(out / "hex_environment.npz")
    assert data["land_fraction"].shape == (512,)
    assert data["temperature_mean"].shape == (512, 12)
    assert data["neighbours"].shape == (512, 6)
