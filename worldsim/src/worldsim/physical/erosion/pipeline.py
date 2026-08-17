"""Milestone 10 — first climate-informed erosion pass."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.erosion.pass_one import (
    apply_erosion_pass_one,
    count_land_local_minima,
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
    iterations: int = 5
    thermal_kappa: float = 0.08
    fluvial_k: float = 8.0
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
    minima_before = count_land_local_minima(before, ocean)
    rough_before = land_roughness(before, ocean)

    dem_v1, delta = apply_erosion_pass_one(
        elevation_m=before,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resistance,
        iterations=params.iterations,
        thermal_kappa=params.thermal_kappa,
        fluvial_k=params.fluvial_k,
        planet_radius_km=params.planet_radius_km,
    )

    if reporter is not None:
        reporter.progress("erosion", 0.8)

    minima_after = count_land_local_minima(dem_v1, ocean)
    rough_after = land_roughness(dem_v1, ocean)
    corr = _macro_relief_correlation(before, dem_v1, ocean)
    slope = slope_magnitude(dem_v1, planet_radius_km=params.planet_radius_km)

    drainage_improved = minima_after <= minima_before
    roughness_reduced = rough_after <= rough_before * 1.02
    macro_preserved = corr >= 0.97

    land = ~ocean
    diagnostics: dict[str, Any] = {
        "width": tw,
        "height": th,
        "iterations": params.iterations,
        "local_minima_before": minima_before,
        "local_minima_after": minima_after,
        "drainage_quality_improved": drainage_improved,
        "roughness_before": rough_before,
        "roughness_after": rough_after,
        "roughness_reduced": roughness_reduced,
        "macro_relief_correlation": corr,
        "macro_relief_preserved": macro_preserved,
        "mean_abs_delta_land_m": float(np.mean(np.abs(delta[land])))
        if np.any(land)
        else 0.0,
        "max_abs_delta_land_m": float(np.max(np.abs(delta[land])))
        if np.any(land)
        else 0.0,
        "ocean_unchanged": bool(np.allclose(dem_v1[ocean], before[ocean])),
        "slope_algorithm": "metric_gridmetrics_v1",
        "acceptance_ok": bool(
            drainage_improved and macro_preserved and roughness_reduced
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
        diagnostics=diagnostics,
    )
