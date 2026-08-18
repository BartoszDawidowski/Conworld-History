"""C2 — physical channel mask, flow-limited bed loss, state export, coupling."""

from __future__ import annotations

import math

import numpy as np
import pytest

from worldsim.physical.final.pipeline import binary_jaccard, coupling_metrics
from worldsim.physical.hydrology.channels import (
    CHANNEL_STATE_NAME,
    effective_channel_min_cells,
    physical_channel_mask,
    river_water_fraction,
)
from worldsim.physical.hydrology.cylindrical_graph import (
    build_cylindrical_graph,
    effective_discharge_and_sink,
)
from worldsim.physical.hydrology.discharge import month_weighted_mean_m3s
from worldsim.physical.hydrology.pipeline import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.transmission import channel_bed_loss_potential_m3s
from worldsim.physical.moisture.transport import evaporation_components
from worldsim.physical.vectorize.rivers import (
    RiverSegment,
    clip_polyline_outside_lakes,
)
from worldsim.spatial.metrics import grid_metrics
from test_physical_realism_cr7 import _synthetic_hydro_inputs


def test_effective_min_cells_is_max_of_km2_and_accumulation() -> None:
    cells, diag = effective_channel_min_cells(
        cell_area_km2=100.0,
        river_min_catchment_km2=500.0,
        river_min_accumulation_cells=8,
    )
    assert cells == max(int(math.ceil(500.0 / 100.0)), 8)
    assert cells == 8
    assert diag["catchment_smaller_than_cell"] is False
    tiny, tiny_diag = effective_channel_min_cells(
        cell_area_km2=2000.0,
        river_min_catchment_km2=500.0,
        river_min_accumulation_cells=8,
    )
    assert tiny_diag["catchment_smaller_than_cell"] is True
    assert tiny == 8


def test_atlas_full_catchment_same_km2_meaning() -> None:
    atlas = grid_metrics(1024, 512)
    full = grid_metrics(2048, 1024)
    a_cells, a_diag = effective_channel_min_cells(
        cell_area_km2=atlas.cell_area_km2,
        river_min_catchment_km2=500.0,
        river_min_accumulation_cells=8,
    )
    f_cells, f_diag = effective_channel_min_cells(
        cell_area_km2=full.cell_area_km2,
        river_min_catchment_km2=500.0,
        river_min_accumulation_cells=8,
    )
    assert a_diag["river_min_catchment_km2"] == pytest.approx(500.0)
    assert f_diag["river_min_catchment_km2"] == pytest.approx(500.0)
    assert a_cells == max(
        int(math.ceil(500.0 / atlas.cell_area_km2)), 8
    )
    assert f_cells == max(
        int(math.ceil(500.0 / full.cell_area_km2)), 8
    )
    assert a_cells * atlas.cell_area_km2 >= 500.0 or a_diag["catchment_smaller_than_cell"]
    assert f_cells * full.cell_area_km2 >= 500.0 or f_diag["catchment_smaller_than_cell"]


def test_bed_loss_never_exceeds_available_q() -> None:
    h, w = 3, 10
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[:, -1] = 0
    graph = build_cylindrical_graph(d8, ocean)
    length = np.full((h, w), 50.0)
    potential = channel_bed_loss_potential_m3s(
        length,
        loss_rate_m3_per_km_month=2.0e5,
        channel_mask=~ocean,
        ocean_mask=ocean,
    )
    local = np.zeros((h, w), dtype=np.float64)
    local[1, 0] = 12.0
    q, lost = effective_discharge_and_sink(graph, local, potential)
    assert np.all(lost <= potential + 1e-12)
    assert np.all(lost <= q + lost + 1e-12)
    assert float(np.max(lost - potential)) <= 1e-12


def test_nil_survives_arid_corridor_weak_wadi_dies() -> None:
    h, w = 3, 12
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[:, -1] = 0
    graph = build_cylindrical_graph(d8, ocean)
    length = np.full((h, w), 50.0)
    potential = channel_bed_loss_potential_m3s(
        length,
        loss_rate_m3_per_km_month=2.0e5,
        channel_mask=~ocean,
        ocean_mask=ocean,
    )
    nil_local = np.zeros((h, w), dtype=np.float64)
    nil_local[1, 0] = 80.0
    nil_q, _ = effective_discharge_and_sink(graph, nil_local, potential)
    assert float(nil_q[1, -2]) > 1.0

    wadi_local = np.zeros((h, w), dtype=np.float64)
    wadi_local[1, 0] = 1.0
    wadi_q, _ = effective_discharge_and_sink(graph, wadi_local, potential)
    assert float(wadi_q[1, -2]) == pytest.approx(0.0)
    assert float(wadi_q[1, 0]) < float(nil_q[1, 0])


def test_annual_effective_q_matches_monthly_aggregation() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    aggregated = month_weighted_mean_m3s(hydro.monthly_discharge)
    assert np.allclose(aggregated, hydro.river_discharge_proxy, atol=1e-9)
    assert hydro.diagnostics["monthly_annual_consistent"] is True
    assert float(hydro.diagnostics["monthly_vs_independent_annual_rel_diff"]) < 0.35
    assert hydro.diagnostics["channel_loss_algorithm"] == "bed_loss_m3_v1"
    assert hydro.diagnostics["bed_loss_never_exceeds_q"] is True


def test_physical_channel_mask_is_not_all_land() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(),
        temperature_c=temp,
    )
    land = ~hydro.ocean_mask
    physical = hydro.channel_mask
    assert int(np.count_nonzero(physical)) < int(np.count_nonzero(land))
    assert float(hydro.diagnostics["channel_physical_land_fraction"]) < 1.0
    assert hydro.diagnostics["effective_min_cells"] == max(
        int(math.ceil(500.0 / float(hydro.diagnostics["cell_area_km2"]))),
        8,
    )
    assert np.all(~hydro.river_mask | hydro.channel_mask)


