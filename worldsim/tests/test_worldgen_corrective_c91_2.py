"""C9.1.2 — periodic snow/soil runoff and lake storage; monthly water/ice fractions."""

from __future__ import annotations

import numpy as np

from worldsim.physical.hydrology.basins_storage import apply_basin_storage
from worldsim.physical.hydrology.runoff import build_monthly_runoff


def test_published_runoff_repeats_within_epsilon() -> None:
    precip = np.full((12, 6, 6), 1.5)
    temp = np.full((12, 6, 6), 18.0)
    ocean = np.zeros((6, 6), dtype=bool)
    out = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        spinup_years=8,
        spinup_rel_tol=0.01,
    )
    diag = out["diagnostics"]
    assert diag["runoff_algorithm"] == "soil_bucket_periodic_v1"
    assert diag["runoff_periodic"] is True
    assert float(diag["runoff_published_vs_repeat_rel_delta"]) <= 0.01
    assert float(diag["runoff_year2_vs_year1_rel_delta"]) > float(
        diag["runoff_published_vs_repeat_rel_delta"]
    )


def test_cold_start_year_is_not_the_published_year() -> None:
    precip = np.full((12, 6, 6), 1.5)
    temp = np.full((12, 6, 6), 18.0)
    ocean = np.zeros((6, 6), dtype=bool)
    cold = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        spinup_years=1,
        spinup_rel_tol=0.01,
    )
    spun = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        spinup_years=8,
        spinup_rel_tol=0.01,
    )
    assert cold["diagnostics"]["runoff_periodic"] is False
    assert spun["diagnostics"]["runoff_periodic"] is True
    rel = float(
        np.mean(np.abs(np.asarray(cold["runoff"]) - np.asarray(spun["runoff"])))
        / max(float(np.mean(np.abs(np.asarray(cold["runoff"])))), 1e-12)
    )
    assert rel > 0.01


def test_nonperiodic_liquid_lake_is_withheld() -> None:
    h, w = 3, 3
    elev = np.array(
        [[9.0, 9.0, 9.0], [9.0, 1.0, 9.0], [9.0, 9.0, 9.0]], dtype=np.float64
    )
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[1, 1] = 1
    q = np.zeros((12, h, w))
    q[:, 1, 1] = 0.5
    temp = np.full((12, h, w), 8.0)
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 8.0,
        "sink_row": 1,
        "sink_col": 1,
        "basin_id": 1,
    }
    diag = apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=0.5,
        spinup_years=1,
        spinup_rel_tol=0.01,
        frozen_temp_c=-50.0,
    )
    assert rec["storage_periodic"] is False
    assert rec["storage_unstable"] is True
    assert rec["water_body_id"] == 0
    assert int(diag["basin_storage_nonperiodic_liquid_withheld_count"]) == 1
    assert int(diag["basin_storage_nonperiodic_liquid_published_count"]) == 0
    assert float(np.max(diag["water_fraction_mean"])) == 0.0


def test_periodic_lake_publishes_monthly_liquid_and_ice() -> None:
    h, w = 3, 3
    elev = np.array(
        [[9.0, 9.0, 9.0], [9.0, 1.0, 9.0], [9.0, 9.0, 9.0]], dtype=np.float64
    )
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[1, 1] = 1
    q = np.zeros((12, h, w))
    q[:, 1, 1] = 0.5
    temp = np.full((12, h, w), 8.0)
    temp[0:3] = -10.0
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 8.0,
        "sink_row": 1,
        "sink_col": 1,
        "basin_id": 1,
    }
    diag = apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=0.5,
        spinup_years=8,
        spinup_rel_tol=0.05,
        frozen_temp_c=1.0,
    )
    assert rec["fractions_are_monthly"] is True
    assert len(rec["liquid_fraction_monthly"]) == 12
    assert len(rec["ice_fraction_monthly"]) == 12
    assert rec["storage_periodic"] is True
    ice = np.asarray(diag["ice_fraction_monthly"])
    water = np.asarray(diag["water_fraction_monthly"])
    assert ice.shape == (12, h, w)
    assert water.shape == (12, h, w)
    assert float(np.sum(ice[0:3])) > 0.0
    assert float(np.sum(water[0:3])) == 0.0
    assert diag["lake_fractions_are_monthly"] is True
