"""Spatial extent / raster grid index over the cylindrical world."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from worldsim.config import PlanetConfig


@dataclass(frozen=True)
class GridIndex:
    """Integer cell address on a raster extent."""

    i: int  # column (x / east–west)
    j: int  # row (y / north–south; j=0 is north)


@dataclass(frozen=True)
class SpatialExtent:
    """Axis-aligned extent in normalised coordinates with a discrete grid.

    Continuous domain matches architecture §11:

    - ``x`` half-open ``[0, 1)`` with east–west wrap
    - ``y`` closed ``[-1, 1]`` with **no** north–south wrap

    Row ``j = 0`` is the northern edge (``y → +1``); ``j = height - 1`` is south.
    """

    width: int
    height: int
    coordinate_system: CoordinateSystem = CoordinateSystem()
    x_min: float = 0.0
    x_max: float = 1.0
    y_min: float = -1.0
    y_max: float = 1.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise CoordinateError("width and height must be positive")
        if self.x_max <= self.x_min:
            raise CoordinateError("x_max must be greater than x_min")
        if self.y_max <= self.y_min:
            raise CoordinateError("y_max must be greater than y_min")
        if self.coordinate_system.wrap_y:
            raise CoordinateError("extent forbids north–south wrapping")
        # Project baseline uses the full cylindrical domain.
        if (self.x_min, self.x_max) != (0.0, 1.0):
            raise CoordinateError("Milestone 1 extents use x in [0, 1)")
        if (self.y_min, self.y_max) != (-1.0, 1.0):
            raise CoordinateError("Milestone 1 extents use y in [-1, 1]")

    @classmethod
    def from_shape(
        cls,
        width: int,
        height: int,
        *,
        coordinate_system: CoordinateSystem | None = None,
    ) -> SpatialExtent:
        return cls(
            width=int(width),
            height=int(height),
            coordinate_system=coordinate_system or CoordinateSystem(),
        )

    @classmethod
    def from_planet_config(
        cls,
        config: PlanetConfig,
        grid: str = "tectonics",
    ) -> SpatialExtent:
        mapping = {
            "tectonics": config.tectonics_resolution,
            "climate": config.climate_resolution,
            "terrain": config.terrain_production,
            "terrain_production": config.terrain_production,
            "terrain_target": config.terrain_target,
            "hydrology": config.hydrology_target,
            "hydrology_target": config.hydrology_target,
            "analysis": (config.analysis_width, config.analysis_height),
        }
        if grid not in mapping:
            raise CoordinateError(f"unknown grid name {grid!r}")
        width, height = mapping[grid]
        return cls.from_shape(
            width,
            height,
            coordinate_system=CoordinateSystem(
                wrap_x=config.wrap_x,
                wrap_y=config.wrap_y,
                projection=config.projection,
            ),
        )

    @property
    def cell_count(self) -> int:
        return self.width * self.height

    def wrap_column(self, i: int) -> int:
        """Wrap column index into ``[0, width)``."""
        return int(i) % self.width

    def contains_row(self, j: int) -> bool:
        return 0 <= int(j) < self.height

    def clamp_row(self, j: int) -> int:
        """Clamp row without wrapping (north–south edges are walls)."""
        if j < 0:
            return 0
        if j >= self.height:
            return self.height - 1
        return int(j)

    def normalize_index(self, i: int, j: int, *, clamp_ns: bool = False) -> GridIndex:
        """Apply E–W wrap; reject or clamp N–S."""
        col = self.wrap_column(i)
        row = int(j)
        if not self.contains_row(row):
            if clamp_ns:
                row = self.clamp_row(row)
            else:
                raise CoordinateError(
                    f"row j={j} outside [0, {self.height}); north–south wrap forbidden"
                )
        return GridIndex(i=col, j=row)

    def cell_center_xy(self, i: int, j: int) -> tuple[float, float]:
        """Normalised coordinates at the centre of cell ``(i, j)``."""
        idx = self.normalize_index(i, j)
        x = (idx.i + 0.5) / self.width
        y = self.y_max - (idx.j + 0.5) * (self.y_max - self.y_min) / self.height
        return wrap_x(x), clamp_y(y)

    def cell_center_lonlat(self, i: int, j: int) -> tuple[float, float]:
        x, y = self.cell_center_xy(i, j)
        return x_to_lon(x), y_to_lat(y)

    def xy_to_index(self, x: float, y: float, *, clamp_ns: bool = False) -> GridIndex:
        """Map continuous normalised coords to the containing cell."""
        x_w = wrap_x(x)
        y_c = clamp_y(y, strict=not clamp_ns)
        i = int(math.floor(x_w * self.width))
        if i >= self.width:
            i = 0
        # y: +1 → j=0, -1 → j=height (exclusive edge maps to last row)
        frac = (self.y_max - y_c) / (self.y_max - self.y_min)
        j = int(math.floor(frac * self.height))
        if j >= self.height:
            j = self.height - 1
        if j < 0:
            j = 0
        return self.normalize_index(i, j, clamp_ns=clamp_ns)

    def lonlat_to_index(
        self, lon_deg: float, lat_deg: float, *, clamp_ns: bool = False
    ) -> GridIndex:
        return self.xy_to_index(lon_to_x(lon_deg), lat_to_y(lat_deg), clamp_ns=clamp_ns)

    def neighbour(self, i: int, j: int, di: int, dj: int) -> GridIndex | None:
        """4/8-neighbour step. Returns ``None`` if the step would cross a pole edge."""
        col = self.wrap_column(i + di)
        row = int(j + dj)
        if not self.contains_row(row):
            return None
        return GridIndex(i=col, j=row)