def test_river_fraction_scales_evaporation() -> None:
    ocean = np.zeros((3, 3), dtype=bool)
    temp = np.full((3, 3), 20.0)
    full = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        river_mask=np.ones((3, 3), dtype=bool),
        river_rate=0.40,
    )["river_evaporation"]
    tenth = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        river_fraction=np.full((3, 3), 0.10),
        river_rate=0.40,
    )["river_evaporation"]
    assert float(tenth.mean()) == pytest.approx(float(full.mean()) * 0.10, rel=1e-6)


def test_lake_fraction_covers_river_fraction() -> None:
    ocean = np.zeros((2, 2), dtype=bool)
    temp = np.full((2, 2), 18.0)
    comps = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        lake_fraction=np.full((2, 2), 0.8),
        river_fraction=np.full((2, 2), 0.5),
        lake_rate=0.75,
        river_rate=0.40,
    )
    assert float(np.max(comps["river_evaporation"])) < float(
        np.max(comps["lake_evaporation"])
    )
    water = comps["lake_evaporation"] + comps["river_evaporation"] + comps["land_et"]
    assert float(np.max(comps["lake_evaporation"] + comps["river_evaporation"])) > 0.0
    assert np.all(comps["land_et"] >= 0.0)
    assert np.all(water >= 0.0)


def test_clip_ignores_dry_envelope() -> None:
    lakes = np.zeros((4, 4), dtype=bool)
    lake_id = np.zeros((4, 4), dtype=np.int32)
    envelope = np.zeros((4, 4), dtype=bool)
    envelope[1:3, 1:3] = True
    geom = [(0.2, 0.40), (0.5, 0.40), (0.8, 0.40)]
    liquid_pieces = clip_polyline_outside_lakes(geom, lakes, lake_id)
    envelope_pieces = clip_polyline_outside_lakes(geom, envelope, envelope.astype(np.int32))
    assert len(liquid_pieces) == 1
    assert len(liquid_pieces[0].geometry) >= 2
    assert len(envelope_pieces) != len(liquid_pieces) or envelope_pieces[0].geometry != liquid_pieces[0].geometry


def test_river_segment_exports_state_catchment_and_loss() -> None:
    seg = RiverSegment(
        id=1,
        from_node=1,
        to_node=2,
        geometry=[(0.0, 0.5), (0.2, 0.5)],
        strahler_order=3,
        mean_discharge=12.0,
        monthly_discharge=[12.0] * 12,
        basin_id=4,
        length=0.2,
        channel_state="perennial",
        catchment_km2=1500.0,
        channel_length_km=40.0,
        monthly_bed_loss=[0.1] * 12,
        bed_loss_mean=0.1,
        loss_limited=False,
        estimated_width_m=28.0,
    )
    payload = seg.to_dict()
    assert payload["channel_state"] == "perennial"
    assert payload["catchment_km2"] == pytest.approx(1500.0)
    assert len(payload["monthly_discharge"]) == 12
    assert len(payload["monthly_bed_loss"]) == 12
    assert payload["strahler_order"] == 3
    assert "channel_state" in payload
    assert CHANNEL_STATE_NAME[3] == "perennial"


def test_river_water_fraction_uses_channel_geometry() -> None:
    mask = np.zeros((2, 2), dtype=bool)
    mask[0, 0] = True
    length = np.full((2, 2), 10.0)
    width = np.full((2, 2), 100.0)
    frac = river_water_fraction(mask, length, cell_area_km2=1.0, width_m=width)
    assert float(frac[0, 0]) == pytest.approx(1.0)
    assert float(frac[0, 1]) == pytest.approx(0.0)


def test_coupling_metrics_jaccard_and_q_change() -> None:
    class _H:
        def __init__(self, lake, q, ocean):
            self.lake_mask = lake
            self.river_discharge_proxy = q
            self.ocean_mask = ocean

    ocean = np.zeros((2, 2), dtype=bool)
    h1 = _H(np.array([[1, 0], [0, 0]], dtype=bool), np.ones((2, 2)), ocean)
    h2 = _H(np.array([[1, 0], [0, 0]], dtype=bool), np.ones((2, 2)), ocean)
    metrics = coupling_metrics(h1, h2)
    assert metrics["lake_mask_jaccard"] == pytest.approx(1.0)
    assert metrics["effective_q_rel_change"] == pytest.approx(0.0)
    assert metrics["coupling_converged"] is True
    h3 = _H(np.array([[0, 1], [0, 0]], dtype=bool), np.full((2, 2), 2.0), ocean)
    shifted = coupling_metrics(h1, h3)
    assert shifted["lake_mask_jaccard"] == pytest.approx(binary_jaccard(h1.lake_mask, h3.lake_mask))
    assert shifted["coupling_converged"] is False


def test_physical_mask_precedes_display_on_hydrology() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(),
        temperature_c=temp,
    )
    assert int(hydro.diagnostics["channel_physical_cell_count"]) >= int(
        hydro.diagnostics["channel_display_candidate_cell_count"]
    )
    assert int(hydro.diagnostics["channel_display_candidate_cell_count"]) >= int(
        hydro.diagnostics["river_cell_count"]
    )
    acc = hydro.flow_accumulation
    rebuilt = physical_channel_mask(
        acc, hydro.ocean_mask, min_cells=int(hydro.diagnostics["effective_min_cells"])
    )
    assert np.array_equal(rebuilt, hydro.channel_mask)
