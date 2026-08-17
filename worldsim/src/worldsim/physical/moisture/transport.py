"""Stage H — moisture sources, advection, orography, precipitation (Milestone 9 / PR-4)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import elevation_gradients_cylindrical
from worldsim.spatial.metrics import EARTH_RADIUS_KM, grid_metrics

# Neighbour mixing weight integrated over one month (independent of advect_steps).
DEFAULT_DIFFUSION_MIX_PER_MONTH = 0.08
# wind_scale is calibrated as cells/month on Atlas width 1024 (CR-8 km Courant).
ADVECT_SCALE_REF_WIDTH = 1024.0
ADVECT_CFL_DEFAULT = 0.9


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
    lake_fraction: NDArray[np.floating] | None = None,
) -> NDArray[np.float64]:
    """Monthly evaporation / ET proxy (moisture units per month).

    Priority: ocean > lake > river > land ET. Inland water uses open-water
    scaling (like ocean) at reduced rates so lakes/rivers humidify interiors.
    """
    comps = evaporation_components(
        temperature_c=temperature_c,
        ocean_mask=ocean_mask,
        sst_c=sst_c,
        wind_speed=wind_speed,
        ocean_rate=ocean_rate,
        land_rate=land_rate,
        lake_mask=lake_mask,
        river_mask=river_mask,
        lake_rate=lake_rate,
        river_rate=river_rate,
        lake_fraction=lake_fraction,
    )
    return comps["total"]


def evaporation_components(
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
    land_store: NDArray[np.floating] | None = None,
    land_store_capacity: float = 0.0,
    lake_fraction: NDArray[np.floating] | None = None,
) -> dict[str, NDArray[np.float64]]:
    """Split ocean / lake / river / land ET (mutually exclusive masks).

    When ``land_store_capacity > 0`` and ``land_store`` is provided, land ET is
    water-limited (PR-7): actual ET ≤ store (temperature sets only the demand).
    ``lake_fraction`` (0–1) scales open-water evaporation when the climate cell
    is only partly covered (CR-6).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if sst_c is not None:
        t_ocean = np.asarray(sst_c, dtype=np.float64)
        t_ocean = np.where(np.isfinite(t_ocean), t_ocean, temperature_c)
    else:
        t_ocean = np.asarray(temperature_c, dtype=np.float64)
    t_land = np.asarray(temperature_c, dtype=np.float64)

    ocean_evap = ocean_rate * np.maximum(0.0, t_ocean + 2.0) / 30.0
    land_et_potential = land_rate * np.maximum(0.0, t_land) / 35.0
    open_water = np.maximum(0.0, t_land + 2.0) / 30.0

    river = np.zeros(ocean.shape, dtype=bool)
    if river_mask is not None:
        river = np.asarray(river_mask, dtype=np.bool_) & ~ocean
    if lake_fraction is not None:
        lake_f = np.clip(np.asarray(lake_fraction, dtype=np.float64), 0.0, 1.0)
        lake_f = np.where(ocean | river, 0.0, lake_f)
    elif lake_mask is not None:
        lake_f = (
            np.asarray(lake_mask, dtype=np.bool_) & ~ocean & ~river
        ).astype(np.float64)
    else:
        lake_f = np.zeros(ocean.shape, dtype=np.float64)
    land_w = np.clip(1.0 - lake_f, 0.0, 1.0)
    land_cells = (~ocean) & (~river) & (land_w > 0.0)

    wind_fac = 1.0
    if wind_speed is not None:
        ws = np.asarray(wind_speed, dtype=np.float64)
        wind_fac = 0.75 + 0.05 * np.clip(ws, 0.0, 20.0)

    ocean_out = np.where(ocean, ocean_evap * wind_fac, 0.0)
    lake_out = lake_f * float(lake_rate) * open_water * wind_fac
    river_out = np.where(river, float(river_rate) * open_water * wind_fac, 0.0)
    potential = np.where(land_cells, land_et_potential * wind_fac * land_w, 0.0)
    if land_store is not None and float(land_store_capacity) > 0.0:
        store = np.asarray(land_store, dtype=np.float64)
        land_out = np.minimum(potential, np.maximum(store, 0.0))
        land_out = np.where(land_cells, land_out, 0.0)
    else:
        land_out = potential
    total = ocean_out + lake_out + river_out + land_out
    return {
        "ocean_evaporation": ocean_out.astype(np.float64),
        "lake_evaporation": lake_out.astype(np.float64),
        "river_evaporation": river_out.astype(np.float64),
        "land_et": land_out.astype(np.float64),
        "land_et_potential": potential.astype(np.float64),
        "total": total.astype(np.float64),
    }


