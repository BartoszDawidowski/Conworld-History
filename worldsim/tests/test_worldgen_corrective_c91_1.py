"""C9.1.1 — lake-aware routing: through-flow counted once; spill is not added twice."""

from __future__ import annotations

import numpy as np

from worldsim.physical.hydrology.basins_storage import apply_basin_storage
from worldsim.physical.hydrology.cylindrical_graph import (
    accumulate_weights,
    accumulate_weights_lake_aware,
    build_cylindrical_graph,
    effective_discharge_and_sink,
    first_downstream_outside_lake,
)
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days


def _east_drain_graph(h: int = 3, w: int = 8):
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)  # east
    d8[ocean] = 0
    return build_cylindrical_graph(d8, ocean), ocean


def test_through_lake_flow_is_not_transmitted() -> None:
    graph, ocean = _east_drain_graph()
    lake_id = np.zeros(ocean.shape, dtype=np.int32)
    lake_id[:, 3:5] = 1
    local = np.zeros(ocean.shape, dtype=np.float64)
    local[1, 0] = 10.0
    sink = np.zeros(ocean.shape, dtype=np.float64)
    q_open, _ = effective_discharge_and_sink(graph, local, sink)
    q_lake, _ = effective_discharge_and_sink(graph, local, sink, lake_id=lake_id)
    assert q_open[1, 6] == 10.0
    assert q_lake[1, 4] == 10.0
    assert q_lake[1, 6] == 0.0


def test_spill_inject_outside_envelope_does_not_double() -> None:
    graph, ocean = _east_drain_graph()
    lake_id = np.zeros(ocean.shape, dtype=np.int32)
    lake_id[:, 3:5] = 1
    local = np.zeros(ocean.shape, dtype=np.float64)
    local[1, 0] = 10.0
    sink = np.zeros(ocean.shape, dtype=np.float64)
    q, _ = effective_discharge_and_sink(graph, local, sink, lake_id=lake_id)
    loc = first_downstream_outside_lake(graph, 1, 4, lake_id, 1)
    assert loc == (1, 5)
    inject_new = np.zeros(ocean.shape, dtype=np.float64)
    inject_new[loc] = 10.0
    q_final = q + accumulate_weights_lake_aware(graph, inject_new, lake_id=lake_id)
    # Pre-C9.1.1: through-flow already at the outlet, then spill injected *inside* the lake.
    q_old, _ = effective_discharge_and_sink(graph, local, sink)
    inject_old = np.zeros(ocean.shape, dtype=np.float64)
    inject_old[1, 4] = 10.0
    doubled = q_old + accumulate_weights(graph, inject_old)
    assert q_final[1, 6] == 10.0
    assert doubled[1, 6] == 20.0


def test_storage_plus_spill_on_synthetic_10_m3s() -> None:
    """10 m³/s into a spilling lake ⇒ ≈10 m³/s below, not 20."""
    graph, ocean = _east_drain_graph()
    h, w = ocean.shape
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[1, 4] = 1
    local = np.zeros((h, w), dtype=np.float64)
    local[1, 0] = 10.0
    sink = np.zeros((h, w), dtype=np.float64)
    q, _ = effective_discharge_and_sink(graph, local, sink, lake_id=lake_id)
    monthly = np.repeat(q[np.newaxis, ...], 12, axis=0)
    rec = {
        "lake_id": 1,
        "closed_basin": False,
        "water_state": "open",
        "spill_elevation_m": 6.05,
        "sink_row": 1,
        "sink_col": 4,
        "outlet_row": 1,
        "outlet_col": 4,
        "basin_id": 1,
    }
    apply_basin_storage(
        graph=graph,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=monthly,
        temperature_c=np.full((12, h, w), 4.0),
        cell_area_km2=1e-6,
        spinup_years=4,
        lake_min_depth_m=0.05,
    )
    seconds = float(month_days(0)) * SECONDS_PER_DAY
    spilled = float((rec.get("spill_m3") or [0.0])[0])
    spill_m3s = spilled / max(seconds, 1.0)
    loc = first_downstream_outside_lake(graph, 1, 4, lake_id, 1)
    inject = np.zeros((h, w), dtype=np.float64)
    inject[loc] = spill_m3s
    q_below = q + accumulate_weights_lake_aware(graph, inject, lake_id=lake_id)
    assert loc == (1, 5)
    assert q[1, 4] == 10.0
    assert abs(q_below[1, 6] - 10.0) < 0.5
    assert q_below[1, 6] < 15.0
