"""Stage A — PyPlatec tectonics (baseline + extended metadata)."""

from __future__ import annotations

from worldsim.physical.tectonics.baseline import (
    TectonicsBaselineResult,
    TectonicsExtendedResult,
    run_pyplatec_baseline,
    run_pyplatec_extended,
)
from worldsim.physical.tectonics.capabilities import (
    PlatecCapabilities,
    detect_platec_capabilities,
)
from worldsim.physical.tectonics.interpretation import (
    BoundaryType,
    InterpretationParams,
    TectonicsInterpretationResult,
    interpret_tectonics,
    run_tectonic_interpretation,
)
from worldsim.physical.tectonics.params import PyPlatecParams

__all__ = [
    "BoundaryType",
    "InterpretationParams",
    "PlatecCapabilities",
    "PyPlatecParams",
    "TectonicsBaselineResult",
    "TectonicsExtendedResult",
    "TectonicsInterpretationResult",
    "detect_platec_capabilities",
    "interpret_tectonics",
    "run_pyplatec_baseline",
    "run_pyplatec_extended",
    "run_tectonic_interpretation",
]
