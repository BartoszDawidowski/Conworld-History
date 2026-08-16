"""Milestone 11 — PyFlwDir hydrology orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology.flow import accuflux_on_land, run_pyflwdir_core
from worldsim.physical.hydrology.rivers import (
    gate_lakes_by_water_supply,
    gate_river_mask_by_discharge,
    lake_mask_from_fill,
    river_mask_from_accumulation,
)
from worldsim.physical.hydrology.transmission import (
    effective_discharge_with_transmission,
    transmission_sink,
)
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class HydrologyParams:
    river_acc_fraction: float = 0.02
    lake_min_depth_m: float = 2.0
    months: int = 12
    # Plan B7 — precip/discharge gates
    river_discharge_candidate_quantile: float = 0.50
    lake_precip_land_quantile: float = 0.70
    lake_arid_precip_land_quantile: float = 0.45
    lake_min_mean_temp_c: float = 1.0
    lake_inflow_land_quantile: float = 0.75
    # §6.3.1 — channel transmission losses (Nil OK / wadi dies)
    transmission_rate: float = 0.45
    precip_scale_mm: float = 200.0


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
    lake_mask: NDArray[np.bool_]
    lake_id: NDArray[np.int32]
    outlet_points: list[tuple[int, int]]
    ocean_mask: NDArray[np.bool_]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "hydrology.npz",
            dem_conditioned_m=self.dem_conditioned_m,
            flow_direction=self.flow_direction,
            flow_accumulation=self.flow_accumulation,
            basin_id=self.basin_id,
            watershed_id=self.watershed_id,
            stream_order=self.stream_order,
            river_mask=self.river_mask.astype(np.uint8),
            river_discharge_proxy=self.river_discharge_proxy,
            river_discharge_gross=self.river_discharge_gross,
            monthly_discharge=self.monthly_discharge,
            lake_mask=self.lake_mask.astype(np.uint8),
            lake_id=self.lake_id,
            ocean_mask=self.ocean_mask.astype(np.uint8),
            outlet_rows=np.array([p[0] for p in self.outlet_points], dtype=np.int32),
            outlet_cols=np.array([p[1] for p in self.outlet_points], dtype=np.int32),
        )
        (directory / "hydrology_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _downstream_accumulation_ok(
    flow_accumulation: NDArray[np.float64],
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
    *,
    samples: int = 200,
) -> bool:
    """Spot-check: moving one D8 step downstream should not decrease accumulation.

    ArcGIS D8 codes: 1 E, 2 SE, 4 S, 8 SW, 16 W, 32 NW, 64 N, 128 NE.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    acc = flow_accumulation
    d8 = flow_direction
    h, w = acc.shape
    deltas = {
        1: (0, 1),
        2: (1, 1),
        4: (1, 0),
        8: (1, -1),
        16: (0, -1),
        32: (-1, -1),
        64: (-1, 0),
        128: (-1, 1),
    }
    land_idx = np.argwhere(~ocean & (d8 > 0) & (d8 != 247))
    if len(land_idx) == 0:
        return False
    rng = np.random.default_rng(0)
    pick = land_idx[
        rng.choice(len(land_idx), size=min(samples, len(land_idx)), replace=False)
    ]
    ok = 0
    checked = 0
    for r, c in pick:
        code = int(d8[r, c])
        if code not in deltas:
            continue
        dr, dc = deltas[code]
        nr, nc = int(r + dr), int(c + dc) % w  # E–W wrap for neighbour probe
        if nr < 0 or nr >= h:
            continue
        if ocean[nr, nc]:
            # draining to ocean is fine
            ok += 1
            checked += 1
            continue
        checked += 1
        if acc[nr, nc] + 1e-6 >= acc[r, c]:
            ok += 1
    return checked > 0 and (ok / checked) >= 0.85


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

    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    flw = core.pop("flw")
    pad = int(core.pop("pad"))

    if reporter is not None:
        reporter.progress("hydrology", 0.45)

    river_candidates = river_mask_from_accumulation(
        core["flow_accumulation"],
        ocean,
        fraction=params.river_acc_fraction,
    )
    lake_raw, lake_id_raw, _lake_count_raw = lake_mask_from_fill(
        elev,
        core["dem_conditioned_m"],
        ocean,
        min_depth_m=params.lake_min_depth_m,
    )

    # Annual gross discharge (no losses) + effective discharge with transmission.
    annual = upsample_bilinear_cylindrical(moisture.annual_precipitation, w, h)
    annual = np.where(ocean, 0.0, np.maximum(annual, 0.0))
    discharge_gross = accuflux_on_land(
        flw, pad=pad, width=w, ocean_mask=ocean, weights=annual
    )

    annual_temp: NDArray[np.float64]
    if temperature_c is not None:
        t = np.asarray(temperature_c, dtype=np.float64)
        if t.ndim == 3:
            t = t.mean(axis=0)
        annual_temp = upsample_bilinear_cylindrical(t, w, h)
    else:
        annual_temp = np.full((h, w), 15.0, dtype=np.float64)

    sink = transmission_sink(
        annual,
        annual_temp,
        ocean,
        transmission_rate=params.transmission_rate,
        precip_scale_mm=params.precip_scale_mm,
    )
    discharge_eff = effective_discharge_with_transmission(
        flw,
        pad=pad,
        width=w,
        ocean_mask=ocean,
        precip=annual,
        sink=sink,
    )

    # B7 / §6.3.1: gate on effective Q (Nil survives, wadi dies).
    river_mask, river_gate_diag = gate_river_mask_by_discharge(
        river_candidates,
        discharge_eff,
        core["flow_direction"],
        ocean,
        candidate_quantile=params.river_discharge_candidate_quantile,
    )
    lake_mask, lake_id, lake_count, lake_gate_diag = gate_lakes_by_water_supply(
        lake_raw,
        lake_id_raw,
        annual,
        ocean,
        river_mask=river_mask,
        discharge_effective=discharge_eff,
        temperature_annual_c=annual_temp,
        precip_land_quantile=params.lake_precip_land_quantile,
        arid_precip_land_quantile=params.lake_arid_precip_land_quantile,
        lake_min_mean_temp_c=params.lake_min_mean_temp_c,
        inflow_land_quantile=params.lake_inflow_land_quantile,
    )

    months = min(params.months, moisture.precipitation.shape[0])
    monthly = np.zeros((months, h, w), dtype=np.float64)
    for m in range(months):
        precip_m = upsample_bilinear_cylindrical(moisture.precipitation[m], w, h)
        precip_m = np.where(ocean, 0.0, np.maximum(precip_m, 0.0))
        monthly[m] = accuflux_on_land(
            flw, pad=pad, width=w, ocean_mask=ocean, weights=precip_m
        )

    if reporter is not None:
        reporter.progress("hydrology", 0.85)

    land = ~ocean
    acc_land = core["flow_accumulation"][land]
    downstream_ok = _downstream_accumulation_ok(
        core["flow_accumulation"], core["flow_direction"], ocean
    )
    drainage_valid = bool(core["isvalid"]) and int(core["nnodes"]) > 0
    if np.any(river_mask) and np.any(land):
        riv_mean = float(core["flow_accumulation"][river_mask].mean())
        land_mean = float(acc_land.mean()) if acc_land.size else 0.0
        sensible_acc = riv_mean > land_mean
    else:
        riv_mean = land_mean = float("nan")
        sensible_acc = False

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
        "acceptance_ok": bool(drainage_valid and downstream_ok and sensible_acc),
        "precip_gate": True,
        "transmission_rate": float(params.transmission_rate),
        "discharge_gross_max": float(discharge_gross.max()),
        "discharge_effective_max": float(discharge_eff.max()),
        "discharge_effective_mean_land": float(discharge_eff[land].mean())
        if np.any(land)
        else 0.0,
        "transmission_sink_mean_land": float(sink[land].mean()) if np.any(land) else 0.0,
        **river_gate_diag,
        **lake_gate_diag,
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
        monthly_discharge=monthly,
        lake_mask=lake_mask,
        lake_id=lake_id,
        outlet_points=core["outlet_points"],
        ocean_mask=ocean,
        diagnostics=diagnostics,
    )
