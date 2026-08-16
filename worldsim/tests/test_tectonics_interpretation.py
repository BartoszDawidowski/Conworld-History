from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.tectonics import (
    PyPlatecParams,
    run_pyplatec_extended,
    run_tectonic_interpretation,
)
from worldsim.physical.tectonics.interpretation import (
    BoundaryType,
    InterpretationParams,
    classify_boundary,
    cylindrical_distance_to_mask,
    interpret_tectonics,
)


def test_classify_boundary_from_relative_velocity() -> None:
    params = InterpretationParams(weak_speed=1e-6)
    assert classify_boundary(-1.0, 0.0, params=params) == BoundaryType.CONVERGENT
    assert classify_boundary(1.0, 0.0, params=params) == BoundaryType.DIVERGENT
    assert classify_boundary(0.0, 1.0, params=params) == BoundaryType.TRANSFORM
    assert classify_boundary(1.0, 1.0, params=params) == BoundaryType.OBLIQUE_DIVERGENT
    assert classify_boundary(-1.0, 1.0, params=params) == BoundaryType.OBLIQUE_CONVERGENT
    assert classify_boundary(0.0, 0.0, params=params) == BoundaryType.WEAK_INACTIVE


def test_synthetic_convergent_boundary() -> None:
    height, width = 16, 32
    plate_id = np.zeros((height, width), dtype=np.int32)
    plate_id[:, width // 2 :] = 1
    elevation = np.ones((height, width), dtype=np.float64)
    elevation[:, width // 2 :] = 2.0
    vx = np.where(plate_id == 0, 0.5, -0.5).astype(np.float64)
    vy = np.zeros((height, width), dtype=np.float64)

    result = interpret_tectonics(
        plate_id=plate_id,
        elevation=elevation,
        plate_velocity_x=vx,
        plate_velocity_y=vy,
    )
    assert result.boundary_mask.any()
    mid = width // 2
    boundary_types = result.boundary_type[:, mid - 1 : mid + 1]
    mask = result.boundary_mask[:, mid - 1 : mid + 1]
    assert np.isin(
        boundary_types[mask],
        [
            int(BoundaryType.CONVERGENT),
            int(BoundaryType.OBLIQUE_CONVERGENT),
        ],
    ).all()
    assert result.diagnostics["correlation_checks"]["activity_concentrated_near_boundaries"]
    assert result.convergence_strength.max() > 0.0
    assert result.orogenic_potential.max() > 0.0


def test_synthetic_divergent_boundary() -> None:
    height, width = 16, 32
    plate_id = np.zeros((height, width), dtype=np.int32)
    plate_id[:, width // 2 :] = 1
    elevation = np.full((height, width), 0.2, dtype=np.float64)
    vx = np.where(plate_id == 0, -0.5, 0.5).astype(np.float64)
    vy = np.zeros_like(vx)

    result = interpret_tectonics(
        plate_id=plate_id,
        elevation=elevation,
        plate_velocity_x=vx,
        plate_velocity_y=vy,
    )
    mid = width // 2
    types = result.boundary_type[:, mid - 1 : mid + 1]
    mask = result.boundary_mask[:, mid - 1 : mid + 1]
    assert np.isin(
        types[mask],
        [int(BoundaryType.DIVERGENT), int(BoundaryType.OBLIQUE_DIVERGENT)],
    ).all()
    assert result.divergence_strength.max() > 0.0
    assert result.volcanic_potential.max() > 0.0


def test_distance_transform_wraps_east_west() -> None:
    mask = np.zeros((8, 16), dtype=np.bool_)
    mask[:, 0] = True
    dist, _, _ = cylindrical_distance_to_mask(mask)
    assert dist[0, 0] == 0.0
    assert dist[0, -1] == 1.0
    assert dist[0, 8] == 8.0


def test_interpretation_on_extended_pyplatec(tmp_path: Path) -> None:
    tectonics = run_pyplatec_extended(
        seed=42,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=6),
    )
    result = run_tectonic_interpretation(tectonics)
    assert result.boundary_mask.any()
    assert result.diagnostics["boundary_cell_count"] > 0
    assert result.diagnostics["correlation_checks"]["ok"] is True
    result.save(tmp_path / "tectonics")
    data = np.load(tmp_path / "tectonics" / "tectonics_interpretation.npz")
    assert "boundary_type" in data.files
    assert "subduction_potential" in data.files
    assert "earthquake_potential" in data.files


def test_ew_seam_boundary_detection() -> None:
    height, width = 10, 20
    plate_id = np.zeros((height, width), dtype=np.int32)
    plate_id[:, -1] = 1
    elevation = np.ones((height, width), dtype=np.float64)
    vx = np.zeros((height, width), dtype=np.float64)
    vy = np.zeros((height, width), dtype=np.float64)
    vx[:, -1] = 0.2
    vx[:, 0] = -0.2
    result = interpret_tectonics(
        plate_id=plate_id,
        elevation=elevation,
        plate_velocity_x=vx,
        plate_velocity_y=vy,
    )
    assert result.boundary_mask[:, 0].any()
    assert result.boundary_mask[:, -1].any()
