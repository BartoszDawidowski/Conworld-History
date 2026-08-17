"""PR-8 / CR-8 — transport-first monsoon wind anomaly.

Seasonal land and SST *anomalies vs their own annual means*, optionally
reduced to sea-level temperature, then a 300–800 km regional mean.
The anomaly is gated off in a hemisphere when the monthly contrast never
changes sign (always onshore or always offshore).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import elevation_gradients_cylindrical
from worldsim.physical.tectonics.interpretation import cylindrical_distance_to_mask


def _box_smooth(field: NDArray[np.floating], half_cells: int) -> NDArray[np.float64]:
    """Separable box mean; E–W wrap, N–S edge clamp."""
    q = np.asarray(field, dtype=np.float64)
    half = max(int(half_cells), 0)
    if half <= 0:
        return q.copy()
    acc = np.zeros_like(q)
    k = 2 * half + 1
    for s in range(-half, half + 1):
        acc += np.roll(q, s, axis=1)
    acc /= float(k)
    ns = np.zeros_like(q)
    for s in range(-half, half + 1):
        if s < 0:
            ns += np.pad(acc[:s, :], ((-s, 0), (0, 0)), mode="edge")
        elif s > 0:
            ns += np.pad(acc[s:, :], ((0, s), (0, 0)), mode="edge")
        else:
            ns += acc
    return ns / float(k)


def _sea_level_temperature(
    temperature_c: NDArray[np.floating],
    elevation_m: NDArray[np.floating] | None,
    ocean_mask: NDArray[np.bool_],
    lapse_rate_c_per_km: float,
) -> NDArray[np.float64]:
    t = np.asarray(temperature_c, dtype=np.float64)
    if elevation_m is None:
        return t
    elev_km = np.maximum(np.asarray(elevation_m, dtype=np.float64), 0.0) / 1000.0
    land = ~np.asarray(ocean_mask, dtype=bool)
    return t + float(lapse_rate_c_per_km) * elev_km[np.newaxis, :, :] * land


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
    regional_mean_cells: float = 0.0,
    elevation_m: NDArray[np.floating] | None = None,
    lapse_rate_c_per_km: float = 6.5,
    sign_flip_eps: float = 0.05,
) -> tuple[NDArray[np.float64], NDArray[np.float64], dict[str, Any]]:
    """Add bounded monsoon wind anomaly to base circulation winds.

    Contrast is monthly land/SST anomaly versus each field's own annual mean,
    not the absolute land−SST difference (CR-8 / F-07).
    """
    u0 = np.asarray(wind_u, dtype=np.float64)
    v0 = np.asarray(wind_v, dtype=np.float64)
    s = float(max(strength, 0.0))
    if s <= 1e-15:
        return u0.copy(), v0.copy(), {
            "b9_terms_active": False,
            "monsoon_strength": 0.0,
            "mean_abs_anomaly_ms": 0.0,
            "monsoon_sign_gate_on": False,
            "algorithm": "monsoon_anomaly_gate_v1",
        }

    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    lat = np.asarray(latitude_deg, dtype=np.float64)
    temp = _sea_level_temperature(
        land_temperature_c, elevation_m, ocean, lapse_rate_c_per_km
    )
    sst = np.asarray(sst_c, dtype=np.float64)
    months = min(u0.shape[0], temp.shape[0], sst.shape[0])

    dist_land, near_ocean_i, near_ocean_j = cylindrical_distance_to_mask(ocean)
    dist_ocean, near_land_i, near_land_j = cylindrical_distance_to_mask(land)
    signed = np.where(ocean, -dist_ocean, dist_land)
    gx, gy = elevation_gradients_cylindrical(signed)
    mag = np.hypot(gx, gy) + 1e-6
    ux_inland = gx / mag
    uv_north = -gy / mag

    abs_lat = np.abs(lat)
    band = (abs_lat >= float(lat_band_min_abs_deg)) & (
        abs_lat <= float(lat_band_max_abs_deg)
    )
    reach = max(float(coast_reach_cells), 1.0)
    envelope = np.exp(-np.abs(signed) / reach) * band.astype(np.float64)
    half = int(max(round(float(regional_mean_cells)), 0))

    t_ann = temp[:months].mean(axis=0)
    sst_ok = np.isfinite(sst[:months])
    sst_sum = np.where(sst_ok, sst[:months], 0.0).sum(axis=0)
    sst_count = np.maximum(sst_ok.sum(axis=0).astype(np.float64), 1.0)
    sst_ann = np.where(sst_ok.any(axis=0), sst_sum / sst_count, 0.0)

    u_out = u0[:months].copy()
    v_out = v0[:months].copy()
    amp = float(s) * float(max_anomaly_ms)
    t_scale = max(float(temp_scale_c), 1e-3)

    monthly_dt: list[float] = []
    monthly_onshore: list[float] = []
    dT_months = np.zeros((months,) + ocean.shape, dtype=np.float64)

    valid_land = land & (near_ocean_i >= 0) & (near_ocean_j >= 0)
    valid_ocean = ocean & (near_land_i >= 0) & (near_land_j >= 0)

    for m in range(months):
        t_anom = temp[m] - t_ann
        sst_anom = np.where(np.isfinite(sst[m]), sst[m] - sst_ann, 0.0)
        dT_field = np.zeros(ocean.shape, dtype=np.float64)

        if np.any(valid_land):
            nearest_sst = sst_anom[near_ocean_j[valid_land], near_ocean_i[valid_land]]
            ok = np.isfinite(nearest_sst)
            idx = np.flatnonzero(valid_land)
            take = idx[ok]
            dT_field.ravel()[take] = t_anom.ravel()[take] - nearest_sst[ok]

        if np.any(valid_ocean):
            nearest_land_t = t_anom[near_land_j[valid_ocean], near_land_i[valid_ocean]]
            local_sst = sst_anom[valid_ocean]
            ok = np.isfinite(local_sst) & np.isfinite(nearest_land_t)
            idx = np.flatnonzero(valid_ocean)
            take = idx[ok]
            dT_field.ravel()[take] = nearest_land_t[ok] - local_sst[ok]

        if half > 0:
            dT_field = _box_smooth(dT_field, half)
        dT_months[m] = dT_field
        active_band = band & (envelope > 0.05)
        monthly_dt.append(
            float(np.mean(dT_field[active_band])) if np.any(active_band) else 0.0
        )

    dt_arr = np.asarray(monthly_dt, dtype=np.float64)
    nh = lat >= 0.0
    sh = lat < 0.0
    eps = float(sign_flip_eps)
    hemi_gate = {
        "nh": True,
        "sh": True,
    }
    for name, mask in (("nh", nh), ("sh", sh)):
        active = mask & band & (envelope > 0.05)
        if not np.any(active):
            hemi_gate[name] = False
            continue
        series = np.array(
            [float(np.mean(dT_months[m][active])) for m in range(months)],
            dtype=np.float64,
        )
        hemi_gate[name] = bool(float(np.max(series)) > eps and float(np.min(series)) < -eps)

    global_flip = bool(float(np.max(dt_arr)) > eps and float(np.min(dt_arr)) < -eps)
    gate_on = bool(hemi_gate["nh"] or hemi_gate["sh"])

    for m in range(months):
        dT_field = dT_months[m]
        if not hemi_gate["nh"]:
            dT_field = np.where(nh, 0.0, dT_field)
        if not hemi_gate["sh"]:
            dT_field = np.where(sh, 0.0, dT_field)
        factor = amp * np.tanh(dT_field / t_scale) * envelope
        du = factor * ux_inland
        dv = factor * uv_north
        u_out[m] = u0[m] + du
        v_out[m] = v0[m] + dv
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
        "monsoon_regional_mean_cells": float(half),
        "mean_abs_anomaly_ms": float(np.mean(anomaly_speed)),
        "max_abs_anomaly_ms": float(np.max(anomaly_speed)),
        "monthly_land_sst_contrast_c": monthly_dt,
        "monthly_onshore_anomaly_ms": monthly_onshore,
        "seasonal_onshore_sign_flip": bool(
            float(np.max(onshore_arr)) > eps and float(np.min(onshore_arr)) < -eps
        ),
        "monsoon_sign_gate_on": gate_on,
        "monsoon_sign_gate_nh": bool(hemi_gate["nh"]),
        "monsoon_sign_gate_sh": bool(hemi_gate["sh"]),
        "monsoon_global_contrast_flip": global_flip,
        "algorithm": "monsoon_anomaly_gate_v1",
    }
    return u_out, v_out, diag
