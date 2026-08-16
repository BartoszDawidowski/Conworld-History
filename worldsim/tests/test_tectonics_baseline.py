from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from worldsim.physical.tectonics.baseline import PyPlatecParams, run_pyplatec_baseline
from worldsim.physical.tectonics.diagnostics import (
    assert_no_ns_adjacency,
    plates_touching_both_poles,
)
from worldsim.physical.tectonics.seam import (
    roll_ew,
    select_ew_seam,
    seam_edge_elevation_gap,
)
from worldsim.spatial.extent import SpatialExtent


def test_select_ew_seam_prefers_low_column() -> None:
    elevation = np.ones((8, 10), dtype=np.float64)
    elevation[:, 3] = 0.0
    assert select_ew_seam(elevation) == 3


def test_roll_ew_moves_seam_to_column_zero() -> None:
    elevation = np.arange(20, dtype=np.float64).reshape(2, 10)
    plates = np.arange(20, dtype=np.int32).reshape(2, 10)
    rolled_e, rolled_p = roll_ew((elevation, plates), 3)
    np.testing.assert_array_equal(rolled_e[:, 0], elevation[:, 3])
    np.testing.assert_array_equal(rolled_p[:, 0], plates[:, 3])


def test_ns_adjacency_forbidden_on_extent() -> None:
    assert_no_ns_adjacency(SpatialExtent.from_shape(64, 32))


def test_pyplatec_baseline_deterministic_small() -> None:
    params = PyPlatecParams(num_plates=6, cycle_count=2)
    a = run_pyplatec_baseline(seed=42, width=64, height=32, params=params)
    b = run_pyplatec_baseline(seed=42, width=64, height=32, params=params)
    np.testing.assert_array_equal(a.elevation_raw, b.elevation_raw)
    np.testing.assert_array_equal(a.plate_id, b.plate_id)
    assert a.seam_column == b.seam_column
    assert a.shape == (32, 64)
    assert a.diagnostics["ns_wrap_in_model"] is False
    assert a.diagnostics["plate_count"] >= 1


def test_seam_consistent_after_roll() -> None:
    result = run_pyplatec_baseline(
        seed=7,
        width=48,
        height=24,
        params=PyPlatecParams(num_plates=5),
        apply_seam=True,
    )
    # After roll, selected column content sits at western edge.
    # Recompute seam on unrolled map via inverse roll.
    unrolled = np.roll(result.elevation_raw, result.seam_column, axis=1)
    assert select_ew_seam(unrolled) == result.seam_column
    # Seam gap metric is finite and diagnostics record before/after.
    assert result.diagnostics["seam_gap_after_roll"] == pytest.approx(
        seam_edge_elevation_gap(result.elevation_raw)
    )
    assert np.isfinite(result.diagnostics["seam_gap_before_roll"])


def test_save_tectonics_artefacts(tmp_path: Path) -> None:
    result = run_pyplatec_baseline(
        seed=11,
        width=32,
        height=16,
        params=PyPlatecParams(num_plates=4),
    )
    out = tmp_path / "tectonics"
    result.save(out)
    data = np.load(out / "tectonics_baseline.npz")
    np.testing.assert_array_equal(data["elevation_raw"], result.elevation_raw)
    np.testing.assert_array_equal(data["plate_id"], result.plate_id)
    diagnostics = json.loads((out / "tectonics_diagnostics.json").read_text())
    assert diagnostics["width"] == 32
    assert diagnostics["height"] == 16
    assert "plates_touching_both_poles" in diagnostics


@pytest.mark.slow
def test_pyplatec_baseline_1024x512_acceptance() -> None:
    """Architecture target resolution — deterministic + cylindrical invariants."""
    result = run_pyplatec_baseline(
        seed=183716,
        width=1024,
        height=512,
        params=PyPlatecParams(),
    )
    assert result.shape == (512, 1024)
    assert result.elevation_raw.dtype == np.float64
    assert result.plate_id.dtype == np.int32
    assert result.diagnostics["plate_count"] >= 1
    assert result.diagnostics["ns_wrap_in_model"] is False
    assert_no_ns_adjacency(result.extent)
    # Model adjacency never wraps N–S even if plate IDs touch both poles.
    _ = plates_touching_both_poles(result.plate_id)
    again = run_pyplatec_baseline(
        seed=183716,
        width=1024,
        height=512,
        params=PyPlatecParams(),
    )
    np.testing.assert_array_equal(result.elevation_raw, again.elevation_raw)
    assert result.seam_column == again.seam_column
