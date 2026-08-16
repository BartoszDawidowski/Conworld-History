"""Coordinate helpers for vector layers (normalised cylindrical space)."""

from __future__ import annotations

from worldsim.spatial.extent import SpatialExtent


def cell_center_norm(
    col: float,
    row: float,
    extent: SpatialExtent,
) -> tuple[float, float]:
    """Map continuous column/row (cell centres OK) to normalised (x, y)."""
    width, height = extent.width, extent.height
    i = float(col)
    j = float(row)
    x = (i + 0.5) / width
    y = 1.0 - (j + 0.5) * 2.0 / height
    return float(x % 1.0), float(y)


def pyflwdir_xy_to_norm(
    x: float,
    y: float,
    extent: SpatialExtent,
) -> tuple[float, float]:
    """Convert pyflwdir default stream coordinates to normalised (x, y).

    Default streams use ``xs = col + 0.5``, ``ys = -(row + 0.5)``.
    """
    col = float(x) - 0.5
    row = -float(y) - 0.5
    return cell_center_norm(col, row, extent)


def polyline_length_norm(coords: list[tuple[float, float]]) -> float:
    """Polyline length in normalised space (E–W unwrap locally)."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        dx = x1 - x0
        if dx > 0.5:
            dx -= 1.0
        elif dx < -0.5:
            dx += 1.0
        total += (dx * dx + (y1 - y0) * (y1 - y0)) ** 0.5
    return float(total)
