"""Stage F — first-order atmospheric circulation (Milestone 7).

Produces coherent monthly ``pressure_proxy``, ``wind_u``, ``wind_v`` and
circulation-zone labels. No fluid solver; no independent random wind arrows.
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class CirculationZone(IntEnum):
    NONE = 0
    HADLEY = 1
    SUBTROPICAL_HIGH = 2
    FERREL = 3
    POLAR = 4


ZONE_NAMES: dict[int, str] = {
    int(CirculationZone.NONE): "none",
    int(CirculationZone.HADLEY): "hadley",
    int(CirculationZone.SUBTROPICAL_HIGH): "subtropical_high",
    int(CirculationZone.FERREL): "ferrel",
    int(CirculationZone.POLAR): "polar",
}


def itcz_latitude_deg(month: int, *, axial_tilt_deg: float = 23.44) -> float:
    """Seasonal ITCZ latitude (°). Positive = NH.

    Tracks solar declination so the thermal equator migrates with the seasons.
    """
    # Mid-month day-of-year (non-leap), matching climate.insolation.
    month_lengths = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    start = sum(month_lengths[:month])
    doy = start + 0.5 * month_lengths[month]
    # Softened migration (~0.4 of axial tilt).
    return 0.40 * axial_tilt_deg * np.sin(2.0 * np.pi * (doy - 81.0) / 365.2422)


def pressure_proxy_field(
    latitude_deg: NDArray[np.floating],
    itcz_deg: float,
) -> NDArray[np.float64]:
    """Dimensionless surface pressure proxy (higher = high).

    Builds equatorial trough near ITCZ, subtropical highs ~±28°, subpolar
    lows ~±60°, polar highs — relative to the seasonal ITCZ.
    """
    lat = np.asarray(latitude_deg, dtype=np.float64)
    x = lat - float(itcz_deg)
    # Band centres relative to ITCZ.
    # Equatorial low:
    eq = -0.55 * np.exp(-0.5 * (x / 8.0) ** 2)
    # Subtropical highs NH/SH:
    sth_n = 0.70 * np.exp(-0.5 * ((x - 28.0) / 9.0) ** 2)
    sth_s = 0.70 * np.exp(-0.5 * ((x + 28.0) / 9.0) ** 2)
    # Subpolar lows:
    spl_n = -0.45 * np.exp(-0.5 * ((x - 60.0) / 10.0) ** 2)
    spl_s = -0.45 * np.exp(-0.5 * ((x + 60.0) / 10.0) ** 2)
    # Polar highs:
    pol_n = 0.35 * np.exp(-0.5 * ((x - 85.0) / 8.0) ** 2)
    pol_s = 0.35 * np.exp(-0.5 * ((x + 85.0) / 8.0) ** 2)
    return eq + sth_n + sth_s + spl_n + spl_s + pol_n + pol_s


def classify_circulation_zones(
    latitude_deg: NDArray[np.floating],
    itcz_deg: float,
) -> NDArray[np.int16]:
    """Assign Hadley / subtropical high / Ferrel / polar belts vs ITCZ."""
    lat = np.asarray(latitude_deg, dtype=np.float64)
    abs_off = np.abs(lat - float(itcz_deg))
    zones = np.zeros(lat.shape, dtype=np.int16)
    zones[abs_off < 18.0] = int(CirculationZone.HADLEY)
    zones[(abs_off >= 18.0) & (abs_off < 35.0)] = int(CirculationZone.SUBTROPICAL_HIGH)
    zones[(abs_off >= 35.0) & (abs_off < 65.0)] = int(CirculationZone.FERREL)
    zones[abs_off >= 65.0] = int(CirculationZone.POLAR)
    return zones


def base_wind_from_zones(
    latitude_deg: NDArray[np.floating],
    zones: NDArray[np.integer],
    itcz_deg: float,
    *,
    trade_speed: float = 6.0,
    westerly_speed: float = 10.0,
    polar_easterly_speed: float = 4.0,
    hadley_meridional: float = 2.5,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Zonal/meridional surface winds from circulation belts (m/s proxy).

    ``u`` > 0 = westerly (eastward); ``v`` > 0 = northward.
    """
    lat = np.asarray(latitude_deg, dtype=np.float64)
    z = np.asarray(zones)
    u = np.zeros(lat.shape, dtype=np.float64)
    v = np.zeros(lat.shape, dtype=np.float64)

    hadley = z == int(CirculationZone.HADLEY)
    ferrel = z == int(CirculationZone.FERREL)
    polar = z == int(CirculationZone.POLAR)
    sth = z == int(CirculationZone.SUBTROPICAL_HIGH)

    # Trades: easterlies; surface flow toward ITCZ.
    u[hadley] = -trade_speed
    # Meridional: north of ITCZ → southward (v<0), south of ITCZ → northward.
    toward = -np.sign(lat - float(itcz_deg))
    toward = np.where(toward == 0.0, 0.0, toward)
    v[hadley] = hadley_meridional * toward[hadley]

    # Ferrel: mid-latitude westerlies; weak poleward surface drift.
    u[ferrel] = westerly_speed
    v[ferrel] = 0.8 * np.sign(lat[ferrel])  # weak toward poles at surface (simplified)

    # Polar easterlies; weak equatorward.
    u[polar] = -polar_easterly_speed
    v[polar] = -0.6 * np.sign(lat[polar])

    # Subtropical high: weak divergence (away from high) — light easterly/westerly blend.
    u[sth] = 1.5 * np.sign(lat[sth] - float(itcz_deg))  # weak
    v[sth] = 0.5 * np.sign(lat[sth] - float(itcz_deg))

    return u, v


