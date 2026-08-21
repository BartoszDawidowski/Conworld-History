"""C9.1.6 — canonical overall acceptance_ok; hex success is not sufficient."""

from __future__ import annotations

from types import SimpleNamespace

from worldsim.export.atlas_display import _climate_summary
from worldsim.spatial.canonical_acceptance import (
    CANONICAL_ACCEPTANCE_VERSION,
    aggregate_canonical_acceptance,
    climate_summary_from_report,
    stamp_into_diagnostics,
)


def _green_kwargs() -> dict:
    return {
        "moisture": {
            "acceptance_ok": True,
            "spinup_converged": True,
            "moisture_budget_ok": True,
        },
        "hydrology": {
            "acceptance_ok": True,
            "q_through_lake_once": True,
            "runoff_periodic": True,
        },
        "vectors": {"acceptance_ok": True},
        "ecology": {"acceptance_ok": True, "biome_v2_ok": True},
        "landforms": {
            "acceptance_ok": True,
            "plateau_area_floor_honesty_ok": True,
            "plateau_interior_not_escarpment_ok": True,
        },
        "hex_grid": {"acceptance_ok": True},
        "erosion": {
            "acceptance_ok": True,
            "erosion_algorithm": "c3_metric_pass1_v1",
        },
        "final": {
            "fluvial_erosion_nontrivial": True,
            "fluvial_corridor_erosion_ok": True,
            "erosion_delta_identity_ok": True,
            "final_stage_acceptance_ok": True,
        },
    }


def test_all_gates_true_is_green() -> None:
    report = aggregate_canonical_acceptance(**_green_kwargs())
    assert report["version"] == CANONICAL_ACCEPTANCE_VERSION
    assert report["overall_acceptance_ok"] is True
    assert report["failed_gates"] == []


def test_hex_only_success_is_not_green() -> None:
    report = aggregate_canonical_acceptance(hex_grid={"acceptance_ok": True})
    assert report["gates"]["hex_layout_ok"] is True
    assert report["overall_acceptance_ok"] is False
    assert "hydrology_ok" in report["failed_gates"]
    assert "moisture_spinup_ok" in report["failed_gates"]
    assert "biome_v2_ok" in report["failed_gates"]


def test_doubled_lake_q_cannot_be_green() -> None:
    kwargs = _green_kwargs()
    kwargs["hydrology"] = {
        "acceptance_ok": True,
        "q_through_lake_once": False,
        "runoff_periodic": True,
    }
    report = aggregate_canonical_acceptance(**kwargs)
    assert report["overall_acceptance_ok"] is False
    assert "hydrology_ok" in report["failed_gates"]


def test_nonperiodic_lakes_cannot_be_green() -> None:
    kwargs = _green_kwargs()
    kwargs["hydrology"] = {
        "acceptance_ok": True,
        "q_through_lake_once": True,
        "runoff_periodic": False,
    }
    report = aggregate_canonical_acceptance(**kwargs)
    assert report["overall_acceptance_ok"] is False
    assert "hydrology_ok" in report["failed_gates"]


def test_growing_moist_on_ice_cannot_be_green() -> None:
    kwargs = _green_kwargs()
    kwargs["ecology"] = {
        "acceptance_ok": True,
        "biome_v2_ok": False,
        "biome_v2_zero_growing_not_growing_class": False,
    }
    report = aggregate_canonical_acceptance(**kwargs)
    assert report["overall_acceptance_ok"] is False
    assert "biome_v2_ok" in report["failed_gates"]
    assert "ecology_ok" in report["failed_gates"]


def test_failed_gate_cannot_be_omitted_to_stay_green() -> None:
    kwargs = _green_kwargs()
    kwargs["landforms"] = {"acceptance_ok": False}
    report = aggregate_canonical_acceptance(**kwargs)
    assert report["overall_acceptance_ok"] is False
    assert "landforms_ok" in report["failed_gates"]


def test_climate_summary_matches_aggregator_not_raster_presence() -> None:
    bad = aggregate_canonical_acceptance(hex_grid={"acceptance_ok": True})
    model = SimpleNamespace(
        manifest=SimpleNamespace(
            extra={"canonical_acceptance": bad, "temperature_integrity_ok": True},
            acceptance_ok=bad["overall_acceptance_ok"],
        )
    )
    summary = _climate_summary(model)
    assert summary["overall_acceptance_ok"] is False
    assert summary["biome_v2_ok"] is False
    assert summary["landforms_ok"] is False
    assert summary["hex_layout_ok"] is True
    assert summary["canonical_acceptance_version"] == CANONICAL_ACCEPTANCE_VERSION

    good = aggregate_canonical_acceptance(**_green_kwargs())
    summary_ok = climate_summary_from_report(good, temperature_integrity_ok=True)
    assert summary_ok["overall_acceptance_ok"] is True
    assert summary_ok["biome_v2_ok"] is True
    assert summary_ok["landforms_ok"] is True


def test_erosion_gate_independent_of_hydrology_failure() -> None:
    """erosion_or_fluvial_ok must not AND final_stage (hydro/landforms bundle)."""
    kwargs = _green_kwargs()
    kwargs["hydrology"] = {
        "acceptance_ok": False,
        "q_through_lake_once": True,
        "runoff_periodic": True,
    }
    kwargs["final"] = {
        "fluvial_erosion_nontrivial": True,
        "fluvial_corridor_erosion_ok": True,
        "erosion_delta_identity_ok": True,
        "final_stage_acceptance_ok": False,
    }
    report = aggregate_canonical_acceptance(**kwargs)
    assert report["gates"]["hydrology_ok"] is False
    assert report["gates"]["erosion_or_fluvial_ok"] is True
    assert "hydrology_ok" in report["failed_gates"]
    assert "erosion_or_fluvial_ok" not in report["failed_gates"]


def test_stamp_copies_overall_onto_final_diagnostics() -> None:
    report = aggregate_canonical_acceptance(hex_grid={"acceptance_ok": True})
    diag = {
        "acceptance_ok": True,
        "final_stage_acceptance_ok": True,
        "fluvial_erosion_nontrivial": True,
    }
    stamp_into_diagnostics(diag, report)
    assert diag["final_stage_acceptance_ok"] is True
    assert diag["overall_acceptance_ok"] is False
    assert diag["acceptance_ok"] is False
    assert diag["canonical_acceptance_version"] == CANONICAL_ACCEPTANCE_VERSION
