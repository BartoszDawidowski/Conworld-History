from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from worldsim.config import load_planet_config, default_config_path
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import (
    TerrainParams,
    benchmark_terrain_resolutions,
    build_terrain_ocean,
)
from worldsim.physical.terrain.refine import refine_terrain
from worldsim.physical.terrain.sealevel import calibrate_sea_level, measured_ocean_fraction
from worldsim.spatial.resample import upsample_bilinear_cylindrical


def test_upsample_preserves_ew_continuity() -> None:
    src = np.linspace(0, 1, 16 * 8, dtype=np.float64).reshape(8, 16)
    src[:, 0] = src[:, -1]
    out = upsample_bilinear_cylindrical(src, 32, 16)
    gap = float(np.mean(np.abs(out[:, 0] - out[:, -1])))
    assert gap < 0.05


def test_sea_level_hits_ocean_fraction_target() -> None:
    rng = np.random.default_rng(0)
    elev = rng.normal(size=(64, 128))
    thr = calibrate_sea_level(elev, ocean_fraction_target=0.71)
    frac = measured_ocean_fraction(elev < thr)
    assert frac == pytest.approx(0.71, abs=0.02)


def test_a6_ocean_fraction_change_visible_at_fixed_seed() -> None:
    """Acceptance A6: same tectonics seed, different ocean.fraction_target → land share moves."""
    tectonics = run_pyplatec_extended(
        seed=124,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=10, cycle_count=2),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    wet = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(
            width=128,
            height=64,
            ocean_fraction_target=0.80,
            detail_amplitude=0.08,
        ),
        detail_seed=99,
    )
    dry = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(
            width=128,
            height=64,
            ocean_fraction_target=0.50,
            detail_amplitude=0.08,
        ),
        detail_seed=99,
    )
    assert wet.ocean_fraction == pytest.approx(0.80, abs=0.05)
    assert dry.ocean_fraction == pytest.approx(0.50, abs=0.05)
    assert dry.ocean_fraction < wet.ocean_fraction - 0.15


def test_terrain_ocean_small_pipeline(tmp_path: Path) -> None:
    tectonics = run_pyplatec_extended(
        seed=21,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    result = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=99,
    )
    assert result.elevation_m.shape == (64, 128)
    assert result.ocean_mask.shape == result.elevation_m.shape
    assert result.ocean_fraction == pytest.approx(0.71, abs=0.05)
    assert result.diagnostics["seam_gap_relative"] < 0.25
    assert len(result.coastline_features) > 0
    assert all(len(f.geometry) >= 2 for f in result.coastline_features[:10])
    result.save(tmp_path / "terrain")
    assert (tmp_path / "terrain" / "terrain_ocean.npz").is_file()
    assert (tmp_path / "terrain" / "coastline_prototype.geojson").is_file()
    assert float(result.elevation_m[~result.ocean_mask].min()) >= -1e-6
    assert float(result.elevation_m[result.ocean_mask].max()) < 0.0


def test_macrostructure_not_relocated_by_detail() -> None:
    tectonics = run_pyplatec_extended(
        seed=7,
        width=48,
        height=24,
        params=PyPlatecParams(num_plates=4),
    )
    coarse = tectonics.elevation_raw
    base = upsample_bilinear_cylindrical(coarse, 96, 48)
    detailed = refine_terrain(
        elevation_raw=coarse,
        out_width=96,
        out_height=48,
        detail_seed=123,
        detail_amplitude=0.08,
    )
    corr = float(np.corrcoef(base.ravel(), detailed.ravel())[0, 1])
    assert corr > 0.90


def test_config_exposes_terrain_production() -> None:
    config = load_planet_config(default_config_path())
    assert config.terrain_production[0] > 0
    assert 0.0 < config.ocean_fraction_target < 1.0


@pytest.mark.slow
def test_benchmark_locks_production_resolution(tmp_path: Path) -> None:
    import json

    tectonics = run_pyplatec_extended(
        seed=183716,
        width=128,
        height=64,
        params=PyPlatecParams(num_plates=6),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    report = benchmark_terrain_resolutions(
        tectonics=tectonics,
        interpretation=interpretation,
        detail_seed=1,
        candidates=((4096, 2048), (2048, 1024)),
        memory_budget_bytes=2_000_000_000,
    )
    assert report["production_resolution"] in ([4096, 2048], [2048, 1024])
    (tmp_path / "benchmark.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
