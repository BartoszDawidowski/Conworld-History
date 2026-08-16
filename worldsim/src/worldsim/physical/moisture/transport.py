"""Stage H — moisture sources, advection, orography, precipitation (Milestone 9)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import elevation_gradients_cylindrical


def saturation_capacity(
    temperature_c: NDArray[np.floating],
    *,
    base: float = 8.0,
    scale_c: float = 12.0,
) -> NDArray[np.float64]:
    """Relative atmospheric moisture capacity (proxy), rises with temperature."""
    t = np.asarray(temperature_c, dtype=np.float64)
    return base * np.exp(np.clip(t, -40.0, 45.0) / scale_c)


def evaporation_field(
    *,
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    sst_c: NDArray[np.floating] | None = None,
    wind_speed: NDArray[np.floating] | None = None,
    ocean_rate: float = 1.15,
    land_rate: float = 0.22,
    lake_mask: NDArray[np.bool_] | None = None,
    river_mask: NDArray[np.bool_] | None = None,
    lake_rate: float = 0.75,
    river_rate: float = 0.40,
) -> NDArray[np.float64]:
    """Monthly evaporation / ET proxy (moisture units per month).

    Priority: ocean > lake > river > land ET. Inland water uses open-water
    scaling (like ocean) at reduced rates so lakes/rivers humidify interiors.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if sst_c is not None:
        t_ocean = np.asarray(sst_c, dtype=np.float64)
        t_ocean = np.where(np.isfinite(t_ocean), t_ocean, temperature_c)
    else:
        t_ocean = np.asarray(temperature_c, dtype=np.float64)
    t_land = np.asarray(temperature_c, dtype=np.float64)

    # Clausius-ish positive branch
    ocean_evap = ocean_rate * np.maximum(0.0, t_ocean + 2.0) / 30.0
    land_et = land_rate * np.maximum(0.0, t_land) / 35.0
    open_water = np.maximum(0.0, t_land + 2.0) / 30.0
    evap = np.where(ocean, ocean_evap, land_et)
    if river_mask is not None:
        river = np.asarray(river_mask, dtype=np.bool_) & ~ocean
        evap = np.where(river, float(river_rate) * open_water, evap)
    if lake_mask is not None:
        lake = np.asarray(lake_mask, dtype=np.bool_) & ~ocean
        evap = np.where(lake, float(lake_rate) * open_water, evap)

    if wind_speed is not None:
        ws = np.asarray(wind_speed, dtype=np.float64)
        evap = evap * (0.75 + 0.05 * np.clip(ws, 0.0, 20.0))
    return evap.astype(np.float64)


def _upwind_advect(
    moisture: NDArray[np.floating],
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    dt: float,
    wind_scale: float = 0.04,
) -> NDArray[np.float64]:
    """One upwind advection step with E–W wrap; no N–S wrap."""
    q = np.asarray(moisture, dtype=np.float64)
    u = np.asarray(wind_u, dtype=np.float64)
    v = np.asarray(wind_v, dtype=np.float64)
    # Scale winds: cell/month → substep; treat |u|=10 as ~0.4 cell/substep baseline
    cu = u * dt * float(wind_scale)
    cv = v * dt * float(wind_scale)
    cu = np.clip(cu, -0.95, 0.95)
    cv = np.clip(cv, -0.95, 0.95)

    # x flux (cylindrical)
    q_e = np.roll(q, -1, axis=1)
    q_w = np.roll(q, 1, axis=1)
    flux_x = np.where(cu >= 0.0, cu * (q - q_w), cu * (q_e - q))

    # y flux (no wrap)
    q_n = np.empty_like(q)
    q_s = np.empty_like(q)
    q_n[:-1, :] = q[1:, :]
    q_n[-1, :] = q[-1, :]
    q_s[1:, :] = q[:-1, :]
    q_s[0, :] = q[0, :]
    # v>0 = northward = toward decreasing j if j=0 is north
    # Our grid: j=0 is north (high lat). Northward wind moves moisture to smaller j.
    # So positive v should use upwind from south (larger j).
    flux_y = np.where(cv >= 0.0, cv * (q - q_s), cv * (q_n - q))

    out = q - flux_x - flux_y
    return np.maximum(out, 0.0)


def orographic_lift(
    *,
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    elev_scale_m: float = 600.0,
) -> NDArray[np.float64]:
    """Signed uplift proxy: >0 windward ascent, <0 leeward descent."""
    gx, gy = elevation_gradients_cylindrical(elevation_m)
    sx = np.tanh(gx / elev_scale_m)
    sy = np.tanh(gy / elev_scale_m)
    u = np.asarray(wind_u, dtype=np.float64)
    v = np.asarray(wind_v, dtype=np.float64)
    # Wind blowing toward higher ground → positive lift
    # Note: +v is northward (toward smaller j); gy = d_elev/dj so northward
    # upslope when gy < 0. Dot with (-gy for v?); use physical: lift ∝ u·∇h
    # with ∇h in (east, south) cell indices ≈ (gx, gy). Northward wind is -j.
    lift = u * sx - v * sy
    return lift


