"""Single monthly lake-supernode router with mass ledger (PC1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.basins_storage import (
    STORAGE_CURVE_DISCRETE,
    STORAGE_CURVE_LINEAR,
    DiscreteAVH,
    build_discrete_avh,
    build_linear_avh_fallback,
    lake_month_storage_step,
    liquid_id_from_fraction,
    _reclass_storage_axes,
    _sink_cell,
    _WET_FRAC_EPS,
)
from worldsim.physical.hydrology.condensed_graph import (
    CondensedLakeGraph,
    build_condensed_lake_graph,
)
from worldsim.physical.hydrology.cylindrical_graph import (
    CylindricalFlowGraph,
    effective_discharge_and_sink,
    flat_index,
)
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days
from worldsim.physical.hydrology.lakes_meta import apply_lake_identity
from worldsim.physical.hydrology.mass_ledger import GlobalMonthLedger, LakeMonthLedger


@dataclass
class _LakeRuntime:
    avh: DiscreteAVH
    body: NDArray[np.bool_]
    sink_row: int
    sink_col: int
    volume_m3: float = 0.0


def spinup_condensed_lake_routing(
    *,
    graph: CylindricalFlowGraph,
    basin_envelope_id: NDArray[np.integer],
    lake_records: list[dict[str, Any]],
    elevation_m: NDArray[np.floating],
    monthly_land_runoff_m3s: NDArray[np.floating],
    bed_loss_potential_m3s: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    cell_area_km2: float,
    monthly_precip: NDArray[np.floating] | None = None,
    precip_scale_mm: float = 200.0,
    lake_min_depth_m: float = 2.0,
    frozen_temp_c: float = 1.0,
    spinup_years: int = 8,
    spinup_rel_tol: float = 0.01,
    storage_curve: str = STORAGE_CURVE_DISCRETE,
    seepage_m_per_month: float = 0.0,
) -> dict[str, Any]:
    """Monthly lake-supernode routing with same-month cascades and land spill bed-loss.

    Replaces post-hoc spill injection. Volumes are conserved internally; discharge
    products are m³/s derived from the last spin-up year.
    """
    q_in = np.asarray(monthly_land_runoff_m3s, dtype=np.float64)
    if q_in.ndim != 3:
        raise ValueError("monthly_land_runoff_m3s must be [months, y, x]")
    months = int(q_in.shape[0])
    h, w = q_in.shape[1], q_in.shape[2]
    elev = np.asarray(elevation_m, dtype=np.float64)
    env = np.asarray(basin_envelope_id, dtype=np.int32)
    if temperature_c.ndim == 3:
        temp_m = np.asarray(temperature_c, dtype=np.float64)
    else:
        temp_m = np.broadcast_to(
            np.asarray(temperature_c, dtype=np.float64), q_in.shape
        ).copy()
    precip_m = None
    if monthly_precip is not None:
        precip_m = np.asarray(monthly_precip, dtype=np.float64)

    condensed = build_condensed_lake_graph(
        graph=graph,
        basin_envelope_id=env,
        lake_records=lake_records,
    )
    area_m2_cell = float(cell_area_km2) * 1e6
    builder = (
        build_linear_avh_fallback
        if storage_curve == STORAGE_CURVE_LINEAR
        else build_discrete_avh
    )
    runtimes: dict[int, _LakeRuntime] = {}
    for rec in lake_records:
        lid = int(rec.get("lake_id") or 0)
        if lid <= 0 or lid not in condensed.supernodes:
            continue
        body = env == lid
        if not np.any(body):
            continue
        sn = condensed.supernodes[lid]
        sr, sc = int(sn.outlet_row), int(sn.outlet_col)
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
        rec["sink_row"] = sr
        rec["sink_col"] = sc
        runtimes[lid] = _LakeRuntime(avh=avh, body=body, sink_row=sr, sink_col=sc)

    lake_rec_by_id = {int(rec.get("lake_id") or 0): rec for rec in lake_records}

    years = max(int(spinup_years), 1)
    used_years = years
    prev_lake_storage: dict[int, list[float] | None] = {lid: None for lid in runtimes}
    lake_periodic: dict[int, bool] = {lid: False for lid in runtimes}
    lake_used_years: dict[int, int] = {lid: years for lid in runtimes}
    prev_storage_signature: list[float] | None = None
    global_signature_periodic = False
    last_monthly_q = np.zeros((months, h, w), dtype=np.float64)
    last_monthly_loss = np.zeros((months, h, w), dtype=np.float64)
    last_month_liquid_by_lake: dict[int, list[NDArray[np.float64]]] = {}
    last_month_ice_by_lake: dict[int, list[NDArray[np.float64]]] = {}
    last_ledgers: list[GlobalMonthLedger] = []
    max_lake_residual = 0.0

    for year in range(years):
        for rec in lake_records:
            lid = int(rec.get("lake_id") or 0)
            if lid not in runtimes:
                continue
            rec["storage_m3"] = []
            rec["level_m"] = []
            rec["wet_area_km2"] = []
            rec["spill_m3"] = []
            rec["inflow_m3"] = []
            rec["evap_loss_m3"] = []

        year_storage_sig: list[float] = []
        month_liquid_by_lake: dict[int, list[NDArray[np.float64]]] = {
            lid: [] for lid in runtimes
        }
        month_ice_by_lake: dict[int, list[NDArray[np.float64]]] = {
            lid: [] for lid in runtimes
        }
        year_ledgers: list[GlobalMonthLedger] = []
        year_q = np.zeros((months, h, w), dtype=np.float64)
        year_loss = np.zeros((months, h, w), dtype=np.float64)

        for m in range(months):
            seconds = float(month_days(m)) * SECONDS_PER_DAY
            land_q, land_loss = effective_discharge_and_sink(
                graph,
                q_in[m],
                bed_loss_potential_m3s,
                lake_id=env,
            )
            land_inflow_m3: dict[int, float] = {}
            for lid, rt in runtimes.items():
                land_inflow_m3[lid] = max(float(land_q[rt.sink_row, rt.sink_col]), 0.0) * seconds

            pending_lake_spill: dict[int, float] = {lid: 0.0 for lid in runtimes}
            land_spill_m3s = np.zeros((h, w), dtype=np.float64)
            global_led = GlobalMonthLedger(month=m)
            global_led.land_local_runoff_m3 = float(np.sum(q_in[m] * seconds))
            global_led.land_bed_loss_m3 = float(np.sum(land_loss) * seconds)

            storage_snap: dict[int, float] = {}
            spill_snap: dict[int, float] = {}
            inflow_snap: dict[int, float] = {}
            evap_snap: dict[int, float] = {}
            wet_snap: dict[int, float] = {}

            for lid in condensed.topo_order:
                if lid not in runtimes:
                    continue
                rt = runtimes[lid]
                rec = lake_rec_by_id[lid]
                body = rt.body
                precip_mm = 0.0
                if precip_m is not None:
                    precip_mm = max(float(np.mean(precip_m[m][body])), 0.0) * float(
                        precip_scale_mm
                    )
                volume, spill, _loss, wet_area, led = lake_month_storage_step(
                    avh=rt.avh,
                    volume_m3=rt.volume_m3,
                    land_inflow_m3=land_inflow_m3.get(lid, 0.0),
                    upstream_lake_spill_m3=pending_lake_spill.get(lid, 0.0),
                    body=body,
                    temp_c=temp_m[m],
                    precip_mm_on_water=precip_mm,
                    frozen_temp_c=frozen_temp_c,
                    seepage_m_per_month=seepage_m_per_month,
                    month_index=m,
                    lake_id=lid,
                )
                rt.volume_m3 = volume
                global_led.lake_ledgers.append(led)
                max_lake_residual = max(max_lake_residual, abs(led.residual_m3()))
                storage_snap[lid] = volume
                spill_snap[lid] = spill
                inflow_snap[lid] = led.sources_m3()
                evap_snap[lid] = led.open_water_evaporation_m3 + led.seepage_m3
                wet_snap[lid] = wet_area / 1e6

                sn = condensed.supernodes[lid]
                if spill > 0.0 and sn.downstream_lake_id > 0:
                    pending_lake_spill[sn.downstream_lake_id] = (
                        pending_lake_spill.get(sn.downstream_lake_id, 0.0) + spill
                    )
                elif spill > 0.0 and sn.spill_target_row is not None:
                    tr, tc = int(sn.spill_target_row), int(sn.spill_target_col)
                    land_spill_m3s[tr, tc] += spill / max(seconds, 1.0)

                frozen = float(np.mean(temp_m[m][body])) < float(frozen_temp_c)
                frac = rt.avh.raster_wet_fraction(volume, (h, w))
                ice_frac = frac if frozen else np.zeros_like(frac)
                liquid_frac = np.zeros_like(frac) if frozen else frac
                month_liquid_by_lake[lid].append(liquid_frac)
                month_ice_by_lake[lid].append(ice_frac)

            if np.any(land_spill_m3s):
                spill_q, spill_loss = effective_discharge_and_sink(
                    graph,
                    land_spill_m3s,
                    bed_loss_potential_m3s,
                    lake_id=env,
                )
                land_q = land_q + spill_q
                land_loss = land_loss + spill_loss
                global_led.land_bed_loss_m3 += float(np.sum(spill_loss) * seconds)

            year_q[m] = land_q
            year_loss[m] = land_loss
            global_led.land_downstream_release_m3 = float(np.sum(land_q) * seconds)
            year_ledgers.append(global_led)

            for lid, rt in runtimes.items():
                rec = lake_rec_by_id[lid]
                rec["storage_m3"].append(float(storage_snap.get(lid, rt.volume_m3)))
                z_w, _a = rt.avh.lookup(rt.volume_m3)
                rec["level_m"].append(max(z_w - rt.avh.z_floor, 0.0))
                rec["wet_area_km2"].append(float(wet_snap.get(lid, 0.0)))
                rec["spill_m3"].append(float(spill_snap.get(lid, 0.0)))
                rec["inflow_m3"].append(float(inflow_snap.get(lid, 0.0)))
                rec["evap_loss_m3"].append(float(evap_snap.get(lid, 0.0)))

        for lid in runtimes:
            rec = lake_rec_by_id[lid]
            liq_list = month_liquid_by_lake.get(lid) or []
            ice_list = month_ice_by_lake.get(lid) or []
            body = runtimes[lid].body
            n_cells = int(np.count_nonzero(body))
            tail_wet = rec.get("wet_area_km2") or []
            rec["mean_storage_m3"] = float(np.mean(rec["storage_m3"])) if rec.get("storage_m3") else 0.0
            rec["mean_wet_area_km2"] = float(np.mean(tail_wet)) if tail_wet else 0.0
            rec["months_wet"] = int(sum(1 for v in tail_wet if v > _WET_FRAC_EPS))
            rec["months_frozen"] = int(
                sum(
                    1
                    for mm in range(months)
                    if float(np.mean(temp_m[mm][body])) < float(frozen_temp_c)
                )
            )
            rec["open_water_fraction_monthly"] = [
                float(np.mean(f[body])) if n_cells else 0.0 for f in liq_list
            ]
            rec["lake_ice_fraction_monthly"] = [
                float(np.mean(f[body])) if n_cells else 0.0 for f in ice_list
            ]
            # Deprecated alias — readers should migrate to lake_ice_fraction_monthly.
            rec["liquid_fraction_monthly"] = list(rec["open_water_fraction_monthly"])
            rec["ice_fraction_monthly"] = list(rec["lake_ice_fraction_monthly"])
            rec["fractions_are_monthly"] = True
            rec["surface_elevation_m"] = float(
                runtimes[lid].avh.z_floor
                + (float(np.mean(rec["level_m"])) if rec.get("level_m") else 0.0)
            )

        for lid in runtimes:
            rec = lake_rec_by_id[lid]
            storage_series = list(rec.get("storage_m3") or [])
            prev = prev_lake_storage.get(lid)
            if prev is not None and prev and storage_series:
                denom = max(float(np.mean(prev)), 1.0)
                rel = float(
                    np.max(np.abs(np.array(storage_series) - np.array(prev)))
                ) / denom
                if rel <= float(spinup_rel_tol):
                    lake_periodic[lid] = True
                    lake_used_years[lid] = year + 1
                else:
                    lake_periodic[lid] = False
                    lake_used_years[lid] = years
            prev_lake_storage[lid] = list(storage_series)

        sig = [float(runtimes[lid].volume_m3) for lid in sorted(runtimes)]
        if prev_storage_signature is not None and prev_storage_signature:
            denom = max(float(np.mean(prev_storage_signature)), 1.0)
            rel = float(
                np.max(np.abs(np.array(sig) - np.array(prev_storage_signature)))
            ) / denom
            if rel <= float(spinup_rel_tol):
                global_signature_periodic = True
        prev_storage_signature = sig
        last_monthly_q = year_q
        last_monthly_loss = year_loss
        last_month_liquid_by_lake = {
            lid: list(month_liquid_by_lake.get(lid) or []) for lid in runtimes
        }
        last_month_ice_by_lake = {
            lid: list(month_ice_by_lake.get(lid) or []) for lid in runtimes
        }
        last_ledgers = year_ledgers
        if runtimes and all(lake_periodic[lid] for lid in runtimes):
            used_years = year + 1
            break

    # Reclass and periodic liquid policy (same as apply_basin_storage).
    stepped = 0
    periodic_count = 0
    liquid_count = 0
    liquid_periodic_count = 0
    withheld_count = 0
    reclass_playa = 0
    reclass_endorheic = 0
    for rec in lake_records:
        lid = int(rec.get("lake_id") or 0)
        if lid not in runtimes:
            continue
        stepped += 1
        lake_is_periodic = bool(lake_periodic.get(lid, False))
        rec["storage_periodic"] = lake_is_periodic
        rec["storage_spinup_years_used"] = int(lake_used_years.get(lid, used_years))
        rec["convergence_state"] = "periodic" if lake_is_periodic else "failed"
        prev_state = str(rec.get("water_state") or "")
        _reclass_storage_axes(
            rec,
            months_wet=int(rec.get("months_wet") or 0),
            months_frozen=int(rec.get("months_frozen") or 0),
            n_months=months,
        )
        new_state = str(rec.get("water_state") or "")
        if new_state == "seasonal_or_playa" and prev_state != "seasonal_or_playa":
            reclass_playa += 1
        if new_state == "endorheic" and prev_state != "endorheic":
            reclass_endorheic += 1
        if lake_is_periodic:
            periodic_count += 1
        if new_state in ("open", "endorheic"):
            liquid_count += 1
            if lake_is_periodic:
                liquid_periodic_count += 1
            else:
                rec["storage_unstable"] = True
                rec["water_body_id"] = 0
                withheld_count += 1
                apply_lake_identity(rec)

    water_present_monthly = np.zeros((months, h, w), dtype=np.float64)
    open_water_monthly = np.zeros((months, h, w), dtype=np.float64)
    lake_ice_monthly = np.zeros((months, h, w), dtype=np.float64)
    for lid in runtimes:
        rec = lake_rec_by_id[lid]
        if bool(rec.get("storage_unstable")):
            continue
        liq_list = last_month_liquid_by_lake.get(lid) or []
        ice_list = last_month_ice_by_lake.get(lid) or []
        if not liq_list:
            continue
        for mm, (liq, ice) in enumerate(zip(liq_list, ice_list, strict=True)):
            open_water_monthly[mm] += liq
            lake_ice_monthly[mm] += ice
            water_present_monthly[mm] += liq + ice

    water_present_monthly = np.clip(water_present_monthly, 0.0, 1.0)
    open_water_monthly = np.clip(open_water_monthly, 0.0, 1.0)
    lake_ice_monthly = np.clip(lake_ice_monthly, 0.0, 1.0)
    water_mean = water_present_monthly.mean(axis=0) if months else np.zeros((h, w), dtype=np.float64)

    ledger_diag = {
        "hydrology_mass_balance_max_lake_residual_m3": float(max_lake_residual),
        "hydrology_mass_balance_ok": bool(max_lake_residual <= 1e-3),
        "global_ledger_months": [g.summary() for g in last_ledgers],
    }

    return {
        "monthly_q_m3s": last_monthly_q,
        "monthly_bed_loss_m3s": last_monthly_loss,
        "water_fraction_mean": water_mean,
        "water_fraction_monthly": water_present_monthly,
        "open_water_fraction_monthly": open_water_monthly,
        "lake_ice_fraction_monthly": lake_ice_monthly,
        "condensed_graph": condensed,
        "basin_storage_stepped_count": stepped,
        "basin_storage_reclass_playa": reclass_playa,
        "basin_storage_reclass_endorheic": reclass_endorheic,
        "basin_storage_spinup_years": int(spinup_years),
        "basin_storage_spinup_years_used": int(used_years),
        "basin_storage_global_signature_periodic": bool(global_signature_periodic),
        "basin_storage_periodic_count": periodic_count,
        "basin_storage_liquid_count": liquid_count,
        "basin_storage_liquid_periodic_count": liquid_periodic_count,
        "basin_storage_nonperiodic_liquid_withheld_count": withheld_count,
        "basin_storage_nonperiodic_liquid_published_count": 0,
        "basin_storage_curve": str(storage_curve),
        "lake_fractions_are_monthly": True,
        "lake_routing_algorithm": "pc1_condensed_supernode_v1",
        **condensed.diagnostics,
        **ledger_diag,
    }
