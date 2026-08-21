"""G0 snow/soil/firn parameters (physical units in precip proxy SWE)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class G0Params:
    snow_threshold_c: float = 0.0
    snow_band_c: float = 2.0
    melt_factor_per_c: float = 0.08
    max_seasonal_snow_swe: float = 40.0
    firn_melt_factor_per_c: float = 0.04
    precip_scale_mm: float = 200.0
    soil_capacity: float = 1.0
    soil_quickflow_frac: float = 0.20
    spinup_years: int = 64
    spinup_rel_tol: float = 0.01
    mass_balance_tol: float = 1e-4
