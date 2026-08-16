"""PR-8 / revised B9 — transport-first monsoon wind anomaly.

Derives a bounded seasonal land–SST thermal contrast and adds an
onshore/offshore wind anomaly near tropical coasts. Base Hadley/trades
outside the active band are left unchanged. No standalone precip belt.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import elevation_gradients_cylindrical
from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask


def apply_monsoon_wind_anomaly(
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    land_temperature_c: NDArray[np.floating],
    sst_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    latitude_deg: NDArray[np.floating],
    strength: float = 0.4,
    lat_band_min_abs_deg: float = 5.0,
    lat_band_max_abs_deg: float = 32.0,
    max_anomaly_ms: float = 3.5,
    coast_reach_cells: float = 10.0,
    temp_scale_c: float = 8.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], dict[str, Any]]:
    """Add bounded monsoon wind anomaly to base circulation winds.

    Parameters
    ----------
    strength:
        0 disables. Modest defaults (~0.4) keep trades coherent.
    land_temperature_c, sst_c:
        Monthly fields ``[months, H, W]``. SST may be NaN on land.
    """
    u0 = np.asarray(wind_u, dtype=np.float64)
    v0 = np.asarray(wind_v, dtype=np.float64)
    s = float(max(strength, 0.0))
    if s <= 1e-15:
        return u0.copy(), v0.copy(), {
            "b9_terms_active": False,
            "monsoon_strength": 0.0,
            "mean_abs_anomaly_ms": 0.0,
        }

    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    lat = np.asarray(latitude_deg, dtype=np.float64)
    temp = np.asarray(land_temperature_c, dtype=np.float64)
    sst = np.asarray(sst_c, dtype=np.float64)
    months = min(u0.shape[0], temp.shape[0], sst.shape[0])

    dist_land, _, _ = cylindrical_distance_to_mask(ocean)
    dist_ocean, _, _ = cylindrical_distance_to_mask(land)
    signed = np.where(ocean, -dist_ocean, dist_land)
    gx, gy = elevation_gradients_cylindrical(signed)
    mag = np.hypot(gx, gy) + 1e-6
    # Inland unit in (east, south); wind v is northward → negate south component.
    ux_inland = gx / mag
    uv_north = -gy / mag

    abs_lat = np.abs(lat)
    band = (abs_lat >= float(lat_band_min_abs_deg)) & (
        abs_lat <= float(lat_band_max_abs_deg)
    )
    reach = max(float(coast_reach_cells), 1.0)
    envelope = np.exp(-np.abs(signed) / reach) * band.astype(np.float64)
    # Suppress deep open-ocean and deep interior (envelope already decays).

    u_out = u0[:months].copy()
    v_out = v0[:months].copy()
    amp = float(s) * float(max_anomaly_ms)
    t_scale = max(float(temp_scale_c), 1e-3)

    monthly_dt: list[float] = []
    monthly_onshore: list[float] = []

    for m in range(months):
        sst_m = sst[m]
        t_m = temp[m]
        dT_field = np.zeros(ocean.shape, dtype=np.float64)
        for hemi_mask in (lat >= 0.0, lat < 0.0):
            region = band & hemi_mask
            land_r = region & land
            ocean_r = region & ocean
            if not np.any(land_r) or not np.any(ocean_r):
                continue
            land_mean = float(np.mean(t_m[land_r]))
            sst_vals = sst_m[ocean_r]
            sst_vals = sst_vals[np.isfinite(sst_vals)]
            if sst_vals.size == 0:
                continue
            ocean_mean = float(np.mean(sst_vals))
            dT = land_mean - ocean_mean
            dT_field = np.where(region, dT, dT_field)

        # Onshore when land warmer than ocean (summer monsoon).
        factor = amp * np.tanh(dT_field / t_scale) * envelope
        du = factor * ux_inland
        dv = factor * uv_north
        u_out[m] = u0[m] + du
        v_out[m] = v0[m] + dv

        monthly_dt.append(float(np.mean(dT_field[band])) if np.any(band) else 0.0)
        # Positive projection on inland direction = onshore
        if np.any(envelope > 0.05):
            active = envelope > 0.05
            onshore = float(np.mean(du[active] * ux_inland[active] + dv[active] * uv_north[active]))
        else:
            onshore = 0.0
        monthly_onshore.append(onshore)

    anomaly_speed = np.hypot(u_out - u0[:months], v_out - v0[:months])
    diag: dict[str, Any] = {
        "b9_terms_active": True,
        "monsoon_strength": s,
        "monsoon_lat_band_min_abs_deg": float(lat_band_min_abs_deg),
        "monsoon_lat_band_max_abs_deg": float(lat_band_max_abs_deg),
        "monsoon_max_anomaly_ms": float(max_anomaly_ms),
        "monsoon_coast_reach_cells": reach,
        "mean_abs_anomaly_ms": float(np.mean(anomaly_speed)),
        "max_abs_anomaly_ms": float(np.max(anomaly_speed)),
        "monthly_land_sst_contrast_c": monthly_dt,
        "monthly_onshore_anomaly_ms": monthly_onshore,
        "algorithm": "monsoon_land_sst_wind_v1",
    }
    return u_out, v_out, diag
