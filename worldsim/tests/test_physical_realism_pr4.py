"""PR-4 — moisture correctness: v-sign, budget, diffusion, spin-up."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.moisture.transport import (
    _upwind_advect,
    build_monthly_moisture,
    partition_precipitation,
    saturation_capacity,
)


def test_four_direction_impulses_and_no_ns_wrap() -> None:
    h, w = 21, 21
    j0, i0 = 10, 10

    def run(u0: float, v0: float) -> np.ndarray:
        q = np.zeros((h, w), dtype=np.float64)
        q[j0, i0] = 1.0
        u = np.full((h, w), u0)
        v = np.full((h, w), v0)
        out = q.copy()
        for _ in range(5):
            out = _upwind_advect(out, u, v, dt=0.2, wind_scale=0.3)
        return out

    east = run(8.0, 0.0)
    west = run(-8.0, 0.0)
    north = run(0.0, 8.0)
    south = run(0.0, -8.0)

    assert float(east[:, i0 + 1 :].sum()) > float(east[:, :i0].sum())
    assert float(west[:, :i0].sum()) > float(west[:, i0 + 1 :].sum())
    assert float(north[:j0, :].sum()) > float(north[j0 + 1 :, :].sum())
    assert float(south[j0 + 1 :, :].sum()) > float(south[:j0, :].sum())

    # No N–S wrap: mass near poles under strong meridional wind stays finite at edges
    strong_n = run(0.0, 20.0)
    assert float(strong_n[-1, :].sum()) < 0.05


def test_ew_seam_westward_wrap() -> None:
    h, w = 9, 16
    q = np.zeros((h, w), dtype=np.float64)
    q[4, 0] = 1.0
    u = np.full((h, w), -10.0)
    v = np.zeros((h, w))
    out = q.copy()
    for _ in range(3):
        out = _upwind_advect(out, u, v, dt=0.25, wind_scale=0.3)
    assert float(out[:, -1].sum()) > float(out[:, 1:3].sum())


def test_precip_components_sum_and_budget_cap() -> None:
    h, w = 12, 20
    q = np.full((h, w), 2.0)
    capacity = saturation_capacity(np.full((h, w), 30.0))
    land_dry = np.ones((h, w))
    lift = np.zeros((h, w))
    lift[:, 8:12] = 2.0
    part = partition_precipitation(
        q=q,
        capacity=capacity,
        land_dry=land_dry,
        lift=lift,
        temperature_c=np.full((h, w), 30.0),
        latitude_deg=np.zeros((h, w)),
        large_scale_frac=0.9,
        orographic_frac=2.0,
        convective_scale=3.0,
        lee_dry=0.0,
    )
    precip = part["precipitation"]
    assert np.allclose(
        precip,
        part["large_scale_precip"]
        + part["orographic_precip"]
        + part["convective_precip"]
        + part["itcz_precip"],
    )
    assert float(np.max(precip - q)) <= 1e-9


def test_spinup_removes_january_ramp() -> None:
    months = 12
    h, w = 10, 20
    temp = np.full((months, h, w), 24.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :4] = True
    wu = np.full((months, h, w), 5.0)
    wv = np.zeros((months, h, w))
    elev = np.zeros((h, w))
    lat = np.zeros((h, w))
    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=months,
        advect_steps=6,
        spinup_max_years=5,
    )
    land = ~ocean
    monthly = [float(fields["precipitation"][m][land].mean()) for m in range(months)]
    assert max(monthly) - min(monthly) < 0.05 * max(float(np.mean(monthly)), 1e-9)
    assert fields["budget"]["spinup_converged"] is True
    assert fields["budget"]["max_precip_overshoot"] <= 1e-9


def test_advect_steps_convergence() -> None:
    """Changing steps alone (fixed physical mix/wind) stays within tolerance."""
    months = 12
    h, w = 10, 24
    temp = np.full((months, h, w), 22.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :5] = True
    wu = np.full((months, h, w), 6.0)
    wv = np.zeros((months, h, w))
    elev = np.zeros((h, w))
    lat = np.zeros((h, w))
    kwargs = dict(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=months,
        advect_wind_scale=0.1,
        diffusion_mix_per_month=0.08,
        large_scale_frac=0.2,
        spinup_max_years=3,
    )
    a = build_monthly_moisture(**kwargs, advect_steps=8)["precipitation"]
    b = build_monthly_moisture(**kwargs, advect_steps=32)["precipitation"]
    land = ~ocean
    mean_a = float(a[:, land].mean())
    mean_b = float(b[:, land].mean())
    denom = max(abs(mean_a), abs(mean_b), 1e-9)
    assert abs(mean_a - mean_b) / denom < 0.15


def test_month_rotation_preserves_climatology() -> None:
    months = 12
    h, w = 8, 16
    temp = np.full((months, h, w), 20.0)
    for m in range(months):
        temp[m] += 4.0 * np.sin(2 * np.pi * m / 12.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :3] = True
    wu = np.full((months, h, w), 4.0)
    wv = np.zeros((months, h, w))
    elev = np.zeros((h, w))
    lat = np.zeros((h, w))
    base = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=months,
        advect_steps=6,
        spinup_max_years=4,
    )["precipitation"]
    # Rotate forcing by 3 months
    shift = 3
    temp_r = np.roll(temp, shift, axis=0)
    wu_r = np.roll(wu, shift, axis=0)
    rot = build_monthly_moisture(
        temperature_c=temp_r,
        wind_u=wu_r,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=months,
        advect_steps=6,
        spinup_max_years=4,
    )["precipitation"]
    # Rotating labels should rotate the annual cycle, not reshape it.
    assert np.allclose(np.roll(base, shift, axis=0), rot, rtol=0.08, atol=0.05)
