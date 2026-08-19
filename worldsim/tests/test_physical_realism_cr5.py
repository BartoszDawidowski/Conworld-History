"""CR-5 — hypsometry tail_softness, power_tail_v2 default, landform km² floors."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.landforms import LandformParams, build_landform_analysis
from worldsim.physical.landforms.params import min_object_cells
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.terrain.elevation import power_tail_v2_curve, power_tail_v2_land_m
from worldsim.spatial.metrics import grid_metrics


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def test_tail_softness_identity_at_one() -> None:
    xs = np.array([0.5, 1.0, 1.5, 3.0], dtype=np.float64)
    a = power_tail_v2_curve(xs, body_exponent=1.5, asymptote_ratio=3.0, tail_softness=1.0)
    b = power_tail_v2_curve(xs, body_exponent=1.5, asymptote_ratio=3.0, tail_softness=1.0)
    assert np.allclose(a, b)
    # C1 at s=1: left/right derivative ≈ p
    p, m, eps = 1.5, 3.0, 1e-5
    left = (
        power_tail_v2_curve(np.array([1.0]), body_exponent=p, asymptote_ratio=m)[0]
        - power_tail_v2_curve(np.array([1.0 - eps]), body_exponent=p, asymptote_ratio=m)[0]
    ) / eps
    right = (
        power_tail_v2_curve(np.array([1.0 + eps]), body_exponent=p, asymptote_ratio=m)[0]
        - power_tail_v2_curve(np.array([1.0]), body_exponent=p, asymptote_ratio=m)[0]
    ) / eps
    assert left == pytest.approx(p, rel=1e-3)
    assert right == pytest.approx(p, rel=1e-3)


def test_tail_softness_stretches_tail_length() -> None:
    x = np.array([2.5], dtype=np.float64)
    tight = power_tail_v2_curve(x, body_exponent=1.5, asymptote_ratio=3.0, tail_softness=0.5)[0]
    soft = power_tail_v2_curve(x, body_exponent=1.5, asymptote_ratio=3.0, tail_softness=2.0)[0]
    assert tight > soft
    assert tight < 3.0 and soft < 3.0


def test_tail_softness_reaches_land_m() -> None:
    raw = np.array([[0.4, 0.9], [0.5, 2.0]], dtype=np.float64)
    ocean = np.array([[True, False], [False, False]], dtype=bool)
    e1, d1 = power_tail_v2_land_m(
        raw, 0.45, ocean, body_exponent=1.5, tail_softness=1.0
    )
    e2, d2 = power_tail_v2_land_m(
        raw, 0.45, ocean, body_exponent=1.5, tail_softness=0.4
    )
    assert d1["tail_softness"] == pytest.approx(1.0)
    assert d2["tail_softness"] == pytest.approx(0.4)
    assert float(e2[~ocean].max()) >= float(e1[~ocean].max()) - 1e-9


def test_config_cr5_defaults() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.hypsometry_mode == "power_tail_v2"
    assert cfg.hypsometry_body_exponent == pytest.approx(1.5)
    assert cfg.hypsometry_anchor_quantile == pytest.approx(0.95)
    assert cfg.hypsometry_anchor_elevation_m == pytest.approx(3000.0)
    hp = cfg.to_hydrology_params()
    assert hp.river_min_catchment_km2 == pytest.approx(500.0)
    lf = cfg.to_landform_params()
    assert lf.mountain_score_threshold == pytest.approx(0.60)
    assert lf.meso_radius_km == pytest.approx(150.0)
    assert lf.min_plateau_km2 == pytest.approx(2500.0)


def test_min_object_cells_resolution_invariant_area() -> None:
    coarse = min_object_cells(min_km2=800.0, min_cells=12, cell_area_km2=400.0)
    fine = min_object_cells(min_km2=800.0, min_cells=12, cell_area_km2=100.0)
    assert coarse == 2
    assert fine == 8
    assert min_object_cells(min_km2=None, min_cells=12, cell_area_km2=100.0) == 12


def test_production_defaults_keep_plateau_and_limit_mountains() -> None:
    h, w = 48, 64
    ocean = _ocean_frame(h, w)
    elev = np.full((h, w), 100.0)
    elev[14:34, 18:46] = 900.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(),
    )
    assert res.diagnostics["calibrated"] is True
    assert len(res.plateaus) >= 1
    assert res.diagnostics["mountain_land_fraction"] < 0.40
    assert res.diagnostics["landforms_geometry_ok"] is True

    cone = np.full((h, w), 200.0)
    jj, ii = np.ogrid[:h, :w]
    cone = cone + 2200.0 * np.exp(-((ii - 32) ** 2 + (jj - 24) ** 2) / 12.0)
    cone = np.where(ocean, -200.0, cone)
    cres = build_landform_analysis(
        elevation_m=cone,
        ocean_mask=ocean,
        params=LandformParams(
            min_range_km2=None,
            fine_radius_km=20.0,
            meso_radius_km=50.0,
            macro_radius_km=120.0,
            planet_radius_km=250.0,
        ),
    )
    assert len(cres.mountain_ranges) >= 1
    assert float(cres.mountain_score_u8[24, 32]) >= 0.60 * 255 * 0.85


def test_hydro_catchment_cells_scale_with_grid() -> None:
    q = grid_metrics(256, 128).cells_for_area_km2(500.0)
    full = grid_metrics(4096, 2048).cells_for_area_km2(500.0)
    assert q == 1
    assert full > q
    assert full >= 8


def test_three_seed_hypsometry_and_landform_table() -> None:
    """Quick-scale seeds 1/42/100: maxima differ; mountain fraction capped."""
    rows = []
    for seed in (1, 42, 100):
        tectonics = run_pyplatec_extended(
            seed=seed,
            width=64,
            height=32,
            params=PyPlatecParams(num_plates=5),
        )
        interpretation = run_tectonic_interpretation(tectonics)
        terrain = build_terrain_ocean(
            tectonics=tectonics,
            interpretation=interpretation,
            params=TerrainParams(
                width=128,
                height=64,
                ocean_fraction_target=0.71,
                land_scale_m=9000.0,
            ),
            detail_seed=seed,
        )
        land = ~terrain.ocean_mask
        z = terrain.elevation_m[land]
        lf = build_landform_analysis(
            elevation_m=terrain.elevation_m,
            ocean_mask=terrain.ocean_mask,
            analysis_width=128,
            analysis_height=64,
            params=LandformParams(),
        )
        rows.append(
            {
                "seed": seed,
                "p50_m": float(np.percentile(z, 50)),
                "mean_m": float(z.mean()),
                "max_m": float(z.max()),
                "hypsometry_mode": terrain.diagnostics["hypsometry"]["hypsometry_mode"],
                "mountain_frac": lf.diagnostics["mountain_land_fraction"],
                "ranges": lf.diagnostics["mountain_range_count"],
                "plateaus": lf.diagnostics["plateau_count"],
                "acceptance_ok": lf.diagnostics["acceptance_ok"],
            }
        )
        assert terrain.diagnostics["hypsometry"]["hypsometry_mode"] == "power_tail_v2"
        assert not np.isclose(float(z.max()), 9000.0, atol=0.5)
        assert lf.diagnostics["calibrated"] is True
        assert lf.diagnostics["mountain_land_fraction"] < 0.40
        assert int(lf.diagnostics["mountain_range_count"]) <= 200

    maxima = {round(r["max_m"], 0) for r in rows}
    assert len(maxima) >= 2
    out = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "validation"
        / "physical_realism_cr5"
        / "seed_table.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"seeds": rows}, indent=2) + "\n", encoding="utf-8")
