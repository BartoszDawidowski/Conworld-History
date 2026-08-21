"""PC2 — final-Q network order and three channel tiers."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.network_tiers import (
    build_display_river_mask,
    geomorphic_channel_mask,
)
from worldsim.physical.hydrology.channels import classify_channel_states, physical_channel_mask
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.spatial.extent import SpatialExtent
from worldsim.validation.production_closure.hydrology_contract import (
    final_q_network_order_ok,
    hydrology_network_order_violations,
)
from worldsim.physical.vectorize.rivers import (
    RiverNetwork,
    RiverNode,
    RiverSegment,
    validate_river_vector_topology,
)

pytestmark = pytest.mark.pc2


def _synthetic(h: int = 24, w: int = 32):
    elev = np.linspace(80.0, 220.0, h, dtype=np.float64)[:, None] + np.linspace(
        200.0, 40.0, w, dtype=np.float64
    )
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -3:] = True
    elev[ocean] = -50.0
    extent = SpatialExtent.from_shape(h, w)
    zeros = np.zeros((h, w), dtype=np.float64)
    erosion = ErosionResult(
        extent=extent,
        elevation_before_m=elev.copy(),
        elevation_m=elev,
        erosion_delta_m=zeros,
        slope=zeros,
        rock_resistance=np.ones((h, w)),
        annual_precip_terrain=np.full((h, w), 24.0),
        ocean_mask=ocean,
        diagnostics={},
    )
    p = np.full((12, h, w), 2.0, dtype=np.float64)
    p[:, ocean] = 0.0
    moisture = MoistureResult(
        extent=extent,
        atmospheric_moisture=p.copy(),
        evaporation=np.zeros_like(p),
        precipitation=p,
        humidity=np.ones_like(p),
        orographic_lift=np.zeros_like(p),
        convective_precip=np.zeros_like(p),
        annual_precipitation=p.sum(axis=0),
        diagnostics={},
    )
    temp = np.full((12, h, w), 14.0, dtype=np.float64)
    return erosion, moisture, temp


def test_pipeline_final_q_order_ok() -> None:
    assert final_q_network_order_ok()
    assert not hydrology_network_order_violations()


def test_three_tier_masks_nested() -> None:
    erosion, moisture, temp = _synthetic()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=20.0),
        temperature_c=temp,
    )
    phys = hydro.channel_mask
    geo = hydro.geomorphic_channel_mask
    disp = hydro.display_river_mask
    assert hydro.diagnostics["hydrology_algorithm"] == "pc2_final_q_network_v1"
    assert hydro.diagnostics["final_q_network_order_ok"]
    assert np.all(disp <= phys)
    assert np.all(geo <= phys)
    assert int(np.count_nonzero(phys)) >= int(np.count_nonzero(disp))


def test_three_water_fraction_products_separate() -> None:
    erosion, moisture, temp = _synthetic()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=20.0),
        temperature_c=temp,
    )
    present = hydro.water_fraction_monthly
    open_w = hydro.open_water_fraction_monthly
    ice = hydro.lake_ice_fraction_monthly
    assert present.shape == open_w.shape == ice.shape
    assert present.shape[0] == 12
    land = ~hydro.ocean_mask
    # Present = open + ice (mutually exclusive per cell/month).
    np.testing.assert_allclose(present[:, land], open_w[:, land] + ice[:, land], atol=1e-6)


def test_display_trace_uses_physical_not_candidate_subset() -> None:
    """Pkg4: downstream walk must leave the discharge-gated candidate set."""
    h, w = 3, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    physical = np.zeros((h, w), dtype=bool)
    physical[1, :7] = True
    acc = np.zeros((h, w), dtype=np.float64)
    # Only upstream cells are high-accumulation candidates.
    acc[1, :3] = 100.0
    acc[1, 3:7] = 1.0
    q = np.zeros((h, w), dtype=np.float64)
    q[1, :3] = 10.0
    q[1, 3:7] = 0.01
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[ocean] = 0
    display, diag = build_display_river_mask(
        physical_mask=physical,
        flow_accumulation=acc,
        discharge_effective=q,
        flow_direction=d8,
        ocean_mask=ocean,
        acc_fraction=0.5,
        candidate_quantile=0.5,
    )
    assert diag["display_trace_limit"] == "physical_channel"
    # Lower physical reach must be filled even when below Q gate.
    assert bool(display[1, 5])
    assert bool(diag["display_terminal_reach_ok"])


def test_display_built_after_final_q_not_preliminary() -> None:
    violations = hydrology_network_order_violations()
    assert "display_channel_candidates used before final-Q tier builder" not in violations
    assert "build_display_river_mask runs before canonical final discharge_eff" not in violations


def test_geomorphic_uses_persistence_not_display_quantile() -> None:
    acc = np.arange(16, dtype=np.float64).reshape(4, 4)
    ocean = np.zeros((4, 4), dtype=bool)
    physical = physical_channel_mask(acc, ocean, min_cells=2)
    q = np.zeros((12, 4, 4), dtype=np.float64)
    q[:, 2, 2] = 2.0
    q[:, 1, 1] = 0.01
    state, _ = classify_channel_states(q, physical, q_min_m3s=0.05)
    geo = geomorphic_channel_mask(physical, q, state, q_min_m3s=0.05, min_wet_months=3)
    display, _ = build_display_river_mask(
        physical_mask=physical,
        flow_accumulation=acc,
        discharge_effective=q.mean(axis=0),
        flow_direction=np.full((4, 4), 1, dtype=np.uint8),
        ocean_mask=ocean,
        acc_fraction=0.25,
    )
    assert bool(geo[2, 2])
    assert not bool(geo[1, 1])


def test_vector_topology_gate_catches_invalid_terminal() -> None:
    n_conf = RiverNode(id=1, x=0.5, y=0.5, type="endorheic_sink", row=1, col=1)
    n_down = RiverNode(id=2, x=0.6, y=0.5, type="junction", row=1, col=2)
    seg = RiverSegment(
        id=1,
        from_node=1,
        to_node=2,
        geometry=[(0.5, 0.5), (0.6, 0.5)],
        strahler_order=1,
        mean_discharge=1.0,
        monthly_discharge=[1.0],
        basin_id=1,
        length=0.1,
    )
    net = RiverNetwork(nodes=[n_conf, n_down], segments=[seg])
    gate = validate_river_vector_topology(net)
    assert gate["invalid_terminal_with_outgoing_edge_count"] == 1
    assert not gate["river_vector_topology_ok"]
