"""C1 — discrete A–V–h lake storage; liquid footprint is not the fill envelope."""

from __future__ import annotations

import numpy as np

from worldsim.physical.hydrology.basins_storage import (
    STORAGE_CURVE_DISCRETE,
    apply_basin_storage,
    build_discrete_avh,
    liquid_id_from_fraction,
)
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days
from worldsim.physical.hydrology.lakes_meta import LIQUID_WATER_STATES
from worldsim.physical.hydrology.pipeline import HydrologyParams, build_hydrology
from test_physical_realism_cr7 import _synthetic_hydro_inputs


def _staircase_avh():
    """Three cells at 0, 1, 2 m; spill at 4 m; 1 m² each."""
    z = np.array([0.0, 1.0, 2.0])
    a = np.array([1.0, 1.0, 1.0])
    rows = np.array([0, 0, 0])
    cols = np.array([0, 1, 2])
    return build_discrete_avh(z, a, rows, cols, spill_elevation_m=4.0)


def test_avh_monotonic_area_with_storage() -> None:
    avh = _staircase_avh()
    prev_a = -1.0
    prev_z = -1.0
    for v in np.linspace(0.0, avh.v_spill, 25):
        z, area = avh.lookup(float(v))
        assert area + 1e-12 >= prev_a
        assert z + 1e-12 >= prev_z
        prev_a = area
        prev_z = z
    assert avh.curve == STORAGE_CURVE_DISCRETE
    assert avh.v_spill > 0.0


def test_raster_wet_area_matches_lookup_within_one_cell() -> None:
    avh = _staircase_avh()
    shape = (1, 3)
    cell_area_m2 = 1.0
    for v in (0.0, 0.4, avh.v_spill * 0.5, avh.v_spill):
        _z, area = avh.lookup(v)
        frac = avh.raster_wet_fraction(v, shape)
        raster_area = float(np.sum(frac)) * cell_area_m2
        assert abs(raster_area - area) <= cell_area_m2 + 1e-9


def test_empty_closed_basin_remains_dry() -> None:
    h, w = 6, 6
    elev = np.full((h, w), 20.0)
    elev[2:5, 2:5] = np.array(
        [[12.0, 11.0, 12.0], [11.0, 8.0, 11.0], [12.0, 11.0, 12.0]]
    )
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[2:5, 2:5] = 1
    q = np.zeros((12, h, w), dtype=np.float64)
    temp = np.full((12, h, w), 14.0)
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 15.0,
        "sink_row": 3,
        "sink_col": 3,
        "basin_id": 9,
    }
    diag = apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=1.0,
        spinup_years=3,
    )
    assert rec["water_state"] == "seasonal_or_playa"
    assert rec["months_wet"] == 0
    assert rec["water_body_id"] == 0
    assert rec["envelope_area_km2"] == 9.0
    assert float(np.max(diag["water_fraction_mean"])) == 0.0


def test_open_basin_below_spill_has_no_outflow() -> None:
    avh = _staircase_avh()
    h, w = 1, 3
    elev = np.array([[0.0, 1.0, 2.0]])
    lake_id = np.ones((h, w), dtype=np.int32)
    # Tiny inflow: cannot reach spill.
    q = np.full((12, h, w), 1e-12)
    temp = np.full((12, h, w), 5.0)
    rec = {
        "lake_id": 1,
        "closed_basin": False,
        "water_state": "open",
        "has_ocean_outlet": False,
        "spill_elevation_m": 4.0,
        "sink_row": 0,
        "sink_col": 0,
        "basin_id": 1,
        "outlet_row": 0,
        "outlet_col": 2,
    }
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=1e-6,
        spinup_years=2,
        frozen_temp_c=-50.0,
    )
    assert rec["v_spill_m3"] == avh.v_spill or rec["v_spill_m3"] > 0.0
    assert max(rec["storage_m3"]) <= rec["v_spill_m3"] + 1e-6
    assert all(s == 0.0 or s < 1e-6 for s in rec["spill_m3"])


def test_open_basin_above_spill_routes_exact_excess() -> None:
    h, w = 1, 3
    elev = np.array([[0.0, 1.0, 2.0]])
    lake_id = np.ones((h, w), dtype=np.int32)
    rec = {
        "lake_id": 1,
        "closed_basin": False,
        "water_state": "open",
        "spill_elevation_m": 4.0,
        "sink_row": 0,
        "sink_col": 0,
        "basin_id": 1,
        "outlet_row": 0,
        "outlet_col": 2,
    }
    z = elev.reshape(-1)
    avh = build_discrete_avh(z, np.ones(3), np.zeros(3, dtype=int), np.arange(3), spill_elevation_m=4.0)
    days = float(month_days(0))
    # First month: dump 2× spill volume into the sink cell.
    q = np.zeros((12, h, w), dtype=np.float64)
    q[0, 0, 0] = (2.0 * avh.v_spill) / (days * SECONDS_PER_DAY)
    temp = np.full((12, h, w), 0.0)  # no PET
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=1e-6,
        spinup_years=1,
        frozen_temp_c=-50.0,
        seepage_m_per_month=0.0,
    )
    assert rec["storage_m3"][0] <= rec["v_spill_m3"] + 1e-6
    assert abs(rec["spill_m3"][0] + rec["storage_m3"][0] - 2.0 * avh.v_spill) < 1e-3 * max(
        avh.v_spill, 1.0
    )


