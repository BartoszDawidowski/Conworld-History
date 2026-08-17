"""PR-8 / revised B9 — transport-first monsoon wind anomaly.

Derives a bounded seasonal land–SST thermal contrast and adds an
onshore/offshore wind anomaly near tropical coasts. Base Hadley/trades
outside the active band are left unchanged. No standalone precip belt.

CR-3: contrast is **local coastal** (land vs nearest SST / ocean vs nearest
land), not hemispheric means on SST-softened land temperatures.
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
        Monthly fields ``[months, H, W]``. Prefer **pre-SST** land temperatures
        for contrast. SST may be NaN on land.
    """
    u0 = np.asarray(wind_u, dtype=np.float64)
    v0 = np.asarray(wind_v, dtype=np.float64)
    s = float(max(strength, 0.0))
    if s <= 1e-15:
        return u0.copy(), v0.copy(), {
            "b9_terms_active": False,
            "monsoon_strength": 0.0,
            "mean_abs_anomaly_ms": 0.0,
            "algorithm": "monsoon_local_coast_wind_v2",
        }

    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    lat = np.asarray(latitude_deg, dtype=np.float64)
    temp = np.asarray(land_temperature_c, dtype=np.float64)
    sst = np.asarray(sst_c, dtype=np.float64)
    months = min(u0.shape[0], temp.shape[0], sst.shape[0])

    dist_land, near_ocean_i, near_ocean_j = cylindrical_distance_to_mask(ocean)
    dist_ocean, near_land_i, near_land_j = cylindrical_distance_to_mask(land)
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

    u_out = u0[:months].copy()
    v_out = v0[:months].copy()
    amp = float(s) * float(max_anomaly_ms)
    t_scale = max(float(temp_scale_c), 1e-3)

    monthly_dt: list[float] = []
    monthly_onshore: list[float] = []

    valid_land = land & (near_ocean_i >= 0) & (near_ocean_j >= 0)
    valid_ocean = ocean & (near_land_i >= 0) & (near_land_j >= 0)

    for m in range(months):
        sst_m = sst[m]
        t_m = temp[m]
        dT_field = np.zeros(ocean.shape, dtype=np.float64)

        if np.any(valid_land):
            nearest_sst = sst_m[near_ocean_j[valid_land], near_ocean_i[valid_land]]
            ok = np.isfinite(nearest_sst)
            idx = np.flatnonzero(valid_land)
            take = idx[ok]
            dT_field.ravel()[take] = t_m.ravel()[take] - nearest_sst[ok]

        if np.any(valid_ocean):
            nearest_land_t = t_m[near_land_j[valid_ocean], near_land_i[valid_ocean]]
            local_sst = sst_m[valid_ocean]
            ok = np.isfinite(local_sst) & np.isfinite(nearest_land_t)
            idx = np.flatnonzero(valid_ocean)
            take = idx[ok]
            dT_field.ravel()[take] = nearest_land_t[ok] - local_sst[ok]

        # Onshore when land warmer than nearby ocean (summer monsoon).
        factor = amp * np.tanh(dT_field / t_scale) * envelope
        du = factor * ux_inland
        dv = factor * uv_north
        u_out[m] = u0[m] + du
        v_out[m] = v0[m] + dv

        active_band = band & (envelope > 0.05)
        monthly_dt.append(
            float(np.mean(dT_field[active_band])) if np.any(active_band) else 0.0
        )
        if np.any(envelope > 0.05):
            active = envelope > 0.05
            onshore = float(
                np.mean(
                    du[active] * ux_inland[active] + dv[active] * uv_north[active]
                )
            )
        else:
            onshore = 0.0
        monthly_onshore.append(onshore)

    anomaly_speed = np.hypot(u_out - u0[:months], v_out - v0[:months])
    onshore_arr = np.asarray(monthly_onshore, dtype=np.float64)
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
        "seasonal_onshore_sign_flip": bool(
            float(np.max(onshore_arr)) > 0.05 and float(np.min(onshore_arr)) < -0.05
        ),
        "algorithm": "monsoon_local_coast_wind_v2",
    }
    return u_out, v_out, diag
