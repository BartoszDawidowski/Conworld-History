"""LandformAnalysis parameters and algorithm version (PR-9)."""

from __future__ import annotations

from dataclasses import dataclass

LANDFORM_ALGORITHM_VERSION = "landform_v1_pr9"


@dataclass(frozen=True)
class LandformParams:
    """Physical kilometre scales + score thresholds (calibration knobs)."""

    enabled: bool = True
    # Multi-scale radii (km)
    fine_radius_km: float = 15.0
    meso_radius_km: float = 60.0
    macro_radius_km: float = 250.0
    # Score / object thresholds (foundation defaults — not seed-tuned)
    mountain_score_threshold: float = 0.42
    plateau_score_threshold: float = 0.40
    min_range_cells: int = 12
    min_plateau_cells: int = 24
    escarpment_slope: float = 0.08  # rise/run (m/m)
    flat_slope: float = 0.02
    planet_radius_km: float = 6371.0
