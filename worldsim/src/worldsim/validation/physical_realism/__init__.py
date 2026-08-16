"""Physical realism regression harness (PR-0+).

Production physics is unchanged by this package. Later PR milestones flip
``xfail`` audit tests to pass as invariants are fixed.
"""

from worldsim.validation.physical_realism.seed_suites import (
    ATLAS_SEEDS,
    AUDIT_BASELINE_COMMIT,
    FULL_SEEDS,
    QUICK_SEEDS,
    REALISM_SCHEMA_VERSION,
)

__all__ = [
    "ATLAS_SEEDS",
    "AUDIT_BASELINE_COMMIT",
    "FULL_SEEDS",
    "QUICK_SEEDS",
    "REALISM_SCHEMA_VERSION",
]
