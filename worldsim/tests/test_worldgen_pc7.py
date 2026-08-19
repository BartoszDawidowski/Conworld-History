"""PC7 — production suite, performance recovery, C10 readiness gate."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.validation.production_closure.baseline import load_atlas_baseline
from worldsim.validation.production_closure.c10_readiness import (
    C10_READINESS_VERSION,
    review_c10_readiness,
)
from worldsim.validation.production_closure.performance import (
    PC7_OPTIMIZATION_VERSION,
    PC7_OPTIMIZATIONS,
    analyze_stage_regression,
)
from worldsim.validation.production_closure.seeds import (
    PC7_ATLAS_SEEDS,
    PC7_FULL_SEEDS,
    PC7_QUICK_SEEDS,
    PC7_SCHEMA_VERSION,
)
from worldsim.validation.production_closure.suite import (
    build_pc7_report,
    directory_size_bytes,
    run_production_seed,
)

pytestmark = pytest.mark.pc7

ROOT = Path(__file__).resolve().parents[2]
GODOT = ROOT / "godot"


def test_pc7_seed_matrix_defined() -> None:
    assert PC7_QUICK_SEEDS == (1, 42, 100)
    assert PC7_ATLAS_SEEDS == (42, 183716)
    assert PC7_FULL_SEEDS == (42,)


def test_runtime_regression_analysis() -> None:
    base = load_atlas_baseline()["runtime_s"]
    analysis = analyze_stage_regression(
        {
            "hydrology": 48.0,
            "final": 22.0,
            "moisture": 18.0,
            "erosion": 12.0,
            "terrain": 10.0,
        },
        total_elapsed_s=float(base["atlas_total_current_audit"]),
    )
    assert analysis["dominant_stage"] == "hydrology"
    assert analysis["regression_fraction"] == pytest.approx(0.22, rel=0.02)
    assert analysis["regression_above_15pct_warning"] is True
    assert len(analysis["optimizations_applied"]) == len(PC7_OPTIMIZATIONS)


def test_c10_readiness_fail_closed_on_baseline_gates() -> None:
    base = load_atlas_baseline()
    review = review_c10_readiness(
        gates=base["canonical_gates"],
        suite_ok=True,
        performance_documented=True,
    )
    assert review["version"] == C10_READINESS_VERSION
    assert review["status"] == "NOT_READY_FOR_CALIBRATION"
    assert "hydrology_ok" in review["failed_gates"]
    assert review["user_review_required"] is True


def test_pc7_report_schema() -> None:
    report = build_pc7_report(seed_results=[])
    assert report["schema_version"] == PC7_SCHEMA_VERSION
    assert report["performance"]["optimization_version"] == PC7_OPTIMIZATION_VERSION
    assert report["c10_readiness"]["ready_for_calibration"] is False


def test_directory_size_helper(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 100)
    assert directory_size_bytes(tmp_path) == 100


@pytest.mark.slow
def test_quick_seed_smoke_run(tmp_path: Path) -> None:
    config = load_planet_config(default_config_path())
    result = run_production_seed(
        config=config,
        profile="quick",
        master_seed=42,
        output_dir=tmp_path / "quick_42",
        write_maps=True,
    )
    assert result.precip_scale_mm == 200.0
    assert (tmp_path / "quick_42" / "world" / "effective_config.json").is_file()
    assert (tmp_path / "quick_42" / "stage_timing.json").is_file()
    assert (tmp_path / "quick_42" / "absolute_maps" / "elevation_m.png").is_file()
    assert result.artifact_bytes > 0
    assert "moisture_spinup_ok" in result.gates


def test_godot_pc7_smoke_script_exists() -> None:
    script = GODOT / "tools" / "pc7_smoke.gd"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "inspector_status" in text
    assert "atlas_meta.json" in text


@pytest.mark.slow
def test_godot_headless_smoke_on_generated_world(tmp_path: Path) -> None:
    config = load_planet_config(default_config_path())
    out = tmp_path / "quick_1"
    run_production_seed(
        config=config,
        profile="quick",
        master_seed=1,
        output_dir=out,
        write_maps=False,
    )
    godot_bin = os.environ.get("GODOT_BIN")
    if not godot_bin:
        for candidate in (
            ROOT / "Godot.app" / "Contents" / "MacOS" / "Godot",
            Path("/Applications/Godot.app/Contents/MacOS/Godot"),
        ):
            if candidate.is_file():
                godot_bin = str(candidate)
                break
    if not godot_bin or not Path(godot_bin).is_file():
        pytest.skip("Godot binary not found (set GODOT_BIN or install Godot 4.7)")
    proc = subprocess.run(
        [
            godot_bin,
            "--headless",
            "--path",
            str(GODOT),
            "--script",
            "res://tools/pc7_smoke.gd",
            "--",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
