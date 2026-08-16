"""East–west seam selection for cylindrical worlds (architecture §11.4)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def score_seam_columns(elevation: NDArray[np.floating]) -> NDArray[np.float64]:
    """Lower score = better E–W cut (prefer ocean / low relief columns)."""
    if elevation.ndim != 2:
        raise ValueError("elevation must be 2D (height, width)")
    # Prefer low mean elevation and low column variance (quieter seam).
    mean = elevation.mean(axis=0).astype(np.float64)
    var = elevation.var(axis=0).astype(np.float64)
    return mean + 0.25 * var


def select_ew_seam(elevation: NDArray[np.floating]) -> int:
    """Return column index to place at the western edge after rolling."""
    scores = score_seam_columns(elevation)
    return int(np.argmin(scores))


def roll_ew(
    arrays: tuple[NDArray, ...],
    seam_column: int,
) -> tuple[NDArray, ...]:
    """Roll arrays so ``seam_column`` becomes column 0 (map left edge)."""
    if not arrays:
        return ()
    width = arrays[0].shape[1]
    if seam_column < 0 or seam_column >= width:
        raise ValueError(f"seam_column {seam_column} out of range for width {width}")
    return tuple(np.roll(arr, -int(seam_column), axis=1) for arr in arrays)


def seam_edge_elevation_gap(elevation: NDArray[np.floating]) -> float:
    """Mean absolute elevation jump across the E–W wrap edge (cols 0 and -1)."""
    return float(np.mean(np.abs(elevation[:, 0] - elevation[:, -1])))