def test_evaporation_cannot_exceed_storage() -> None:
    h, w = 1, 2
    elev = np.array([[0.0, 1.0]])
    lake_id = np.ones((h, w), dtype=np.int32)
    q = np.zeros((12, h, w))
    q[0, 0, 0] = 1e-4
    temp = np.full((12, h, w), 30.0)
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 5.0,
        "sink_row": 0,
        "sink_col": 0,
        "basin_id": 1,
    }
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=1.0,
        spinup_years=2,
    )
    assert min(rec["storage_m3"]) >= -1e-9
    for m in range(12):
        assert rec["evap_loss_m3"][m] <= rec["inflow_m3"][m] + rec["storage_m3"][m] + 1e-6


def test_frozen_month_suppresses_liquid_evaporation() -> None:
    h, w = 1, 2
    elev = np.array([[0.0, 1.0]])
    lake_id = np.ones((h, w), dtype=np.int32)
    q = np.zeros((12, h, w))
    q[:, 0, 0] = 1.0
    temp = np.full((12, h, w), -10.0)
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 5.0,
        "sink_row": 0,
        "sink_col": 0,
        "basin_id": 1,
    }
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=0.01,
        spinup_years=2,
        frozen_temp_c=1.0,
    )
    assert rec["months_frozen"] == 12
    assert rec["ice_regime"] == "perennially_frozen"
    assert rec["water_state"] == "frozen_or_ice_covered"
    assert all(v == 0.0 for v in rec["evap_loss_m3"])
    assert rec["water_body_id"] == 0


def test_seasonal_basin_expands_and_contracts() -> None:
    h, w = 4, 4
    elev = np.full((h, w), 30.0)
    elev[1:3, 1:3] = np.array([[5.0, 6.0], [6.0, 7.0]])
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_id[1:3, 1:3] = 1
    q = np.zeros((12, h, w))
    q[:3, 1, 1] = 0.2
    temp = np.full((12, h, w), 0.0)
    rec = {
        "lake_id": 1,
        "closed_basin": True,
        "water_state": "endorheic",
        "spill_elevation_m": 20.0,
        "sink_row": 1,
        "sink_col": 1,
        "basin_id": 2,
    }
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=0.25,
        spinup_years=4,
        frozen_temp_c=-50.0,
        seepage_m_per_month=0.4,
    )
    wet = rec["wet_area_km2"]
    assert rec["hydroperiod"] == "seasonal" or rec["months_wet"] < 12
    assert rec["months_wet"] >= 1
    assert rec["months_wet"] < 12
    assert max(wet) > min(wet)


def test_ew_seam_basin_is_one_avh_object() -> None:
    h, w = 4, 8
    z = np.array([1.0, 1.0, 2.0, 2.0])
    a = np.ones(4)
    rows = np.array([1, 1, 1, 1])
    cols = np.array([0, 7, 1, 6])
    avh = build_discrete_avh(z, a, rows, cols, spill_elevation_m=5.0)
    frac = avh.raster_wet_fraction(avh.v_spill, (h, w))
    assert frac[1, 0] > 0.0 and frac[1, 7] > 0.0
    assert avh.order.size == 4


def test_storage_periodic_on_repeating_climate() -> None:
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
    apply_basin_storage(
        graph=None,
        lake_id=lake_id,
        lake_records=[rec],
        elevation_m=elev,
        monthly_q_m3s=q,
        temperature_c=temp,
        cell_area_km2=0.5,
        spinup_years=8,
        spinup_rel_tol=0.05,
        frozen_temp_c=-50.0,
    )
    assert rec["storage_periodic"] is True
    assert rec["storage_spinup_years_used"] <= 8


def test_build_hydrology_raster_matches_reported_wet_area() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs(
        precip=2.0, basin_precip=3.0, temp_c=14.0
    )
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0, lake_storage_spinup_years=4),
        temperature_c=temp,
    )
    assert hydro.basin_envelope_id.shape == hydro.lake_mask.shape
    envelope = int(np.count_nonzero(hydro.basin_envelope_id > 0))
    liquid = int(np.count_nonzero(hydro.lake_mask))
    assert envelope >= liquid
    reported = float(hydro.diagnostics["lake_reported_wet_area_km2"])
    rastered = float(hydro.diagnostics["lake_raster_wet_area_km2"])
    if reported > 1e-6:
        ratio = rastered / reported
        assert 0.95 <= ratio <= 1.05
    for rec in hydro.lake_records:
        assert "envelope_area_km2" in rec
        if rec.get("water_state") in LIQUID_WATER_STATES:
            assert rec["mean_wet_area_km2"] <= rec["envelope_area_km2"] + 1e-6
    lid, mask = liquid_id_from_fraction(
        hydro.basin_envelope_id, hydro.water_fraction_mean, hydro.lake_records
    )
    assert np.array_equal(mask, hydro.lake_mask)
    assert np.array_equal(lid > 0, hydro.lake_id > 0)
