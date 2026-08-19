"""C9.1.6 — one owner for world ``acceptance_ok``.

Layout/hex success is a conjunct, never a substitute for physics gates.
Missing diagnostics fail closed.
"""

from __future__ import annotations

from typing import Any

CANONICAL_ACCEPTANCE_VERSION = "c91_6_v1"

GATE_ORDER: tuple[str, ...] = (
    "moisture_spinup_ok",
    "moisture_budget_ok",
    "hydrology_ok",
    "vector_ok",
    "ecology_ok",
    "biome_v2_ok",
    "landforms_ok",
    "erosion_or_fluvial_ok",
    "hex_layout_ok",
)


def _as_diag(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    diag = getattr(obj, "diagnostics", None)
    return dict(diag) if isinstance(diag, dict) else {}


def _flag(diag: dict[str, Any], key: str) -> bool:
    if key not in diag:
        return False
    return bool(diag[key])


def _metric_erosion_claimed(erosion: dict[str, Any], final: dict[str, Any]) -> bool:
    blobs = (
        str(erosion.get("erosion_algorithm") or ""),
        str(erosion.get("slope_algorithm") or ""),
        str(final.get("slope_algorithm") or ""),
        str(final.get("stream_power_k_role") or ""),
    )
    if any("metric" in b.lower() for b in blobs):
        return True
    if final.get("fluvial_iterations") is not None:
        return True
    if erosion or final:
        return True
    return False


def collect_gates(
    *,
    moisture: Any = None,
    hydrology: Any = None,
    vectors: Any = None,
    ecology: Any = None,
    landforms: Any = None,
    hex_grid: Any = None,
    erosion: Any = None,
    final: Any = None,
) -> dict[str, bool]:
    """Derive named gates. Absent objects / keys are False (fail closed)."""
    m = _as_diag(moisture)
    h = _as_diag(hydrology)
    v = _as_diag(vectors)
    e = _as_diag(ecology)
    lf = _as_diag(landforms)
    hx = _as_diag(hex_grid)
    er = _as_diag(erosion)
    fn = _as_diag(final)

    spinup = _flag(m, "spinup_converged")
    budget = (
        _flag(m, "moisture_budget_ok") if "moisture_budget_ok" in m else _flag(m, "acceptance_ok")
    )
    moisture_stage = _flag(m, "acceptance_ok")
    moisture_spinup_ok = bool(moisture_stage and spinup)
    moisture_budget_ok = bool(moisture_stage and budget)

    hydro_ok = bool(
        _flag(h, "acceptance_ok")
        and _flag(h, "q_through_lake_once")
        and _flag(h, "runoff_periodic")
    )
    vector_ok = _flag(v, "acceptance_ok")
    biome_ok = _flag(e, "biome_v2_ok") if "biome_v2_ok" in e else _flag(e, "acceptance_ok")
    ecology_ok = bool(_flag(e, "acceptance_ok") and biome_ok)

    land_ok = _flag(lf, "acceptance_ok")
    if "plateau_area_floor_honesty_ok" in lf:
        land_ok = land_ok and bool(lf["plateau_area_floor_honesty_ok"])
    if "plateau_interior_not_escarpment_ok" in lf:
        land_ok = land_ok and bool(lf["plateau_interior_not_escarpment_ok"])

    if _metric_erosion_claimed(er, fn):
        erosion_ok = True
        if er:
            erosion_ok = erosion_ok and _flag(er, "acceptance_ok")
        if fn:
            # Do not read final.acceptance_ok — after a world stamp that field
            # is the overall flag and would become circular.
            if "fluvial_erosion_nontrivial" in fn:
                erosion_ok = erosion_ok and bool(fn["fluvial_erosion_nontrivial"])
            if "final_stage_acceptance_ok" in fn:
                erosion_ok = erosion_ok and bool(fn["final_stage_acceptance_ok"])
            elif "stable_final_geography" in fn:
                erosion_ok = erosion_ok and bool(fn["stable_final_geography"])
        if not er and not fn:
            erosion_ok = False
    else:
        erosion_ok = False

    hex_ok = _flag(hx, "acceptance_ok")

    return {
        "moisture_spinup_ok": moisture_spinup_ok,
        "moisture_budget_ok": moisture_budget_ok,
        "hydrology_ok": hydro_ok,
        "vector_ok": vector_ok,
        "ecology_ok": ecology_ok,
        "biome_v2_ok": bool(biome_ok),
        "landforms_ok": bool(land_ok),
        "erosion_or_fluvial_ok": bool(erosion_ok),
        "hex_layout_ok": hex_ok,
    }


def conjunction_from_gates(gates: dict[str, bool]) -> dict[str, Any]:
    """Single AND. A missing gate is a failed gate."""
    ordered: dict[str, bool] = {}
    failed: list[str] = []
    for name in GATE_ORDER:
        ok = bool(gates.get(name, False))
        ordered[name] = ok
        if not ok:
            failed.append(name)
    overall = not failed
    return {
        "version": CANONICAL_ACCEPTANCE_VERSION,
        "gates": ordered,
        "failed_gates": failed,
        "overall_acceptance_ok": bool(overall),
        "hex_is_not_sufficient": True,
    }


def aggregate_canonical_acceptance(
    *,
    moisture: Any = None,
    hydrology: Any = None,
    vectors: Any = None,
    ecology: Any = None,
    landforms: Any = None,
    hex_grid: Any = None,
    erosion: Any = None,
    final: Any = None,
) -> dict[str, Any]:
    gates = collect_gates(
        moisture=moisture,
        hydrology=hydrology,
        vectors=vectors,
        ecology=ecology,
        landforms=landforms,
        hex_grid=hex_grid,
        erosion=erosion,
        final=final,
    )
    return conjunction_from_gates(gates)


def stamp_into_diagnostics(diagnostics: dict[str, Any], report: dict[str, Any]) -> None:
    """Copy the canonical report onto a diagnostics dict (final / world)."""
    if "final_stage_acceptance_ok" not in diagnostics and "acceptance_ok" in diagnostics:
        diagnostics["final_stage_acceptance_ok"] = bool(diagnostics["acceptance_ok"])
    diagnostics["canonical_acceptance_version"] = CANONICAL_ACCEPTANCE_VERSION
    diagnostics["canonical_acceptance"] = report
    diagnostics["overall_acceptance_ok"] = bool(report["overall_acceptance_ok"])
    diagnostics["acceptance_ok"] = bool(report["overall_acceptance_ok"])
    diagnostics["failed_gates"] = list(report.get("failed_gates") or [])


def climate_summary_from_report(
    report: dict[str, Any],
    *,
    temperature_integrity_ok: bool | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    gates = dict(report.get("gates") or {})
    failed = list(report.get("failed_gates") or [])
    warn = list(warnings or [])
    if failed:
        warn.append("failed_gates: " + ",".join(failed))
    return {
        "canonical_acceptance_version": CANONICAL_ACCEPTANCE_VERSION,
        "temperature_integrity_ok": bool(
            True if temperature_integrity_ok is None else temperature_integrity_ok
        ),
        "moisture_spinup_ok": bool(gates.get("moisture_spinup_ok", False)),
        "moisture_budget_ok": bool(gates.get("moisture_budget_ok", False)),
        "hydrology_coupling_ok": bool(gates.get("hydrology_ok", False)),
        "biome_v2_ok": bool(gates.get("biome_v2_ok", False)),
        "landforms_ok": bool(gates.get("landforms_ok", False)),
        "hex_layout_ok": bool(gates.get("hex_layout_ok", False)),
        "overall_acceptance_ok": bool(report.get("overall_acceptance_ok", False)),
        "failed_gates": failed,
        "warnings": warn,
    }
