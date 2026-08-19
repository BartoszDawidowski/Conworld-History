"""G0 pipeline entry — single owner of precipitation phase partition."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.cryosphere.params import G0Params
from worldsim.physical.cryosphere.snow_firn import build_g0_climatology


def build_g0_surface_water(
    *,
    precipitation: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    params: G0Params | None = None,
    # Legacy keyword aliases from HydrologyParams / build_monthly_runoff
    snow_threshold_c: float | None = None,
    snow_band_c: float | None = None,
    melt_factor_per_c: float | None = None,
    max_snow_store: float | None = None,
    precip_scale_mm: float | None = None,
    soil_capacity: float | None = None,
    soil_quickflow_frac: float | None = None,
    spinup_years: int | None = None,
    spinup_rel_tol: float | None = None,
) -> dict[str, NDArray[np.float64] | dict[str, Any]]:
    """Build SurfaceWaterForcing after G0 climatological spin-up."""
    base = params or G0Params()
    overrides = {
        "snow_threshold_c": snow_threshold_c,
        "snow_band_c": snow_band_c,
        "melt_factor_per_c": melt_factor_per_c,
        "max_seasonal_snow_swe": max_snow_store,
        "precip_scale_mm": precip_scale_mm,
        "soil_capacity": soil_capacity,
        "soil_quickflow_frac": soil_quickflow_frac,
        "spinup_years": spinup_years,
        "spinup_rel_tol": spinup_rel_tol,
    }
    kw = {k: v for k, v in overrides.items() if v is not None}
    p = G0Params(**{**base.__dict__, **kw}) if kw else base
    return build_g0_climatology(
        precipitation=precipitation,
        temperature_c=temperature_c,
        ocean_mask=ocean_mask,
        params=p,
    )
