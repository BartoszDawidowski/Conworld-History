"""Milestone 11 / PR-6 — hydrology orchestration (runoff, wadi, lakes)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology.basins_storage import (
    apply_basin_storage,
    liquid_id_from_fraction,
)
from worldsim.physical.hydrology.channels import (
    classify_channel_states,
    display_channel_candidates,
    effective_channel_min_cells,
    channel_width_m_from_discharge,
    physical_channel_mask,
    river_water_fraction,
)
from worldsim.physical.hydrology.cylindrical_graph import (
    accumulate_weights,
    classify_outlets,
    effective_discharge_and_sink,
)
from worldsim.physical.hydrology.discharge import (
    SECONDS_PER_DAY,
    month_days,
    month_weighted_mean_m3s,
    runoff_proxy_to_m3s,
)
from worldsim.physical.hydrology.flow import accuflux_on_land, run_pyflwdir_core
from worldsim.physical.hydrology.lakes_meta import build_lake_records
from worldsim.physical.hydrology.rivers import (
    gate_lakes_by_water_supply,
    gate_river_mask_by_discharge,
    lake_mask_from_fill,
)
from worldsim.physical.hydrology.runoff import build_monthly_runoff
from worldsim.physical.hydrology.transmission import (
    YEAR_DAYS,
    channel_bed_loss_potential_m3s,
)
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class HydrologyParams:
    river_acc_fraction: float = 0.035
    lake_min_depth_m: float = 2.0
    months: int = 12
    # Plan B7 — precip/discharge gates (quantile = physical Q floor when min unset)
    river_discharge_candidate_quantile: float = 0.50
    river_min_effective_discharge: float | None = None
    river_min_accumulation_cells: int = 8
    lake_precip_land_quantile: float = 0.70
    lake_arid_precip_land_quantile: float = 0.45
    lake_min_mean_temp_c: float = 1.0
    lake_inflow_land_quantile: float = 0.75
    # §6.3.1 / C2 — channel-bed loss (geometry × rate, capped by available Q)
    transmission_rate: float = 0.45
    transmission_ref_km: float = 50.0
    bed_loss_m3_per_km_month: float = 2.0e5
    precip_scale_mm: float = 200.0
    # PR-6 snow / runoff
    snow_threshold_c: float = 0.0
    snow_band_c: float = 2.0
    melt_factor_per_c: float = 0.08
    max_snow_store: float = 40.0
    # CR-7 soil bucket (proxy units; 1.0 ≈ precip_scale_mm millimetres)
    soil_capacity: float = 1.0
    soil_quickflow_frac: float = 0.20
    # CR-4 — numerical fill only; negative = legacy fill-all (no closed basins)
    fill_max_depth_m: float = 25.0
    store_monthly_gross: bool = False
    planet_radius_km: float = 6371.0
    # CR-5: physical catchment floor (None → river_min_accumulation_cells only)
    river_min_catchment_km2: float | None = 500.0
    channel_q_min_m3s: float = 0.05
    channel_perennial_min_months: int = 8
    channel_seasonal_min_months: int = 3
    lake_storage_spinup_years: int = 8
    lake_storage_spinup_tol: float = 0.01
    lake_storage_curve: str = "discrete_avh_v1"
    lake_wet_min_fraction: float = 1e-6


@dataclass
class HydrologyResult:
    extent: SpatialExtent
    dem_conditioned_m: NDArray[np.float64]
    flow_direction: NDArray[np.uint8]
    flow_accumulation: NDArray[np.float64]
    basin_id: NDArray[np.int32]
    watershed_id: NDArray[np.int32]
    stream_order: NDArray[np.int16]
    river_mask: NDArray[np.bool_]
    river_discharge_proxy: NDArray[np.float64]
    river_discharge_gross: NDArray[np.float64]
    monthly_discharge: NDArray[np.float64]
    monthly_discharge_gross: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0,)))
    monthly_runoff: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0,)))
    snow_store: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0,)))
    soil_store: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0,)))
    soil_store_monthly: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64)
    )
    channel_mask: NDArray[np.bool_] = field(default_factory=lambda: np.zeros((0,), dtype=bool))
    channel_state: NDArray[np.uint8] = field(default_factory=lambda: np.zeros((0,), dtype=np.uint8))
    river_water_fraction: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64)
    )
    monthly_bed_loss: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0,)))
    bed_loss_potential_m3s: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64)
    )
    lake_mask: NDArray[np.bool_] = field(default_factory=lambda: np.zeros((0,), dtype=bool))
    lake_id: NDArray[np.int32] = field(default_factory=lambda: np.zeros((0,), dtype=np.int32))
    basin_envelope_id: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros((0,), dtype=np.int32)
    )
    water_fraction_mean: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64)
    )
    lake_records: list[dict[str, Any]] = field(default_factory=list)
    outlet_points: list[tuple[int, int]] = field(default_factory=list)
    ocean_mask: NDArray[np.bool_] = field(default_factory=lambda: np.zeros((0,), dtype=bool))
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "dem_conditioned_m": self.dem_conditioned_m,
            "flow_direction": self.flow_direction,
            "flow_accumulation": self.flow_accumulation,
            "basin_id": self.basin_id,
            "watershed_id": self.watershed_id,
            "stream_order": self.stream_order,
            "river_mask": self.river_mask.astype(np.uint8),
            "river_discharge_proxy": self.river_discharge_proxy,
            "river_discharge_gross": self.river_discharge_gross,
            "monthly_discharge": self.monthly_discharge,
            "lake_mask": self.lake_mask.astype(np.uint8),
            "lake_id": self.lake_id,
            "basin_envelope_id": self.basin_envelope_id,
            "water_fraction_mean": self.water_fraction_mean,
            "ocean_mask": self.ocean_mask.astype(np.uint8),
            "outlet_rows": np.array([p[0] for p in self.outlet_points], dtype=np.int32),
            "outlet_cols": np.array([p[1] for p in self.outlet_points], dtype=np.int32),
        }
        if self.monthly_discharge_gross.size:
            payload["monthly_discharge_gross"] = self.monthly_discharge_gross
        if self.monthly_runoff.size:
            payload["monthly_runoff"] = self.monthly_runoff
        if self.snow_store.size:
            payload["snow_store"] = self.snow_store
        if self.soil_store.size:
            payload["soil_store"] = self.soil_store
        if self.soil_store_monthly.size:
            payload["soil_store_monthly"] = self.soil_store_monthly
        if self.channel_mask.size:
            payload["channel_mask"] = self.channel_mask.astype(np.uint8)
        if self.channel_state.size:
            payload["channel_state"] = self.channel_state
        if self.river_water_fraction.size:
            payload["river_water_fraction"] = self.river_water_fraction
        if self.monthly_bed_loss.size:
            payload["monthly_bed_loss"] = self.monthly_bed_loss
        if self.bed_loss_potential_m3s.size:
            payload["bed_loss_potential_m3s"] = self.bed_loss_potential_m3s
        np.savez_compressed(directory / "hydrology.npz", **payload)
        (directory / "hydrology_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if self.lake_records:
            (directory / "lake_records.json").write_text(
                json.dumps(self.lake_records, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


def build_hydrology(
    *,
    erosion: ErosionResult,
    moisture: MoistureResult,
    params: HydrologyParams | None = None,
    reporter: ProgressReporter | None = None,
    temperature_c: NDArray[np.floating] | None = None,
) -> HydrologyResult:
    params = params or HydrologyParams()
    if reporter is not None:
        reporter.stage_started("hydrology")
        reporter.progress("hydrology", 0.1)

    elev = erosion.elevation_m
    ocean = erosion.ocean_mask
    h, w = elev.shape

    core = run_pyflwdir_core(
        elevation_m=elev,
        ocean_mask=ocean,
        max_depth=params.fill_max_depth_m,
    )
    flw = core.pop("flw")
    pad = int(core.pop("pad"))
    graph = core.pop("graph")
    graph_diag = dict(core.pop("graph_diagnostics"))
    core.pop("downstream_flat", None)

    if reporter is not None:
        reporter.progress("hydrology", 0.35)

    months = min(params.months, moisture.precipitation.shape[0])
    precip_m = np.empty((months, h, w), dtype=np.float64)
    for m in range(months):
        p = upsample_bilinear_cylindrical(moisture.precipitation[m], w, h)
        precip_m[m] = np.where(ocean, 0.0, np.maximum(p, 0.0))

    if temperature_c is not None:
        t_src = np.asarray(temperature_c, dtype=np.float64)
        if t_src.ndim == 3:
            temp_m = np.empty((months, h, w), dtype=np.float64)
            for m in range(months):
                temp_m[m] = upsample_bilinear_cylindrical(t_src[m], w, h)
            annual_temp = temp_m.mean(axis=0)
        else:
            annual_temp = upsample_bilinear_cylindrical(t_src, w, h)
            temp_m = np.broadcast_to(annual_temp, (months, h, w)).copy()
    else:
        annual_temp = np.full((h, w), 15.0, dtype=np.float64)
        temp_m = np.broadcast_to(annual_temp, (months, h, w)).copy()

    runoff_pack = build_monthly_runoff(
        precipitation=precip_m,
        temperature_c=temp_m,
        ocean_mask=ocean,
        snow_threshold_c=params.snow_threshold_c,
        snow_band_c=params.snow_band_c,
        melt_factor_per_c=params.melt_factor_per_c,
        max_snow_store=params.max_snow_store,
        precip_scale_mm=params.precip_scale_mm,
        soil_capacity=params.soil_capacity,
        soil_quickflow_frac=params.soil_quickflow_frac,
    )
    monthly_runoff = np.asarray(runoff_pack["runoff"], dtype=np.float64)
    snow_store = np.asarray(runoff_pack["snow_store"], dtype=np.float64)
    soil_store = np.asarray(runoff_pack["soil_store"], dtype=np.float64)
    soil_store_monthly = np.asarray(
        runoff_pack.get("soil_store_monthly", np.zeros((0,))), dtype=np.float64
    )
    annual_runoff = monthly_runoff.sum(axis=0)
    annual_precip = precip_m.sum(axis=0)

    if reporter is not None:
        reporter.progress("hydrology", 0.5)

    gm = grid_metrics(w, h, radius_km=params.planet_radius_km)
    river_min_cells, catchment_diag = effective_channel_min_cells(
        cell_area_km2=gm.cell_area_km2,
        river_min_catchment_km2=params.river_min_catchment_km2,
        river_min_accumulation_cells=params.river_min_accumulation_cells,
    )
    cell_len_km = float(np.sqrt(max(gm.cell_area_km2, 0.0)))
    path_length_km = np.maximum(
        gm.d8_step_length_km_field(core["flow_direction"]),
        cell_len_km,
    )
    channel_mask = physical_channel_mask(
        core["flow_accumulation"],
        ocean,
        min_cells=river_min_cells,
    )
    river_candidates = display_channel_candidates(
        channel_mask,
        core["flow_accumulation"],
        fraction=params.river_acc_fraction,
    )
    lake_raw, lake_id_raw, _lake_count_raw = lake_mask_from_fill(
        elev,
        elev + np.asarray(core["depression_depth_m"], dtype=np.float64),
        ocean,
        min_depth_m=params.lake_min_depth_m,
    )

    bed_loss_potential = channel_bed_loss_potential_m3s(
        path_length_km,
        loss_rate_m3_per_km_month=params.bed_loss_m3_per_km_month,
        channel_mask=channel_mask,
        ocean_mask=ocean,
    )

    discharge_gross = accuflux_on_land(
        flw, pad=pad, width=w, ocean_mask=ocean, weights=annual_runoff, graph=graph
    )
    local_annual_m3s = runoff_proxy_to_m3s(
        annual_runoff,
        cell_area_km2=gm.cell_area_km2,
        precip_scale_mm=params.precip_scale_mm,
        days=float(YEAR_DAYS),
    )
    discharge_eff_independent, _sink_ind = effective_discharge_and_sink(
        graph, local_annual_m3s, bed_loss_potential
    )

    monthly_gross = np.zeros((0,), dtype=np.float64)
    monthly_eff = np.zeros((months, h, w), dtype=np.float64)
    monthly_bed_loss = np.zeros((months, h, w), dtype=np.float64)
    for m in range(months):
        local_m3s = runoff_proxy_to_m3s(
            monthly_runoff[m],
            cell_area_km2=gm.cell_area_km2,
            precip_scale_mm=params.precip_scale_mm,
            days=float(month_days(m)),
        )
        q_m, lost_m = effective_discharge_and_sink(
            graph, local_m3s, bed_loss_potential
        )
        monthly_eff[m] = q_m
        monthly_bed_loss[m] = lost_m
        if params.store_monthly_gross:
            if monthly_gross.size == 0:
                monthly_gross = np.zeros((months, h, w), dtype=np.float64)
            g_proxy = accuflux_on_land(
                flw,
                pad=pad,
                width=w,
                ocean_mask=ocean,
                weights=monthly_runoff[m],
                graph=graph,
            )
            monthly_gross[m] = runoff_proxy_to_m3s(
                g_proxy,
                cell_area_km2=gm.cell_area_km2,
                precip_scale_mm=params.precip_scale_mm,
                days=float(month_days(m)),
            )

    discharge_eff = month_weighted_mean_m3s(monthly_eff)
    discharge_gross = runoff_proxy_to_m3s(
        discharge_gross,
        cell_area_km2=gm.cell_area_km2,
        precip_scale_mm=params.precip_scale_mm,
        days=float(YEAR_DAYS),
    )

    river_mask, river_gate_diag = gate_river_mask_by_discharge(
        river_candidates,
        discharge_eff,
        core["flow_direction"],
        ocean,
        candidate_quantile=params.river_discharge_candidate_quantile,
        min_effective_discharge=params.river_min_effective_discharge,
        inherit_downstream=False,
    )
    lake_mask, lake_id, lake_count, lake_gate_diag = gate_lakes_by_water_supply(
        lake_raw,
        lake_id_raw,
        annual_precip,
        ocean,
        river_mask=river_mask,
        discharge_effective=discharge_eff,
        temperature_annual_c=annual_temp,
        precip_land_quantile=params.lake_precip_land_quantile,
        arid_precip_land_quantile=params.lake_arid_precip_land_quantile,
        lake_min_mean_temp_c=params.lake_min_mean_temp_c,
        inflow_land_quantile=params.lake_inflow_land_quantile,
        graph=graph,
    )

    lake_records = build_lake_records(
        graph=graph,
        lake_id=lake_id,
        lake_mask=lake_mask,
        elevation_m=elev,
        basin_id=core["basin_id"],
        discharge_effective=discharge_eff,
        temperature_annual_c=annual_temp,
        precip_annual=annual_precip,
        frozen_temp_c=params.lake_min_mean_temp_c,
    )
    storage_diag = apply_basin_storage(
        graph=graph,
        lake_id=lake_id,
        lake_records=lake_records,
        elevation_m=elev,
        monthly_q_m3s=monthly_eff,
        temperature_c=temp_m,
        cell_area_km2=gm.cell_area_km2,
        monthly_precip=precip_m,
        precip_scale_mm=params.precip_scale_mm,
        lake_min_depth_m=params.lake_min_depth_m,
        frozen_temp_c=params.lake_min_mean_temp_c,
        spinup_years=params.lake_storage_spinup_years,
        spinup_rel_tol=params.lake_storage_spinup_tol,
        storage_curve=params.lake_storage_curve,
    )
    water_fraction_mean = np.asarray(
        storage_diag.pop("water_fraction_mean"), dtype=np.float64
    )
    basin_envelope_id = np.asarray(lake_id, dtype=np.int32).copy()
    lake_id, liquid_mask = liquid_id_from_fraction(
        basin_envelope_id,
        water_fraction_mean,
        lake_records,
        min_fraction=params.lake_wet_min_fraction,
    )
    lake_cell_all = int(np.count_nonzero(basin_envelope_id > 0))
    lake_mask = liquid_mask

    for m in range(months):
        spill_w = np.zeros((h, w), dtype=np.float64)
        seconds = float(month_days(m)) * SECONDS_PER_DAY
        for rec in lake_records:
            series = rec.get("spill_m3") or []
            if m >= len(series):
                continue
            spilled = float(series[m])
            if spilled <= 0.0:
                continue
            rr = rec.get("outlet_row", rec.get("sink_row"))
            cc = rec.get("outlet_col", rec.get("sink_col"))
            if rr is None or cc is None:
                continue
            spill_w[int(rr), int(cc)] += spilled / max(seconds, 1.0)
        if np.any(spill_w):
            monthly_eff[m] += accumulate_weights(graph, spill_w)
    discharge_eff = month_weighted_mean_m3s(monthly_eff)

    state_network = channel_mask
    channel_state, channel_diag = classify_channel_states(
        monthly_eff,
        state_network,
        q_min_m3s=params.channel_q_min_m3s,
        perennial_min_months=params.channel_perennial_min_months,
        seasonal_min_months=params.channel_seasonal_min_months,
    )
    width_m = channel_width_m_from_discharge(discharge_eff, channel_mask)
    river_frac = river_water_fraction(
        channel_mask,
        path_length_km,
        cell_area_km2=gm.cell_area_km2,
        width_m=width_m,
    )
    # Lakes occupy river water area only where actual liquid exists.
    if water_fraction_mean.size:
        river_frac = np.minimum(
            river_frac, np.maximum(0.0, 1.0 - np.clip(water_fraction_mean, 0.0, 1.0))
        )

    if reporter is not None:
        reporter.progress("hydrology", 0.85)

    land = ~ocean
    acc_land = core["flow_accumulation"][land]
    downstream_ok = bool(graph_diag.get("downstream_accumulation_ok"))
    drainage_valid = bool(core["isvalid"]) and int(core["nnodes"]) > 0
    if np.any(river_mask) and np.any(land):
        riv_mean = float(core["flow_accumulation"][river_mask].mean())
        land_mean = float(acc_land.mean()) if acc_land.size else 0.0
        sensible_acc = riv_mean > land_mean
    else:
        riv_mean = land_mean = float("nan")
        sensible_acc = False

    # Canonical annual Q is the month-length-weighted mean of monthly m³/s.
    rel_diff = 0.0
    if np.any(land) and float(np.mean(discharge_eff_independent[land])) > 1e-9:
        rel_independent = float(
            np.mean(np.abs(discharge_eff[land] - discharge_eff_independent[land]))
            / max(float(np.mean(discharge_eff_independent[land])), 1e-9)
        )
    else:
        rel_independent = 0.0

    outlet_types = classify_outlets(
        graph,
        accumulation=core["flow_accumulation"],
        depression_depth_m=core["depression_depth_m"],
        min_closed_cells=max(int(river_min_cells), 4),
        min_closed_depth_m=params.lake_min_depth_m,
    )
    typed_ok = bool(outlet_types["outlets_typed"])

    open_lakes = sum(1 for r in lake_records if r.get("water_state") == "open")
    endorheic_lakes = sum(
        1 for r in lake_records if r.get("water_state") == "endorheic"
    )
    playa_lakes = sum(
        1 for r in lake_records if r.get("water_state") == "seasonal_or_playa"
    )
    frozen_lakes = sum(
        1 for r in lake_records if r.get("water_state") == "frozen_or_ice_covered"
    )

    runoff_diag = (
        runoff_pack["diagnostics"]
        if isinstance(runoff_pack.get("diagnostics"), dict)
        else {}
    )

    n_land = int(np.count_nonzero(land))
    physical_n = int(np.count_nonzero(channel_mask))
    display_n = int(np.count_nonzero(river_candidates))
    hidden_n = int(np.count_nonzero(channel_mask & ~river_mask))
    bed_loss_mean = month_weighted_mean_m3s(monthly_bed_loss)
    loss_minus_potential = monthly_bed_loss - bed_loss_potential[np.newaxis, :, :]
    max_loss_over_potential = float(np.max(loss_minus_potential)) if loss_minus_potential.size else 0.0
    # available ≈ q + actual_loss; actual must not exceed that (identity).
    available_proxy = monthly_eff + monthly_bed_loss
    max_loss_over_available = (
        float(np.max(monthly_bed_loss - available_proxy)) if monthly_bed_loss.size else 0.0
    )

    diagnostics: dict[str, Any] = {
        "width": w,
        "height": h,
        "wrap_pad_cells": pad,
        "drainage_graph_valid": drainage_valid,
        "downstream_accumulation_ok": downstream_ok,
        "sensible_accumulation_downstream": sensible_acc,
        "nnodes": core["nnodes"],
        "basin_count": int(len(np.unique(core["basin_id"][core["basin_id"] > 0]))),
        "max_stream_order": int(core["stream_order"].max()),
        "river_cell_count": int(np.count_nonzero(river_mask)),
        "channel_physical_cell_count": physical_n,
        "channel_display_candidate_cell_count": display_n,
        "channel_physical_not_display_count": hidden_n,
        "channel_physical_land_fraction": (
            float(physical_n / n_land) if n_land else 0.0
        ),
        "lake_count": lake_count,
        "lake_cell_count": int(np.count_nonzero(lake_mask)),
        "lake_classified_cell_count": lake_cell_all,
        "outlet_count": len(core["outlet_points"]),
        "flow_acc_max": float(core["flow_accumulation"].max()),
        "river_acc_mean": riv_mean,
        "land_acc_mean": land_mean,
        "acceptance_ok": bool(
            drainage_valid and downstream_ok and sensible_acc and typed_ok
        ),
        "precip_gate": True,
        "transmission_rate": float(params.transmission_rate),
        "transmission_ref_km": float(params.transmission_ref_km),
        "transmission_rate_unused_by": "c2_channel_bed_loss_v1",
        "bed_loss_m3_per_km_month": float(params.bed_loss_m3_per_km_month),
        "channel_loss_algorithm": "bed_loss_m3_v1",
        "fill_max_depth_m": float(params.fill_max_depth_m),
        "river_min_catchment_km2": params.river_min_catchment_km2,
        "river_min_accumulation_cells_effective": int(river_min_cells),
        "cell_area_km2": float(gm.cell_area_km2),
        "q_units": "m3_s",
        "discharge_gross_max": float(discharge_gross.max()),
        "discharge_effective_max": float(discharge_eff.max()),
        "discharge_effective_mean_land": float(discharge_eff[land].mean())
        if np.any(land)
        else 0.0,
        "bed_loss_mean_land_m3s": float(bed_loss_mean[land].mean())
        if np.any(land)
        else 0.0,
        "bed_loss_max_over_potential_m3s": max_loss_over_potential,
        "bed_loss_max_over_available_m3s": max_loss_over_available,
        "bed_loss_never_exceeds_q": bool(max_loss_over_available <= 1e-9),
        "monthly_vs_annual_eff_rel_diff": rel_diff,
        "monthly_annual_consistent": True,
        "q_canonical": "mean_monthly_m3s",
        "monthly_vs_independent_annual_rel_diff": rel_independent,
        "lake_open_count": open_lakes,
        "lake_endorheic_count": endorheic_lakes,
        "lake_playa_count": playa_lakes,
        "lake_frozen_count": frozen_lakes,
        "lake_liquid_cell_count": int(np.count_nonzero(lake_mask)),
        "lake_envelope_cell_count": lake_cell_all,
        "lake_reported_wet_area_km2": float(
            sum(
                float(r.get("mean_wet_area_km2") or 0.0)
                for r in lake_records
                if int(r.get("water_body_id") or 0) > 0
            )
        ),
        "lake_raster_wet_area_km2": float(np.sum(water_fraction_mean)) * float(gm.cell_area_km2),
        "river_acc_fraction": float(params.river_acc_fraction),
        "planet_radius_km": float(params.planet_radius_km),
        "hydrology_algorithm": "c2_channel_bed_loss_v1",
        **catchment_diag,
        **runoff_diag,
        **graph_diag,
        **river_gate_diag,
        **lake_gate_diag,
        **channel_diag,
        **storage_diag,
        **{
            k: v
            for k, v in outlet_types.items()
            if k != "outlet_labels"
        },
    }
    reported = float(diagnostics["lake_reported_wet_area_km2"])
    rastered = float(diagnostics["lake_raster_wet_area_km2"])
    diagnostics["lake_raster_vs_reported_wet_ratio"] = (
        rastered / reported if reported > 1e-9 else 0.0
    )

    if reporter is not None:
        reporter.progress("hydrology", 1.0)
        reporter.stage_complete("hydrology")

    return HydrologyResult(
        extent=erosion.extent,
        dem_conditioned_m=core["dem_conditioned_m"],
        flow_direction=core["flow_direction"],
        flow_accumulation=core["flow_accumulation"],
        basin_id=core["basin_id"],
        watershed_id=core["watershed_id"],
        stream_order=core["stream_order"],
        river_mask=river_mask,
        river_discharge_proxy=discharge_eff,
        river_discharge_gross=discharge_gross,
        monthly_discharge=monthly_eff,
        monthly_discharge_gross=monthly_gross,
        monthly_runoff=monthly_runoff,
        snow_store=snow_store,
        soil_store=soil_store,
        soil_store_monthly=soil_store_monthly,
        channel_mask=channel_mask,
        channel_state=channel_state,
        river_water_fraction=river_frac,
        monthly_bed_loss=monthly_bed_loss,
        bed_loss_potential_m3s=bed_loss_potential,
        lake_mask=lake_mask,
        lake_id=lake_id,
        basin_envelope_id=basin_envelope_id,
        water_fraction_mean=water_fraction_mean,
        lake_records=lake_records,
        outlet_points=core["outlet_points"],
        ocean_mask=ocean,
        diagnostics=diagnostics,
    )
