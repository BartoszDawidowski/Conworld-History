"""PC7 runtime regression analysis and optimization ledger."""

from __future__ import annotations

from typing import Any

from worldsim.validation.production_closure.baseline import load_atlas_baseline

PC7_OPTIMIZATION_VERSION = "pc7_perf_v1"

# Documented PC7 optimization attempts (code + expected stage).
PC7_OPTIMIZATIONS: tuple[dict[str, str], ...] = (
    {
        "id": "g0_skip_redundant_repeat_year",
        "stage": "hydrology",
        "module": "physical/cryosphere/snow_firn.py",
        "summary": (
            "Skip the extra G0 validation year when spin-up already converged "
            "within tolerance during the year loop."
        ),
    },
    {
        "id": "lake_record_index_lookup",
        "stage": "hydrology",
        "module": "physical/hydrology/monthly_router.py",
        "summary": (
            "Replace O(n) lake record scan per lake-month with a pre-built id→record map."
        ),
    },
)


def analyze_stage_regression(
    stage_timings_s: dict[str, float],
    *,
    total_elapsed_s: float | None = None,
) -> dict[str, Any]:
    """Attribute Atlas runtime regression to dominant stages."""
    base = load_atlas_baseline()
    runtime = dict(base.get("runtime_s") or {})
    prev_total = float(runtime.get("atlas_total_previous_audit", 134.3))
    cur_total = float(
        total_elapsed_s
        if total_elapsed_s is not None
        else runtime.get("atlas_total_current_audit", 163.9)
    )
    regression_fraction = (cur_total - prev_total) / prev_total if prev_total > 0 else 0.0

    timings = {k: float(v) for k, v in stage_timings_s.items() if float(v) > 0.0}
    total_stages = float(sum(timings.values())) or cur_total
    ranked = sorted(timings.items(), key=lambda kv: kv[1], reverse=True)
    dominant_stage = ranked[0][0] if ranked else None
    dominant_fraction = (
        float(ranked[0][1]) / total_stages if ranked and total_stages > 0 else 0.0
    )

    # PC1–PC3 additions land primarily in hydrology (lake spin-up + G0 runoff).
    attributed_stages = ("hydrology", "final", "moisture", "erosion")
    attributed_s = sum(timings.get(s, 0.0) for s in attributed_stages)
    attributed_fraction = attributed_s / total_stages if total_stages > 0 else 0.0

    return {
        "optimization_version": PC7_OPTIMIZATION_VERSION,
        "baseline_total_s": prev_total,
        "current_total_s": cur_total,
        "regression_fraction": float(regression_fraction),
        "regression_above_15pct_warning": bool(regression_fraction > 0.15),
        "dominant_stage": dominant_stage,
        "dominant_stage_fraction": float(dominant_fraction),
        "attributed_pc1_pc3_stages": list(attributed_stages),
        "attributed_pc1_pc3_fraction": float(attributed_fraction),
        "stage_ranking": [{"stage": s, "seconds": t} for s, t in ranked[:8]],
        "optimizations_applied": list(PC7_OPTIMIZATIONS),
        "note": (
            "Mid-audit Atlas +22% (134→164 s) predates PC1 condensed routing and "
            "G0 8-year spin-up; post PC1+PC3 local Atlas ~600 s is expected. "
            "Per-lake lake-storage periodicity repair (2026-08-19) restores "
            "partial liquid-lake publish when global signature has not converged."
        ),
    }
