"""PR-6 — monthly runoff/snow, Q-aware wadis, lake states."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from worldsim.physical.hydrology.cylindrical_graph import build_cylindrical_graph
from worldsim.physical.hydrology.lakes_meta import build_lake_records, classify_lake_body
from worldsim.physical.hydrology.rivers import gate_river_mask_by_discharge
from worldsim.physical.hydrology.runoff import build_monthly_runoff, partition_rain_snow
from worldsim.physical.vectorize.lakes import build_lakes
from worldsim.spatial.extent import SpatialExtent


def test_cold_precip_is_snow_not_immediate_runoff() -> None:
    precip = np.full((12, 8, 8), 2.0)
    temp = np.full((12, 8, 8), -10.0)
    ocean = np.zeros((8, 8), dtype=bool)
    out = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        melt_factor_per_c=0.05,
    )
    # January: mostly snow store, little melt/runoff
    assert float(out["snowfall"][0].mean()) > float(out["rain"][0].mean())
    assert float(out["runoff"][0].mean()) < float(out["snowfall"][0].mean()) * 0.5
    assert float(out["snow_store"][0].mean()) > 0.5


def test_thaw_releases_delayed_melt_pulse() -> None:
    precip = np.zeros((6, 6, 6), dtype=np.float64)
    precip[0] = 5.0  # snowfall in month 0
    temp = np.full((6, 6, 6), -5.0)
    temp[3:] = 8.0  # thaw from month 3
    ocean = np.zeros((6, 6), dtype=bool)
    out = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        melt_factor_per_c=0.2,
    )
    assert float(out["runoff"][0].mean()) < float(out["runoff"][3].mean())
    assert float(out["melt"][3].mean()) > float(out["melt"][0].mean())


def test_wadi_extinction_fixture() -> None:
    h, w = 3, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    candidate = np.zeros((h, w), dtype=bool)
    candidate[1, :6] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    q = np.zeros((h, w), dtype=np.float64)
    q[1, :6] = [100, 80, 20, 0, 0, 0]
    gated, diag = gate_river_mask_by_discharge(
        candidate, q, d8, ocean, min_effective_discharge=15.0
    )
    assert list(gated[1, :6].astype(int)) == [1, 1, 1, 0, 0, 0]
    assert diag["river_inherit_downstream"] is False


def test_nil_corridor_survives_when_q_remains() -> None:
    h, w = 3, 10
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    candidate = np.ones((h, w), dtype=bool) & ~ocean
    d8 = np.full((h, w), 1, dtype=np.uint8)
    q = np.zeros((h, w), dtype=np.float64)
    q[1, :9] = [50, 45, 40, 35, 30, 25, 20, 18, 16]  # stays above thr through arid
    gated, _ = gate_river_mask_by_discharge(
        candidate, q, d8, ocean, min_effective_discharge=15.0
    )
    assert bool(gated[1, 8])


def test_open_vs_endorheic_lake_classification() -> None:
    h, w = 10, 12
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-1, :] = True
    d8 = np.full((h, w), 4, dtype=np.uint8)  # south
    d8[-1, :] = 0
    # Closed pit lake in NW
    elev = np.full((h, w), 100.0)
    elev[2:4, 2:4] = 40.0
    d8[2:4, 2:4] = 0  # pits
    # Open lake that drains south to ocean
    elev[2:4, 7:9] = 50.0
    d8[2:4, 7:9] = 4
    graph = build_cylindrical_graph(d8, ocean)
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[2:4, 2:4] = 1
    lake_id[2:4, 7:9] = 2
    q = np.full((h, w), 5.0)
    temp = np.full((h, w), 12.0)
    precip = np.full((h, w), 2.0)
    recs = build_lake_records(
        graph=graph,
        lake_id=lake_id,
        lake_mask=lake_id > 0,
        elevation_m=elev,
        basin_id=np.ones((h, w), dtype=np.int32),
        discharge_effective=q,
        temperature_annual_c=temp,
        precip_annual=precip,
    )
    by_id = {r["lake_id"]: r for r in recs}
    assert by_id[1]["closed_basin"] is True
    assert by_id[1]["water_state"] in ("endorheic", "seasonal_or_playa")
    assert by_id[2]["closed_basin"] is False
    assert by_id[2]["water_state"] == "open"


def test_frozen_lake_state() -> None:
    h, w = 6, 6
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-1, :] = True
    d8 = np.zeros((h, w), dtype=np.uint8)
    elev = np.full((h, w), 80.0)
    elev[1:3, 1:3] = 30.0
    graph = build_cylindrical_graph(d8, ocean)
    body = np.zeros((h, w), dtype=bool)
    body[1:3, 1:3] = True
    rec = classify_lake_body(
        graph=graph,
        lake_mask=body,
        lake_id_value=1,
        elevation_m=elev,
        discharge_effective=np.ones((h, w)),
        temperature_annual_c=np.full((h, w), -5.0),
        precip_annual=np.ones((h, w)),
        frozen_temp_c=1.0,
    )
    assert rec["water_state"] == "frozen_or_ice_covered"


def test_lake_metadata_round_trip(tmp_path: Path) -> None:
    extent = SpatialExtent.from_shape(8, 8)
    lake_id = np.zeros((8, 8), dtype=np.int32)
    lake_id[2:5, 2:5] = 1
    elev = np.full((8, 8), 50.0)
    basin = np.ones((8, 8), dtype=np.int32)
    records = [
        {
            "lake_id": 1,
            "water_state": "open",
            "closed_basin": False,
            "spill_elevation_m": 55.0,
            "surface_elevation_m": 48.0,
            "mean_effective_inflow": 12.0,
            "basin_id": 1,
        }
    ]
    lakes = build_lakes(
        lake_id=lake_id,
        lake_mask=lake_id > 0,
        elevation_m=elev,
        basin_id=basin,
        extent=extent,
        lake_records=records,
    )
    assert lakes
    assert lakes[0].water_state == "open"
    assert lakes[0].closed_basin is False
    assert lakes[0].spill_elevation == 55.0
    path = tmp_path / "lakes.json"
    path.write_text(
        json.dumps({"lakes": [lakes[0].to_dict()]}, indent=2) + "\n",
        encoding="utf-8",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["lakes"][0]["water_state"] == "open"
    assert data["lakes"][0]["outlet_river_id"] is None


def test_partition_rain_snow_band() -> None:
    precip = np.full((4, 4), 10.0)
    rain, snow = partition_rain_snow(precip, np.full((4, 4), 0.0), snow_threshold_c=0.0)
    assert float(rain.mean() + snow.mean()) == pytest.approx(10.0)
    assert float(snow.mean()) > 0.0