def soft_plume_mix(
    moisture: NDArray[np.floating],
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    strength: float,
    steps: int = 6,
) -> NDArray[np.float64]:
    """Conservative wind-aligned mixing of existing ``q`` (PR-7 soft plume).

    Redistributes atmospheric moisture over several neighbour steps; does not
    inject precipitation. Total mass is renormalised after the sweep.
    """
    s_total = float(np.clip(strength, 0.0, 0.95))
    q = np.asarray(moisture, dtype=np.float64)
    if s_total <= 1e-15:
        return q.copy()
    n = max(int(steps), 1)
    # Per-step mix so n steps ≈ strength toward the flow-aligned target.
    s = 1.0 - (1.0 - s_total) ** (1.0 / float(n))
    s = float(np.clip(s, 0.0, 0.95))
    u = np.asarray(wind_u, dtype=np.float64)
    v = np.asarray(wind_v, dtype=np.float64)
    sum0 = float(np.sum(q))
    for _ in range(n):
        q_w = np.roll(q, 1, axis=1)
        q_e = np.roll(q, -1, axis=1)
        q_s = np.pad(q[1:, :], ((0, 1), (0, 0)), mode="edge")
        q_n = np.pad(q[:-1, :], ((1, 0), (0, 0)), mode="edge")
        speed = np.hypot(u, v) + 1e-6
        wu = np.abs(u) / speed
        wv = np.abs(v) / speed
        up_x = np.where(u >= 0.0, q_w, q_e)
        up_y = np.where(v >= 0.0, q_s, q_n)
        upwind = wu * up_x + wv * up_y
        iso = 0.25 * (q_w + q_e + q_s + q_n)
        target = 0.7 * upwind + 0.3 * iso
        q = (1.0 - s) * q + s * target
        q = np.maximum(q, 0.0)
    sum1 = float(np.sum(q))
    if sum1 > 1e-15 and sum0 > 1e-15:
        q = q * (sum0 / sum1)
    return np.maximum(q, 0.0)


