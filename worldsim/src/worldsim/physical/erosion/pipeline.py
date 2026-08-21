"""Milestone 10 — first climate-informed erosion pass."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.gates import (
    domain_mean_abs_delta,
    hillslope_erosion_gate,
    process_delta_stats,
)
from worldsim.physical.erosion.process_deltas import ProcessDeltas
from worldsim.physical.erosion.pass_one import (
    apply_erosion_pass_one,
    count_land_local_minima,
    land_elevation_delta_stats,
    land_roughness,
    rock_resistance_proxy,
    slope_magnitude,
)
from worldsim.spatial.metrics import EARTH_RADIUS_KM
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.tectonics.interpretation import TectonicsInterpretationResult
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class ErosionParams:
    """First-pass (pre-hydrology) erosion. Independent of final stream-power.

    Units: ``thermal_kappa`` is the 1 km-cell thermal coefficient
    (``kappa_m2 = thermal_kappa * 1000²``). ``fluvial_k`` is precip×slope
    incision on this pass only — not ``FinalRecalcParams.stream_power_k``.
    """

    iterations: int = 5
    thermal_kappa: float = 20.0
    fluvial_k: float = 8.0
    max_step_m: float = 25.0
    macro_blend: float = 0.35
    planet_radius_km: float = EARTH_RADIUS_KM


@dataclass
class ErosionResult:
    extent: SpatialExtent
    elevation_before_m: NDArray[np.float64]
    elevation_m: NDArray[np.float64]
    erosion_delta_m: NDArray[np.float64]
    slope: NDArray[np.float64]
    rock_resistance: NDArray[np.float64]
    annual_precip_terrain: NDArray[np.float64]
    ocean_mask: NDArray[np.bool_]
    diagnostics: dict[str, Any]
    process_deltas: ProcessDeltas | None = None

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "erosion_pass1.npz",
            elevation_before_m=self.elevation_before_m,
            elevation_m=self.elevation_m,
            erosion_delta_m=self.erosion_delta_m,
            slope=self.slope,
            rock_resistance=self.rock_resistance,
            annual_precip_terrain=self.annual_precip_terrain,
            ocean_mask=self.ocean_mask.astype(np.uint8),
        )
        (directory / "erosion_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _macro_relief_correlation(
    before: NDArray[np.float64],
    after: NDArray[np.float64],
    ocean_mask: NDArray[np.bool_],
) -> float:
    land = ~ocean_mask
    if np.count_nonzero(land) < 10:
        return 1.0
    b = before[land]
    a = after[land]
    if float(np.std(b)) < 1e-9 or float(np.std(a)) < 1e-9:
        return 1.0
    return float(np.corrcoef(b, a)[0, 1])


def build_erosion_pass_one(
    *,
    terrain: TerrainOceanResult,
    moisture: MoistureResult,
    interpretation: TectonicsInterpretationResult | None = None,
    params: ErosionParams | None = None,
    reporter: ProgressReporter | None = None,
) -> ErosionResult:
    params = params or ErosionParams()
    if reporter is not None:
        reporter.stage_started("erosion")
        reporter.progress("erosion", 0.1)

    th, tw = terrain.elevation_m.shape
    precip = upsample_bilinear_cylindrical(
        moisture.annual_precipitation, tw, th
    )

    oro = act = None
    if interpretation is not None:
        oro = upsample_bilinear_cylindrical(
            interpretation.orogenic_potential, tw, th
        )
        act = upsample_bilinear_cylindrical(
            interpretation.tectonic_activity, tw, th
        )

    resistance = rock_resistance_proxy(
        orogenic_potential=oro,
        tectonic_activity=act,
        shape=(th, tw),
    )

    if reporter is not None:
        reporter.progress("erosion", 0.35)

    before = np.asarray(terrain.elevation_m, dtype=np.float64)
    ocean = np.asarray(terrain.ocean_mask, dtype=np.bool_)
    land = ~ocean
    minima_before = count_land_local_minima(before, ocean)
    rough_before = land_roughness(before, ocean)

    dem_v1, process = apply_erosion_pass_one(
        elevation_m=before,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resistance,
        iterations=params.iterations,
        thermal_kappa=params.thermal_kappa,
        fluvial_k=params.fluvial_k,
        max_step_m=params.max_step_m,
        macro_blend=params.macro_blend,
        planet_radius_km=params.planet_radius_km,
    )
    delta = process.total_erosion_delta_m

    if reporter is not None:
        reporter.progress("erosion", 0.8)

    minima_after = count_land_local_minima(dem_v1, ocean)
    rough_after = land_roughness(dem_v1, ocean)
    corr = _macro_relief_correlation(before, dem_v1, ocean)
    slope = slope_magnitude(dem_v1, planet_radius_km=params.planet_radius_km)

    delta_stats = land_elevation_delta_stats(before, dem_v1, ocean)
    hillslope = process.thermal_or_hillslope_delta_m + process.first_fluvial_delta_m
    hillslope_mean = domain_mean_abs_delta(hillslope, land, ocean)
    nontrivial, min_required = hillslope_erosion_gate(
        hillslope_mean,
        float(delta_stats["elev_range_land_m"]),
    )
    proc_stats = process_delta_stats(
        process,
        ocean,
        elev_range_m=float(delta_stats["elev_range_land_m"]),
        elev_before_m=before,
        elev_after_m=dem_v1,
    )
    drainage_improved = minima_after <= minima_before
    roughness_reduced = rough_after <= rough_before * 1.02
    macro_preserved = corr >= 0.97
    ocean_unchanged = bool(delta_stats["ocean_unchanged"])

    diagnostics: dict[str, Any] = {
        "width": tw,
        "height": th,
        "iterations": params.iterations,
        "thermal_kappa": float(params.thermal_kappa),
        "thermal_kappa_units": "1km_cell_coeff; kappa_m2=thermal_kappa*1000^2",
        "fluvial_k": float(params.fluvial_k),
        "fluvial_k_role": "first_pass_precip_slope_hillslope",
        "max_step_m": float(params.max_step_m),
        "macro_blend": float(params.macro_blend),
        "thermal_mean_abs_delta_m": float(
            domain_mean_abs_delta(process.thermal_or_hillslope_delta_m, land, ocean)
        ),
        "first_fluvial_mean_abs_delta_m": float(
            domain_mean_abs_delta(process.first_fluvial_delta_m, land, ocean)
        ),
        "conditioning_mean_abs_delta_m": float(
            domain_mean_abs_delta(process.conditioning_or_pit_fill_delta_m, land, ocean)
        ),
        "hillslope_mean_abs_delta_m": hillslope_mean,
        **proc_stats,
        "local_minima_before": minima_before,
        "local_minima_after": minima_after,
        "drainage_quality_improved": drainage_improved,
        "roughness_before": rough_before,
        "roughness_after": rough_after,
        "roughness_reduced": roughness_reduced,
        "macro_relief_correlation": corr,
        "macro_relief_preserved": macro_preserved,
        "mean_abs_delta_land_m": float(delta_stats["mean_abs_delta_land_m"]),
        "median_abs_delta_land_m": float(delta_stats["median_abs_delta_land_m"]),
        "p90_abs_delta_land_m": float(delta_stats["p90_abs_delta_land_m"]),
        "max_abs_delta_land_m": float(delta_stats["max_abs_delta_land_m"]),
        "elev_range_land_m": float(delta_stats["elev_range_land_m"]),
        "erosion_min_mean_abs_delta_m": min_required,
        "erosion_nontrivial": nontrivial,
        "ocean_unchanged": ocean_unchanged,
        "slope_algorithm": "metric_gridmetrics_v1",
        "erosion_algorithm": "pc4_process_deltas_v1",
        "acceptance_ok": bool(
            drainage_improved
            and macro_preserved
            and roughness_reduced
            and ocean_unchanged
            and nontrivial
            and bool(proc_stats["conditioning_excluded_from_erosion_acceptance"])
            and bool(proc_stats.get("erosion_delta_identity_ok", False))
        ),
    }

    if reporter is not None:
        reporter.progress("erosion", 1.0)
        reporter.stage_complete("erosion")

    return ErosionResult(
        extent=terrain.extent,
        elevation_before_m=before,
        elevation_m=dem_v1,
        erosion_delta_m=delta,
        slope=slope,
        rock_resistance=resistance,
        annual_precip_terrain=precip,
        ocean_mask=ocean,
        process_deltas=process,
        diagnostics=diagnostics,
    )
