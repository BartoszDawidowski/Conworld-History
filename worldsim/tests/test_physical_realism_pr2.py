"""PR-2 hypsometry power_tail_v2 + robust terrain detail tests."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.terrain.elevation import (
    power_tail_v2_curve,
    power_tail_v2_land_m,
    raw_to_elevation_m,
)
from worldsim.physical.terrain.refine import refine_terrain, robust_tectonic_range
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def test_power_tail_curve_c1_at_anchor() -> None:
    p = 0.7
    m = 3.0
    xs = np.array([0.0, 0.5, 1.0, 1.0 + 1e-6, 2.0, 10.0], dtype=np.float64)
    f = power_tail_v2_curve(xs, body_exponent=p, asymptote_ratio=m)
    assert f[0] == pytest.approx(0.0)
    assert f[2] == pytest.approx(1.0)
    # Numerical derivative from both sides near 1
    eps = 1e-5
    left = (
        power_tail_v2_curve(np.array([1.0]), body_exponent=p, asymptote_ratio=m)[0]
        - power_tail_v2_curve(np.array([1.0 - eps]), body_exponent=p, asymptote_ratio=m)[
            0
        ]
    ) / eps
    right = (
        power_tail_v2_curve(np.array([1.0 + eps]), body_exponent=p, asymptote_ratio=m)[0]
        - power_tail_v2_curve(np.array([1.0]), body_exponent=p, asymptote_ratio=m)[0]
    ) / eps
    assert left == pytest.approx(p, rel=1e-3)
    assert right == pytest.approx(p, rel=1e-3)
    assert f[-1] < m
    assert np.all(np.diff(f) >= -1e-12)


def test_power_tail_zero_and_rank() -> None:
    raw = np.array(
        [
            [0.2, 0.5, 0.8, 1.2],
            [0.3, 0.6, 0.9, 1.5],
        ],
        dtype=np.float64,
    )
    ocean = raw < 0.45
    land_m, diag = power_tail_v2_land_m(
        raw,
        0.45,
        ocean,
        anchor_quantile=0.9,
        anchor_elevation_m=3000.0,
        body_exponent=0.7,
        max_elevation_m=9000.0,
    )
    assert float(land_m[ocean].max()) == 0.0
    land = ~ocean
    u = np.maximum(raw[land] - 0.45, 0.0)
    # Monotonic: higher u → higher or equal elevation
    order = np.argsort(u)
    z = land_m[land][order]
    assert np.all(np.diff(z) >= -1e-9)
    assert diag["land_max_m"] < 9000.0 + 1e-6


def test_power_tail_maxima_differ_across_peaks() -> None:
    """HYP-01: two different peaks must not both hit a fixed mechanical max."""
    ocean = np.array([[True, False], [False, False]], dtype=bool)
    raw_a = np.array([[0.4, 0.8], [0.5, 0.9]], dtype=np.float64)
    raw_b = np.array([[0.4, 0.7], [0.5, 1.5]], dtype=np.float64)
    ea, _ = power_tail_v2_land_m(raw_a, 0.45, ocean, max_elevation_m=9000.0)
    eb, _ = power_tail_v2_land_m(raw_b, 0.45, ocean, max_elevation_m=9000.0)
    max_a = float(ea[~ocean].max())
    max_b = float(eb[~ocean].max())
    assert not (
        np.isclose(max_a, 9000.0, atol=1.0) and np.isclose(max_b, 9000.0, atol=1.0)
    )
    assert max_b > max_a


def test_legacy_mode_still_hits_land_scale() -> None:
    raw = np.array([[0.4, 0.8], [0.5, 0.9]], dtype=np.float64)
    ocean = np.array([[True, False], [False, False]], dtype=bool)
    out = raw_to_elevation_m(
        raw,
        0.45,
        land_scale_m=9000.0,
        ocean_scale_m=1000.0,
        ocean_mask=ocean,
        hypsometry_mode="legacy_max",
    )
    assert float(out[~ocean].max()) == pytest.approx(9000.0)


def test_robust_range_insensitive_to_outlier() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(size=(64, 128))
    spiked = base.copy()
    spiked[0, 0] = 1e6
    r0, _ = robust_tectonic_range(base)
    r1, d1 = robust_tectonic_range(spiked)
    assert r1 == pytest.approx(r0, rel=0.05)
    assert d1["peak_to_peak"] > d1["robust_range"] * 10


def test_refine_outlier_does_not_inflate_detail_rms() -> None:
    elev = np.linspace(0.2, 0.8, 32 * 16, dtype=np.float64).reshape(32, 16)
    a = refine_terrain(
        elevation_raw=elev,
        out_width=64,
        out_height=32,
        detail_seed=7,
        detail_amplitude=0.08,
    )
    elev2 = elev.copy()
    elev2[0, 0] = 50.0
    b = refine_terrain(
        elevation_raw=elev2,
        out_width=64,
        out_height=32,
        detail_seed=7,
        detail_amplitude=0.08,
    )
    # Compare detail proxy: difference from bilinear upsample of base without spike
    from worldsim.spatial.resample import upsample_bilinear_cylindrical

    base_a = upsample_bilinear_cylindrical(elev, 64, 32)
    base_b = upsample_bilinear_cylindrical(elev2, 64, 32)
    # Exclude the spiked neighbourhood when measuring RMS detail change
    mask = np.ones((32, 64), dtype=bool)
    mask[:4, :4] = False
    det_a = a - base_a
    det_b = b - base_b
    rms_a = float(np.sqrt(np.mean(det_a[mask] ** 2)))
    rms_b = float(np.sqrt(np.mean(det_b[mask] ** 2)))
    assert abs(rms_b - rms_a) / max(rms_a, 1e-12) < 0.15


def test_terrain_pipeline_power_tail_invariants() -> None:
    tectonics = run_pyplatec_extended(
        seed=42,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    result = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(
            width=128,
            height=64,
            ocean_fraction_target=0.71,
            land_scale_m=9000.0,
            ocean_scale_m=10000.0,
            hypsometry_mode="power_tail_v2",
            hypsometry_anchor_elevation_m=3000.0,
            hypsometry_body_exponent=0.70,
            hypsometry_max_elevation_m=9000.0,
        ),
        detail_seed=3,
    )
    d = result.diagnostics
    assert d["hypsometry"]["hypsometry_mode"] == "power_tail_v2"
    assert d["ocean_mask_unchanged"] is True
    assert d["land_components_unchanged"] is True
    assert d["rank_order_ok"] is True
    land = ~result.ocean_mask
    assert float(result.elevation_m[land].min()) >= 0.0
    # Not forced to exact land_scale across the board
    assert not np.isclose(float(result.elevation_m[land].max()), 9000.0, atol=0.5)
