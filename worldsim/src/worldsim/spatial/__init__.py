"""Spatial substrate: coordinates, extents, and later stores/indexes."""

from __future__ import annotations

from worldsim.spatial.coordinates import (
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
