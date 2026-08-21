"""PC7 C10 readiness review (addendum §12 gate)."""

from __future__ import annotations

from typing import Any

from worldsim.spatial.canonical_acceptance import GATE_ORDER

C10_READINESS_VERSION = "pc7_c10_readiness_v1"

# Gates that must be green before calibration may begin.
C10_BLOCKING_GATES: tuple[str, ...] = GATE_ORDER


def review_c10_readiness(
    *,
    gates: dict[str, bool],
    suite_ok: bool = True,
    performance_documented: bool = True,
    all_seeds_acceptance_ok: bool | None = None,
) -> dict[str, Any]:
    """Explicit readiness verdict for user review — fail closed on any blocking gate."""
    failed = [name for name in C10_BLOCKING_GATES if not bool(gates.get(name, False))]
    acceptance_ok = (
        True if all_seeds_acceptance_ok is None else bool(all_seeds_acceptance_ok)
    )
    ready = (
        suite_ok
        and performance_documented
        and acceptance_ok
        and not failed
    )
    status = "READY_FOR_CALIBRATION" if ready else "NOT_READY_FOR_CALIBRATION"
    return {
        "version": C10_READINESS_VERSION,
        "status": status,
        "ready_for_calibration": bool(ready),
        "suite_ok": bool(suite_ok),
        "all_seeds_acceptance_ok": (
            None if all_seeds_acceptance_ok is None else bool(all_seeds_acceptance_ok)
        ),
        "performance_documented": bool(performance_documented),
        "blocking_gates": list(C10_BLOCKING_GATES),
        "failed_gates": failed,
        "gates": {k: bool(gates.get(k, False)) for k in C10_BLOCKING_GATES},
        "user_review_required": True,
        "note": (
            "C10 may start only after PC7 reports READY_FOR_CALIBRATION and the user "
            "explicitly accepts the gate review. suite_ok means the seed matrix ran; "
            "it is not a substitute for green physics gates."
        ),
    }
