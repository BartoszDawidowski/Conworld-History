"""PC5 — landform representability, geometry, and catastrophe acceptance gates."""

from __future__ import annotations

from typing import Any

MAX_CANONICAL_MOUNTAIN_RANGES = 200
MAX_PLATEAU_CONTEXT_ESCARPMENT_FRAC = 0.50
MAX_LAND_ESCARPMENT_FRAC = 0.20
MIN_RIDGE_COVERAGE_FRAC = 0.95


def object_explosion_catastrophe(
    *,
    mountain_range_count: int,
    plateau_context_escarpment_fraction: float,
) -> bool:
    """True when audited Atlas-style object/escarpment alarms fire.

    ``plateau_context_escarpment_fraction`` must be the **interior** escarpment
    share (C9.1.5): thin all-rim plateaus may be 100% rim escarpment without
    tripping this gate.
    """
    return bool(
        int(mountain_range_count) > MAX_CANONICAL_MOUNTAIN_RANGES
        or float(plateau_context_escarpment_fraction)
        > MAX_PLATEAU_CONTEXT_ESCARPMENT_FRAC
    )


def canonical_extraction_min_cells(
    *,
    floor_cells: int,
    representable_ok: bool,
    min_component_cells: int,
) -> int:
    """When km² floors collapse to one cell, refuse 1-cell canonical objects."""
    applied = max(1, int(floor_cells))
    if not representable_ok:
        applied = max(applied, int(min_component_cells))
    return applied


def landform_acceptance_gates(
    *,
    structural_ok: bool,
    calibrated: bool,
    mask_ok: bool,
    local_coverage_ok: bool,
    ridge_in_mask_ok: bool,
    ridge_no_duplicate_ok: bool,
    plateau_honesty_ok: bool,
    plateau_interior_ok: bool,
    escarpment_dominance_ok: bool,
    mountain_fraction_ok: bool,
    mountain_fraction_alarm: bool,
    plateau_fraction_alarm: bool,
    plateau_context_escarpment_ok: bool,
    representability_ok: bool,
    ridge_coverage_ok: bool,
    plateau_rim_valid_ok: bool,
    object_count_catastrophe_ok: bool,
    zero_semantic_objects_ok: bool,
) -> dict[str, bool]:
    geometry_ok = bool(
        ridge_in_mask_ok
        and ridge_no_duplicate_ok
        and ridge_coverage_ok
        and plateau_interior_ok
        and plateau_rim_valid_ok
    )
    representability_gate = bool(
        plateau_honesty_ok and representability_ok and zero_semantic_objects_ok
    )
    alarms_ok = bool(
        escarpment_dominance_ok
        and not mountain_fraction_alarm
        and not plateau_fraction_alarm
        and plateau_context_escarpment_ok
        and object_count_catastrophe_ok
    )
    acceptance_ok = bool(
        structural_ok
        and calibrated
        and mask_ok
        and local_coverage_ok
        and representability_gate
        and geometry_ok
        and alarms_ok
        and mountain_fraction_ok
    )
    return {
        "landforms_representability_ok": representability_gate,
        "landforms_geometry_ok": geometry_ok,
        "object_count_catastrophe_ok": object_count_catastrophe_ok,
        "escarpment_dominance_ok": escarpment_dominance_ok,
        "plateau_context_escarpment_ok": plateau_context_escarpment_ok,
        "mountain_fraction_alarm": mountain_fraction_alarm,
        "plateau_fraction_alarm": plateau_fraction_alarm,
        "ridge_coverage_ok": ridge_coverage_ok,
        "plateau_rim_valid_ok": plateau_rim_valid_ok,
        "acceptance_ok": acceptance_ok,
    }


def gate_payload(gates: dict[str, bool]) -> dict[str, Any]:
    """Flatten gate booleans for diagnostics JSON."""
    return {k: bool(v) for k, v in gates.items()}
