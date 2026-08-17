"""Milestone 13 — fluvial erosion + final physical recalculation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.atmosphere.pipeline import AtmosphereResult
from worldsim.physical.climate.pipeline import (
    ClimateResult,
    downsample_mean,
    replace_climate_temperature,
)
from worldsim.physical.erosion.fluvial import apply_fluvial_erosion
from worldsim.physical.erosion.pass_one import (
    count_land_local_minima,
    land_roughness,
    rock_resistance_proxy,
)
from worldsim.physical.erosion.pipeline import ErosionResult, _macro_relief_correlation
from worldsim.physical.hydrology import HydrologyParams, HydrologyResult, build_hydrology
from worldsim.physical.landforms import LandformParams, LandformResult, build_landform_analysis
from worldsim.physical.moisture import MoistureParams, MoistureResult, build_moisture
from worldsim.physical.ocean import (
    OceanParams,
    OceanResult,
    apply_ocean_temperature_to_climate,
    build_ocean_circulation,
)
from worldsim.physical.tectonics.interpretation import TectonicsInterpretationResult
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.physical.vectorize import VectorGeographyResult, build_vector_geography
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class FinalRecalcParams:
    fluvial_iterations: int = 4
    stream_power_k: float = 12.0
    lapse_rate_c_per_km: float = 6.5
    months: int = 12
    axial_tilt_deg: float = 23.44
    ocean: OceanParams = field(default_factory=OceanParams)
    moisture: MoistureParams = field(default_factory=MoistureParams)
    hydrology: HydrologyParams = field(default_factory=HydrologyParams)
    landforms: LandformParams = field(default_factory=LandformParams)
    landform_analysis_width: int | None = None
    landform_analysis_height: int | None = None


@dataclass
class FinalRecalcResult:
    extent: SpatialExtent
    elevation_v1_m: NDArray[np.float64]
    elevation_v2_m: NDArray[np.float64]
    fluvial_delta_m: NDArray[np.float64]
    ocean_mask: NDArray[np.bool_]
    climate: ClimateResult
    atmosphere: AtmosphereResult
    ocean: OceanResult
    moisture: MoistureResult
    hydrology: HydrologyResult
    vectors: VectorGeographyResult
    landforms: LandformResult | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "terrain_v2.npz",
            elevation_v1_m=self.elevation_v1_m,
            elevation_v2_m=self.elevation_v2_m,
            fluvial_delta_m=self.fluvial_delta_m,
            ocean_mask=self.ocean_mask.astype(np.uint8),
        )
        self.climate.save(directory / "climate")
        self.atmosphere.save(directory / "atmosphere")
        self.ocean.save(directory / "ocean")
        self.moisture.save(directory / "moisture")
        self.hydrology.save(directory / "hydrology")
        self.vectors.save(directory / "vectors")
        if self.landforms is not None:
            self.landforms.save(directory / "landforms")
        (directory / "final_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def correct_climate_for_dem(
    climate: ClimateResult,
    *,
    elev_terrain_v1: NDArray[np.floating],
    elev_terrain_v2: NDArray[np.floating],
    lapse_rate_c_per_km: float = 6.5,
) -> ClimateResult:
    """Lapse-rate temperature correction from terrain DEM change + elev update."""
    h, w = climate.elevation_m.shape
    e1 = downsample_mean(np.asarray(elev_terrain_v1, dtype=np.float64), w, h)
    e2 = downsample_mean(np.asarray(elev_terrain_v2, dtype=np.float64), w, h)
    # Keep ocean elev from climate (bathymetry); update land
    ocean = climate.ocean_mask
    elev_new = np.where(ocean, climate.elevation_m, e2)
    delta_km = (elev_new - climate.elevation_m) / 1000.0
    # Only apply lapse on land elevation changes
    dT = -lapse_rate_c_per_km * np.where(ocean, 0.0, delta_km)
    temp = climate.temperature_c + dT[np.newaxis, :, :]
    diag = {
        **climate.diagnostics,
        "climate_correction": "lapse_from_dem_v2",
        "lapse_owner": "final_dem_delta",
        "mean_abs_temp_delta_c": float(np.mean(np.abs(dT[~ocean])))
        if np.any(~ocean)
        else 0.0,
        "elev_v1_climate_mean": float(e1[~ocean].mean()) if np.any(~ocean) else 0.0,
        "elev_v2_climate_mean": float(e2[~ocean].mean()) if np.any(~ocean) else 0.0,
    }
    prior_lapse = int(diag.get("lapse_apply_count", 1) or 1)
    diag["lapse_apply_count"] = prior_lapse + 1
    return replace_climate_temperature(
        climate,
        temp,
        diagnostics=diag,
        elevation_m=elev_new,
    )


def _erosion_view_for_hydrology(
    *,
    elevation_m: NDArray[np.float64],
    ocean_mask: NDArray[np.bool_],
    extent: SpatialExtent,
    resistance: NDArray[np.float64],
) -> ErosionResult:
    """Minimal ErosionResult wrapper so hydrology can consume DEM v2."""
    return ErosionResult(
        extent=extent,
        elevation_before_m=elevation_m,
        elevation_m=elevation_m,
        erosion_delta_m=np.zeros_like(elevation_m),
        slope=np.zeros_like(elevation_m),
        rock_resistance=resistance,
        annual_precip_terrain=np.zeros_like(elevation_m),
        ocean_mask=ocean_mask,
        diagnostics={"source": "dem_v2_wrapper"},
    )


def build_final_recalculation(
    *,
    erosion_v1: ErosionResult,
    hydrology_v1: HydrologyResult,
    climate_v1: ClimateResult,
    terrain: TerrainOceanResult,
    interpretation: TectonicsInterpretationResult | None = None,
    params: FinalRecalcParams | None = None,
    reporter: ProgressReporter | None = None,
) -> FinalRecalcResult:
    """Fluvial erosion → terrain v2 → climate/ocean/moisture → hydro/vectors final."""
    params = params or FinalRecalcParams()
    if reporter is not None:
        reporter.stage_started("final")
        reporter.progress("final", 0.05)

    th, tw = erosion_v1.elevation_m.shape
    oro = act = None
    if interpretation is not None:
        oro = upsample_bilinear_cylindrical(interpretation.orogenic_potential, tw, th)
        act = upsample_bilinear_cylindrical(interpretation.tectonic_activity, tw, th)
    resistance = rock_resistance_proxy(
        orogenic_potential=oro,
        tectonic_activity=act,
        shape=(th, tw),
    )

    elev_v2, delta = apply_fluvial_erosion(
        elevation_m=erosion_v1.elevation_m,
        ocean_mask=erosion_v1.ocean_mask,
        river_mask=hydrology_v1.river_mask,
        discharge_proxy=hydrology_v1.river_discharge_proxy,
        resistance=resistance,
        iterations=params.fluvial_iterations,
        stream_power_k=params.stream_power_k,
    )

    if reporter is not None:
        reporter.progress("final", 0.25)

    ocean = erosion_v1.ocean_mask
    land = ~ocean
    corr = _macro_relief_correlation(erosion_v1.elevation_m, elev_v2, ocean)
    elev_range = float(np.ptp(erosion_v1.elevation_m[land])) if np.any(land) else 1.0
    elev_range = max(elev_range, 1.0)
    mean_abs = float(np.mean(np.abs(delta[land]))) if np.any(land) else 0.0
    max_abs = float(np.max(np.abs(delta[land]))) if np.any(land) else 0.0
    mean_before = float(np.mean(erosion_v1.elevation_m[land])) if np.any(land) else 0.0
    mean_after = float(np.mean(elev_v2[land])) if np.any(land) else 0.0
    mean_drop_frac = (mean_before - mean_after) / elev_range

    climate_c = correct_climate_for_dem(
        climate_v1,
        elev_terrain_v1=erosion_v1.elevation_m,
        elev_terrain_v2=elev_v2,
        lapse_rate_c_per_km=params.lapse_rate_c_per_km,
    )

    if reporter is not None:
        reporter.progress("final", 0.40)

    atmosphere = build_atmosphere(
        climate=climate_c,
        params=AtmosphereParams(
            axial_tilt_deg=params.axial_tilt_deg,
            months=params.months,
        ),
    )
    ocean_circ = build_ocean_circulation(
        climate=climate_c,
        atmosphere=atmosphere,
        params=OceanParams(
            months=params.months,
            sst_mix=params.ocean.sst_mix,
            inland_decay_cells=params.ocean.inland_decay_cells,
            inland_decay_km=params.ocean.inland_decay_km,
            western_boundary_width_km=params.ocean.western_boundary_width_km,
            western_boundary_width_cells=params.ocean.western_boundary_width_cells,
            western_warm_c=params.ocean.western_warm_c,
            eastern_cool_c=params.ocean.eastern_cool_c,
            planet_radius_km=params.ocean.planet_radius_km,
        ),
    )
    # Plan B1: Holdridge / hex / atlas temperatures follow ocean SST + inland decay
    climate_c = apply_ocean_temperature_to_climate(climate_c, ocean_circ)
    climate_c.diagnostics["temperature_state"] = "temperature_final_c"
    climate_c.diagnostics["provenance_lapse_then_sst"] = True
    # CR-1: pass the full MoistureParams (PR-7/PR-8 knobs included). Do not
    # rebuild a partial dataclass — that silently dropped plume/ITCZ/monsoon.
    moisture_params = replace(params.moisture, months=params.months)
    # First pass (ocean/land only) drives hydrology; lakes/rivers do not exist yet.
    moisture = build_moisture(
        climate=climate_c,
        atmosphere=atmosphere,
        ocean=ocean_circ,
        params=moisture_params,
    )

    if reporter is not None:
        reporter.progress("final", 0.60)

    erosion_view = _erosion_view_for_hydrology(
        elevation_m=elev_v2,
        ocean_mask=ocean,
        extent=erosion_v1.extent,
        resistance=resistance,
    )
    hydrology = build_hydrology(
        erosion=erosion_view,
        moisture=moisture,
        params=params.hydrology,
        temperature_c=climate_c.temperature_c,
    )

    # Rebuild moisture with inland water sources so lakes/rivers humidify interiors
    # (ecology / Holdridge use this second pass).
    ch, cw = climate_c.ocean_mask.shape
    lake_c = downsample_mean(
        hydrology.lake_mask.astype(np.float64), cw, ch
    ) >= 0.15
    river_c = downsample_mean(
        hydrology.river_mask.astype(np.float64), cw, ch
    ) >= 0.05
    moisture = build_moisture(
        climate=climate_c,
        atmosphere=atmosphere,
        ocean=ocean_circ,
        params=moisture_params,
        lake_mask=lake_c,
        river_mask=river_c,
    )

    if reporter is not None:
        reporter.progress("final", 0.80)

    # Terrain for coastline water_body ids — keep v1 labels; elev changed only
    vectors = build_vector_geography(
        hydrology=hydrology,
        terrain=terrain,
    )

    # PR-9 — LandformAnalysis on unconditioned elevation_v2 (analysis grid)
    aw = params.landform_analysis_width or climate_c.extent.width
    ah = params.landform_analysis_height or climate_c.extent.height
    landforms = build_landform_analysis(
        elevation_m=elev_v2,
        ocean_mask=ocean,
        extent=erosion_v1.extent,
        analysis_width=aw,
        analysis_height=ah,
        orogenic_potential=(
            interpretation.orogenic_potential if interpretation is not None else None
        ),
        tectonic_activity=(
            interpretation.tectonic_activity if interpretation is not None else None
        ),
        params=params.landforms,
        reporter=reporter,
    )

    stable = (
        corr >= 0.95
        and max_abs < 0.35 * elev_range + 50.0
        and mean_drop_frac < 0.20
        and mean_abs < 0.15 * elev_range + 25.0
    )
    moisture_ok = bool(moisture.diagnostics.get("acceptance_ok"))
    landforms_ok = bool(landforms.diagnostics.get("acceptance_ok"))
    no_catastrophe = (
        bool(hydrology.diagnostics.get("acceptance_ok"))
        and bool(vectors.diagnostics.get("acceptance_ok"))
        and moisture_ok
        and stable
        and float(np.min(elev_v2[land])) >= -1.0
        if np.any(land)
        else True
    )

    diagnostics: dict[str, Any] = {
        "width": tw,
        "height": th,
        "fluvial_iterations": params.fluvial_iterations,
        "macro_relief_correlation_v1_v2": corr,
        "mean_abs_fluvial_delta_m": mean_abs,
        "max_abs_fluvial_delta_m": max_abs,
        "mean_land_elev_v1_m": mean_before,
        "mean_land_elev_v2_m": mean_after,
        "mean_elev_drop_frac_of_range": mean_drop_frac,
        "local_minima_v2": count_land_local_minima(elev_v2, ocean),
        "roughness_v2": land_roughness(elev_v2, ocean),
        "stable_final_geography": stable,
        "no_catastrophic_feedback": no_catastrophe,
        "hydrology_final_ok": bool(hydrology.diagnostics.get("acceptance_ok")),
        "vectors_final_ok": bool(vectors.diagnostics.get("acceptance_ok")),
        "moisture_ok": moisture_ok,
        "moisture_spinup_converged": bool(
            moisture.diagnostics.get("spinup_converged")
        ),
        "landforms_ok": landforms_ok,
        "landform_algorithm": landforms.diagnostics.get("algorithm"),
        "mountain_range_count": landforms.diagnostics.get("mountain_range_count"),
        "plateau_count": landforms.diagnostics.get("plateau_count"),
        "climate_mean_abs_temp_delta_c": climate_c.diagnostics.get(
            "mean_abs_temp_delta_c"
        ),
        "ocean_temperature_applied": bool(
            climate_c.diagnostics.get("ocean_temperature_applied")
        ),
        "ocean_land_temp_delta_mean_abs": climate_c.diagnostics.get(
            "ocean_land_temp_delta_mean_abs"
        ),
        "moisture_inland_water_sources": bool(
            moisture.diagnostics.get("inland_water_sources")
        ),
        "acceptance_ok": bool(stable and no_catastrophe),
    }

    if reporter is not None:
        reporter.progress("final", 1.0)
        reporter.stage_complete("final")

    return FinalRecalcResult(
        extent=erosion_v1.extent,
        elevation_v1_m=np.asarray(erosion_v1.elevation_m, dtype=np.float64),
        elevation_v2_m=elev_v2,
        fluvial_delta_m=delta,
        ocean_mask=ocean,
        climate=climate_c,
        atmosphere=atmosphere,
        ocean=ocean_circ,
        moisture=moisture,
        hydrology=hydrology,
        vectors=vectors,
        landforms=landforms,
        diagnostics=diagnostics,
    )
