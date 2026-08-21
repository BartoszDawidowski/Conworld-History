"""Single monthly lake-supernode router with mass ledger (PC1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.basins_storage import (
    MATERIAL_WITHHELD_WET_SHARE,
    STORAGE_CURVE_DISCRETE,
    STORAGE_CURVE_LINEAR,
    DiscreteAVH,
    build_discrete_avh,
    build_linear_avh_fallback,
    lake_month_storage_step,
    liquid_id_from_fraction,
    storage_series_converged,
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
    _touches_ocean,
    effective_discharge_and_sink,
    flat_index,
    unravel,
)
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days
from worldsim.physical.hydrology.lakes_meta import apply_lake_identity
from worldsim.physical.hydrology.mass_ledger import (
    LAKE_INFLOW_CAPTURE_RATIO_MIN,
    GlobalMonthLedger,
    land_terminal_exports_m3s,
)


@dataclass
class _LakeRuntime:
    avh: DiscreteAVH
    body: NDArray[np.bool_]
    sink_row: int
    sink_col: int
    volume_m3: float = 0.0


def _solve_annual_storage_fixed_point(
    *,
    rt: _LakeRuntime,
    inflow_m3: list[float],
    temp_m: NDArray[np.floating],
    precip_mm_monthly: list[float] | None,
    frozen_temp_c: float,
    months: int,
    rel_tol: float,
    max_iters: int = 24,
) -> tuple[float, bool, str, list[float]]:
    """Annual mean fixed-point on ``[0, V_spill]`` with frozen land inflows.

    Returns ``(V_star, accepted, limiting_process, storage_series)``.

    Runaway fill-to-spill from a still-empty basin is attempted but not accepted:
    publishing those inland seas inflated Atlas wet area ~10×. Natural spill-rim
    states (already near full after spin-up) remain acceptable.
    """
    v_spill = float(rt.avh.v_spill)
    if v_spill <= 1.0:
        return 0.0, True, "empty_domain", [0.0] * max(months, 1)

    def _one_year(v0: float) -> list[float]:
        volume = float(v0)
        series: list[float] = []
        for m in range(months):
            precip = (
                float(precip_mm_monthly[m])
                if precip_mm_monthly is not None and m < len(precip_mm_monthly)
                else 0.0
            )
            inflow = float(inflow_m3[m]) if m < len(inflow_m3) else 0.0
            volume, _spill, _loss, _area, _led = lake_month_storage_step(
                avh=rt.avh,
                volume_m3=volume,
                land_inflow_m3=inflow,
                upstream_lake_spill_m3=0.0,
                body=rt.body,
                temp_c=temp_m[m],
                precip_mm_on_water=precip,
                frozen_temp_c=float(frozen_temp_c),
                month_index=m,
                lake_id=0,
            )
            series.append(float(volume))
        return series

    v_start = float(np.clip(rt.volume_m3, 0.0, v_spill))
    volume = v_start
    series = _one_year(volume)
    for it in range(max_iters):
        series = _one_year(volume)
        mean_s = float(np.mean(series))
        v_next = float(np.clip(mean_s, 0.0, v_spill))
        # Scale by the cycle volume itself — scaling by V_spill accepts any
        # tiny step as "converged" and publishes half-filled seas.
        step_tol = float(rel_tol) * max(abs(volume), abs(v_next), 1.0)
        within_rise = float(series[-1] - series[0]) if series else 0.0
        rise_tol = float(rel_tol) * max(abs(mean_s), 1.0)
        if abs(v_next - volume) <= step_tol and within_rise <= rise_tol:
            if v_next >= 0.98 * v_spill and v_start < 0.50 * v_spill:
                return v_next, False, "fill_to_spill_unbounded", series
            limit = "spill_rim" if v_next >= 0.98 * v_spill else "mean_cycle"
            return v_next, True, limit, series
        # Persistent within-year fill toward capacity → unbounded spill attractor.
        if within_rise > rise_tol and v_next >= volume and v_start < 0.50 * v_spill:
            if v_next >= 0.98 * v_spill or (it + 1) >= max_iters:
                return min(v_next, v_spill), False, "fill_to_spill_unbounded", series
        volume = v_next
    if volume >= 0.98 * v_spill and v_start < 0.50 * v_spill:
        return volume, False, "fill_to_spill_unbounded", series
    if series and float(series[-1] - series[0]) > float(rel_tol) * max(
        abs(float(np.mean(series))), 1.0
    ):
        return volume, False, "fill_to_spill_unbounded", series
    return volume, False, "nonconverged", series


def _lake_land_inflow_m3s(
    *,
    graph: CylindricalFlowGraph,
    land_q_m3s: NDArray[np.floating],
    local_runoff_m3s: NDArray[np.floating],
    basin_envelope_id: NDArray[np.integer],
    lake_ids: list[int],
) -> dict[int, float]:
    """Sum all external land edges into each lake plus local runoff on the envelope.

    Addendum §5.1/§5.2: accumulate every incoming graph edge at the supernode —
    never a single sink cell.

    Vectorized (no per-call Python adjacency rebuild): Atlas grids are ~5e5 cells
    and the monthly spin-up used to OOM/SIGKILL when building upstream lists of
    lists every month.
    """
    env = np.asarray(basin_envelope_id, dtype=np.int32).ravel()
    q = np.maximum(np.asarray(land_q_m3s, dtype=np.float64).ravel(), 0.0)
    local = np.asarray(local_runoff_m3s, dtype=np.float64).ravel()
    out = {int(lid): 0.0 for lid in lake_ids}
    if not lake_ids:
        return out

    max_id = int(max(int(lid) for lid in lake_ids))
    # Local runoff generated on envelope cells (land-fraction proxy).
    if max_id > 0:
        local_sum = np.bincount(
            np.clip(env, 0, max_id),
            weights=local,
            minlength=max_id + 1,
        )
        for lid in lake_ids:
            out[int(lid)] += float(local_sum[int(lid)])

    # Edge inflow: land cell i → lake cell j. Do not credit lake→lake edges from
    # the discharge ghost field — inter-lake mass moves via spill supernodes.
    ds = np.asarray(graph.downstream_flat, dtype=np.int64).ravel()
    ocean = np.asarray(graph.ocean_mask, dtype=bool).ravel()
    n = int(ds.size)
    i = np.arange(n, dtype=np.int64)
    valid = (~ocean) & (ds >= 0)
    if not np.any(valid):
        return out
    ii = i[valid]
    jj = ds[valid]
    lid_j = env[jj]
    lid_i = env[ii]
    edge = (lid_j > 0) & (lid_i == 0) & (lid_j <= max_id)
    if np.any(edge):
        edge_sum = np.bincount(
            lid_j[edge],
            weights=q[ii[edge]],
            minlength=max_id + 1,
        )
        for lid in lake_ids:
            out[int(lid)] += float(edge_sum[int(lid)])
    return out


def _route_spill_along_path(
    *,
    graph: CylindricalFlowGraph,
    land_q_m3s: NDArray[np.floating],
    land_loss_m3s: NDArray[np.floating],
    remaining_bed_m3s: NDArray[np.floating],
    basin_envelope_id: NDArray[np.integer],
    start_row: int,
    start_col: int,
    pulse_m3s: float,
    source_lake_id: int,
) -> tuple[float, dict[int, float], float, str | None]:
    """Walk a spill pulse along D8 — O(path), not a full-grid re-route.

    Mutates ``land_q_m3s``, ``land_loss_m3s``, and ``remaining_bed_m3s`` in place.
    Returns ``(loss_m3s, delivered_to_lakes_m3s, terminal_export_m3s, terminal_kind)``.
    ``terminal_kind`` is ``\"ocean\"`` / ``\"boundary\"`` / ``\"closed\"`` when the
    residual must be ledger-declared (not sitting on a land ``q`` SINK cell);
    ``None`` means any residual is already in ``land_q`` for terminal probes.
    """
    rate = max(float(pulse_m3s), 0.0)
    if rate <= 0.0:
        return 0.0, {}, 0.0, None
    env = np.asarray(basin_envelope_id, dtype=np.int32)
    ocean = graph.ocean_mask
    ds = graph.downstream_flat
    w = graph.width
    h = graph.height
    q = np.asarray(land_q_m3s, dtype=np.float64)
    loss = np.asarray(land_loss_m3s, dtype=np.float64)
    bed = np.asarray(remaining_bed_m3s, dtype=np.float64)
    r, c = int(start_row), int(start_col)
    seen: set[int] = set()
    delivered: dict[int, float] = {}
    loss_total = 0.0
    src = int(source_lake_id)
    for _ in range(h * w + 1):
        if r < 0 or r >= h:
            return loss_total, delivered, rate, "boundary"
        c = c % w
        if ocean[r, c]:
            return loss_total, delivered, rate, "ocean"
        i = flat_index(r, c, w)
        if i in seen:
            break
        seen.add(i)
        lid = int(env[r, c])
        if lid > 0 and lid != src:
            delivered[lid] = delivered.get(lid, 0.0) + rate
            return loss_total, delivered, 0.0, None
        demand = max(float(bed[r, c]), 0.0)
        lost = demand if demand < rate else rate
        if lost > 0.0:
            loss[r, c] = float(loss[r, c]) + lost
            bed[r, c] = float(bed[r, c]) - lost
            rate -= lost
            loss_total += lost
        if rate <= 1e-18:
            return loss_total, delivered, 0.0, None
        if lid <= 0:
            q[r, c] = float(q[r, c]) + rate
        j = int(ds[i])
        if j < 0:
            if lid > 0:
                return loss_total, delivered, rate, _terminal_kind_at(graph, r, c)
            return loss_total, delivered, 0.0, None
        r, c = unravel(j, w)
    return loss_total, delivered, rate, _terminal_kind_at(graph, start_row, start_col)


def _terminal_kind_at(
    graph: CylindricalFlowGraph, row: int, col: int
) -> str:
    """Classify a cell as ocean / boundary / closed terminal."""
    h, w = graph.height, graph.width
    r, c = int(row), int(col) % w
    if r < 0 or r >= h:
        return "boundary"
    if graph.ocean_mask[r, c] or _touches_ocean(r, c, graph.ocean_mask):
        return "ocean"
    if r == 0 or r == h - 1:
        return "boundary"
    return "closed"


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
    spinup_years: int = 24,
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
        n_cells = int(np.count_nonzero(body))
        rec["envelope_cell_count"] = n_cells
        rec["envelope_area_km2"] = float(n_cells) * float(cell_area_km2)
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
    # Extra years for between-year fixed-point projection (§5.5). Short synthetic
    # fixtures (spinup_years < 8) must still demonstrate hard non-convergence (§5.6.10).
    fp_extra_years = 16 if years >= 8 else 0
    max_years = years + fp_extra_years
    used_years = years
    prev_lake_storage: dict[int, list[float] | None] = {lid: None for lid in runtimes}
    lake_periodic: dict[int, bool] = {lid: False for lid in runtimes}
    lake_used_years: dict[int, int] = {lid: years for lid in runtimes}
    prev_storage_signature: list[float] | None = None
    global_signature_periodic = False
    last_monthly_q = np.zeros((months, h, w), dtype=np.float64)
    last_monthly_loss = np.zeros((months, h, w), dtype=np.float64)
    last_ledgers: list[GlobalMonthLedger] = []
    max_lake_residual = 0.0
    max_global_residual = 0.0
    max_global_residual_rel = 0.0
    min_capture_ratio = 1.0
    last_capture_terminal_m3s = 0.0
    last_capture_full_m3s = 0.0
    last_unassigned_spill_m3 = 0.0
    fixed_point_boost_count = 0
    allow_fill_boost = years >= 8

    for year in range(max_years):
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

        month_open_mean_by_lake: dict[int, list[float]] = {lid: [] for lid in runtimes}
        month_ice_mean_by_lake: dict[int, list[float]] = {lid: [] for lid in runtimes}
        year_ledgers: list[GlobalMonthLedger] = []
        year_q = np.zeros((months, h, w), dtype=np.float64)
        year_loss = np.zeros((months, h, w), dtype=np.float64)

        for m in range(months):
            seconds = float(month_days(m)) * SECONDS_PER_DAY
            # Channel bed loss applies on land reaches only — not lake envelopes.
            bed_pot = np.asarray(bed_loss_potential_m3s, dtype=np.float64).copy()
            bed_pot[env > 0] = 0.0
            land_q, land_loss = effective_discharge_and_sink(
                graph,
                q_in[m],
                bed_pot,
                lake_id=env,
            )
            lake_id_list = list(runtimes.keys())
            land_inflow_m3s = _lake_land_inflow_m3s(
                graph=graph,
                land_q_m3s=land_q,
                local_runoff_m3s=q_in[m],
                basin_envelope_id=env,
                lake_ids=lake_id_list,
            )
            land_inflow_m3 = {
                lid: max(float(land_inflow_m3s.get(lid, 0.0)), 0.0) * seconds
                for lid in lake_id_list
            }
            # Terminal / envelope inflow available for capture-ratio diagnostics.
            terminal_inflow_m3s = 0.0
            for lid, rt in runtimes.items():
                # Legacy single-cell probe (audit comparison only).
                terminal_inflow_m3s += max(
                    float(land_q[rt.sink_row, rt.sink_col]), 0.0
                )
            captured_inflow_m3s = float(sum(land_inflow_m3s.values()))

            pending_lake_spill: dict[int, float] = {lid: 0.0 for lid in runtimes}
            remaining_bed = np.maximum(0.0, bed_pot - land_loss)
            remaining_bed[env > 0] = 0.0
            global_led = GlobalMonthLedger(month=m)
            global_led.land_local_runoff_m3 = float(np.sum(q_in[m] * seconds))
            global_led.land_bed_loss_m3 = float(np.sum(land_loss) * seconds)
            global_led.lake_inflow_available_m3 = float(captured_inflow_m3s * seconds)
            global_led.lake_inflow_accounted_m3 = float(sum(land_inflow_m3.values()))

            storage_snap: dict[int, float] = {}
            spill_snap: dict[int, float] = {}
            inflow_snap: dict[int, float] = {}
            evap_snap: dict[int, float] = {}
            wet_snap: dict[int, float] = {}
            unassigned_spill_m3 = 0.0
            declared_ocean_spill_m3 = 0.0
            declared_closed_spill_m3 = 0.0
            declared_boundary_spill_m3 = 0.0
            processed: set[int] = set()

            def _declare_terminal_kind(amount_m3: float, kind: str) -> None:
                nonlocal declared_ocean_spill_m3, declared_closed_spill_m3
                nonlocal declared_boundary_spill_m3
                if amount_m3 <= 0.0:
                    return
                if kind == "ocean":
                    declared_ocean_spill_m3 += amount_m3
                elif kind == "boundary":
                    declared_boundary_spill_m3 += amount_m3
                else:
                    declared_closed_spill_m3 += amount_m3

            def _declare_terminal(amount_m3: float, row: int, col: int) -> None:
                _declare_terminal_kind(amount_m3, _terminal_kind_at(graph, row, col))

            def _absorb_into_processed(down: int, amount_m3: float) -> float:
                """Credit spill into an already-stepped lake; return overflow spill."""
                if amount_m3 <= 0.0 or down not in runtimes:
                    return max(amount_m3, 0.0)
                rt_d = runtimes[down]
                room = max(float(rt_d.avh.v_spill) - float(rt_d.volume_m3), 0.0)
                take = min(float(amount_m3), room)
                rt_d.volume_m3 = float(rt_d.volume_m3) + take
                storage_snap[down] = rt_d.volume_m3
                # Late inflow is a source for diagnostics on the receiving lake.
                inflow_snap[down] = float(inflow_snap.get(down, 0.0)) + take
                return max(float(amount_m3) - take, 0.0)

            def _emit_spill(from_lid: int, spill_m3: float, depth: int = 0) -> None:
                nonlocal unassigned_spill_m3
                if spill_m3 <= 1e-12:
                    return
                if depth > len(runtimes) + 2:
                    # Pathological cascade — last resort terminal at outlet.
                    sn_x = condensed.supernodes[from_lid]
                    _declare_terminal(
                        spill_m3, int(sn_x.outlet_row), int(sn_x.outlet_col)
                    )
                    return
                sn_e = condensed.supernodes[from_lid]
                down = int(sn_e.downstream_lake_id)
                # Immediate lake→lake (no land reach).
                if down > 0 and (
                    sn_e.spill_target_row is None
                    or int(env[int(sn_e.spill_target_row), int(sn_e.spill_target_col)])
                    == down
                ):
                    if down not in processed:
                        pending_lake_spill[down] = (
                            pending_lake_spill.get(down, 0.0) + spill_m3
                        )
                    else:
                        overflow = _absorb_into_processed(down, spill_m3)
                        if overflow > 0.0:
                            _emit_spill(down, overflow, depth + 1)
                    return

                # Land-mediated (or ocean-mouth with no land cell).
                start_r = sn_e.spill_target_row
                start_c = sn_e.spill_target_col
                if start_r is None or start_c is None:
                    # Outlet itself is a graph SINK (ocean mouth / closed pit).
                    _declare_terminal(
                        spill_m3, int(sn_e.outlet_row), int(sn_e.outlet_col)
                    )
                    return

                pulse_rate = spill_m3 / max(seconds, 1.0)
                spill_loss_rate, delivered, terminal_rate, term_kind = (
                    _route_spill_along_path(
                        graph=graph,
                        land_q_m3s=land_q,
                        land_loss_m3s=land_loss,
                        remaining_bed_m3s=remaining_bed,
                        basin_envelope_id=env,
                        start_row=int(start_r),
                        start_col=int(start_c),
                        pulse_m3s=pulse_rate,
                        source_lake_id=int(from_lid),
                    )
                )
                global_led.land_bed_loss_m3 += float(spill_loss_rate) * seconds
                for down_i, rate in delivered.items():
                    if int(down_i) == int(from_lid) or rate <= 0.0:
                        continue
                    got = float(rate) * seconds
                    if int(down_i) not in processed:
                        pending_lake_spill[int(down_i)] = (
                            pending_lake_spill.get(int(down_i), 0.0) + got
                        )
                    else:
                        overflow = _absorb_into_processed(int(down_i), got)
                        if overflow > 0.0:
                            _emit_spill(int(down_i), overflow, depth + 1)
                if terminal_rate > 0.0 and term_kind is not None:
                    _declare_terminal_kind(
                        float(terminal_rate) * seconds, term_kind
                    )
                # Residual pulse mass sits on land_q SINK cells (picked up by
                # land_terminal_exports) or was declared above — never unassigned.

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
                processed.add(lid)
                global_led.lake_ledgers.append(led)
                max_lake_residual = max(max_lake_residual, abs(led.residual_m3()))
                storage_snap[lid] = volume
                spill_snap[lid] = spill
                inflow_snap[lid] = led.sources_m3()
                evap_snap[lid] = led.open_water_evaporation_m3 + led.seepage_m3
                wet_snap[lid] = wet_area / 1e6

                if spill > 0.0:
                    _emit_spill(int(lid), float(spill))

                frozen = float(np.mean(temp_m[m][body])) < float(frozen_temp_c)
                # Scalar means only during spin-up (full HxW per lake/month OOMs Atlas).
                n_body = int(np.count_nonzero(body))
                envelope_m2 = float(n_body) * area_m2_cell
                mean_frac = (
                    float(wet_area / envelope_m2) if envelope_m2 > 0.0 else 0.0
                )
                if frozen:
                    month_ice_mean_by_lake[lid].append(mean_frac)
                    month_open_mean_by_lake[lid].append(0.0)
                else:
                    month_open_mean_by_lake[lid].append(mean_frac)
                    month_ice_mean_by_lake[lid].append(0.0)

            year_q[m] = land_q
            year_loss[m] = land_loss
            ocean_x, closed_x, boundary_x = land_terminal_exports_m3s(
                graph, land_q, env
            )
            global_led.ocean_export_m3 = (
                float(ocean_x) * seconds + declared_ocean_spill_m3
            )
            global_led.closed_retention_m3 = (
                float(closed_x) * seconds + declared_closed_spill_m3
            )
            global_led.boundary_export_m3 = (
                float(boundary_x) * seconds + declared_boundary_spill_m3
            )
            global_led.land_downstream_release_m3 = (
                global_led.ocean_export_m3
                + global_led.closed_retention_m3
                + global_led.boundary_export_m3
            )
            global_led.unassigned_spill_m3 = float(unassigned_spill_m3)
            global_led.lake_inflow_accounted_m3 = float(sum(land_inflow_m3.values()))
            year_ledgers.append(global_led)
            max_global_residual = max(
                max_global_residual, abs(global_led.residual_m3())
            )
            max_global_residual_rel = max(
                max_global_residual_rel, global_led.residual_rel()
            )
            min_capture_ratio = min(
                min_capture_ratio, global_led.lake_inflow_capture_ratio()
            )

            for lid, rt in runtimes.items():
                rec = lake_rec_by_id[lid]
                rec["storage_m3"].append(float(storage_snap.get(lid, rt.volume_m3)))
                z_w, _a = rt.avh.lookup(rt.volume_m3)
                rec["level_m"].append(max(z_w - rt.avh.z_floor, 0.0))
                rec["wet_area_km2"].append(float(wet_snap.get(lid, 0.0)))
                rec["spill_m3"].append(float(spill_snap.get(lid, 0.0)))
                rec["inflow_m3"].append(float(inflow_snap.get(lid, 0.0)))
                rec["evap_loss_m3"].append(float(evap_snap.get(lid, 0.0)))

            # Persist last-month capture diagnostics on the year loop.
            last_capture_terminal_m3s = terminal_inflow_m3s
            last_capture_full_m3s = captured_inflow_m3s
            last_unassigned_spill_m3 = unassigned_spill_m3

        for lid in runtimes:
            rec = lake_rec_by_id[lid]
            open_means = month_open_mean_by_lake.get(lid) or []
            ice_means = month_ice_mean_by_lake.get(lid) or []
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
            rec["open_water_fraction_monthly"] = [float(v) for v in open_means]
            rec["lake_ice_fraction_monthly"] = [float(v) for v in ice_means]
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
                if storage_series_converged(
                    prev,
                    storage_series,
                    rel_tol=float(spinup_rel_tol),
                    v_spill_m3=float(runtimes[lid].avh.v_spill),
                ):
                    lake_periodic[lid] = True
                    lake_used_years[lid] = year + 1
                else:
                    lake_periodic[lid] = False
                    lake_used_years[lid] = year + 1
                    # §5.5: phase-invariant mean reseed only — never jump toward
                    # V_spill (that published ~188 inland seas on Atlas 183716).
                    if allow_fill_boost:
                        mean_c = float(np.mean(storage_series))
                        v_spill = float(runtimes[lid].avh.v_spill)
                        seeded = float(np.clip(mean_c, 0.0, v_spill))
                        if abs(seeded - float(runtimes[lid].volume_m3)) > 1.0:
                            runtimes[lid].volume_m3 = seeded
                            rec["storage_fixed_point_attempted"] = True
                            rec["storage_limiting_process"] = "mean_cycle"
                            fixed_point_boost_count += 1
            prev_lake_storage[lid] = list(storage_series)

        sig = [float(runtimes[lid].volume_m3) for lid in sorted(runtimes)]
        if prev_storage_signature is not None and prev_storage_signature:
            # Global signature uses mean spill capacity as the absolute scale.
            mean_v_spill = float(
                np.mean([float(runtimes[lid].avh.v_spill) for lid in runtimes])
            ) if runtimes else 1.0
            if storage_series_converged(
                prev_storage_signature,
                sig,
                rel_tol=float(spinup_rel_tol),
                v_spill_m3=mean_v_spill,
            ):
                global_signature_periodic = True
        prev_storage_signature = sig
        last_monthly_q = year_q
        last_monthly_loss = year_loss
        last_ledgers = year_ledgers
        if runtimes and all(lake_periodic[lid] for lid in runtimes):
            used_years = year + 1
            break
    else:
        used_years = max_years

    # §5.5 post-spinup annual fixed-point on frozen last-year inflows.
    # Accept only bounded mean-cycle / natural spill-rim solutions — never
    # promote empty→spill runaway fills into the published liquid product.
    fixed_point_solved = 0
    if allow_fill_boost and runtimes:
        for lid in condensed.topo_order:
            if lid not in runtimes or lake_periodic.get(lid):
                continue
            rec = lake_rec_by_id[lid]
            rt = runtimes[lid]
            inflow = list(rec.get("inflow_m3") or [])
            if len(inflow) < months:
                continue
            precip_mm: list[float] | None = None
            if precip_m is not None:
                body = rt.body
                precip_mm = [
                    float(np.mean(precip_m[m][body])) * float(precip_scale_mm)
                    if np.any(body)
                    else 0.0
                    for m in range(months)
                ]
            v_star, accepted, limit, series = _solve_annual_storage_fixed_point(
                rt=rt,
                inflow_m3=inflow,
                temp_m=temp_m,
                precip_mm_monthly=precip_mm,
                frozen_temp_c=float(frozen_temp_c),
                months=months,
                rel_tol=float(spinup_rel_tol),
            )
            rec["storage_fixed_point_attempted"] = True
            rec["storage_limiting_process"] = limit
            fixed_point_boost_count += 1
            if not accepted:
                continue
            rt.volume_m3 = float(v_star)
            # Refresh published monthly series from the accepted cycle.
            rec["storage_m3"] = [float(v) for v in series]
            levels: list[float] = []
            wet: list[float] = []
            for v in series:
                z, area_m2 = rt.avh.lookup(float(v))
                levels.append(float(z - rt.avh.z_floor))
                wet.append(float(area_m2) / 1e6)
            rec["level_m"] = levels
            rec["wet_area_km2"] = wet
            rec["mean_wet_area_km2"] = float(np.mean(wet)) if wet else 0.0
            rec["months_wet"] = int(sum(1 for v in wet if v > _WET_FRAC_EPS))
            lake_periodic[lid] = True
            rec["storage_periodic"] = True
            rec["convergence_state"] = "periodic"
            fixed_point_solved += 1
            lake_used_years[lid] = int(used_years)

    # Reclass and periodic liquid policy (same as apply_basin_storage).
    stepped = 0
    periodic_count = 0
    liquid_count = 0
    liquid_periodic_count = 0
    withheld_count = 0
    withheld_wet_km2 = 0.0
    liquid_wet_km2 = 0.0
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
            wet_km2 = float(rec.get("mean_wet_area_km2") or 0.0)
            liquid_wet_km2 += wet_km2
            if lake_is_periodic:
                liquid_periodic_count += 1
            else:
                rec["storage_unstable"] = True
                rec["water_body_id"] = 0
                withheld_count += 1
                withheld_wet_km2 += wet_km2
                apply_lake_identity(rec)

    water_present_monthly = np.zeros((months, h, w), dtype=np.float64)
    open_water_monthly = np.zeros((months, h, w), dtype=np.float64)
    lake_ice_monthly = np.zeros((months, h, w), dtype=np.float64)
    for lid in runtimes:
        rec = lake_rec_by_id[lid]
        if bool(rec.get("storage_unstable")):
            continue
        rt = runtimes[lid]
        body = rt.body
        storage_series = list(rec.get("storage_m3") or [])
        if len(storage_series) < months:
            continue
        for mm in range(months):
            frac = rt.avh.raster_wet_fraction(float(storage_series[mm]), (h, w))
            frozen = float(np.mean(temp_m[mm][body])) < float(frozen_temp_c)
            if frozen:
                lake_ice_monthly[mm] += frac
            else:
                open_water_monthly[mm] += frac
            water_present_monthly[mm] += frac

    water_present_monthly = np.clip(water_present_monthly, 0.0, 1.0)
    open_water_monthly = np.clip(open_water_monthly, 0.0, 1.0)
    lake_ice_monthly = np.clip(lake_ice_monthly, 0.0, 1.0)
    water_mean = water_present_monthly.mean(axis=0) if months else np.zeros((h, w), dtype=np.float64)

    withheld_share = (
        float(withheld_wet_km2) / float(liquid_wet_km2) if liquid_wet_km2 > 1e-12 else 0.0
    )
    all_liquid_failed = bool(liquid_count > 0 and liquid_periodic_count == 0)
    material_withheld = bool(
        withheld_count > 0
        and (all_liquid_failed or withheld_share > float(MATERIAL_WITHHELD_WET_SHARE))
    )

    ledger_diag = {
        "hydrology_mass_balance_max_lake_residual_m3": float(max_lake_residual),
        "hydrology_mass_balance_max_global_residual_m3": float(max_global_residual),
        "hydrology_mass_balance_max_global_residual_rel": float(max_global_residual_rel),
        "hydrology_mass_balance_ok": bool(
            max_lake_residual <= 1.0
            and (
                max_global_residual <= 1.0
                or max_global_residual_rel <= 1e-6
            )
        ),
        "global_ledger_months": [g.summary() for g in last_ledgers],
        "lake_inflow_single_sink_m3s": float(last_capture_terminal_m3s),
        "lake_inflow_all_edges_m3s": float(last_capture_full_m3s),
        "lake_inflow_capture_ratio_vs_single_sink": (
            float(last_capture_full_m3s) / float(last_capture_terminal_m3s)
            if last_capture_terminal_m3s > 1e-12
            else (1.0 if last_capture_full_m3s <= 1e-12 else float("inf"))
        ),
        "lake_inflow_capture_ratio": float(min_capture_ratio),
        "lake_inflow_capture_ok": bool(
            min_capture_ratio >= float(LAKE_INFLOW_CAPTURE_RATIO_MIN)
        ),
        "unassigned_spill_m3": float(last_unassigned_spill_m3),
        "unassigned_spill_ok": bool(last_unassigned_spill_m3 <= 1e-3),
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
        "basin_storage_spinup_years_cap": int(max_years),
        "basin_storage_fixed_point_boost_events": int(fixed_point_boost_count),
        "basin_storage_fixed_point_solved_count": int(fixed_point_solved),
        "basin_storage_global_signature_periodic": bool(global_signature_periodic),
        "basin_storage_periodic_count": periodic_count,
        "basin_storage_liquid_count": liquid_count,
        "basin_storage_liquid_periodic_count": liquid_periodic_count,
        "basin_storage_nonperiodic_liquid_withheld_count": withheld_count,
        "basin_storage_nonperiodic_liquid_published_count": 0,
        "basin_storage_withheld_wet_area_km2": float(withheld_wet_km2),
        "basin_storage_liquid_wet_area_km2": float(liquid_wet_km2),
        "basin_storage_withheld_wet_area_share": float(withheld_share),
        "basin_storage_material_withheld": bool(material_withheld),
        "basin_storage_curve": str(storage_curve),
        "lake_fractions_are_monthly": True,
        "lake_routing_algorithm": "pc1_condensed_supernode_v1",
        **condensed.diagnostics,
        **ledger_diag,
    }
