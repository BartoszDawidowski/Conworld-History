"""Cylindrical equal-area coordinate helpers (architecture §11).

Normalised planar coordinates:

- ``x ∈ [0, 1)`` — longitude proxy; wraps east–west
- ``y ∈ [-1, 1]`` — ``y = sin(latitude)``; does **not** wrap north–south

Longitude / latitude use degrees unless a function name ends in ``_rad``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Y_MIN = -1.0
Y_MAX = 1.0
X_MIN = 0.0
X_MAX = 1.0


class CoordinateError(ValueError):
    """Invalid coordinate under the project cylindrical model."""


@dataclass(frozen=True)
class CoordinateSystem:
    """Project CRS: cylindrical equal-area conceptual mapping."""

    wrap_x: bool = True
    wrap_y: bool = False
    projection: str = "cylindrical_equal_area"

    def __post_init__(self) -> None:
        if self.wrap_y:
            raise CoordinateError("wrap_y must be false (no north–south wrapping)")
        if not self.wrap_x:
            raise CoordinateError("wrap_x must be true for the cylindrical world")
        if self.projection != "cylindrical_equal_area":
            raise CoordinateError(
                f"unsupported projection {self.projection!r}; "
                "expected 'cylindrical_equal_area'"
            )


def wrap_x(x: float) -> float:
    """Wrap ``x`` into the half-open interval ``[0, 1)``."""
    # math.fmod keeps sign of dividend; normalise into [0, 1).
    wrapped = math.fmod(float(x), 1.0)
    if wrapped < 0.0:
        wrapped += 1.0
    # Guard against -0.0 and tiny float noise at the seam.
    if wrapped >= 1.0 or wrapped == -0.0:
        wrapped = 0.0
    return wrapped


def clamp_y(y: float, *, strict: bool = False) -> float:
    """Keep ``y`` in ``[-1, 1]`` without wrapping.

    If ``strict`` is true, values outside the closed interval raise.
    """
    value = float(y)
    if strict and (value < Y_MIN or value > Y_MAX):
        raise CoordinateError(f"y={value} outside [-1, 1]; north–south wrap is forbidden")
    if value < Y_MIN:
        return Y_MIN
    if value > Y_MAX:
        return Y_MAX
    return value


def lon_to_x(lon_deg: float) -> float:
    """Convert longitude degrees in roughly ``[-180, 180]`` to wrapped ``x``."""
    return wrap_x((float(lon_deg) + 180.0) / 360.0)


def x_to_lon(x: float) -> float:
    """Convert normalised ``x`` to longitude degrees in ``[-180, 180)``."""
    return 360.0 * wrap_x(x) - 180.0


def lat_to_y(lat_deg: float) -> float:
    """Convert latitude degrees to equal-area ``y = sin(lat)``."""
    lat = float(lat_deg)
    if lat < -90.0 or lat > 90.0:
        raise CoordinateError(f"latitude {lat} out of [-90, 90]")
    return math.sin(math.radians(lat))


def y_to_lat(y: float) -> float:
    """Convert equal-area ``y`` to latitude degrees via ``asin(y)``."""
    return math.degrees(math.asin(clamp_y(y, strict=True)))


def lat_to_y_rad(lat_rad: float) -> float:
    if lat_rad < -math.pi / 2 or lat_rad > math.pi / 2:
        raise CoordinateError(f"latitude_rad {lat_rad} out of [-π/2, π/2]")
    return math.sin(float(lat_rad))


def y_to_lat_rad(y: float) -> float:
    return math.asin(clamp_y(y, strict=True))


def normalised_to_lonlat(x: float, y: float) -> tuple[float, float]:
    return x_to_lon(x), y_to_lat(y)


def lonlat_to_normalised(lon_deg: float, lat_deg: float) -> tuple[float, float]:
    return lon_to_x(lon_deg), lat_to_y(lat_deg)
