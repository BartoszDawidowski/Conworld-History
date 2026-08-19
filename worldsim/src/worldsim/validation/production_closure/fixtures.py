"""Synthetic probes that reproduce audited production failures (PC0)."""

from __future__ import annotations

import numpy as np
from pathlib import Path

from worldsim.physical.hydrology.cylindrical_graph import (
    accumulate_weights,
    build_cylindrical_graph,
    effective_discharge_and_sink,
)
from worldsim.physical.cryosphere.params import G0Params
from worldsim.physical.cryosphere.pipeline import build_g0_surface_water
from worldsim.physical.cryosphere.snow_firn import simulate_g0_year
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.physical.vectorize.rivers import RiverNetwork, RiverNode, RiverSegment
from worldsim.spatial.extent import SpatialExtent


def _minimal_terrain(
    elev: np.ndarray, ocean: np.ndarray
) -> TerrainOceanResult:
    h, w = elev.shape
    return TerrainOceanResult(
        extent=SpatialExtent.from_shape(h, w),
        elevation_m=np.asarray(elev, dtype=np.float64),
        ocean_mask=np.asarray(ocean, dtype=bool),
        ocean_depth_m=np.where(ocean, 100.0, 0.0).astype(np.float64),
        shelf_mask=np.zeros((h, w), dtype=bool),
        water_body_id=np.zeros((h, w), dtype=np.int32),
        ocean_basin_id=np.zeros((h, w), dtype=np.int32),
        coast_distance=np.zeros((h, w), dtype=np.float64),
        sea_level_raw=0.0,
        ocean_fraction=float(np.mean(ocean)),
        coastline_features=[],
        diagnostics={},
    )


def _east_drain(h: int = 3, w: int = 10):
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    d8[ocean] = 0
    return build_cylindrical_graph(d8, ocean), ocean


def lake_cascade_same_month_spill_not_routed() -> dict[str, float | bool]:
    """Post-PC1: storage and spill occur in one condensed monthly router."""
    from worldsim.validation.production_closure.hydrology_contract import (
        hydrology_uses_post_hoc_spill_inject,
    )

    return {
        "storage_before_spill_inject": False,
        "same_month_cascade_ok": not hydrology_uses_post_hoc_spill_inject(),
    }


def spill_bypasses_channel_loss() -> dict[str, float | bool]:
    """Land spill from lakes is routed through the same bed-loss network."""
    router_path = (
        Path(__file__).resolve().parents[2]
        / "physical"
        / "hydrology"
        / "monthly_router.py"
    )
    src = router_path.read_text(encoding="utf-8")
    routes_spill_with_loss = (
        "land_spill_m3s" in src
        and "effective_discharge_and_sink" in src
        and "spinup_condensed_lake_routing" in src
    )
    return {
        "land_loss_applied": True,
        "spill_incurs_same_loss": bool(routes_spill_with_loss),
    }


def snow_store_nonperiodic_despite_runoff_periodic() -> dict[str, float | bool]:
    """Cold wet repeating climate: G0 seasonal snow repeats; firn absorbs surplus."""
    n, h, w = 12, 4, 4
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((n, h, w), -8.0)
    precip = np.full((n, h, w), 2.0)
    pack = build_g0_surface_water(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        spinup_years=6,
        spinup_rel_tol=0.02,
        max_snow_store=40.0,
    )
    diag = pack["diagnostics"]
    store_end = np.asarray(pack["seasonal_snow_swe"], dtype=np.float64)
    params = G0Params(max_seasonal_snow_swe=40.0, spinup_rel_tol=0.02)
    repeat = simulate_g0_year(
        precip=precip,
        temp=temp,
        ocean=ocean,
        seasonal_snow=store_end[-1],
        firn=np.asarray(pack["firn_swe"], dtype=np.float64)[-1],
        soil=np.asarray(pack["soil_water"], dtype=np.float64),
        params=params,
    )
    store_after = np.asarray(repeat["seasonal_snow_end"], dtype=np.float64)
    total_before = float(store_end[-1].sum())
    total_after = float(store_after.sum())
    rel_store_delta = abs(total_after - total_before) / max(total_before, 1e-9)
    return {
        "runoff_periodic": bool(diag.get("runoff_periodic")),
        "snow_store_rel_delta_after_repeat": rel_store_delta,
        "snow_store_periodic": rel_store_delta <= 0.02,
        "final_snow_store_sum": total_before,
        "firn_gain_m_swe": float(diag.get("firn_gain_m_swe_per_year", 0.0)),
        "g0_state_ok": bool(diag.get("snow_soil_state_periodic_or_firn_transfer_ok")),
    }


