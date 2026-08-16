from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from worldsim.config import load_planet_config, default_config_path
from worldsim.pipeline import run_tectonics
from worldsim.physical.tectonics import PyPlatecParams
from worldsim.progress import ProgressReporter
from io import StringIO


def test_run_tectonics_pipeline_small(tmp_path: Path) -> None:
    config = load_planet_config(default_config_path())
    buf = StringIO()
    reporter = ProgressReporter(stream=buf)
    state = run_tectonics(
        config=config,
        master_seed=99,
        output_dir=tmp_path / "world",
        reporter=reporter,
        width=40,
        height=20,
        params=PyPlatecParams(num_plates=4),
    )
    reporter.close()
    events = [json.loads(line) for line in buf.getvalue().splitlines() if line]
    assert events[0]["event"] == "started"
    assert events[-1]["event"] == "complete"
    assert any(e.get("stage") == "tectonics" for e in events)
    assert (tmp_path / "world" / "tectonics" / "tectonics_baseline.npz").is_file()
    assert state.tectonics is not None
    assert state.tectonics.shape == (20, 40)
    assert state.metadata["tectonics_metadata_source"] == "native_extended"
    assert state.metadata.get("tectonics_interpretation") is True
    assert "crust_age" in state.rasters
    assert "boundary_mask" in state.rasters
    assert "tectonic_activity" in state.rasters
    data = np.load(tmp_path / "world" / "tectonics" / "tectonics_extended.npz")
    assert data["elevation_raw"].shape == (20, 40)
    assert "plate_velocity_x" in data.files
    interp = np.load(tmp_path / "world" / "tectonics" / "tectonics_interpretation.npz")
    assert "boundary_type" in interp.files
    assert int(state.metadata["boundary_cell_count"]) > 0
