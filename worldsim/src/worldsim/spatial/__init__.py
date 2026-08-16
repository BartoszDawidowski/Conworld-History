"""Spatial substrate: coordinates, extents, metrics, and later stores/indexes."""

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
from worldsim.spatial.metrics import EARTH_RADIUS_KM, GridMetrics, grid_metrics

__all__ = [
    "EARTH_RADIUS_KM",
    "CoordinateSystem",
    "GridIndex",
    "GridMetrics",
    "SpatialExtent",
    "clamp_y",
    "grid_metrics",
    "lat_to_y",
    "lon_to_x",
    "wrap_x",
    "x_to_lon",
    "y_to_lat",
]
