"""C9.1.3 — honest river terminals; display filter defaults unchanged."""

from __future__ import annotations

import json

import numpy as np

from worldsim.physical.hydrology import HydrologyParams
from worldsim.physical.vectorize.indexes import SpatialIndex
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.physical.vectorize.rivers import (
    build_river_network,
    ocean_mouth_ocean_adjacent_fraction,
)
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.vector_store import VectorStore


def _east_inputs(
    *,
    w: int = 8,
    river_start: int = 0,
    river_end: int = 6,
    physical_end: int | None = None,
    lake_cols: tuple[int, int] | None = None,
    ocean_last: bool = True,
):
    h = 3
    ocean = np.zeros((h, w), dtype=bool)
    if ocean_last:
        ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[ocean] = 0
    if not ocean_last:
        d8[:, -1] = 0
    river = np.zeros((h, w), dtype=bool)
    river[1, river_start : river_end + 1] = True
    if ocean_last:
        river[:, -1] = False
    physical = np.zeros((h, w), dtype=bool)
    pe = physical_end if physical_end is not None else river_end
    physical[1, river_start : pe + 1] = True
    if ocean_last:
        physical[:, -1] = False
    lake = np.zeros((h, w), dtype=bool)
    lake_id = np.zeros((h, w), dtype=np.int32)
    if lake_cols is not None:
        a, b = lake_cols
        lake[1, a : b + 1] = True
        lake_id[lake] = 3
    acc = np.zeros((h, w), dtype=np.float64)
    acc[river | physical] = 10.0
    monthly = np.repeat(acc[np.newaxis, ...], 3, axis=0)
    net = build_river_network(
        flow_direction=d8,
        river_mask=river,
        stream_order=np.ones((h, w), dtype=np.int16),
        basin_id=np.ones((h, w), dtype=np.int32),
        ocean_mask=ocean,
        lake_mask=lake,
        lake_id=lake_id,
        discharge_proxy=acc,
        monthly_discharge=monthly,
        extent=SpatialExtent.from_shape(w, h),
        channel_mask=physical,
    )
    return net, ocean


def test_ocean_adjacent_terminus_is_ocean_mouth_not_junction() -> None:
    net, ocean = _east_inputs(river_end=6)
    types = {n.type for n in net.nodes}
    assert "ocean_mouth" in types
    assert "mouth" not in types
    mouths = [n for n in net.nodes if n.type == "ocean_mouth"]
    assert mouths
    assert ocean_mouth_ocean_adjacent_fraction(net, ocean) == 1.0
    for n in mouths:
        assert n.to_dict()["legacy_type"] == "mouth"


def test_out_zero_inland_is_endorheic_sink_not_mouth() -> None:
    net, _ocean = _east_inputs(river_end=6, ocean_last=False)
    types = {n.type for n in net.nodes}
    assert "mouth" not in types
    assert "endorheic_sink" in types
    assert "ocean_mouth" not in types


def test_lake_inlet_and_outlet_round_trip_geojson(tmp_path) -> None:
    inlet_net, _ = _east_inputs(river_end=4, lake_cols=(3, 4))
    outlet_net, _ = _east_inputs(river_start=3, river_end=6, lake_cols=(3, 4))
    assert any(n.type == "lake_inlet" for n in inlet_net.nodes)
    assert any(n.type == "lake_outlet" for n in outlet_net.nodes)
    # Round-trip both vocabularies through GeoJSON + VectorStore.
    merged_nodes = list(inlet_net.nodes) + [
        n for n in outlet_net.nodes if n.type == "lake_outlet"
    ]
    for i, node in enumerate(merged_nodes, start=1):
        node.id = i
    from worldsim.physical.vectorize.rivers import RiverNetwork

    merged = RiverNetwork(nodes=merged_nodes, segments=list(inlet_net.segments))
    vec = VectorGeographyResult(
        extent=SpatialExtent.from_shape(8, 3),
        coastline=[],
        rivers=merged,
        lakes=[],
        basins=[],
        spatial_index=SpatialIndex(),
        diagnostics={},
    )
    vec.save(tmp_path)
    raw = json.loads((tmp_path / "river_nodes.geojson").read_text(encoding="utf-8"))
    kinds = {f["properties"]["type"] for f in raw["features"]}
    assert "lake_inlet" in kinds
    assert "lake_outlet" in kinds
    store_dir = tmp_path / "store"
    VectorStore(
        extent=SpatialExtent.from_shape(8, 3),
        rivers=merged,
    ).save(store_dir)
    loaded = VectorStore.load(store_dir)
    loaded_types = {n.type for n in loaded.rivers.nodes}
    assert "lake_inlet" in loaded_types
    assert "lake_outlet" in loaded_types


def test_lod_cutoff_when_physical_channel_continues() -> None:
    net, _ocean = _east_inputs(river_end=3, physical_end=6)
    types = {n.type for n in net.nodes}
    assert "lod_cutoff" in types
    assert "ocean_mouth" not in types


def test_display_filter_defaults_not_retuned() -> None:
    p = HydrologyParams()
    assert p.river_acc_fraction == 0.035
    assert p.river_discharge_candidate_quantile == 0.50
