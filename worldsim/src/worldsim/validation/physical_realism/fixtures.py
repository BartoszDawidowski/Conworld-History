"""Synthetic fixtures documenting annex audit gaps (read-only probes)."""

from __future__ import annotations

from typing import Any

import numpy as np

from worldsim.physical.moisture.transport import (
    _upwind_advect,
    build_monthly_moisture,
    partition_precipitation,
    saturation_capacity,
)
from worldsim.physical.moisture.transport import orographic_lift


def northward_impulse_result(*, steps: int = 4) -> dict[str, float]:
    """Compact moisture impulse under ``wind_v > 0`` (documented northward).

    Convention (annex §10.2): ``j=0`` north; ``wind_v > 0`` → toward smaller ``j``.
    """
    h, w = 21, 9
    j0, i0 = 10, 4
    q = np.zeros((h, w), dtype=np.float64)
    q[j0, i0] = 1.0
    u = np.zeros((h, w), dtype=np.float64)
    v = np.full((h, w), 8.0, dtype=np.float64)
    out = q.copy()
    for _ in range(steps):
        out = _upwind_advect(out, u, v, dt=0.25, wind_scale=0.25)
    north = float(out[:j0, :].sum())
    south = float(out[j0 + 1 :, :].sum())
    centre = float(out[j0, i0])
    return {
        "mass_north_of_seed": north,
        "mass_south_of_seed": south,
        "mass_at_seed": centre,
        "total_mass": float(out.sum()),
    }


def precip_vs_available_q_overshoot(
    *,
    h: int = 16,
    w: int = 32,
) -> dict[str, float]:
    """Probe precip partition vs available ``q`` using the live PR-4 budget path."""
    elev = np.zeros((h, w), dtype=np.float64)
    elev[:, w // 2 - 1 : w // 2 + 2] = 4000.0
    temp = np.full((h, w), 28.0, dtype=np.float64)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    lat = np.zeros((h, w), dtype=np.float64)
    wu = np.full((h, w), 10.0, dtype=np.float64)
    wv = np.zeros((h, w), dtype=np.float64)

    from worldsim.physical.moisture.transport import evaporation_field, _diffuse_moisture

    q = np.zeros((h, w), dtype=np.float64)
    evap = evaporation_field(
        temperature_c=temp,
        ocean_mask=ocean,
        ocean_rate=1.4,
        land_rate=0.4,
    )
    q = q + evap
    steps = 8
    dt = 1.0 / float(steps)
    for _ in range(steps):
        q = _upwind_advect(q, wu, wv, dt=dt, wind_scale=0.2)
        q, _clip = _diffuse_moisture(q, dt=dt, mix_per_month=0.08)

    q_available = q.copy()
    capacity = saturation_capacity(temp)
    land_dry = np.ones((h, w), dtype=np.float64)
    lift = orographic_lift(wind_u=wu, wind_v=wv, elevation_m=elev)
    part = partition_precipitation(
        q=q,
        capacity=capacity,
        land_dry=land_dry,
        lift=lift,
        temperature_c=temp,
        latitude_deg=lat,
        large_scale_frac=0.55,
        orographic_frac=0.85,
        convective_scale=2.0,
        lee_dry=0.12,
    )
    precip = part["precipitation"]
    overshoot = precip - q_available
    return {
        "max_overshoot": float(overshoot.max()),
        "mean_precip": float(precip.mean()),
        "mean_q_available": float(q_available.mean()),
        "cells_overshoot": float(np.mean(overshoot > 1e-9)),
    }


def january_dry_start_ramp(
    *,
    months: int = 12,
) -> dict[str, Any]:
    """Annual precip under constant forcing; should be flat after PR-4 spin-up."""
    h, w = 12, 24
    elev = np.zeros((h, w), dtype=np.float64)
    temp = np.full((months, h, w), 24.0, dtype=np.float64)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :5] = True
    lat = np.zeros((h, w), dtype=np.float64)
    wu = np.full((months, h, w), 6.0, dtype=np.float64)
    wv = np.zeros((months, h, w), dtype=np.float64)
    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=months,
        advect_steps=6,
        spinup_max_years=4,
        spinup_tolerance_relative=0.02,
        spinup_tolerance_absolute=1e-3,
    )
    land = ~ocean
    monthly_land = [
        float(fields["precipitation"][m][land].mean()) for m in range(months)
    ]
    return {
        "monthly_land_mean_precip": monthly_land,
        "jan_over_jul_ratio": (
            monthly_land[0] / monthly_land[6] if monthly_land[6] > 1e-12 else None
        ),
        "max_minus_min": float(max(monthly_land) - min(monthly_land)),
        "spinup_converged": bool(fields["budget"]["spinup_converged"]),
    }


def land_max_hits_scale(
    land_scale_m: float = 9000.0,
) -> dict[str, float]:
    """Two different raw peaks under the production hypsometry curve.

    ``legacy_max`` would pin both maxima to ``land_scale_m``. ``power_tail``
    (CR-5 default) maps them to different elevations below the scale.
    """
    from worldsim.physical.terrain.elevation import raw_to_elevation_m

    raw_a = np.array([[0.4, 0.8], [0.5, 0.9]], dtype=np.float64)
    raw_b = np.array([[0.4, 0.7], [0.5, 1.5]], dtype=np.float64)
    ocean = np.array([[True, False], [False, False]], dtype=bool)
    # sea at 0.45 so land cells are positive centered
    ea = raw_to_elevation_m(raw_a, 0.45, land_scale_m=land_scale_m, ocean_scale_m=1000.0)
    eb = raw_to_elevation_m(raw_b, 0.45, land_scale_m=land_scale_m, ocean_scale_m=1000.0)
    return {
        "max_a": float(ea[~ocean].max()),
        "max_b": float(eb[~ocean].max()),
        "land_scale_m": float(land_scale_m),
    }
