"""PC0 — reproducible production failures; no physics or default changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.spatial.canonical_acceptance import aggregate_canonical_acceptance
from worldsim.validation.production_closure.baseline import load_atlas_baseline
from worldsim.validation.production_closure.fixtures import (
    conditioning_counted_in_erosion_gate,
    confluence_marked_endorheic_with_outgoing_edge,
    lake_cascade_same_month_spill_not_routed,
    landform_false_acceptance_on_object_explosion,
    snow_store_nonperiodic_despite_runoff_periodic,
    spill_bypasses_channel_loss,
)
from worldsim.validation.production_closure.hydrology_contract import (
    hydrology_network_order_violations,
    hydrology_uses_post_hoc_spill_inject,
)

pytestmark = pytest.mark.pc0


def test_atlas_183716_baseline_frozen() -> None:
    base = load_atlas_baseline()
    assert base["audit_commit"] == "68d0ce93c24a030e9581a810ceadc228289de19f"
    assert base["reference_seed"] == 183716
    assert base["overall_acceptance_ok"] is False
    assert set(base["failed_gates"]) == {
        "hydrology_ok",
        "erosion_or_fluvial_ok",
        "landforms_ok",
    }
    assert base["channels"]["physical_channel_cell_count"] == 25260
    assert base["channels"]["display_candidate_after_acc_fraction"] == 888
    assert base["channels"]["display_after_discharge_quantile"] == 444
    assert base["hydrology"]["periodic_liquid_lakes"] == 25
    assert base["hydrology"]["nonperiodic_liquid_withheld"] == 115
    assert base["effective_config"]["precip_scale_mm"] == 200


def test_precip_scale_mm_code_matches_baseline() -> None:
    cfg = load_planet_config(default_config_path())
    assert float(cfg.precip_scale_mm) == 200.0
    assert load_atlas_baseline()["effective_config"]["precip_scale_mm"] == 200


def test_canonical_acceptance_matches_baseline_gates() -> None:
    base = load_atlas_baseline()
    report = aggregate_canonical_acceptance(
        moisture={
            "acceptance_ok": True,
            "spinup_converged": True,
            "moisture_budget_ok": True,
        },
        hydrology={
            "acceptance_ok": base["hydrology"]["acceptance_ok"],
            "q_through_lake_once": base["hydrology"]["q_through_lake_once"],
            "runoff_periodic": base["hydrology"]["runoff_periodic"],
        },
        vectors={"acceptance_ok": True},
        ecology={"acceptance_ok": True, "biome_v2_ok": True},
        landforms={"acceptance_ok": base["landforms"]["acceptance_ok"]},
        hex_grid={"acceptance_ok": True},
        erosion={"acceptance_ok": False, "erosion_algorithm": "c3_metric_pass1_v1"},
        final={
            "fluvial_erosion_nontrivial": base["erosion"]["fluvial_erosion_nontrivial"],
            "final_stage_acceptance_ok": False,
        },
    )
    assert report["overall_acceptance_ok"] is False
    assert set(report["failed_gates"]) == set(base["failed_gates"])


def test_hydrology_pipeline_order_ok() -> None:
    violations = hydrology_network_order_violations()
    assert not violations, violations
    assert not hydrology_uses_post_hoc_spill_inject()


def test_lake_cascade_same_month_inflow() -> None:
    probe = lake_cascade_same_month_spill_not_routed()
    assert probe["same_month_cascade_ok"]


def test_spill_incurs_channel_loss() -> None:
    probe = spill_bypasses_channel_loss()
    assert probe["land_loss_applied"]
    assert probe["spill_incurs_same_loss"]


def test_stale_river_mask_pipeline_order() -> None:
    """PC2: display LOD is chosen only after final lake-aware Q exists."""
    violations = hydrology_network_order_violations()
    assert not violations


def test_confluence_topology_gate_detects_misclassification() -> None:
    probe = confluence_marked_endorheic_with_outgoing_edge()
    assert probe["invalid_terminal_with_outgoing_edge"]


def test_snow_store_periodic_when_runoff_periodic() -> None:
    probe = snow_store_nonperiodic_despite_runoff_periodic()
    assert probe["runoff_periodic"]
    assert probe["snow_store_periodic"]
    assert probe["g0_state_ok"]


def test_conditioning_excluded_from_erosion_acceptance() -> None:
    probe = conditioning_counted_in_erosion_gate()
    assert probe["separate_conditioning_delta_tracked"]
    assert probe["conditioning_excluded_from_gate"]
    assert probe["observed_conditioning_mean_abs_delta_m"] >= 0.0


def test_landform_object_explosion_fails_acceptance() -> None:
    probe = landform_false_acceptance_on_object_explosion()
    assert probe["object_explosion_catastrophe"]
    assert probe["pc5_gates_would_fail"]


def test_progress_reporter_records_stage_timings() -> None:
    from io import StringIO

    from worldsim.progress import ProgressReporter

    reporter = ProgressReporter(stream=StringIO())
    reporter.stage_started("terrain")
    reporter.stage_complete("terrain")
    summary = reporter.timing_summary()
    assert "terrain" in summary["stage_timings_s"]
    assert summary["stage_timings_s"]["terrain"] >= 0.0


def test_atlas_baseline_json_on_disk_if_present() -> None:
    root = Path(__file__).resolve().parents[2]
    godot = root / "godot" / "worlds" / "atlas_run_183716"
    if not (godot / "final" / "final_diagnostics.json").is_file():
        pytest.skip("Atlas 183716 run tree not present locally")
    final = json.loads(
        (godot / "final" / "final_diagnostics.json").read_text(encoding="utf-8")
    )
    hydro = json.loads(
        (godot / "final" / "hydrology" / "hydrology_diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    base = load_atlas_baseline()
    assert final.get("overall_acceptance_ok") == base["overall_acceptance_ok"]
    ch = int(hydro.get("channel_physical_cell_count", 0))
    base_ch = int(base["channels"]["physical_channel_cell_count"])
    # Same seed may drift slightly after post-PC tier/network changes.
    assert abs(ch - base_ch) <= max(12, int(base_ch * 0.001))
