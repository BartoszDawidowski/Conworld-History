"""Diagnostics for Milestone 2 PyPlatec baseline maps."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.extent import SpatialExtent


def plates_touching_both_poles(plate_id: NDArray[np.integer]) -> list[int]:
    """Plate IDs that appear on both northernmost and southernmost rows.

    PyPlatec is toroidal; such IDs are artefacts to report. Our spatial model
    still forbids treating N–S edges as adjacent.
    """
    top = set(np.unique(plate_id[0, :]).tolist())
    bottom = set(np.unique(plate_id[-1, :]).tolist())
    return sorted(int(p) for p in top.intersection(bottom))


def assert_no_ns_adjacency(extent: SpatialExtent) -> None:
    """Acceptance helper: neighbour steps must not wrap north–south."""
    height = extent.height
    width = extent.width
    assert extent.neighbour(0, 0, 0, -1) is None
    assert extent.neighbour(0, height - 1, 0, 1) is None
    # E–W wrap still allowed
    assert extent.neighbour(0, 0, -1, 0) is not None
    assert extent.neighbour(width - 1, height - 1, 1, 0) is not None


def build_tectonics_diagnostics(
    *,
    elevation: NDArray[np.floating],
    plate_id: NDArray[np.integer],
    seam_column: int,
    seam_gap_before: float,
    seam_gap_after: float,
    seed: int,
    steps: int,
) -> dict[str, Any]:
    height, width = elevation.shape
    unique_plates = np.unique(plate_id)
    touching = plates_touching_both_poles(plate_id)
    return {
        "seed": int(seed),
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "plate_count": int(unique_plates.size),
        "plate_ids": [int(x) for x in unique_plates.tolist()],
        "elevation_min": float(np.min(elevation)),
        "elevation_max": float(np.max(elevation)),
        "elevation_mean": float(np.mean(elevation)),
        "seam_column_selected": int(seam_column),
        "seam_gap_before_roll": float(seam_gap_before),
        "seam_gap_after_roll": float(seam_gap_after),
        "plates_touching_both_poles": touching,
        "ns_wrap_in_model": False,
        "notes": [
            "PyPlatec simulation is toroidal; final worldsim model uses E–W wrap only.",
            "plates_touching_both_poles lists raw ID overlaps on pole rows (not model adjacency).",
        ],
    }
