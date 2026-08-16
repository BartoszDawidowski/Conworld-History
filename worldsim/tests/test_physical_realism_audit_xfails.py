"""Annex audit invariants — fixed by later PR milestones become required.

MOIST-01…03 are required after PR-4. Remaining HYP legacy notes live in PR-2 tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.moisture.transport import _upwind_advect
from worldsim.spatial.hex_grid.layout import HexGridSpec, hex_center_xy, hex_latitudes_deg
from worldsim.validation.physical_realism.fixtures import (
    january_dry_start_ramp,
    precip_vs_available_q_overshoot,
)


def test_audit_northward_wind_moves_moisture_to_smaller_j() -> None:
    """PR-4 MOIST-01."""
    h, w = 21, 9
    j0, i0 = 10, 4
    q = np.zeros((h, w), dtype=np.float64)
    q[j0, i0] = 1.0
    u = np.zeros((h, w), dtype=np.float64)
    v = np.full((h, w), 8.0, dtype=np.float64)
    out = q.copy()
    for _ in range(4):
        out = _upwind_advect(out, u, v, dt=0.25, wind_scale=0.25)
    north = float(out[:j0, :].sum())
    south = float(out[j0 + 1 :, :].sum())
    assert north > south, (
        "wind_v>0 must move moisture toward smaller j (north); "
        f"got north={north:.4f} south={south:.4f}"
    )


def test_audit_precip_never_exceeds_available_moisture() -> None:
    """PR-4 MOIST-02."""
    probe = precip_vs_available_q_overshoot()
    assert probe["max_overshoot"] <= 1e-9, (
        f"precip exceeds available q by up to {probe['max_overshoot']:.4f}"
    )


def test_audit_constant_climate_has_no_january_startup_ramp() -> None:
    """PR-4 MOIST-03."""
    ramp = january_dry_start_ramp()
    monthly = ramp["monthly_land_mean_precip"]
    assert ramp["max_minus_min"] / max(float(np.mean(monthly)), 1e-12) < 0.05
    assert monthly[0] == pytest.approx(monthly[6], rel=0.05)


def test_audit_hex_latitudes_mirror_and_mean_near_zero() -> None:
    """PR-1 GRID-02 — required to pass."""
    spec = HexGridSpec(width=256, height=128)
    lats = hex_latitudes_deg(spec)
    assert abs(float(lats.mean())) < 0.25
    for q in (0, 1, 2, 255):
        for r in (0, 127):
            _x, y = hex_center_xy(q, r, width=256, height=128)
            assert abs(y) < 1.0 - 1e-9, f"clipped pole centre at q={q} r={r} y={y}"
    w, h = 32, 16
    ys = []
    for r in range(h):
        row_y = [hex_center_xy(q, r, width=w, height=h)[1] for q in range(w)]
        ys.append(float(np.mean(row_y)))
    for r in range(h // 2):
        assert abs(ys[r] + ys[h - 1 - r]) < 0.02, (
            f"row y asymmetry r={r}: {ys[r]} vs {ys[h - 1 - r]}"
        )
