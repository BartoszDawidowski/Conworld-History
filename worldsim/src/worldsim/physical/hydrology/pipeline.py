"""Milestone 11 / PR-6 — hydrology orchestration (runoff, wadi, lakes)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology.cylindrical_graph import classify_outlets
from worldsim.physical.hydrology.flow import accuflux_on_land, run_pyflwdir_core
from worldsim.physical.hydrology.lakes_meta import build_lake_records
from worldsim.physical.hydrology.rivers import (
    gate_lakes_by_water_supply,
    gate_river_mask_by_discharge,
    lake_mask_from_fill,
    river_mask_from_accumulation,
)
from worldsim.physical.hydrology.runoff import build_monthly_runoff
from worldsim.physical.hydrology.transmission import (
    effective_discharge_with_transmission,
    transmission_sink,
)
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class HydrologyParams:
    river_acc_fraction: float = 0.02
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
    # §6.3.1 — channel transmission losses (Nil OK / wadi dies)
    transmission_rate: float = 0.45
    precip_scale_mm: float = 200.0
    # PR-6 snow / runoff
    snow_threshold_c: float = 0.0
    snow_band_c: float = 2.0
    melt_factor_per_c: float = 0.08
    max_snow_store: float = 40.0
    # CR-4 — numerical fill only; negative = legacy fill-all (no closed basins)
    fill_max_depth_m: float = 25.0
    store_monthly_gross: bool = False
    planet_radius_km: float = 6371.0
    # CR-5: physical catchment floor (None → river_min_accumulation_cells only)
    river_min_catchment_km2: float | None = 500.0


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
    lake_mask: NDArray[np.bool_] = field(default_factory=lambda: np.zeros((0,), dtype=bool))
    lake_id: NDArray[np.int32] = field(default_factory=lambda: np.zeros((0,), dtype=np.int32))
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
    )
    monthly_runoff = np.asarray(runoff_pack["runoff"], dtype=np.float64)
    snow_store = np.asarray(runoff_pack["snow_store"], dtype=np.float64)
    annual_runoff = monthly_runoff.sum(axis=0)
    annual_precip = precip_m.sum(axis=0)

    if reporter is not None:
        reporter.progress("hydrology", 0.5)

    gm = grid_metrics(w, h, radius_km=params.planet_radius_km)
    if params.river_min_catchment_km2 is not None and params.river_min_catchment_km2 > 0:
        river_min_cells = gm.cells_for_area_km2(params.river_min_catchment_km2)
    else:
        river_min_cells = int(params.river_min_accumulation_cells)
    river_candidates = river_mask_from_accumulation(
        core["flow_accumulation"],
        ocean,
        fraction=params.river_acc_fraction,
        min_cells=river_min_cells,
    )
    lake_raw, lake_id_raw, _lake_count_raw = lake_mask_from_fill(
        elev,
        elev + np.asarray(core["depression_depth_m"], dtype=np.float64),
        ocean,
        min_depth_m=params.lake_min_depth_m,
    )

    discharge_gross = accuflux_on_land(
        flw, pad=pad, width=w, ocean_mask=ocean, weights=annual_runoff, graph=graph
    )
    sink_annual = transmission_sink(
        annual_runoff,
        annual_temp,
        ocean,
        transmission_rate=params.transmission_rate,
        precip_scale_mm=params.precip_scale_mm,
    )
    discharge_eff_independent = effective_discharge_with_transmission(
        flw,
        pad=pad,
        width=w,
        ocean_mask=ocean,
        precip=annual_runoff,
        sink=sink_annual,
        graph=graph,
    )

    monthly_gross = np.zeros((0,), dtype=np.float64)
    monthly_eff = np.zeros((months, h, w), dtype=np.float64)
    for m in range(months):
        sink_m = transmission_sink(
            monthly_runoff[m],
            temp_m[m],
            ocean,
            transmission_rate=params.transmission_rate,
            precip_scale_mm=params.precip_scale_mm,
        )
        monthly_eff[m] = effective_discharge_with_transmission(
            flw,
            pad=pad,
            width=w,
            ocean_mask=ocean,
            precip=monthly_runoff[m],
            sink=sink_m,
            graph=graph,
        )
        if params.store_monthly_gross:
            if monthly_gross.size == 0:
                monthly_gross = np.zeros((months, h, w), dtype=np.float64)
            monthly_gross[m] = accuflux_on_land(
                flw,
                pad=pad,
                width=w,
                ocean_mask=ocean,
                weights=monthly_runoff[m],
                graph=graph,
            )

    # CR-4 / F-09: monthly effective Q is canonical; annual products are the sum.
    discharge_eff = monthly_eff.sum(axis=0)

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

    # Canonical monthly vs annual is identity. Independent annual routing is
    # diagnosed (nonlinear PET/max) but does not define Q products.
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
        "lake_count": lake_count,
        "lake_cell_count": int(np.count_nonzero(lake_mask)),
        "outlet_count": len(core["outlet_points"]),
        "flow_acc_max": float(core["flow_accumulation"].max()),
        "river_acc_mean": riv_mean,
        "land_acc_mean": land_mean,
        "acceptance_ok": bool(
            drainage_valid and downstream_ok and sensible_acc and typed_ok
        ),
        "precip_gate": True,
        "transmission_rate": float(params.transmission_rate),
        "fill_max_depth_m": float(params.fill_max_depth_m),
        "river_min_catchment_km2": params.river_min_catchment_km2,
        "river_min_accumulation_cells_effective": int(river_min_cells),
        "cell_area_km2": float(gm.cell_area_km2),
        "discharge_gross_max": float(discharge_gross.max()),
        "discharge_effective_max": float(discharge_eff.max()),
        "discharge_effective_mean_land": float(discharge_eff[land].mean())
        if np.any(land)
        else 0.0,
        "transmission_sink_mean_land": float(sink_annual[land].mean())
        if np.any(land)
        else 0.0,
        "monthly_vs_annual_eff_rel_diff": rel_diff,
        "monthly_annual_consistent": True,
        "q_canonical": "sum_monthly_effective",
        "monthly_vs_independent_annual_rel_diff": rel_independent,
        "lake_open_count": open_lakes,
        "lake_endorheic_count": endorheic_lakes,
        "lake_playa_count": playa_lakes,
        "lake_frozen_count": frozen_lakes,
        "hydrology_algorithm": "cr4_typed_outlets_canonical_monthly_q_v1",
        **runoff_diag,
        **graph_diag,
        **river_gate_diag,
        **lake_gate_diag,
        **{
            k: v
            for k, v in outlet_types.items()
            if k != "outlet_labels"
        },
    }

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
        lake_mask=lake_mask,
        lake_id=lake_id,
        lake_records=lake_records,
        outlet_points=core["outlet_points"],
        ocean_mask=ocean,
        diagnostics=diagnostics,
    )
