"""LandformAnalysis parameters and algorithm version (PR-9 / CR-5)."""

from __future__ import annotations

import math
from dataclasses import dataclass

LANDFORM_ALGORITHM_VERSION = "landform_v2_cr9"
# Production CR-9 band: threshold must be in this range to claim calibrated.
CALIBRATED_MOUNTAIN_THRESHOLD_MIN = 0.58
CALIBRATED_MOUNTAIN_THRESHOLD_MAX = 0.65


def min_object_cells(
    *,
    min_km2: float | None,
    min_cells: int,
    cell_area_km2: float,
) -> int:
    """Prefer a physical area floor (km²); fall back to a cell count."""
    if min_km2 is not None and float(min_km2) > 0.0:
        area = max(float(cell_area_km2), 1e-12)
        return max(1, int(math.ceil(float(min_km2) / area)))
    return max(1, int(min_cells))


@dataclass(frozen=True)
class LandformParams:
    """Physical kilometre scales + score thresholds (CR-9 calibrated)."""

    enabled: bool = True
    # Multi-scale radii (km) — CR-5 band ~60 / 120–180 / 250–400
    fine_radius_km: float = 60.0
    meso_radius_km: float = 150.0
    macro_radius_km: float = 300.0
    # Score / object thresholds
    mountain_score_threshold: float = 0.60
    plateau_score_threshold: float = 0.40
    min_range_cells: int = 12
    min_plateau_cells: int = 24
    min_range_km2: float | None = 800.0
    min_plateau_km2: float | None = 2500.0
    # Drop 1–3 cell specks when km² floors collapse to 1 cell (Atlas/Quick).
    min_component_cells: int = 4
    escarpment_slope: float = 0.08  # rise/run (m/m)
    flat_slope: float = 0.02
    planet_radius_km: float = 6371.0
    # Land-fraction cap used by acceptance (not a hard mask)
    max_mountain_land_fraction: float = 0.40


def params_are_calibrated(params: LandformParams) -> bool:
    """True when production CR-9 knobs are in the accepted band (not a constant)."""
    thr = float(params.mountain_score_threshold)
    return bool(
        params.enabled
        and CALIBRATED_MOUNTAIN_THRESHOLD_MIN
        <= thr
        <= CALIBRATED_MOUNTAIN_THRESHOLD_MAX
        and params.min_range_km2 is not None
        and float(params.min_range_km2) > 0.0
        and params.min_plateau_km2 is not None
        and float(params.min_plateau_km2) > 0.0
    )
