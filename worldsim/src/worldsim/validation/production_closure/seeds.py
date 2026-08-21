"""PC7 production-suite seed lists (addendum §11 PC7)."""

from __future__ import annotations

from worldsim.validation.physical_realism.seed_suites import PROFILE_GRIDS

PC7_SCHEMA_VERSION = "pc7_production_suite_v2"

# Required suite membership — distinct from legacy PR-0 ATLAS_SEEDS (7, 1337).
PC7_QUICK_SEEDS: tuple[int, ...] = (1, 42, 100)
PC7_ATLAS_SEEDS: tuple[int, ...] = (42, 183716)
PC7_FULL_SEEDS: tuple[int, ...] = (42,)

PC7_PROFILES: tuple[str, ...] = ("quick", "atlas", "full")

__all__ = [
    "PC7_SCHEMA_VERSION",
    "PC7_QUICK_SEEDS",
    "PC7_ATLAS_SEEDS",
    "PC7_FULL_SEEDS",
    "PC7_PROFILES",
    "PROFILE_GRIDS",
]
