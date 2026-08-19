"""Basin storage from a discrete area–volume–height curve (C1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.cylindrical_graph import CylindricalFlowGraph
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days
from worldsim.physical.hydrology.lakes_meta import (
    apply_lake_identity,
    derive_lake_axes,
)
from worldsim.physical.hydrology.transmission import month_pet_fraction

_VOLUME_EPS_M3 = 1.0
_WET_FRAC_EPS = 1e-6
STORAGE_CURVE_DISCRETE = "discrete_avh_v1"
STORAGE_CURVE_LINEAR = "linear_a_of_h"


def _sink_cell(
    graph: CylindricalFlowGraph, body: NDArray[np.bool_]
) -> tuple[int, int] | None:
    """Inland sink or first cell inside a lake body."""
    w = body.shape[1]
    ds = graph.downstream_flat
    rows, cols = np.where(body)
    if rows.size == 0:
        return None
    for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
        if int(ds[int(r) * w + int(c)]) < 0:
            return int(r), int(c)
    return int(rows[0]), int(cols[0])


@dataclass
class DiscreteAVH:
    """Piecewise-constant A(z) built from sorted depression cells."""

    z_stage: NDArray[np.float64]
    area_stage_m2: NDArray[np.float64]
    volume_stage_m3: NDArray[np.float64]
    cell_z: NDArray[np.float64]
    cell_area_m2: NDArray[np.float64]
    rows: NDArray[np.int32]
    cols: NDArray[np.int32]
    order: NDArray[np.int32]
    z_floor: float
    z_spill: float
    v_spill: float
    a_spill: float
    curve: str = STORAGE_CURVE_DISCRETE

    def lookup(self, volume_m3: float) -> tuple[float, float]:
        """Return ``(water_surface_m, wet_area_m2)`` for a storage volume."""
        v = float(np.clip(volume_m3, 0.0, self.v_spill))
        if v <= _VOLUME_EPS_M3:
            return float(self.z_floor), 0.0
        vol = self.volume_stage_m3
        k = int(np.searchsorted(vol, v, side="right") - 1)
        k = max(0, min(k, vol.size - 2))
        v0 = float(vol[k])
        v1 = float(vol[k + 1])
        t = 0.0 if v1 <= v0 + 1e-12 else (v - v0) / (v1 - v0)
        z = float(self.z_stage[k] + t * (self.z_stage[k + 1] - self.z_stage[k]))
        a0 = float(self.area_stage_m2[k])
        a1 = float(self.area_stage_m2[k + 1])
        if self.curve == STORAGE_CURVE_LINEAR:
            area = a0 + t * (a1 - a0)
        else:
            area = a0 if a0 > 0.0 else a1
        return z, area

    def raster_wet_fraction(self, volume_m3: float, shape: tuple[int, int]) -> NDArray[np.float64]:
        """Wet fraction per cell; leftover area goes to one shoreline cell."""
        frac = np.zeros(shape, dtype=np.float64)
        _z_w, area_m2 = self.lookup(volume_m3)
        remaining = float(area_m2)
        if remaining <= 0.0:
            return frac
        for idx in self.order.tolist():
            z = float(self.cell_z[idx])
            if z >= float(self.z_spill) - 1e-12:
                continue
            a = float(self.cell_area_m2[idx])
            if a <= 0.0:
                continue
            r = int(self.rows[idx])
            c = int(self.cols[idx])
            if remaining >= a - 1e-9:
                frac[r, c] = 1.0
                remaining -= a
            else:
                frac[r, c] = float(np.clip(remaining / a, 0.0, 1.0))
                remaining = 0.0
                break
        return frac


def build_discrete_avh(
    floor_m: NDArray[np.floating],
    area_m2: NDArray[np.floating],
    rows: NDArray[np.integer],
    cols: NDArray[np.integer],
    *,
    spill_elevation_m: float,
) -> DiscreteAVH:
    """Sort cells by (elevation, row, col) and build a discrete A–V–h curve."""
    z = np.asarray(floor_m, dtype=np.float64).reshape(-1)
    a = np.maximum(np.asarray(area_m2, dtype=np.float64).reshape(-1), 0.0)
    rr = np.asarray(rows, dtype=np.int32).reshape(-1)
    cc = np.asarray(cols, dtype=np.int32).reshape(-1)
    n = int(z.size)
    if n == 0:
        raise ValueError("need at least one depression cell")
    order = np.lexsort((cc, rr, z)).astype(np.int32)
    z_floor = float(np.min(z))
    z_spill = float(max(spill_elevation_m, z_floor))
    hold = z < z_spill - 1e-12
    if not np.any(hold):
        z_spill = float(np.max(z) + max(1.0, abs(float(np.max(z) - z_floor))))
        hold = z < z_spill - 1e-12
    unique_z = np.unique(z[hold])
    stages_z = np.unique(np.concatenate([unique_z, np.array([z_spill], dtype=np.float64)]))
    if stages_z.size < 2:
        stages_z = np.array([z_floor, z_spill if z_spill > z_floor else z_floor + 1.0], dtype=np.float64)
    n_s = int(stages_z.size)
    area_stage = np.zeros(n_s, dtype=np.float64)
    volume = np.zeros(n_s, dtype=np.float64)
    for k in range(n_s - 1):
        area_stage[k] = float(np.sum(a[(z <= stages_z[k] + 1e-12) & (z < z_spill - 1e-12)]))
        volume[k + 1] = volume[k] + area_stage[k] * float(stages_z[k + 1] - stages_z[k])
    area_stage[-1] = float(np.sum(a[z < z_spill - 1e-12]))
    return DiscreteAVH(
        z_stage=stages_z,
        area_stage_m2=area_stage,
        volume_stage_m3=volume,
        cell_z=z,
        cell_area_m2=a,
        rows=rr,
        cols=cc,
        order=order,
        z_floor=z_floor,
        z_spill=float(stages_z[-1]),
        v_spill=float(volume[-1]),
        a_spill=float(area_stage[-1]),
        curve=STORAGE_CURVE_DISCRETE,
    )


def build_linear_avh_fallback(
    floor_m: NDArray[np.floating],
    area_m2: NDArray[np.floating],
    rows: NDArray[np.integer],
    cols: NDArray[np.integer],
    *,
    spill_elevation_m: float,
) -> DiscreteAVH:
    """Legacy linear A(h); raster still uses lowest cells in elevation order."""
    discrete = build_discrete_avh(
        floor_m, area_m2, rows, cols, spill_elevation_m=spill_elevation_m
    )
    h_spill = max(float(discrete.z_spill - discrete.z_floor), 1.0)
    a_max = float(np.sum(discrete.cell_area_m2[discrete.cell_z < discrete.z_spill - 1e-12]))
    v_spill = 0.5 * a_max * h_spill
    z_stage = np.array([discrete.z_floor, discrete.z_spill], dtype=np.float64)
    area_stage = np.array([0.0, a_max], dtype=np.float64)
    volume = np.array([0.0, v_spill], dtype=np.float64)
    return DiscreteAVH(
        z_stage=z_stage,
        area_stage_m2=area_stage,
        volume_stage_m3=volume,
        cell_z=discrete.cell_z,
        cell_area_m2=discrete.cell_area_m2,
        rows=discrete.rows,
        cols=discrete.cols,
        order=discrete.order,
        z_floor=discrete.z_floor,
        z_spill=discrete.z_spill,
        v_spill=v_spill,
        a_spill=a_max,
        curve=STORAGE_CURVE_LINEAR,
    )


def _month_frozen(temp_m: NDArray[np.floating], body: NDArray[np.bool_], frozen_temp_c: float) -> bool:
    if not np.any(body):
        return True
    return float(np.mean(temp_m[body])) < float(frozen_temp_c)


def _reclass_storage_axes(rec: dict[str, Any], *, months_wet: int, months_frozen: int, n_months: int) -> None:
    closed = bool(rec.get("closed_basin"))
    if months_frozen >= n_months:
        ice = "perennially_frozen"
    elif months_frozen > 0:
        ice = "seasonally_frozen"
    else:
        ice = "normally_liquid"
    if months_wet <= 0:
        hp = "ephemeral_or_dry"
    elif months_wet >= n_months:
        hp = "permanent"
    else:
        hp = "seasonal"
    ot = str(rec.get("outlet_type") or "")
    if not ot:
        if rec.get("has_ocean_outlet"):
            ot = "ocean_draining"
        elif closed:
            ot = "closed_endorheic"
        else:
            ot = "open_lake"
    axes = derive_lake_axes(
        outlet_type=ot,
        hydroperiod=hp,
        ice_regime=ice,
        closed_basin=closed,
        water_state=str(rec.get("water_state") or ""),
    )
    rec.update(axes)
    apply_lake_identity(rec)


def apply_basin_storage(
    *,
    graph: CylindricalFlowGraph | None,
    lake_id: NDArray[np.integer],
    lake_records: list[dict[str, Any]],
    elevation_m: NDArray[np.floating],
    monthly_q_m3s: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    cell_area_km2: float,
    monthly_precip: NDArray[np.floating] | None = None,
    precip_scale_mm: float = 200.0,
    lake_min_depth_m: float = 2.0,
    frozen_temp_c: float = 1.0,
    spinup_years: int = 8,
    spinup_rel_tol: float = 0.01,
    seepage_m_per_month: float = 0.0,
    storage_curve: str = STORAGE_CURVE_DISCRETE,
) -> dict[str, Any]:
    """Monthly storage for every retained basin envelope (open and closed).

    Mutates ``lake_records``. Returns diagnostics plus liquid/ice fraction rasters.
    Non-periodic liquid lakes are withheld from the published liquid product.
    """
    q = np.asarray(monthly_q_m3s, dtype=np.float64)
    if q.ndim != 3:
        raise ValueError("monthly_q_m3s must be [months, y, x]")
    months = int(q.shape[0])
    elev = np.asarray(elevation_m, dtype=np.float64)
    ids = np.asarray(lake_id)
    h, w = elev.shape
    if temperature_c.ndim == 3:
        temp_m = np.asarray(temperature_c, dtype=np.float64)
    else:
        annual = np.asarray(temperature_c, dtype=np.float64)
        temp_m = np.broadcast_to(annual, q.shape)
    precip_m = None
    if monthly_precip is not None:
        precip_m = np.asarray(monthly_precip, dtype=np.float64)

    area_m2_cell = float(cell_area_km2) * 1e6
    water_monthly = np.zeros((months, h, w), dtype=np.float64)
    ice_monthly = np.zeros((months, h, w), dtype=np.float64)
    stepped = 0
    reclass_playa = 0
    reclass_endorheic = 0
    periodic_count = 0
    liquid_count = 0
    liquid_periodic_count = 0
    withheld_count = 0
    years = max(int(spinup_years), 1)
    builder = (
        build_linear_avh_fallback
        if storage_curve == STORAGE_CURVE_LINEAR
        else build_discrete_avh
    )

    for rec in lake_records:
        lid = int(rec["lake_id"])
        body = ids == lid
        n_cells = int(np.count_nonzero(body))
        rec["envelope_cell_count"] = n_cells
        rec["envelope_area_km2"] = float(n_cells) * float(cell_area_km2)
        if n_cells == 0:
            continue
        sink = rec.get("sink_row"), rec.get("sink_col")
        if sink[0] is None or sink[1] is None:
            found = _sink_cell(graph, body) if graph is not None else None
            if found is None:
                rows0, cols0 = np.where(body)
                found = (int(rows0[0]), int(cols0[0]))
            sink = found
        sr, sc = int(sink[0]), int(sink[1])
        rec["sink_row"] = sr
        rec["sink_col"] = sc
        rows, cols = np.where(body)
        z_floor = float(np.min(elev[body]))
        z_spill = float(rec.get("spill_elevation_m", z_floor + lake_min_depth_m))
        z_spill = max(z_spill, z_floor + max(float(lake_min_depth_m), 0.0))
        avh = builder(
            elev[rows, cols],
            np.full(rows.size, area_m2_cell),
            rows,
            cols,
            spill_elevation_m=z_spill,
        )
        rec["v_spill_m3"] = float(avh.v_spill)
        rec["h_spill_m"] = float(avh.z_spill - avh.z_floor)
        rec["storage_curve"] = avh.curve

        volume = 0.0
        prev_storage: list[float] | None = None
        storage: list[float] = []
        level: list[float] = []
        wet_area: list[float] = []
        spill: list[float] = []
        inflow_m3: list[float] = []
        evap_m3: list[float] = []
        frozen_flags: list[bool] = []
        used_years = years
        periodic = False
        month_liquid: list[NDArray[np.float64]] = []
        month_ice: list[NDArray[np.float64]] = []
        for year in range(years):
            storage.clear()
            level.clear()
            wet_area.clear()
            spill.clear()
            inflow_m3.clear()
            evap_m3.clear()
            frozen_flags.clear()
            month_liquid = []
            month_ice = []
            for m in range(months):
                days = float(month_days(m))
                seconds = days * SECONDS_PER_DAY
                frozen = _month_frozen(temp_m[m], body, frozen_temp_c)
                frozen_flags.append(frozen)
                _z0, area0 = avh.lookup(volume)
                inflow = max(float(q[m, sr, sc]), 0.0) * seconds
                precip_vol = 0.0
                if precip_m is not None and area0 > 0.0:
                    p_mm = max(float(np.mean(precip_m[m][body])), 0.0) * float(
                        precip_scale_mm
                    )
                    precip_vol = (p_mm / 1000.0) * area0
                volume = max(volume + inflow + precip_vol, 0.0)
                _z1, area1 = avh.lookup(volume)
                pet_mm = 0.0
                if not frozen:
                    bio = float(np.clip(np.mean(temp_m[m][body]), 0.0, 30.0))
                    pet_mm = 58.93 * bio * month_pet_fraction(m)
                evap = (pet_mm / 1000.0) * area1
                seep = max(float(seepage_m_per_month), 0.0) * area1
                loss = min(volume, evap + seep)
                volume = max(volume - loss, 0.0)
                spilled = 0.0
                if volume > avh.v_spill:
                    spilled = volume - avh.v_spill
                    volume = avh.v_spill
                z_w, area = avh.lookup(volume)
                frac = avh.raster_wet_fraction(volume, (h, w))
                ice_frac = frac if frozen else np.zeros_like(frac)
                liquid_frac = np.zeros_like(frac) if frozen else frac
                if frozen:
                    area = 0.0
                storage.append(volume)
                level.append(max(z_w - avh.z_floor, 0.0))
                wet_area.append(area / 1e6)
                spill.append(spilled)
                inflow_m3.append(inflow + precip_vol)
                evap_m3.append(loss)
                month_liquid.append(liquid_frac)
                month_ice.append(ice_frac)
            if prev_storage is not None and prev_storage:
                denom = max(float(np.mean(prev_storage)), 1.0)
                rel = float(np.max(np.abs(np.array(storage) - np.array(prev_storage)))) / denom
                if rel <= float(spinup_rel_tol):
                    periodic = True
                    used_years = year + 1
                    break
            prev_storage = list(storage)

        rec["storage_m3"] = [float(v) for v in storage]
        rec["level_m"] = [float(v) for v in level]
        rec["wet_area_km2"] = [float(v) for v in wet_area]
        rec["spill_m3"] = [float(v) for v in spill]
        rec["inflow_m3"] = [float(v) for v in inflow_m3]
        rec["evap_loss_m3"] = [float(v) for v in evap_m3]
        rec["mean_storage_m3"] = float(np.mean(storage)) if storage else 0.0
        rec["mean_wet_area_km2"] = float(np.mean(wet_area)) if wet_area else 0.0
        rec["months_wet"] = int(sum(1 for v in wet_area if v > _WET_FRAC_EPS))
        rec["months_frozen"] = int(sum(1 for f in frozen_flags if f))
        rec["storage_periodic"] = bool(periodic)
        rec["storage_spinup_years_used"] = int(used_years)
        rec["surface_elevation_m"] = float(avh.z_floor + (np.mean(level) if level else 0.0))
        rec["wet_area_km2_monthly"] = [float(v) for v in wet_area]
        rec["ice_area_km2_monthly"] = [
            float(np.sum(f) * float(cell_area_km2)) for f in month_ice
        ]
        rec["liquid_fraction_monthly"] = [
            float(np.mean(f[body])) if n_cells else 0.0 for f in month_liquid
        ]
        rec["ice_fraction_monthly"] = [
            float(np.mean(f[body])) if n_cells else 0.0 for f in month_ice
        ]
        rec["fractions_are_monthly"] = True
        stepped += 1
        if periodic:
            periodic_count += 1

        prev_state = str(rec.get("water_state") or "")
        _reclass_storage_axes(
            rec,
            months_wet=int(rec["months_wet"]),
            months_frozen=int(rec["months_frozen"]),
            n_months=months,
        )
        new_state = str(rec.get("water_state") or "")
        if new_state == "seasonal_or_playa" and prev_state != "seasonal_or_playa":
            reclass_playa += 1
        if new_state == "endorheic" and prev_state != "endorheic":
            reclass_endorheic += 1
        if new_state in ("open", "endorheic"):
            liquid_count += 1
            if periodic:
                liquid_periodic_count += 1
            else:
                rec["storage_unstable"] = True
                rec["water_body_id"] = 0
                withheld_count += 1
                apply_lake_identity(rec)
        publish = not bool(rec.get("storage_unstable"))
        if publish and month_liquid:
            for m, (liq, ice) in enumerate(zip(month_liquid, month_ice, strict=True)):
                water_monthly[m] += liq
                ice_monthly[m] += ice

    water_monthly = np.clip(water_monthly, 0.0, 1.0)
    ice_monthly = np.clip(ice_monthly, 0.0, 1.0)
    water_sum = water_monthly.mean(axis=0) if months else np.zeros((h, w), dtype=np.float64)

    return {
        "basin_storage_stepped_count": stepped,
        "basin_storage_reclass_playa": reclass_playa,
        "basin_storage_reclass_endorheic": reclass_endorheic,
        "basin_storage_spinup_years": int(spinup_years),
        "basin_storage_periodic_count": periodic_count,
        "basin_storage_liquid_count": liquid_count,
        "basin_storage_liquid_periodic_count": liquid_periodic_count,
        "basin_storage_nonperiodic_liquid_withheld_count": withheld_count,
        "basin_storage_nonperiodic_liquid_published_count": 0,
        "basin_storage_curve": str(storage_curve),
        "water_fraction_mean": water_sum,
        "water_fraction_monthly": water_monthly,
        "ice_fraction_monthly": ice_monthly,
        "lake_fractions_are_monthly": True,
    }


def apply_closed_basin_storage(**kwargs: Any) -> dict[str, Any]:
    """Backward-compatible name; open and closed basins both step storage."""
    return apply_basin_storage(**kwargs)


def liquid_id_from_fraction(
    envelope_id: NDArray[np.integer],
    water_fraction_mean: NDArray[np.floating],
    lake_records: list[dict[str, Any]],
    *,
    min_fraction: float = 0.05,
) -> tuple[NDArray[np.int32], NDArray[np.bool_]]:
    """Product lake_id / mask from actual mean liquid fraction, not the envelope."""
    env = np.asarray(envelope_id, dtype=np.int32)
    frac = np.asarray(water_fraction_mean, dtype=np.float64)
    wet = frac >= float(min_fraction)
    liquid_ids = {
        int(rec["lake_id"])
        for rec in lake_records
        if int(rec.get("water_body_id") or 0) > 0
        and not bool(rec.get("storage_unstable"))
        and str(rec.get("water_state") or "") not in ("seasonal_or_playa", "frozen_or_ice_covered")
    }
    lake_id = np.where(wet & np.isin(env, list(liquid_ids) or [0]), env, 0).astype(np.int32)
    if not liquid_ids:
        lake_id[:] = 0
    mask = lake_id > 0
    return lake_id, mask