def _courant_uv(
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    dt: float,
    wind_scale: float,
    dx_km: NDArray[np.floating] | None = None,
    dy_km: NDArray[np.floating] | None = None,
    dx_ref_km: float | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Cell Courant numbers for one substep.

    Without spacing, ``wind_scale`` is cells per (m/s) per month (legacy tests).
    With GridMetrics spacing, the same scale is km-calibrated on Atlas width 1024.
    """
    u = np.asarray(wind_u, dtype=np.float64)
    v = np.asarray(wind_v, dtype=np.float64)
    scale = float(dt) * float(wind_scale)
    if dx_km is None or dy_km is None or dx_ref_km is None:
        return u * scale, v * scale
    dx = np.asarray(dx_km, dtype=np.float64)
    dy = np.asarray(dy_km, dtype=np.float64)
    if dx.ndim == 1:
        dx = dx[:, None]
    if dy.ndim == 1:
        dy = dy[:, None]
    dx = np.maximum(dx, 1e-6)
    dy = np.maximum(dy, 1e-6)
    ref = max(float(dx_ref_km), 1e-6)
    return u * scale * (ref / dx), v * scale * (ref / dy)


def _cfl_substeps(
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    wind_scale: float,
    max_steps: int,
    dx_km: NDArray[np.floating] | None = None,
    dy_km: NDArray[np.floating] | None = None,
    dx_ref_km: float | None = None,
    cfl: float = ADVECT_CFL_DEFAULT,
) -> tuple[int, float]:
    """Substeps so max |Courant| ≤ ``cfl``, capped by ``max_steps`` (YAML leftover)."""
    cu, cv = _courant_uv(
        wind_u,
        wind_v,
        dt=1.0,
        wind_scale=wind_scale,
        dx_km=dx_km,
        dy_km=dy_km,
        dx_ref_km=dx_ref_km,
    )
    cmax = float(np.max(np.maximum(np.abs(cu), np.abs(cv))))
    limit = max(float(cfl), 1e-6)
    if cmax <= limit:
        return 1, cmax
    n = int(np.ceil(cmax / limit))
    n = max(1, min(max(int(max_steps), 1), n))
    return n, cmax


def _upwind_advect(
    moisture: NDArray[np.floating],
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    *,
    dt: float,
    wind_scale: float = 0.04,
    dx_km: NDArray[np.floating] | None = None,
    dy_km: NDArray[np.floating] | None = None,
    dx_ref_km: float | None = None,
    cfl_clip: float = 0.95,
) -> NDArray[np.float64]:
    """One donor-cell finite-volume step with E–W wrap; no N–S wrap.

    Convention (annex §10.2): ``j=0`` north; ``wind_v > 0`` northward (smaller j);
    ``wind_u > 0`` eastward.
    """
    q = np.asarray(moisture, dtype=np.float64)
    cu, cv = _courant_uv(
        wind_u,
        wind_v,
        dt=dt,
        wind_scale=wind_scale,
        dx_km=dx_km,
        dy_km=dy_km,
        dx_ref_km=dx_ref_km,
    )
    clip = max(float(cfl_clip), 1e-6)
    cu = np.clip(cu, -clip, clip)
    cv = np.clip(cv, -clip, clip)

    # x flux (cylindrical): u>0 eastward → upwind from west
    q_e = np.roll(q, -1, axis=1)
    q_w = np.roll(q, 1, axis=1)
    flux_x = np.where(cu >= 0.0, cu * (q - q_w), cu * (q_e - q))

    # y neighbours: south = larger j, north = smaller j
    q_south = np.empty_like(q)
    q_north = np.empty_like(q)
    q_south[:-1, :] = q[1:, :]
    q_south[-1, :] = q[-1, :]
    q_north[1:, :] = q[:-1, :]
    q_north[0, :] = q[0, :]
    # v>0 northward → upwind from south (PR-4 sign fix)
    flux_y = np.where(cv >= 0.0, cv * (q - q_south), cv * (q_north - q))

    out = q - flux_x - flux_y
    return np.maximum(out, 0.0)


def _diffuse_moisture(
    moisture: NDArray[np.floating],
    *,
    dt: float,
    mix_per_month: float = DEFAULT_DIFFUSION_MIX_PER_MONTH,
) -> NDArray[np.float64]:
    """Weak 4-neighbour mixing scaled so monthly strength is independent of steps."""
    q = np.asarray(moisture, dtype=np.float64)
    mix = float(np.clip(mix_per_month, 0.0, 0.95))
    # Compound: (1 - mix)^1 over a month ≈ product of substeps
    w = 1.0 - (1.0 - mix) ** float(dt)
    w = float(np.clip(w, 0.0, 0.95))
    if w <= 1e-15:
        return q.copy()
    neigh = (
        np.roll(q, 1, axis=1)
        + np.roll(q, -1, axis=1)
        + np.pad(q[1:, :], ((0, 1), (0, 0)), mode="edge")
        + np.pad(q[:-1, :], ((1, 0), (0, 0)), mode="edge")
    )
    out = (1.0 - w) * q + (w * 0.25) * neigh
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
    # ∇h in (east, south); wind (east, north) → lift ∝ u·sx - v·sy
    lift = u * sx - v * sy
    return lift


def partition_precipitation(
    *,
    q: NDArray[np.floating],
    capacity: NDArray[np.floating],
    land_dry: NDArray[np.floating],
    lift: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    latitude_deg: NDArray[np.floating],
    large_scale_frac: float,
    orographic_frac: float,
    convective_scale: float,
    lee_dry: float,
    itcz_latitude_deg: float | None = None,
    itcz_convective_scale: float = 0.0,
    itcz_width_deg: float = 8.0,
) -> dict[str, NDArray[np.float64]]:
    """Candidate precip components, scaled so total ≤ available ``q`` (PR-4/PR-7).

    When ``itcz_convective_scale > 0``, tropical peaking uses the monthly ITCZ
    band as a separate demand term (not a post-hoc rain field). Base convection
    keeps a weak background so the ITCZ term is non-duplicative.
    """
    qq = np.asarray(q, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)
    dry = np.asarray(land_dry, dtype=np.float64)
    lf = np.asarray(lift, dtype=np.float64)
    temp = np.asarray(temperature_c, dtype=np.float64)
    lat = np.asarray(latitude_deg, dtype=np.float64)

    excess = np.maximum(0.0, qq - cap * dry)
    large_scale = float(large_scale_frac) * excess
    oro = float(orographic_frac) * np.maximum(0.0, lf) * np.minimum(qq, cap)
    warm = np.clip((temp - 18.0) / 12.0, 0.0, 1.0)
    moist_frac = np.clip(qq / np.maximum(cap, 1e-6), 0.0, 1.5)
    moist_cap = np.minimum(qq, cap)
    tropical_fixed = np.exp(-0.5 * (lat / 18.0) ** 2)
    itcz_s = float(max(itcz_convective_scale, 0.0))
    if itcz_s > 0.0 and itcz_latitude_deg is not None:
        width = max(float(itcz_width_deg), 1.0)
        itcz_band = np.exp(
            -0.5 * ((lat - float(itcz_latitude_deg)) / width) ** 2
        )
        # Weak background convection; seasonal peak is the ITCZ term.
        conv = (
            float(convective_scale)
            * 0.35
            * warm
            * moist_frac
            * moist_cap
        )
        itcz_extra = itcz_s * warm * moist_frac * itcz_band * moist_cap
    else:
        conv = (
            float(convective_scale)
            * warm
            * moist_frac
            * tropical_fixed
            * moist_cap
        )
        itcz_extra = np.zeros_like(qq)

    # CR-8: lee_dry inhibits condensation on descent; it is not a q mass sink.
    lee_w = float(lee_dry) * np.maximum(0.0, -lf)
    brake = 1.0 / (1.0 + lee_w)
    oro_braked = oro * brake
    large_braked = large_scale * (0.5 + 0.5 * brake)
    inhibited = (oro - oro_braked) + (large_scale - large_braked)
    demand = large_braked + oro_braked + conv + itcz_extra
    scale = np.ones_like(qq)
    positive = demand > 1e-15
    scale = np.where(positive, np.minimum(1.0, qq / np.maximum(demand, 1e-15)), 1.0)
    large_scale = large_braked * scale
    oro = oro_braked * scale
    conv = conv * scale
    itcz_extra = itcz_extra * scale
    precip = large_scale + oro + conv + itcz_extra

    return {
        "large_scale_precip": large_scale,
        "orographic_precip": oro,
        "convective_precip": conv,
        "itcz_precip": itcz_extra,
        "precipitation": precip,
        "lee_sink": np.zeros_like(qq),
        "lee_inhibited": inhibited * scale,
        "precip_scale": scale,
        "lee_brake": brake,
    }


def _month_step(
    q: NDArray[np.float64],
    land_store: NDArray[np.float64],
    *,
    temperature_c: NDArray[np.floating],
    wind_u: NDArray[np.floating],
    wind_v: NDArray[np.floating],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    latitude_deg: NDArray[np.floating],
    continentality: NDArray[np.float64],
    sst_c: NDArray[np.floating] | None,
    lake_mask: NDArray[np.bool_] | None,
    river_mask: NDArray[np.bool_] | None,
    lake_fraction: NDArray[np.floating] | None,
    advect_steps: int,
    advect_wind_scale: float,
    diffusion_mix_per_month: float,
    large_scale_frac: float,
    orographic_frac: float,
    convective_scale: float,
    ocean_evap_rate: float,
    lake_evap_rate: float,
    river_evap_rate: float,
    land_et_rate: float,
    continentality_dry: float,
    lee_dry: float,
    plume_strength: float,
    plume_mix_steps: int,
    land_store_capacity: float,
    itcz_latitude_deg: float | None,
    itcz_convective_scale: float,
    itcz_width_deg: float,
    dx_km: NDArray[np.floating] | None = None,
    dy_km: NDArray[np.floating] | None = None,
    dx_ref_km: float | None = None,
    advect_cfl: float = ADVECT_CFL_DEFAULT,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    dict[str, NDArray[np.float64]],
    dict[str, float],
]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    speed = np.hypot(wind_u, wind_v)
    store = np.asarray(land_store, dtype=np.float64)
    cap_store = float(max(land_store_capacity, 0.0))
    evap_c = evaporation_components(
        temperature_c=temperature_c,
        ocean_mask=ocean,
        sst_c=sst_c,
        wind_speed=speed,
        ocean_rate=ocean_evap_rate,
        land_rate=land_et_rate,
        lake_mask=lake_mask,
        river_mask=river_mask,
        lake_rate=lake_evap_rate,
        river_rate=river_evap_rate,
        land_store=store if cap_store > 0.0 else None,
        land_store_capacity=cap_store,
        lake_fraction=lake_fraction,
    )
    evap = evap_c["total"]
    land_et = evap_c["land_et"]
    if cap_store > 0.0:
        store = np.maximum(store - land_et, 0.0)

    storage_start = float(np.sum(q))

    q = q + evap
    steps, cfl_month = _cfl_substeps(
        wind_u,
        wind_v,
        wind_scale=advect_wind_scale,
        max_steps=advect_steps,
        dx_km=dx_km,
        dy_km=dy_km,
        dx_ref_km=dx_ref_km,
        cfl=advect_cfl,
    )
    dt = 1.0 / float(steps)
    for _ in range(steps):
        q = _upwind_advect(
            q,
            wind_u,
            wind_v,
            dt=dt,
            wind_scale=advect_wind_scale,
            dx_km=dx_km,
            dy_km=dy_km,
            dx_ref_km=dx_ref_km,
            cfl_clip=advect_cfl,
        )
        q = _diffuse_moisture(
            q, dt=dt, mix_per_month=diffusion_mix_per_month
        )
    # Once-per-month soft plume (existing q only; mass-conserving).
    q = soft_plume_mix(
        q, wind_u, wind_v, strength=plume_strength, steps=plume_mix_steps
    )

    capacity = saturation_capacity(temperature_c)
    land_dry = 1.0 - float(continentality_dry) * continentality * (~ocean).astype(
        np.float64
    )
    lift = orographic_lift(wind_u=wind_u, wind_v=wind_v, elevation_m=elevation_m)
    part = partition_precipitation(
        q=q,
        capacity=capacity,
        land_dry=land_dry,
        lift=lift,
        temperature_c=temperature_c,
        latitude_deg=latitude_deg,
        large_scale_frac=large_scale_frac,
        orographic_frac=orographic_frac,
        convective_scale=convective_scale,
        lee_dry=lee_dry,
        itcz_latitude_deg=itcz_latitude_deg,
        itcz_convective_scale=itcz_convective_scale,
        itcz_width_deg=itcz_width_deg,
    )

    precip = part["precipitation"]
    lee = part["lee_sink"]
    lee_inhibited = part["lee_inhibited"]
    max_overshoot = float(np.max(precip - q))
    q_after = np.maximum(q - precip, 0.0)
    # Soft capacity ceiling (not a hidden precip sink — track delta)
    q_capped = np.minimum(q_after, capacity * 1.25)
    capacity_sink = np.maximum(q_after - q_capped, 0.0)
    q = q_capped

    # Land-store refill from precipitation (runoff = excess over capacity).
    river = np.zeros(ocean.shape, dtype=bool)
    lake = np.zeros(ocean.shape, dtype=bool)
    if river_mask is not None:
        river = np.asarray(river_mask, dtype=bool) & ~ocean
    if lake_mask is not None:
        lake = np.asarray(lake_mask, dtype=bool) & ~ocean & ~river
    land_cells = ~ocean & ~lake & ~river
    runoff_discard = 0.0
    if cap_store > 0.0:
        store = np.where(land_cells, store + precip, store)
        excess = np.maximum(store - cap_store, 0.0)
        runoff_discard = float(np.sum(excess))
        store = np.where(land_cells, np.minimum(store, cap_store), 0.0)
    else:
        store = np.zeros_like(q)

    storage_end = float(np.sum(q))
    sources = float(np.sum(evap))
    sinks = float(np.sum(precip) + np.sum(capacity_sink))
    residual = storage_start + sources - sinks - storage_end

    fields = {
        "evaporation": evap,
        "ocean_evaporation": evap_c["ocean_evaporation"],
        "lake_evaporation": evap_c["lake_evaporation"],
        "river_evaporation": evap_c["river_evaporation"],
        "land_et": land_et,
        "land_et_potential": evap_c["land_et_potential"],
        "atmospheric_moisture": q,
        "humidity": np.clip(q / np.maximum(capacity, 1e-6), 0.0, 1.5),
        "precipitation": precip,
        "large_scale_precip": part["large_scale_precip"],
        "orographic_precip": part["orographic_precip"],
        "convective_precip": part["convective_precip"],
        "itcz_precip": part["itcz_precip"],
        "lee_sink": lee,
        "lee_inhibited": lee_inhibited,
        "capacity_sink": capacity_sink,
        "orographic_lift": lift,
        "land_store": store,
    }
    budget = {
        "storage_start": storage_start,
        "sources": sources,
        "precipitation_sum": float(np.sum(precip)),
        "lee_sink_sum": 0.0,
        "lee_inhibited_sum": float(np.sum(lee_inhibited)),
        "advect_steps_used": int(steps),
        "advect_cfl_month": float(cfl_month),
        "capacity_sink_sum": float(np.sum(capacity_sink)),
        "storage_end": storage_end,
        "numerical_residual": residual,
        "max_precip_overshoot": max_overshoot,
        "land_store_runoff_discard": runoff_discard,
        "land_et_sum": float(np.sum(land_et)),
        "itcz_precip_sum": float(np.sum(part["itcz_precip"])),
    }
    return q, store, fields, budget


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
    lake_fraction: NDArray[np.floating] | None = None,
    months: int | None = None,
    advect_steps: int = 6,
    advect_wind_scale: float = 0.04,
    diffusion_mix_per_month: float = DEFAULT_DIFFUSION_MIX_PER_MONTH,
    large_scale_frac: float = 0.55,
    orographic_frac: float = 0.85,
    convective_scale: float = 1.4,
    ocean_evap_rate: float = 1.15,
    lake_evap_rate: float = 0.75,
    river_evap_rate: float = 0.40,
    land_et_rate: float = 0.22,
    continentality_dry: float = 0.45,
    lee_dry: float = 0.12,
    spinup_max_years: int = 4,
    spinup_tolerance_relative: float = 0.02,
    spinup_tolerance_absolute: float = 1e-3,
    # PR-7 defaults off here so PR-4 fixtures stay calendar-invariant;
    # MoistureParams / YAML enable them for production.
    plume_strength: float = 0.0,
    plume_mix_steps: int = 6,
    land_store_capacity: float = 0.0,
    itcz_latitude_deg: NDArray[np.floating] | None = None,
    itcz_convective_scale: float = 0.0,
    itcz_width_deg: float = 8.0,
    axial_tilt_deg: float = 23.44,
    planet_radius_km: float = EARTH_RADIUS_KM,
    advect_cfl: float = ADVECT_CFL_DEFAULT,
    advect_scale_ref_width: float | None = None,
) -> dict[str, NDArray | dict[str, Any]]:
    """Monthly moisture state with periodic spin-up and closed precip budget (PR-4/7)."""
    from worldsim.physical.atmosphere.circulation import itcz_latitude_deg as itcz_lat_fn

    temp = np.asarray(temperature_c, dtype=np.float64)
    wu = np.asarray(wind_u, dtype=np.float64)
    wv = np.asarray(wind_v, dtype=np.float64)
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    lat = np.asarray(latitude_deg, dtype=np.float64)
    n = int(months if months is not None else temp.shape[0])
    h, w = ocean.shape
    gm = grid_metrics(w, h, radius_km=float(planet_radius_km))
    dx_km = gm.ew_spacing_km()
    dy_km = gm.ns_spacing_km()
    ref_width = float(
        advect_scale_ref_width if advect_scale_ref_width is not None else w
    )
    dx_ref_km = float(gm.circumference_km) / max(ref_width, 1.0)

    if continentality is None:
        cont = np.zeros((h, w), dtype=np.float64)
    else:
        cont = np.asarray(continentality, dtype=np.float64)

    if itcz_latitude_deg is None:
        itcz = np.array(
            [itcz_lat_fn(m, axial_tilt_deg=axial_tilt_deg) for m in range(n)],
            dtype=np.float64,
        )
    else:
        itcz = np.asarray(itcz_latitude_deg, dtype=np.float64)
        if itcz.shape == ():
            itcz = np.full(n, float(itcz))
        elif itcz.shape[0] < n:
            raise ValueError("itcz_latitude_deg must cover all months")

    # Warm start: mean monthly evaporation (avoids January dry transient).
    q = np.zeros((h, w), dtype=np.float64)
    for m in range(n):
        sst_m = sst_c[m] if sst_c is not None else None
        speed = np.hypot(wu[m], wv[m])
        q += evaporation_field(
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
            lake_fraction=lake_fraction,
        )
    q = q / float(max(n, 1))
    q = np.minimum(q, saturation_capacity(temp.mean(axis=0)) * 0.8)

    cap_store = float(max(land_store_capacity, 0.0))
    land_store = np.where(~ocean, 0.5 * cap_store, 0.0).astype(np.float64)

    years = max(int(spinup_max_years), 1)
    closure = float("inf")
    closure_q = float("inf")
    closure_s = 0.0
    converged = False
    year_used = 0
    store_gated = cap_store > 0.0

    evaporation = np.empty((n, h, w), dtype=np.float64)
    moisture = np.empty((n, h, w), dtype=np.float64)
    humidity = np.empty((n, h, w), dtype=np.float64)
    precipitation = np.empty((n, h, w), dtype=np.float64)
    large_scale_precip = np.empty((n, h, w), dtype=np.float64)
    orographic_precip = np.empty((n, h, w), dtype=np.float64)
    convective = np.empty((n, h, w), dtype=np.float64)
    itcz_precip = np.empty((n, h, w), dtype=np.float64)
    lee_sink = np.empty((n, h, w), dtype=np.float64)
    lee_inhibited = np.empty((n, h, w), dtype=np.float64)
    orographic = np.empty((n, h, w), dtype=np.float64)
    ocean_evaporation = np.empty((n, h, w), dtype=np.float64)
    lake_evaporation = np.empty((n, h, w), dtype=np.float64)
    river_evaporation = np.empty((n, h, w), dtype=np.float64)
    land_et = np.empty((n, h, w), dtype=np.float64)
    land_et_potential = np.empty((n, h, w), dtype=np.float64)
    land_store_out = np.empty((n, h, w), dtype=np.float64)
    monthly_residuals: list[float] = []
    steps_used: list[int] = []

    for year in range(years):
        q_year_start = q.copy()
        store_year_start = land_store.copy()
        monthly_residuals = []
        steps_used = []
        for m in range(n):
            sst_m = sst_c[m] if sst_c is not None else None
            q, land_store, fields, budget = _month_step(
                q,
                land_store,
                temperature_c=temp[m],
                wind_u=wu[m],
                wind_v=wv[m],
                elevation_m=elev,
                ocean_mask=ocean,
                latitude_deg=lat,
                continentality=cont,
                sst_c=sst_m,
                lake_mask=lake_mask,
                river_mask=river_mask,
                lake_fraction=lake_fraction,
                advect_steps=advect_steps,
                advect_wind_scale=advect_wind_scale,
                diffusion_mix_per_month=diffusion_mix_per_month,
                large_scale_frac=large_scale_frac,
                orographic_frac=orographic_frac,
                convective_scale=convective_scale,
                ocean_evap_rate=ocean_evap_rate,
                lake_evap_rate=lake_evap_rate,
                river_evap_rate=river_evap_rate,
                land_et_rate=land_et_rate,
                continentality_dry=continentality_dry,
                lee_dry=lee_dry,
                plume_strength=plume_strength,
                plume_mix_steps=plume_mix_steps,
                land_store_capacity=cap_store,
                itcz_latitude_deg=float(itcz[m % len(itcz)]),
                itcz_convective_scale=itcz_convective_scale,
                itcz_width_deg=itcz_width_deg,
                dx_km=dx_km,
                dy_km=dy_km,
                dx_ref_km=dx_ref_km,
                advect_cfl=advect_cfl,
            )
            evaporation[m] = fields["evaporation"]
            moisture[m] = fields["atmospheric_moisture"]
            humidity[m] = fields["humidity"]
            precipitation[m] = fields["precipitation"]
            large_scale_precip[m] = fields["large_scale_precip"]
            orographic_precip[m] = fields["orographic_precip"]
            convective[m] = fields["convective_precip"]
            itcz_precip[m] = fields["itcz_precip"]
            lee_sink[m] = fields["lee_sink"]
            lee_inhibited[m] = fields["lee_inhibited"]
            orographic[m] = fields["orographic_lift"]
            ocean_evaporation[m] = fields["ocean_evaporation"]
            lake_evaporation[m] = fields["lake_evaporation"]
            river_evaporation[m] = fields["river_evaporation"]
            land_et[m] = fields["land_et"]
            land_et_potential[m] = fields["land_et_potential"]
            land_store_out[m] = fields["land_store"]
            monthly_residuals.append(float(budget["numerical_residual"]))
            steps_used.append(int(budget.get("advect_steps_used", advect_steps)))

        year_used = year + 1
        # CR-3: close on atmospheric q and land store jointly when store is active.
        delta_q = np.abs(q - q_year_start)
        closure_q = float(np.max(delta_q))
        mean_q = float(np.mean(q_year_start) + np.mean(q)) * 0.5 + 1e-9
        rel_q = closure_q / mean_q
        if cap_store > 0.0:
            delta_s = np.abs(land_store - store_year_start)
            # Mean |Δ| for store — cell-wise max stays noisy under seasonal ET.
            closure_s = float(np.mean(delta_s))
            mean_s = float(np.mean(store_year_start) + np.mean(land_store)) * 0.5 + 1e-9
            rel_s = closure_s / mean_s
        else:
            closure_s = 0.0
            rel_s = 0.0
        closure = max(closure_q, closure_s)
        q_ok = closure_q <= float(spinup_tolerance_absolute) or rel_q <= float(
            spinup_tolerance_relative
        )
        store_ok = (
            cap_store <= 0.0
            or closure_s <= float(spinup_tolerance_absolute)
            or rel_s <= float(spinup_tolerance_relative)
        )
        if q_ok and store_ok:
            converged = True
            break

    annual = precipitation.sum(axis=0)
    land = ~ocean
    # Interior / coast ratio for diagnostics (PR-7 interior reach).
    coast_band = land.copy()
    # crude: land cells within 3 cols of ocean via E–W roll
    near = np.zeros_like(land)
    ocean_f = ocean.astype(np.float64)
    for shift in range(1, 4):
        near |= (np.roll(ocean_f, shift, axis=1) > 0) | (
            np.roll(ocean_f, -shift, axis=1) > 0
        )
    near &= land
    interior = land & ~near
    interior_coast_ratio = float("nan")
    if np.any(interior) and np.any(near):
        c_mean = float(annual[near].mean())
        if c_mean > 1e-9:
            interior_coast_ratio = float(annual[interior].mean()) / c_mean

    june = min(5, n - 1)
    itcz_j = float(itcz[june % len(itcz)])
    in_band = np.abs(lat - itcz_j) <= float(itcz_width_deg)
    off_band = (np.abs(lat - itcz_j) > float(itcz_width_deg) * 2.0) & (
        np.abs(lat) < 40.0
    )
    itcz_off_ratio = float("nan")
    if np.any(in_band) and np.any(off_band):
        off_m = float(precipitation[june][off_band].mean())
        if off_m > 1e-9:
            itcz_off_ratio = float(precipitation[june][in_band].mean()) / off_m

    budget_diag: dict[str, Any] = {
        "algorithm": "moisture_budget_spinup_v4_cr8",
        "advect_algorithm": "finite_volume_cfl_v1",
        "lee_mode": "condensation_brake",
        "b8_terms_active": bool(
            float(plume_strength) > 0.0
            or cap_store > 0.0
            or float(itcz_convective_scale) > 0.0
        ),
        "plume_strength": float(plume_strength),
        "plume_mix_steps": int(plume_mix_steps),
        "land_store_capacity": cap_store,
        "itcz_convective_scale": float(itcz_convective_scale),
        "itcz_width_deg": float(itcz_width_deg),
        "spinup_max_years": years,
        "spinup_years_used": year_used,
        "spinup_converged": converged,
        "spinup_closure_max_abs": closure,
        "spinup_closure_q_max_abs": closure_q,
        "spinup_closure_store_max_abs": closure_s,
        "spinup_store_gated": store_gated,
        "spinup_tolerance_relative": float(spinup_tolerance_relative),
        "spinup_tolerance_absolute": float(spinup_tolerance_absolute),
        "diffusion_mix_per_month": float(diffusion_mix_per_month),
        "advect_steps": int(advect_steps),
        "advect_steps_used_max": int(max(steps_used) if steps_used else advect_steps),
        "advect_cfl": float(advect_cfl),
        "advect_dx_ref_km": float(dx_ref_km),
        "advect_scale_ref_width": float(ref_width),
        "monthly_numerical_residual": monthly_residuals,
        "annual_numerical_residual": float(sum(monthly_residuals)),
        "annual_evaporation_sum": float(np.sum(evaporation)),
        "annual_precipitation_sum": float(np.sum(precipitation)),
        "annual_lee_sink_sum": 0.0,
        "annual_lee_inhibited_sum": float(np.sum(lee_inhibited)),
        "annual_land_et_sum": float(np.sum(land_et)),
        "annual_land_et_potential_sum": float(np.sum(land_et_potential)),
        "annual_ocean_evaporation_sum": float(np.sum(ocean_evaporation)),
        "annual_itcz_precip_sum": float(np.sum(itcz_precip)),
        "annual_base_convective_sum": float(np.sum(convective)),
        "interior_coast_precip_ratio": interior_coast_ratio,
        "itcz_offband_precip_ratio_june": itcz_off_ratio,
        "max_abs_component_sum_error": float(
            np.max(
                np.abs(
                    precipitation
                    - large_scale_precip
                    - orographic_precip
                    - convective
                    - itcz_precip
                )
            )
        ),
        "max_precip_overshoot": float(
            np.max(precipitation - (moisture + precipitation))
        ),
    }

    return {
        "atmospheric_moisture": moisture,
        "evaporation": evaporation,
        "precipitation": precipitation,
        "humidity": humidity,
        "orographic_lift": orographic,
        "convective_precip": convective,
        "itcz_precip": itcz_precip,
        "large_scale_precip": large_scale_precip,
        "orographic_precip": orographic_precip,
        "lee_sink": lee_sink,
        "lee_inhibited": lee_inhibited,
        "ocean_evaporation": ocean_evaporation,
        "lake_evaporation": lake_evaporation,
        "river_evaporation": river_evaporation,
        "land_et": land_et,
        "land_et_potential": land_et_potential,
        "land_store": land_store_out,
        "budget": budget_diag,
    }