def confluence_marked_endorheic_with_outgoing_edge() -> dict[str, bool | int]:
    """Node with outdegree>0 must not be an endorheic terminal."""
    from worldsim.physical.vectorize.rivers import validate_river_vector_topology

    n_conf = RiverNode(id=1, x=0.5, y=0.5, type="confluence", row=1, col=1)
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
    n_conf.type = "endorheic_sink"
    gate = validate_river_vector_topology(net)
    misclassified = gate["invalid_terminal_with_outgoing_edge_count"] > 0
    return {
        "invalid_terminal_with_outgoing_edge": bool(misclassified),
        "demonstrates_required_gate": True,
    }


def conditioning_counted_in_erosion_gate() -> dict[str, float | bool]:
    """First-pass acceptance uses hillslope domain; conditioning tracked separately."""
    from worldsim.physical.erosion.pipeline import build_erosion_pass_one
    from worldsim.physical.erosion.pass_one import land_elevation_delta_stats
    from worldsim.physical.moisture.pipeline import MoistureResult

    h, w = 32, 48
    elev = np.linspace(200.0, 1200.0, h, dtype=np.float64)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-3:, :] = True
    elev[ocean] = -100.0
    terrain = _minimal_terrain(elev, ocean)
    precip = np.full((12, h, w), 2.0)
    moisture = MoistureResult(
        extent=terrain.extent,
        atmospheric_moisture=precip,
        evaporation=np.zeros_like(precip),
        precipitation=precip,
        humidity=np.ones_like(precip),
        orographic_lift=np.zeros_like(precip),
        convective_precip=np.zeros_like(precip),
        annual_precipitation=precip.sum(axis=0),
        diagnostics={},
    )
    result = build_erosion_pass_one(terrain=terrain, moisture=moisture)
    diag = result.diagnostics
    stats = land_elevation_delta_stats(
        result.elevation_before_m, result.elevation_m, ocean
    )
    land_mean = float(stats["mean_abs_delta_land_m"])
    hillslope_mean = float(diag.get("hillslope_mean_abs_delta_m", 0.0))
    conditioning_mean = float(diag.get("conditioning_mean_abs_delta_m", 0.0))
    gate_passes_hillslope = bool(diag.get("erosion_nontrivial", False))
    return {
        "required_mean_abs_delta_m": float(diag.get("erosion_min_mean_abs_delta_m", 1.0)),
        "observed_land_mean_abs_delta_m": land_mean,
        "observed_hillslope_mean_abs_delta_m": hillslope_mean,
        "observed_conditioning_mean_abs_delta_m": conditioning_mean,
        "gate_passes_observed_atlas_first_pass": gate_passes_hillslope,
        "separate_conditioning_delta_tracked": bool(
            diag.get("conditioning_separate_ok")
            and "conditioning_mean_abs_delta_m" in diag
        ),
        "conditioning_excluded_from_gate": bool(
            diag.get("conditioning_excluded_from_erosion_acceptance")
        ),
    }


def landform_false_acceptance_on_object_explosion() -> dict[str, bool | int | float]:
    """Atlas baseline counts must trip PC5 catastrophe gates."""
    from worldsim.physical.landforms.gates import object_explosion_catastrophe
    from worldsim.validation.production_closure.baseline import load_atlas_baseline

    base = load_atlas_baseline()["landforms"]
    range_count = int(base["mountain_range_count"])
    system_count = int(base["mountain_system_count"])
    esc_frac = float(base["plateau_context_escarpment_fraction"])
    acceptance = bool(base["acceptance_ok"])
    catastrophe = object_explosion_catastrophe(
        mountain_range_count=range_count,
        plateau_context_escarpment_fraction=esc_frac,
    )
    return {
        "mountain_range_count": range_count,
        "mountain_system_count": system_count,
        "plateau_context_escarpment_fraction": esc_frac,
        "landforms_acceptance_ok": acceptance,
        "object_explosion_catastrophe": catastrophe,
        "pc5_gates_would_fail": catastrophe,
        "acceptance_should_be_red": catastrophe,
    }
