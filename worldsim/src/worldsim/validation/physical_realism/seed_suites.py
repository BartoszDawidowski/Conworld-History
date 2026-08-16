"""Fixed seed suites for physical-realism regression (annex §16.2)."""

from __future__ import annotations

# Audited repository tip when the annex was written (PR-0 baseline).
AUDIT_BASELINE_COMMIT = "6a961161c2a10d322de0990e6cbec8317ea80a5c"

# Schema of the harness artefact JSON (not planet config schema).
REALISM_SCHEMA_VERSION = 1

# Fast regression — Quick profile sizes (Godot PROFILE_QUICK).
QUICK_SEEDS: tuple[int, ...] = (1, 42, 100)

# Integration — Atlas profile (not run by default in PR-0 capture).
ATLAS_SEEDS: tuple[int, ...] = (7, 42, 1337)

# Before retuning defaults — Full production resolutions.
FULL_SEEDS: tuple[int, ...] = (42,)

# Profile → CLI-equivalent grid sizes (must match SimulationRunner.gd).
PROFILE_GRIDS: dict[str, dict[str, tuple[int, int]]] = {
    "quick": {
        "tectonics": (128, 64),
        "terrain": (256, 128),
        "climate": (128, 64),
        "analysis": (128, 64),
    },
    "atlas": {
        "tectonics": (512, 256),
        "terrain": (1024, 512),
        "climate": (512, 256),
        "analysis": (256, 128),
    },
    "full": {
        "tectonics": (1024, 512),
        "terrain": (4096, 2048),
        "climate": (1024, 512),
        "analysis": (256, 128),
    },
}
