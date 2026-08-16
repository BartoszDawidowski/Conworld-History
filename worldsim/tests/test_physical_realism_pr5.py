"""PR-5 — canonical cylindrical hydrology graph."""

from __future__ import annotations

import time

import numpy as np

from worldsim.physical.hydrology.cylindrical_graph import (
    accumulate_cells,
    build_cylindrical_graph,
    cell_path_to_norm_geometry,
    extract_river_cell_paths,
    label_basins,
    rotate_longitude,
    stream_order_strahler,
    validate_graph,
)
from worldsim.physical.hydrology.flow import run_pyflwdir_core
from worldsim.physical.vectorize.rivers import build_river_network, topology_valid
from worldsim.spatial.extent import SpatialExtent


def _seam_valley_dem(
    h: int = 24,
    w: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """Land with a valley that can drain across the E–W seam."""
    elev = np.full((h, w), 200.0, dtype=np.float64)
    for c in range(w):
        elev[:, c] += 0.5 * abs(c - (w - 4))
    channel_cols = list(range(w - 6, w)) + list(range(0, 5))
    for i, c in enumerate(channel_cols):
        elev[h // 2 - 1 : h // 2 + 2, c] = 40.0 - 0.5 * i
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -2:] = True
    elev[ocean] = -50.0
    return elev, ocean


def test_downstream_wraps_ew() -> None:
    h, w = 8, 12
    ocean = np.zeros((h, w), dtype=bool)
    ocean[0, :] = True
    d8 = np.full((h, w), 64, dtype=np.uint8)  # north toward ocean fringe
    d8[0, :] = 0
    d8[4, 0] = 16  # west → wrap to w-1
    ocean[4, :] = False
    ocean[0, :] = True
    g = build_cylindrical_graph(d8, ocean)
    assert g.downstream_rc(4, 0) == (4, w - 1)


def test_seam_crossing_basin_single_id() -> None:
    elev, ocean = _seam_valley_dem()
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    g = core["graph"]
    diag = validate_graph(g)
    assert diag["graph_valid"] is True
    assert diag["downstream_accumulation_ok"] is True
    assert diag["seam_basin_mismatch"] == 0
    basins = core["basin_id"]
    ds = g.downstream_flat
    w = g.width
    for i in range(g.size):
        j = int(ds[i])
        if j < 0:
            continue
        r, c = divmod(i, w)
        nr, nc = divmod(j, w)
        if (c == 0 and nc == w - 1) or (c == w - 1 and nc == 0):
            assert basins[r, c] == basins[nr, nc]


def test_longitude_rotation_preserves_basin_partition() -> None:
    elev, ocean = _seam_valley_dem()
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    basins = core["basin_id"]
    shift = 7
    elev_r = rotate_longitude(elev, shift)
    ocean_r = rotate_longitude(ocean, shift)
    core_r = run_pyflwdir_core(elevation_m=elev_r, ocean_mask=ocean_r)
    basins_r = core_r["basin_id"]
    land_r = rotate_longitude(~ocean, shift)
    b0 = rotate_longitude(basins, shift)
    coords = np.argwhere(land_r)
    rng = np.random.default_rng(0)
    if len(coords) > 40:
        pick = coords[rng.choice(len(coords), size=40, replace=False)]
    else:
        pick = coords
    for (r1, c1), (r2, c2) in zip(pick[::2], pick[1::2], strict=False):
        same0 = b0[r1, c1] == b0[r2, c2] and b0[r1, c1] > 0
        same1 = basins_r[r1, c1] == basins_r[r2, c2] and basins_r[r1, c1] > 0
        assert same0 == same1


def test_accumulation_never_decreases_along_edges() -> None:
    elev, ocean = _seam_valley_dem()
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    assert core["graph_diagnostics"]["bad_accumulation_edges"] == 0


def test_river_vector_from_graph_topology() -> None:
    elev, ocean = _seam_valley_dem(h=20, w=32)
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    acc = core["flow_accumulation"]
    thr = float(np.quantile(acc[~ocean], 0.85)) if np.any(~ocean) else 1.0
    river = (~ocean) & (acc >= thr)
    h, w = elev.shape
    months = 3
    monthly = np.broadcast_to(acc, (months, h, w)).copy()
    network = build_river_network(
        flow_direction=core["flow_direction"],
        river_mask=river,
        stream_order=core["stream_order"],
        basin_id=core["basin_id"],
        ocean_mask=ocean,
        lake_mask=np.zeros_like(ocean),
        discharge_proxy=acc,
        monthly_discharge=monthly,
        extent=SpatialExtent.from_shape(w, h),
    )
    assert topology_valid(network)


def test_extract_paths_match_downstream_relation() -> None:
    h, w = 12, 20
    d8 = np.full((h, w), 4, dtype=np.uint8)  # south
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-1, :] = True
    d8[-1, :] = 0
    g = build_cylindrical_graph(d8, ocean)
    river = np.zeros((h, w), dtype=bool)
    river[2:-1, 5] = True
    paths = extract_river_cell_paths(g, river)
    assert paths
    for path in paths:
        for (r0, c0), (r1, c1) in zip(path, path[1:], strict=False):
            assert g.downstream_rc(r0, c0) == (r1, c1)


def test_fullish_performance_budget() -> None:
    """Graph products on ~0.5M cells stay within a generous wall-time budget."""
    h, w = 512, 1024
    elev = np.random.default_rng(0).random((h, w)) * 100.0
    ocean = elev < 30.0
    elev[ocean] = -10
    d8 = np.where(ocean, 0, 1).astype(np.uint8)
    t0 = time.perf_counter()
    g = build_cylindrical_graph(d8, ocean)
    _ = accumulate_cells(g)
    _ = label_basins(g)
    _ = stream_order_strahler(g)
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0
    assert validate_graph(g)["graph_valid"]


def test_cell_path_unwrap_across_seam() -> None:
    geom = cell_path_to_norm_geometry(
        [5, 5, 5],
        [14, 15, 0],
        height=10,
        width=16,
    )
    assert len(geom) == 3
    assert geom[2][0] > geom[1][0]
