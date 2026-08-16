"""Monthly relative insolation from latitude and axial tilt (Stage E)."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def mid_month_day_of_year(month: int) -> float:
    """Day-of-year at mid-month (0 = January … 11 = December)."""
    if not 0 <= month <= 11:
        raise ValueError(f"month must be in [0, 11], got {month}")
    # Cumulative days to start of month (non-leap) + half month length.
    month_lengths = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    start = sum(month_lengths[:month])
    return start + 0.5 * month_lengths[month]


def solar_declination_rad(day_of_year: float, *, axial_tilt_deg: float = 23.44) -> float:
    """Approximate solar declination (radians).

    Uses ``δ ≈ ε · sin(2π · (doy − 81) / 365)`` so NH summer peaks near June.
    """
    eps = math.radians(axial_tilt_deg)
    return eps * math.sin(2.0 * math.pi * (float(day_of_year) - 81.0) / 365.2422)


def daily_mean_relative_insolation(
    latitude_rad: NDArray[np.floating] | float,
    declination_rad: float,
) -> NDArray[np.float64] | float:
    """Daily-mean relative insolation (clear-sky geometric factor).

    ``(H·sinφ·sinδ + cosφ·cosδ·sin H) / π`` with sunset hour angle ``H``.
    Values are in ``[0, ~1]`` (not absolute W/m²).
    """
    lat = np.asarray(latitude_rad, dtype=np.float64)
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    sin_d = math.sin(declination_rad)
    cos_d = math.cos(declination_rad)

    # Clamp for polar day/night.
    arg = (-sin_lat * sin_d) / np.maximum(cos_lat * cos_d, 1e-12)
    arg = np.clip(arg, -1.0, 1.0)
    hour_angle = np.arccos(arg)

    # |arg| ≥ 1 → continuous polar day/night.
    polar_day = arg <= -1.0
    polar_night = arg >= 1.0
    hour_angle = np.where(polar_day, math.pi, hour_angle)
    hour_angle = np.where(polar_night, 0.0, hour_angle)

    insol = (
        hour_angle * sin_lat * sin_d + cos_lat * cos_d * np.sin(hour_angle)
    ) / math.pi
    return np.maximum(insol, 0.0)


def monthly_insolation_field(
    latitude_rad: NDArray[np.floating],
    *,
    axial_tilt_deg: float = 23.44,
    months: int = 12,
) -> NDArray[np.float64]:
    """Return ``insolation[month, y, x]`` relative daily-mean factors."""
    lat = np.asarray(latitude_rad, dtype=np.float64)
    if lat.ndim != 2:
        raise ValueError("latitude_rad must be 2D (height, width)")
    out = np.empty((months, lat.shape[0], lat.shape[1]), dtype=np.float64)
    for month in range(months):
        doy = mid_month_day_of_year(month)
        decl = solar_declination_rad(doy, axial_tilt_deg=axial_tilt_deg)
        out[month] = daily_mean_relative_insolation(lat, decl)
    return out
