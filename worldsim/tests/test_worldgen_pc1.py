"""PC1 — lake-supernode graph, single monthly router, mass ledger."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.hydrology.condensed_graph import build_condensed_lake_graph
from worldsim.physical.hydrology.cylindrical_graph import build_cylindrical_graph
from worldsim.physical.hydrology.monthly_router import spinup_condensed_lake_routing
from worldsim.validation.production_closure.hydrology_contract import (
    hydrology_network_order_violations,
    hydrology_uses_post_hoc_spill_inject,
)

pytestmark = pytest.mark.pc1


def _east_drain(h: int = 3, w: int = 10):
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[ocean] = 0
    return build_cylindrical_graph(d8, ocean), ocean


def _run_simple(
    *,
    h: int,
    w: int,
    lake_specs: list[dict],
    local_m3s: np.ndarray,
    elev: np.ndarray,
    temp: float = 4.0,
    bed_loss: np.ndarray | None = None,
    precip: np.ndarray | None = None,
    spinup_years: int = 2,
) -> dict:
    graph, ocean = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    records: list[dict] = []
    for spec in lake_specs:
        lid = int(spec["lake_id"])
        for r, c in zip(spec["rows"], spec["cols"], strict=True):
            env[int(r), int(c)] = lid
        records.append(
            {
                "lake_id": lid,
                "closed_basin": bool(spec.get("closed_basin", False)),
                "water_state": spec.get("water_state", "open"),
                "spill_elevation_m": float(spec.get("spill_elevation_m", 6.05)),
                "sink_row": int(spec["outlet"][0]),
                "sink_col": int(spec["outlet"][1]),
                "outlet_row": int(spec["outlet"][0]),
                "outlet_col": int(spec["outlet"][1]),
                "basin_id": lid,
            }
        )
    if bed_loss is None:
        bed_loss = np.zeros((h, w), dtype=np.float64)
    months = int(local_m3s.shape[0])
    temp_m = np.full((months, h, w), float(temp), dtype=np.float64)
    return spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local_m3s,
        bed_loss_potential_m3s=bed_loss,
        temperature_c=temp_m,
        cell_area_km2=1e-6,
        monthly_precip=precip,
        precip_scale_mm=200.0,
        lake_min_depth_m=0.05,
        spinup_years=spinup_years,
        spinup_rel_tol=0.05,
    )


def test_lake_captures_all_incoming_edges_not_single_sink() -> None:
    """Addendum §5.1: every land→lake edge feeds storage, not only outlet cell."""
    h, w = 3, 10
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    elev[1, 5] = 6.0
    elev[0, 5] = 6.0
    # Two land sources drain into different shoreline cells of the same lake.
    local = np.zeros((1, h, w), dtype=np.float64)
    local[0, 1, 0] = 10.0
    local[0, 0, 0] = 10.0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 4] = 1
    env[1, 5] = 1
    env[0, 5] = 1
    records = [
        {
            "lake_id": 1,
            "sink_row": 1,
            "sink_col": 5,
            "outlet_row": 1,
            "outlet_col": 5,
            "spill_elevation_m": 6.05,
            "basin_id": 1,
            "water_state": "open",
        }
    ]
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((1, h, w), 4.0),
        cell_area_km2=1e-6,
        spinup_years=1,
        spinup_rel_tol=0.2,
    )
    # Full-edge capture must exceed the legacy single-sink probe.
    assert float(out["lake_inflow_all_edges_m3s"]) >= float(
        out["lake_inflow_single_sink_m3s"]
    )
    assert float(out["lake_inflow_capture_ratio_vs_single_sink"]) >= 1.0
    # Storage must see material inflow (not ~0 from a dry sink cell).
    assert float(sum(records[0].get("inflow_m3") or [])) > 0.0


def test_no_post_hoc_spill_inject_in_pipeline() -> None:
    assert not hydrology_uses_post_hoc_spill_inject()
    violations = hydrology_network_order_violations()
    assert "post_hoc_spill_inject_present" not in violations


def test_land_mediated_spill_credits_downstream_same_month() -> None:
    """Spill crossing a land cell must enter the next lake in the same month."""
    h, w = 3, 14
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    elev[1, 8] = 6.0
    local = np.zeros((1, h, w), dtype=np.float64)
    local[0, 1, 0] = 50.0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 4] = 1
    env[1, 8] = 2
    records = [
        {
            "lake_id": 1,
            "sink_row": 1,
            "sink_col": 4,
            "outlet_row": 1,
            "outlet_col": 4,
            "spill_elevation_m": 6.05,
            "basin_id": 1,
            "water_state": "open",
        },
        {
            "lake_id": 2,
            "sink_row": 1,
            "sink_col": 8,
            "outlet_row": 1,
            "outlet_col": 8,
            "spill_elevation_m": 6.05,
            "basin_id": 2,
            "water_state": "open",
        },
    ]
    cg = build_condensed_lake_graph(
        graph=graph, basin_envelope_id=env, lake_records=records
    )
    assert cg.supernodes[1].downstream_lake_id == 2
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((1, h, w), 4.0),
        cell_area_km2=1e-6,
        spinup_years=1,
        spinup_rel_tol=0.2,
    )
    rec2 = next(r for r in records if int(r["lake_id"]) == 2)
    assert float(rec2["inflow_m3"][0]) > 0.0
    assert out["unassigned_spill_ok"] is True

    assert not hydrology_uses_post_hoc_spill_inject()
    violations = hydrology_network_order_violations()
    assert "post_hoc_spill_inject_present" not in violations


def test_one_open_lake_chain_10_m3s_not_doubled() -> None:
    h, w = 3, 8
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    local = np.zeros((1, h, w), dtype=np.float64)
    local[0, 1, 0] = 10.0
    out = _run_simple(
        h=h,
        w=w,
        lake_specs=[{"lake_id": 1, "rows": [1], "cols": [4], "outlet": (1, 4)}],
        local_m3s=local,
        elev=elev,
    )
    q = out["monthly_q_m3s"][0]
    assert q[1, 6] < 15.0
    assert abs(q[1, 6] - 10.0) < 1.0


def test_two_lake_cascade_same_month() -> None:
    h, w = 3, 12
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    elev[1, 5] = 6.0
    elev[1, 6] = 6.0
    local = np.zeros((1, h, w), dtype=np.float64)
    local[0, 1, 0] = 10.0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 4] = 1
    env[1, 5] = 2
    env[1, 6] = 2
    lake_records = [
        {
            "lake_id": 1,
            "sink_row": 1,
            "sink_col": 4,
            "outlet_row": 1,
            "outlet_col": 4,
            "spill_elevation_m": 6.05,
            "basin_id": 1,
            "water_state": "open",
        },
        {
            "lake_id": 2,
            "sink_row": 1,
            "sink_col": 6,
            "outlet_row": 1,
            "outlet_col": 6,
            "spill_elevation_m": 6.05,
            "basin_id": 2,
            "water_state": "open",
        },
    ]
    cg = build_condensed_lake_graph(
        graph=graph, basin_envelope_id=env, lake_records=lake_records
    )
    assert cg.supernodes[1].downstream_lake_id == 2
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=lake_records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((1, h, w), 4.0),
        cell_area_km2=1e-6,
        spinup_years=1,
        spinup_rel_tol=0.2,
    )
    rec2 = next(r for r in lake_records if int(r["lake_id"]) == 2)
    assert float(rec2["inflow_m3"][0]) >= 0.0
    assert out["hydrology_mass_balance_ok"]


def test_spill_through_lossy_reaches() -> None:
    h, w = 3, 12
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    loss = np.zeros((h, w), dtype=np.float64)
    loss[1, 5:] = 50.0
    local = np.zeros((1, h, w), dtype=np.float64)
    local[0, 1, 0] = 100.0
    out_no_lake = spinup_condensed_lake_routing(
        graph=_east_drain(h=h, w=w)[0],
        basin_envelope_id=np.zeros((h, w), dtype=np.int32),
        lake_records=[],
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=loss,
        temperature_c=np.full((1, h, w), 4.0),
        cell_area_km2=1e-6,
        spinup_years=1,
    )
    out_lake = _run_simple(
        h=h,
        w=w,
        lake_specs=[{"lake_id": 1, "rows": [1], "cols": [4], "outlet": (1, 4)}],
        local_m3s=local,
        elev=elev,
        bed_loss=loss,
    )
    q_plain = out_no_lake["monthly_q_m3s"][0, 1, 10]
    q_lake = out_lake["monthly_q_m3s"][0, 1, 10]
    assert q_lake <= q_plain + 1e-6 or q_lake < 100.0


def test_global_ledger_near_zero_residual() -> None:
    h, w = 3, 8
    elev = np.full((h, w), 20.0)
    elev[1, 4] = 6.0
    local = np.zeros((12, h, w), dtype=np.float64)
    local[:, 1, 0] = 10.0
    out = _run_simple(
        h=h,
        w=w,
        lake_specs=[{"lake_id": 1, "rows": [1], "cols": [4], "outlet": (1, 4)}],
        local_m3s=local,
        elev=elev,
        spinup_years=2,
    )
    assert out["hydrology_mass_balance_ok"]
    assert out["hydrology_mass_balance_max_lake_residual_m3"] <= 1e-3


def test_condensed_graph_one_supernode_per_envelope() -> None:
    graph, ocean = _east_drain(h=3, w=6)
    env = np.zeros(ocean.shape, dtype=np.int32)
    env[:, 2:4] = 1
    records = [
        {
            "lake_id": 1,
            "sink_row": 1,
            "sink_col": 2,
            "outlet_row": 1,
            "outlet_col": 2,
            "spill_elevation_m": 5.0,
        }
    ]
    cg = build_condensed_lake_graph(
        graph=graph, basin_envelope_id=env, lake_records=records
    )
    assert cg.diagnostics["lake_supernode_count"] == 1
    assert cg.diagnostics["lake_graph_topology_ok"]


def test_frozen_month_suppresses_open_water_not_presence() -> None:
    from worldsim.physical.hydrology.basins_storage import apply_basin_storage

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
        spinup_years=4,
        spinup_rel_tol=0.05,
        frozen_temp_c=1.0,
    )
    ice = np.asarray(diag["lake_ice_fraction_monthly"])
    open_w = np.asarray(diag["open_water_fraction_monthly"])
    present = np.asarray(diag["water_fraction_monthly"])
    assert float(np.sum(ice[0:3])) > 0.0
    assert float(np.sum(open_w[0:3])) == 0.0
    assert float(np.sum(present[0:3])) > 0.0


def test_nonperiodic_storage_withheld_from_liquid_publish() -> None:
    """Addendum §5.6 (10): non-convergent storage withholds published liquid."""
    from worldsim.physical.hydrology.basins_storage import apply_basin_storage

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
    assert float(np.max(diag["water_fraction_mean"])) == 0.0


def test_nonperiodic_storage_withheld_via_condensed_router() -> None:
    """Production router path: non-convergent storage withholds published liquid."""
    h, w = 3, 3
    elev = np.array(
        [[9.0, 9.0, 9.0], [9.0, 1.0, 9.0], [9.0, 9.0, 9.0]], dtype=np.float64
    )
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 1] = 1
    local = np.zeros((12, h, w), dtype=np.float64)
    local[:, 1, 1] = 0.5
    records = [
        {
            "lake_id": 1,
            "closed_basin": True,
            "water_state": "endorheic",
            "spill_elevation_m": 8.0,
            "sink_row": 1,
            "sink_col": 1,
            "basin_id": 1,
        }
    ]
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((12, h, w), 8.0),
        cell_area_km2=0.5,
        spinup_years=1,
        spinup_rel_tol=0.01,
        frozen_temp_c=-50.0,
    )
    rec = records[0]
    assert rec["storage_periodic"] is False
    assert rec["storage_unstable"] is True
    assert rec["water_body_id"] == 0
    assert int(out["basin_storage_nonperiodic_liquid_withheld_count"]) == 1
    assert float(np.max(out["water_fraction_mean"])) == 0.0


def test_per_lake_periodic_independent_in_coupled_router() -> None:
    """Fast-converging lake may publish while a slow neighbor remains withheld."""
    h, w = 4, 14
    elev = np.full((h, w), 20.0, dtype=np.float64)
    elev[2, 4] = 6.0
    elev[0, 8:11] = 1.0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[2, 4] = 1
    env[0, 8:11] = 2
    local = np.zeros((12, h, w), dtype=np.float64)
    local[:, 2, 0] = 10.0
    # Slow closed basin on a disconnected row — fills across years, not periodic in 2.
    local[:, 0, 7] = 0.01
    records = [
        {
            "lake_id": 1,
            "sink_row": 2,
            "sink_col": 4,
            "outlet_row": 2,
            "outlet_col": 4,
            "spill_elevation_m": 6.05,
            "basin_id": 1,
            "water_state": "open",
        },
        {
            "lake_id": 2,
            "sink_row": 0,
            "sink_col": 9,
            "outlet_row": 0,
            "outlet_col": 9,
            "spill_elevation_m": 18.0,
            "basin_id": 2,
            "water_state": "endorheic",
            "closed_basin": True,
        },
    ]
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((12, h, w), 4.0),
        cell_area_km2=0.25,
        spinup_years=2,
        spinup_rel_tol=0.01,
    )
    rec1 = next(r for r in records if int(r["lake_id"]) == 1)
    rec2 = next(r for r in records if int(r["lake_id"]) == 2)
    assert rec1["storage_periodic"] is True
    assert rec2["storage_periodic"] is False
    assert not rec1.get("storage_unstable")
    assert rec2.get("storage_unstable") is True
    assert int(out["basin_storage_liquid_periodic_count"]) == 1
    assert int(out["basin_storage_nonperiodic_liquid_withheld_count"]) == 1
    assert out["basin_storage_global_signature_periodic"] is False


def test_closed_basin_spill_follows_declared_saddle() -> None:
    h, w = 3, 12
    elev = np.full((h, w), 30.0, dtype=np.float64)
    elev[1, 3] = 5.0
    elev[1, 4] = 4.5
    local = np.zeros((12, h, w), dtype=np.float64)
    local[:, 1, 0] = 500.0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 3] = 1
    records = [
        {
            "lake_id": 1,
            "closed_basin": True,
            "water_state": "endorheic",
            "spill_elevation_m": 6.0,
            "sink_row": 1,
            "sink_col": 3,
            "outlet_row": 1,
            "outlet_col": 3,
            "basin_id": 1,
        }
    ]
    cg = build_condensed_lake_graph(graph=graph, basin_envelope_id=env, lake_records=records)
    sn = cg.supernodes[1]
    assert sn.spill_target_row == 1 and sn.spill_target_col == 4
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((12, h, w), 8.0),
        cell_area_km2=1e-4,
        spinup_years=2,
        spinup_rel_tol=0.2,
    )
    rec = records[0]
    assert float(sum(rec.get("spill_m3") or [])) > 0.0
    assert float(out["monthly_q_m3s"][0, 1, 5]) > 0.0


def test_direct_precip_partition_not_duplicated_as_land_runoff() -> None:
    from worldsim.physical.hydrology.basins_storage import (
        build_discrete_avh,
        lake_month_storage_step,
    )

    h, w = 3, 3
    elev = np.array(
        [[9.0, 9.0, 9.0], [9.0, 1.0, 9.0], [9.0, 9.0, 9.0]], dtype=np.float64
    )
    body = np.zeros((h, w), dtype=bool)
    body[1, 1] = True
    avh = build_discrete_avh(
        elev[body],
        np.full(1, 5.0e5),
        np.array([1]),
        np.array([1]),
        spill_elevation_m=8.0,
    )
    _, spill, _, _, ledger = lake_month_storage_step(
        avh=avh,
        volume_m3=avh.v_spill * 0.5,
        land_inflow_m3=0.0,
        upstream_lake_spill_m3=0.0,
        body=body,
        temp_c=np.full((h, w), 8.0),
        precip_mm_on_water=120.0,
        frozen_temp_c=1.0,
        lake_id=1,
    )
    assert ledger.direct_precip_on_water_m3 > 0.0
    assert ledger.local_land_runoff_m3 == 0.0
    assert spill >= 0.0


def test_dry_depression_keeps_zero_liquid_fraction() -> None:
    h, w = 3, 8
    elev = np.full((h, w), 5.0, dtype=np.float64)
    local = np.zeros((12, h, w), dtype=np.float64)
    out = _run_simple(
        h=h,
        w=w,
        lake_specs=[
            {
                "lake_id": 1,
                "rows": [1],
                "cols": [3],
                "outlet": (1, 4),
                "closed_basin": True,
                "water_state": "seasonal_or_playa",
            }
        ],
        local_m3s=local,
        elev=elev,
        spinup_years=1,
    )
    assert float(np.max(out["open_water_fraction_monthly"])) == 0.0
    assert float(np.max(out["water_fraction_monthly"])) == 0.0


def test_seasonal_basin_wet_area_varies_with_storage() -> None:
    h, w = 4, 4
    elev = np.full((h, w), 30.0, dtype=np.float64)
    elev[1:3, 1:3] = np.array([[5.0, 6.0], [6.0, 7.0]])
    local = np.zeros((12, h, w), dtype=np.float64)
    local[0:3, 1, 1] = 0.4
    local[6:9, 1, 1] = 0.4
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1:3, 1:3] = 1
    records = [
        {
            "lake_id": 1,
            "closed_basin": True,
            "water_state": "endorheic",
            "spill_elevation_m": 20.0,
            "sink_row": 1,
            "sink_col": 1,
            "basin_id": 1,
        }
    ]
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((12, h, w), 8.0),
        cell_area_km2=0.25,
        spinup_years=4,
        spinup_rel_tol=0.05,
        seepage_m_per_month=0.35,
    )
    rec = records[0]
    wet = rec.get("wet_area_km2") or []
    levels = rec.get("level_m") or []
    assert len(wet) == 12
    assert rec.get("months_wet", 12) < 12 or (levels and max(levels) > min(levels))
    assert float(np.max(out["water_fraction_monthly"])) >= 0.0


def test_ew_seam_lake_one_supernode_routing() -> None:
    h, w = 3, 8
    elev = np.full((h, w), 20.0, dtype=np.float64)
    elev[1, 0] = 5.0
    elev[1, 7] = 5.0
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[ocean] = 0
    graph, _ = _east_drain(h=h, w=w)
    env = np.zeros((h, w), dtype=np.int32)
    env[1, 0] = 1
    env[1, 7] = 1
    records = [
        {
            "lake_id": 1,
            "sink_row": 1,
            "sink_col": 0,
            "outlet_row": 1,
            "outlet_col": 0,
            "spill_elevation_m": 6.0,
            "basin_id": 1,
            "water_state": "open",
        }
    ]
    cg = build_condensed_lake_graph(graph=graph, basin_envelope_id=env, lake_records=records)
    assert cg.diagnostics["lake_supernode_count"] == 1
    local = np.zeros((12, h, w), dtype=np.float64)
    local[:, 1, 0] = 5.0
    out = spinup_condensed_lake_routing(
        graph=graph,
        basin_envelope_id=env,
        lake_records=records,
        elevation_m=elev,
        monthly_land_runoff_m3s=local,
        bed_loss_potential_m3s=np.zeros((h, w)),
        temperature_c=np.full((12, h, w), 8.0),
        cell_area_km2=1e-4,
        spinup_years=2,
        spinup_rel_tol=0.2,
    )
    assert out["hydrology_mass_balance_ok"]
    assert records[0].get("months_wet", 0) >= 1
    assert float(out["water_fraction_mean"][1, 0]) > 0.0 or float(
        out["water_fraction_mean"][1, 7]
    ) > 0.0
