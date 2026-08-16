"""Compatibility shim — prefer ``worldsim.spatial.coordinates``.

Architecture path mapping listed ``coordinates.py`` at the package root; the
Milestone 1 implementation lives under ``worldsim.spatial`` as requested.
"""

from __future__ import annotations

from worldsim.spatial.coordinates import *  # noqa: F403
from worldsim.spatial.coordinates import (
    CoordinateError,
    CoordinateSystem,
    clamp_y,
    lat_to_y,
    lon_to_x,
    wrap_x,
    x_to_lon,
    y_to_lat,
)
from worldsim.spatial.extent import GridIndex, SpatialExtent

__all__ = [
    "CoordinateError",
    "CoordinateSystem",
    "GridIndex",
    "SpatialExtent",
    "clamp_y",
    "lat_to_y",
    "lon_to_x",
    "wrap_x",
    "x_to_lon",
    "y_to_lat",
]
