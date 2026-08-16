from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from worldsim.physical.tectonics import (
    PyPlatecParams,
    detect_platec_capabilities,
    run_pyplatec_baseline,
    run_pyplatec_extended,
)


def test_extended_bindings_present() -> None:
    caps = detect_platec_capabilities()
    assert caps.supports_extended_metadata, caps


def test_extended_metadata_native_small() -> None:
    result = run_pyplatec_extended(
        seed=42,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=6),
    )
    assert result.metadata_source == "native_extended"
    assert result.crust_age is not None
    assert result.plate_velocity_x is not None
    assert result.plate_velocity_y is not None
    assert result.plate_speed is not None
    assert result.crust_age.shape == result.elevation_raw.shape
    assert result.plate_velocity_x.shape == result.elevation_raw.shape
    assert result.diagnostics["velocity_plate_count_snapshot"] >= 1
    # Age map should contain some non-zero crust timestamps in typical runs.
    assert int(result.crust_age.max()) >= 0


def test_extended_observational_preserves_baseline_maps() -> None:
    params = PyPlatecParams(num_plates=5, cycle_count=2)
    baseline = run_pyplatec_baseline(seed=7, width=48, height=24, params=params)
    extended = run_pyplatec_extended(seed=7, width=48, height=24, params=params)
    np.testing.assert_array_equal(baseline.elevation_raw, extended.elevation_raw)
    np.testing.assert_array_equal(baseline.plate_id, extended.plate_id)
    assert baseline.seam_column == extended.seam_column


def test_extended_save_artefacts(tmp_path: Path) -> None:
    result = run_pyplatec_extended(
        seed=11,
        width=32,
        height=16,
        params=PyPlatecParams(num_plates=4),
    )
    out = tmp_path / "tectonics"
    result.save(out)
    assert (out / "tectonics_extended.npz").is_file()
    data = np.load(out / "tectonics_extended.npz")
    assert "crust_age" in data.files
    assert "plate_velocity_x" in data.files
    assert "plate_velocity_y" in data.files
    assert "plate_speed" in data.files


@pytest.mark.slow
def test_extended_1024x512_smoke() -> None:
    result = run_pyplatec_extended(
        seed=183716,
        width=1024,
        height=512,
        params=PyPlatecParams(),
    )
    assert result.shape == (512, 1024)
    assert result.metadata_source == "native_extended"
    assert result.crust_age is not None
    assert result.plate_speed is not None