def build_monthly_moisture(
    *,
    temperature_c: NDArray[np.floating],
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    latitude_deg: NDArray[np.floating],
    sst_c: NDArray[np.floating] | None = None,
    continentality: NDArray[np.floating] | None = None,
    lake_mask: NDArray[np.bool_] | None = None,
    river_mask: NDArray[np.bool_] | None = None,
    months: int | None = None,
    advect_steps: int = 6,
    advect_wind_scale: float = 0.04,
    large_scale_frac: float = 0.55,
    orographic_frac: float = 0.85,
    convective_scale: float = 1.4,
    ocean_evap_rate: float = 1.15,
    lake_evap_rate: float = 0.75,
    river_evap_rate: float = 0.40,
    land_et_rate: float = 0.22,
    continentality_dry: float = 0.45,
    lee_dry: float = 0.12,
) -> dict[str, NDArray]:
    """Monthly moisture state: evaporation, moisture, humidity, precipitation."""
    temp = np.asarray(temperature_c, dtype=np.float64)
    wu = np.asarray(wind_u, dtype=np.float64)
    wv = np.asarray(wind_v, dtype=np.float64)
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    lat = np.asarray(latitude_deg, dtype=np.float64)
    n = int(months if months is not None else temp.shape[0])
    h, w = ocean.shape

    if continentality is None:
        cont = np.zeros((h, w), dtype=np.float64)
    else:
        cont = np.asarray(continentality, dtype=np.float64)

    evaporation = np.empty((n, h, w), dtype=np.float64)
    moisture = np.empty((n, h, w), dtype=np.float64)
    humidity = np.empty((n, h, w), dtype=np.float64)
    precipitation = np.empty((n, h, w), dtype=np.float64)
    orographic = np.empty((n, h, w), dtype=np.float64)
    convective = np.empty((n, h, w), dtype=np.float64)

    q = np.zeros((h, w), dtype=np.float64)
    steps = max(int(advect_steps), 1)

    for m in range(n):
        speed = np.hypot(wu[m], wv[m])
        sst_m = sst_c[m] if sst_c is not None else None
        evap = evaporation_field(
            temperature_c=temp[m],
            ocean_mask=ocean,
            sst_c=sst_m,
            wind_speed=speed,
            ocean_rate=ocean_evap_rate,
            land_rate=land_et_rate,
            lake_mask=lake_mask,
            river_mask=river_mask,
            lake_rate=lake_evap_rate,
            river_rate=river_evap_rate,
        )
        evaporation[m] = evap

        capacity = saturation_capacity(temp[m])
        # Land drying with continentality (far inland holds / receives less)
        land_dry = 1.0 - float(continentality_dry) * cont * (~ocean).astype(np.float64)

        q = q + evap
        dt = 1.0 / float(steps)
        for _ in range(steps):
            q = _upwind_advect(
                q, wu[m], wv[m], dt=dt, wind_scale=advect_wind_scale
            )
            # Weak diffusion for coherence
            q = 0.92 * q + 0.02 * (
                np.roll(q, 1, axis=1)
                + np.roll(q, -1, axis=1)
                + np.pad(q[1:, :], ((0, 1), (0, 0)), mode="edge")
                + np.pad(q[:-1, :], ((1, 0), (0, 0)), mode="edge")
            )
            q = np.maximum(q, 0.0)

        lift = orographic_lift(wind_u=wu[m], wind_v=wv[m], elevation_m=elev)
        orographic[m] = lift

        excess = np.maximum(0.0, q - capacity * land_dry)
        large_scale = float(large_scale_frac) * excess

        oro_precip = float(orographic_frac) * np.maximum(0.0, lift) * np.minimum(
            q, capacity
        )

        warm = np.clip((temp[m] - 18.0) / 12.0, 0.0, 1.0)
        moist_frac = np.clip(q / np.maximum(capacity, 1e-6), 0.0, 1.5)
        tropical = np.exp(-0.5 * (lat / 18.0) ** 2)
        conv = (
            float(convective_scale)
            * warm
            * moist_frac
            * tropical
            * np.minimum(q, capacity)
        )
        convective[m] = conv

        precip = large_scale + oro_precip + conv
        precip = np.maximum(precip, 0.0)

        lee = float(lee_dry) * np.maximum(0.0, -lift) * q
        q = np.maximum(q - precip - lee, 0.0)
        q = np.minimum(q, capacity * 1.25)

        moisture[m] = q
        humidity[m] = np.clip(q / np.maximum(capacity, 1e-6), 0.0, 1.5)
        precipitation[m] = precip

    return {
        "atmospheric_moisture": moisture,
        "evaporation": evaporation,
        "precipitation": precipitation,
        "humidity": humidity,
        "orographic_lift": orographic,
        "convective_precip": convective,
    }