def apply_coriolis(
    u: NDArray[np.floating],
    v: NDArray[np.floating],
    latitude_rad: NDArray[np.floating],
    *,
    strength: float = 0.35,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Deflect wind by a Coriolis-like rotation proportional to ``sin(lat)``.

    Northern Hemisphere: deflection to the right (clockwise rotation of vector).
    """
    uu = np.asarray(u, dtype=np.float64)
    vv = np.asarray(v, dtype=np.float64)
    f = strength * np.sin(np.asarray(latitude_rad, dtype=np.float64))
    # Clockwise rotation for NH (θ∝f>0): rightward deflection when looking down.
    # Small-angle: u' ≈ u + θ v, v' ≈ v − θ u
    theta = f
    u2 = uu + theta * vv
    v2 = vv - theta * uu
    return u2, v2


def elevation_gradients_cylindrical(
    elevation_m: NDArray[np.floating],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """``(d_elev/dx, d_elev/dy)`` with E–W wrap; no N–S wrap (edge one-sided)."""
    elev = np.asarray(elevation_m, dtype=np.float64)
    # x: central difference with roll
    de_dx = 0.5 * (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1))
    de_dy = np.empty_like(elev)
    de_dy[1:-1, :] = 0.5 * (elev[2:, :] - elev[:-2, :])
    de_dy[0, :] = elev[1, :] - elev[0, :]
    de_dy[-1, :] = elev[-1, :] - elev[-2, :]
    return de_dx, de_dy


def apply_topographic_perturbation(
    u: NDArray[np.floating],
    v: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    *,
    elev_scale_m: float = 800.0,
    drag_amp: float = 1.5,
    divert_amp: float = 1.0,
    max_frac: float = 0.45,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Perturb winds with elevation gradients (blocking / diversion).

    Gradients are soft-normalized so steep cells cannot explode the field.
    Absolute perturbation is capped relative to local wind speed.
    """
    uu = np.asarray(u, dtype=np.float64).copy()
    vv = np.asarray(v, dtype=np.float64).copy()
    gx, gy = elevation_gradients_cylindrical(elevation_m)
    # Soft unitless slope ∈ (−1, 1)
    sx = np.tanh(gx / elev_scale_m)
    sy = np.tanh(gy / elev_scale_m)

    du = -drag_amp * sx
    dv = -drag_amp * sy
    # Flow into the slope → extra blocking + mild diversion around high ground
    into = uu * sx + vv * sy
    du = du - divert_amp * into * sx
    dv = dv - divert_amp * into * sy
    du = du + divert_amp * 0.35 * (-sy) * np.abs(into)
    dv = dv + divert_amp * 0.35 * sx * np.abs(into)

    # Cap perturbation magnitude vs local wind
    speed = np.hypot(uu, vv)
    max_du = max_frac * speed + 0.75
    mag = np.hypot(du, dv)
    scale = np.ones_like(mag)
    over = mag > max_du
    scale[over] = max_du[over] / np.maximum(mag[over], 1e-9)
    return uu + du * scale, vv + dv * scale


def build_monthly_atmosphere(
    *,
    latitude_deg: NDArray[np.floating],
    latitude_rad: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    axial_tilt_deg: float = 23.44,
    months: int = 12,
) -> dict[str, NDArray]:
    """Return monthly atmosphere arrays on the climate grid."""
    lat_d = np.asarray(latitude_deg, dtype=np.float64)
    lat_r = np.asarray(latitude_rad, dtype=np.float64)
    elev = np.asarray(elevation_m, dtype=np.float64)
    h, w = lat_d.shape

    pressure = np.empty((months, h, w), dtype=np.float64)
    wind_u = np.empty((months, h, w), dtype=np.float64)
    wind_v = np.empty((months, h, w), dtype=np.float64)
    zones = np.empty((months, h, w), dtype=np.int16)
    itcz = np.empty(months, dtype=np.float64)

    for m in range(months):
        itcz_m = float(itcz_latitude_deg(m, axial_tilt_deg=axial_tilt_deg))
        itcz[m] = itcz_m
        p = pressure_proxy_field(lat_d, itcz_m)
        z = classify_circulation_zones(lat_d, itcz_m)
        u, v = base_wind_from_zones(lat_d, z, itcz_m)
        u, v = apply_coriolis(u, v, lat_r)
        u, v = apply_topographic_perturbation(u, v, elev)
        pressure[m] = p
        wind_u[m] = u
        wind_v[m] = v
        zones[m] = z

    return {
        "pressure_proxy": pressure,
        "wind_u": wind_u,
        "wind_v": wind_v,
        "circulation_zone": zones,
        "itcz_latitude_deg": itcz,
    }
