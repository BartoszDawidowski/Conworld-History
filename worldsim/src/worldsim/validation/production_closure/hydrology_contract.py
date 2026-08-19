"""Static hydrology pipeline-order contracts (PC0/PC2)."""

from __future__ import annotations

from pathlib import Path

_PIPELINE = (
    Path(__file__).resolve().parents[2]
    / "physical"
    / "hydrology"
    / "pipeline.py"
)


def hydrology_pipeline_source() -> str:
    return _PIPELINE.read_text(encoding="utf-8")


def line_index(source: str, needle: str, *, occurrence: int = 1) -> int:
    count = 0
    for i, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            count += 1
            if count == occurrence:
                return i
    return -1


def hydrology_network_order_violations() -> list[str]:
    """Return human-readable violations of the PC2 final-Q network order."""
    src = hydrology_pipeline_source()
    violations: list[str] = []

    routing_line = line_index(src, "spinup_condensed_lake_routing(")
    display_line = line_index(src, "build_display_river_mask(")
    final_q_lines = [
        i
        for i, line in enumerate(src.splitlines(), start=1)
        if "discharge_eff = month_weighted_mean_m3s(monthly_eff)" in line
    ]
    final_q_after_routing = max(
        (ln for ln in final_q_lines if ln > routing_line),
        default=-1,
    )
    spill_inject_line = line_index(src, "monthly_eff[m] += accumulate_weights_lake_aware(")
    early_display = line_index(src, "display_channel_candidates(")

    if routing_line < 0:
        violations.append("spinup_condensed_lake_routing call not found")
    if display_line < 0:
        violations.append("build_display_river_mask call not found")
    if final_q_after_routing < 0:
        violations.append("final discharge_eff after lake routing not found")

    if early_display > 0:
        violations.append("display_channel_candidates used before final-Q tier builder")

    if (
        routing_line > 0
        and display_line > 0
        and display_line < routing_line
    ):
        violations.append("display river mask built before lake-condensed routing")

    if (
        final_q_after_routing > 0
        and display_line > 0
        and display_line < final_q_after_routing
    ):
        violations.append(
            "build_display_river_mask runs before canonical final discharge_eff"
        )

    if spill_inject_line > 0:
        violations.append("post_hoc_spill_inject_present")

    return violations


def hydrology_uses_post_hoc_spill_inject() -> bool:
    return "monthly_eff[m] += accumulate_weights_lake_aware(" in hydrology_pipeline_source()


def final_q_network_order_ok() -> bool:
    return not hydrology_network_order_violations()
