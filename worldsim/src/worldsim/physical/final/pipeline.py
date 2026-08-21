"""Milestone 13 — fluvial erosion + final physical recalculation."""

from __future__ import annotations

import hashlib
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
    climate_grid_land_elevation,
    downsample_mean,
    replace_climate_temperature,
    restamp_temperature_diagnostics,
    temperature_diagnostics,
)
from worldsim.physical.climate.temperature import (
    TEMPERATURE_STATE_BASE,
    TEMPERATURE_STATE_EQUILIBRIUM,
    TEMPERATURE_STATE_FINAL,
)
from worldsim.physical.erosion.fluvial import apply_fluvial_erosion
from worldsim.physical.erosion.gates import (
    domain_mean_abs_delta,
    fluvial_corridor_erosion_gate,
    process_delta_stats,
)
from worldsim.physical.erosion.pass_one import (
    count_land_local_minima,
    land_elevation_delta_stats,
    land_roughness,
    rock_resistance_proxy,
)
from worldsim.physical.erosion.pipeline import ErosionResult, _macro_relief_correlation
from worldsim.spatial.metrics import grid_metrics
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


def binary_jaccard(a: NDArray[np.bool_], b: NDArray[np.bool_]) -> float:
    """Intersection-over-union of two boolean masks."""
    aa = np.asarray(a, dtype=bool)
    bb = np.asarray(b, dtype=bool)
    inter = int(np.count_nonzero(aa & bb))
    union = int(np.count_nonzero(aa | bb))
    if union == 0:
        return 1.0
    return float(inter) / float(union)


def array_checksum(arr: NDArray) -> str:
    payload = np.ascontiguousarray(arr)
    return hashlib.sha256(payload.tobytes()).hexdigest()[:16]


def total_effective_q_m3s(hydrology: HydrologyResult) -> float:
    ocean = np.asarray(hydrology.ocean_mask, dtype=bool)
    q = np.asarray(hydrology.river_discharge_proxy, dtype=np.float64)
    land = ~ocean
    if not np.any(land):
        return 0.0
    return float(np.sum(q[land]))


def coupling_metrics(
    h_pre: HydrologyResult, h_post: HydrologyResult
) -> dict[str, Any]:
    jaccard = binary_jaccard(h_pre.lake_mask, h_post.lake_mask)
    q_pre = total_effective_q_m3s(h_pre)
    q_post = total_effective_q_m3s(h_post)
    dq = abs(q_post - q_pre) / max(abs(q_pre), 1e-9)
    return {
        "lake_mask_jaccard": float(jaccard),
        "effective_q_pre_m3s": float(q_pre),
        "effective_q_post_m3s": float(q_post),
        "effective_q_rel_change": float(dq),
        "lake_checksum_pre": array_checksum(h_pre.lake_mask),
        "lake_checksum_post": array_checksum(h_post.lake_mask),
        "coupling_converged": bool(jaccard >= 0.98 and dq <= 0.05),
    }


def _climate_inland_fractions(
    hydrology: HydrologyResult, cw: int, ch: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    frac_src = getattr(hydrology, "water_fraction_mean", None)
    if frac_src is not None and np.asarray(frac_src).size:
        lake_frac = downsample_mean(np.asarray(frac_src, dtype=np.float64), cw, ch)
    else:
        lake_frac = downsample_mean(hydrology.lake_mask.astype(np.float64), cw, ch)
    riv_src = getattr(hydrology, "river_water_fraction", None)
    if riv_src is not None and np.asarray(riv_src).size:
        river_frac = downsample_mean(np.asarray(riv_src, dtype=np.float64), cw, ch)
    else:
        river_frac = downsample_mean(hydrology.river_mask.astype(np.float64), cw, ch)
    lake_frac = np.clip(lake_frac, 0.0, 1.0)
    river_frac = np.clip(river_frac, 0.0, 1.0)
    river_frac = np.minimum(river_frac, np.maximum(0.0, 1.0 - lake_frac))
    return lake_frac, river_frac


@dataclass(frozen=True)
class FinalRecalcParams:
    """Final fluvial incision + climate/hydro rebuild.

    ``stream_power_k`` is river incision on this pass only — independent of
    first-pass ``ErosionParams.fluvial_k``.
    """

    fluvial_iterations: int = 4
    stream_power_k: float = 500.0
    stream_power_max_step_m: float = 30.0
    stream_power_macro_blend: float = 0.40
    micro_fill_max_depth_m: float = 25.0
    lapse_rate_c_per_km: float = 6.5
    months: int = 12
    axial_tilt_deg: float = 23.44
    ocean: OceanParams = field(default_factory=OceanParams)
    moisture: MoistureParams = field(default_factory=MoistureParams)
    hydrology: HydrologyParams = field(default_factory=HydrologyParams)
    landforms: LandformParams = field(default_factory=LandformParams)
    landform_analysis_width: int | None = None
    landform_analysis_height: int | None = None
    # CR-8: one damped rebuild of hydrology from ecology moisture (0 = keep first hydro).
    hydro_evap_blend: float = 0.5


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
    ocean_terrain: NDArray[np.bool_],
    lapse_rate_c_per_km: float = 6.5,
) -> ClimateResult:
    """Lapse-rate correction on every DEM-dependent named temperature state."""
    h, w = climate.elevation_m.shape
    ocean = climate.ocean_mask
    e1 = climate_grid_land_elevation(
        elev_terrain_v1,
        ocean_terrain,
        w,
        h,
        climate_ocean_mask=ocean,
        ocean_elevation_m=climate.elevation_m,
    )
    e2 = climate_grid_land_elevation(
        elev_terrain_v2,
        ocean_terrain,
        w,
        h,
        climate_ocean_mask=ocean,
        ocean_elevation_m=climate.elevation_m,
    )
    elev_new = np.where(ocean, climate.elevation_m, e2)
    delta_km = (elev_new - climate.elevation_m) / 1000.0
    dT = -lapse_rate_c_per_km * np.where(ocean, 0.0, delta_km)
    dT3 = dT[np.newaxis, :, :]

    temp = np.asarray(climate.temperature_c, dtype=np.float64) + dT3
    updated = ["temperature_c"]
    base = climate.temperature_base_c
    if base is not None:
        base = np.asarray(base, dtype=np.float64) + dT3
        updated.append(TEMPERATURE_STATE_BASE)
    else:
        base = temp.copy()
        updated.append(TEMPERATURE_STATE_BASE)
    eq = climate.temperature_equilibrium_c
    if eq is not None:
        eq = np.asarray(eq, dtype=np.float64) + dT3
        updated.append(TEMPERATURE_STATE_EQUILIBRIUM)

    stats = temperature_diagnostics(
        temp,
        latitude_deg=climate.latitude_deg,
        elevation_m=elev_new,
        ocean_mask=ocean,
        state_name=TEMPERATURE_STATE_BASE,
    )
    diag = {
        **dict(climate.diagnostics),
        **stats,
        "climate_correction": "lapse_from_dem_v2",
        "lapse_owner": "final_dem_delta",
        "mean_abs_temp_delta_c": float(np.mean(np.abs(dT[~ocean])))
        if np.any(~ocean)
        else 0.0,
        "elev_v1_climate_mean": float(e1[~ocean].mean()) if np.any(~ocean) else 0.0,
        "elev_v2_climate_mean": float(e2[~ocean].mean()) if np.any(~ocean) else 0.0,
        "temperature_states_updated": updated,
        "temperature_provenance": {
            "equilibrium": TEMPERATURE_STATE_EQUILIBRIUM,
            "pre_sst_base": TEMPERATURE_STATE_BASE,
            "published": TEMPERATURE_STATE_BASE,
        },
    }
    prior_lapse = int(diag.get("lapse_apply_count", 1) or 1)
    diag["lapse_apply_count"] = prior_lapse + 1
    return replace_climate_temperature(
        climate,
        temp,
        diagnostics=diag,
        elevation_m=elev_new,
        temperature_equilibrium_c=eq,
        temperature_base_c=base,
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
    gm = grid_metrics(tw, th, radius_km=params.moisture.planet_radius_km)
    cell_len_km = float(np.sqrt(max(gm.cell_area_km2, 0.0)))
    path_length_km = np.maximum(
        gm.d8_step_length_km_field(np.full((th, tw), 1, dtype=np.uint8)),
        cell_len_km,
    )
    geomorphic = getattr(
        hydrology_v1,
        "geomorphic_channel_mask",
        hydrology_v1.channel_mask,
    )
    oro = act = None
    if interpretation is not None:
        oro = upsample_bilinear_cylindrical(interpretation.orogenic_potential, tw, th)
        act = upsample_bilinear_cylindrical(interpretation.tectonic_activity, tw, th)
    resistance = rock_resistance_proxy(
        orogenic_potential=oro,
        tectonic_activity=act,
        shape=(th, tw),
    )

    elev_v2, fluvial_process = apply_fluvial_erosion(
        elevation_m=erosion_v1.elevation_m,
        ocean_mask=erosion_v1.ocean_mask,
        geomorphic_channel_mask=geomorphic,
        discharge_proxy=hydrology_v1.river_discharge_proxy,
        resistance=resistance,
        step_length_km=path_length_km,
        iterations=params.fluvial_iterations,
        stream_power_k=params.stream_power_k,
        max_step_m=params.stream_power_max_step_m,
        macro_blend=params.stream_power_macro_blend,
        planet_radius_km=params.moisture.planet_radius_km,
        micro_fill_max_depth_m=params.micro_fill_max_depth_m,
    )
    delta = fluvial_process.total_erosion_delta_m

    if reporter is not None:
        reporter.progress("final", 0.25)

    ocean = erosion_v1.ocean_mask
    land = ~ocean
    fluvial_stats = land_elevation_delta_stats(
        erosion_v1.elevation_m, elev_v2, ocean
    )
    corr = _macro_relief_correlation(erosion_v1.elevation_m, elev_v2, ocean)
    elev_range = float(fluvial_stats["elev_range_land_m"])
    mean_abs = float(fluvial_stats["mean_abs_delta_land_m"])
    max_abs = float(fluvial_stats["max_abs_delta_land_m"])
    mean_before = float(np.mean(erosion_v1.elevation_m[land])) if np.any(land) else 0.0
    mean_after = float(np.mean(elev_v2[land])) if np.any(land) else 0.0
    mean_drop_frac = (mean_before - mean_after) / elev_range
    corridor_mean = domain_mean_abs_delta(
        fluvial_process.final_stream_power_delta_m,
        geomorphic,
        ocean,
    )
    fluvial_nontrivial, fluvial_min_required = fluvial_corridor_erosion_gate(
        corridor_mean, elev_range
    )
    fluvial_proc_stats = process_delta_stats(
        fluvial_process,
        ocean,
        geomorphic_mask=geomorphic,
        elev_range_m=elev_range,
        elev_before_m=erosion_v1.elevation_m,
        elev_after_m=elev_v2,
    )

    climate_c = correct_climate_for_dem(
        climate_v1,
        elev_terrain_v1=erosion_v1.elevation_m,
        elev_terrain_v2=elev_v2,
        ocean_terrain=ocean,
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
    climate_c = restamp_temperature_diagnostics(
        climate_c,
        state_name=TEMPERATURE_STATE_FINAL,
        extra={
            "provenance_lapse_then_sst": True,
            "sst_owner": "ocean_coupling",
        },
    )
    # CR-1: pass the full MoistureParams (PR-7/PR-8 knobs included). Do not
    # rebuild a partial dataclass — that silently dropped plume/ITCZ/monsoon.
    moisture_params = replace(params.moisture, months=params.months)
    # First pass (ocean/land only) drives hydrology; lakes/rivers do not exist yet.
    moisture_hydro = build_moisture(
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
    hydrology_h1 = build_hydrology(
        erosion=erosion_view,
        moisture=moisture_hydro,
        params=params.hydrology,
        temperature_c=climate_c.temperature_c,
    )

    # M2: fractional lake/river evaporation from H1 actual water.
    ch, cw = climate_c.ocean_mask.shape
    lake_frac, river_frac = _climate_inland_fractions(hydrology_h1, cw, ch)
    q_m1 = np.asarray(moisture_hydro.atmospheric_moisture[-1], dtype=np.float64)
    store_m1 = (
        np.asarray(moisture_hydro.land_store[-1], dtype=np.float64)
        if moisture_hydro.land_store is not None
        and moisture_hydro.land_store.ndim == 3
        else None
    )
    moisture_m2 = build_moisture(
        climate=climate_c,
        atmosphere=atmosphere,
        ocean=ocean_circ,
        params=moisture_params,
        lake_fraction=lake_frac,
        river_fraction=river_frac,
        q_init=q_m1,
        land_store_init=store_m1,
    )

    # H2: same DEM / drainage topology, M2 precipitation.
    hydrology_h2 = build_hydrology(
        erosion=erosion_view,
        moisture=moisture_m2,
        params=params.hydrology,
        temperature_c=climate_c.temperature_c,
    )
    metrics_h2 = coupling_metrics(hydrology_h1, hydrology_h2)
    blend = float(np.clip(params.hydro_evap_blend, 0.0, 1.0))
    coupling: dict[str, Any] = {
        **metrics_h2,
        "hydro_evap_blend": blend,
        "hydro_evap_iteration": 1,
        "coupling_damped_pass": False,
        "coupling_nonconverged": False,
        "moisture_water_source": "published_hydrology",
        "hydro_precip_source": "m2",
        "h1_lake_checksum": array_checksum(hydrology_h1.lake_mask),
        "m2_precip_checksum": array_checksum(moisture_m2.precipitation),
    }

    hydrology = hydrology_h2
    hydro_input_precip = moisture_m2.precipitation
    if not metrics_h2["coupling_converged"]:
        precip_blend = (
            (1.0 - blend) * moisture_hydro.precipitation
            + blend * moisture_m2.precipitation
        )
        moisture_damped = MoistureResult(
            extent=moisture_m2.extent,
            atmospheric_moisture=moisture_m2.atmospheric_moisture,
            evaporation=moisture_m2.evaporation,
            precipitation=precip_blend,
            humidity=moisture_m2.humidity,
            orographic_lift=moisture_m2.orographic_lift,
            convective_precip=moisture_m2.convective_precip,
            annual_precipitation=precip_blend.sum(axis=0),
            diagnostics={
                **dict(moisture_m2.diagnostics),
                "moisture_role": "moisture_hydrology_damped",
                "hydro_evap_blend": blend,
            },
            land_store=moisture_m2.land_store,
        )
        hydrology_h3 = build_hydrology(
            erosion=erosion_view,
            moisture=moisture_damped,
            params=params.hydrology,
            temperature_c=climate_c.temperature_c,
        )
        metrics_h3 = coupling_metrics(hydrology_h2, hydrology_h3)
        hydrology = hydrology_h3
        hydro_input_precip = precip_blend
        coupling.update(
            {
                "hydro_evap_iteration": 2,
                "coupling_damped_pass": True,
                "hydro_precip_source": "damped_blend",
                "damped_lake_mask_jaccard": metrics_h3["lake_mask_jaccard"],
                "damped_effective_q_rel_change": metrics_h3["effective_q_rel_change"],
                "coupling_nonconverged": not bool(metrics_h3["coupling_converged"]),
                "lake_mask_jaccard": metrics_h3["lake_mask_jaccard"],
                "effective_q_rel_change": metrics_h3["effective_q_rel_change"],
                "coupling_converged": bool(metrics_h3["coupling_converged"]),
            }
        )

    # Published moisture uses H1 fractional water (M2). When H2 has converged
    # against H1, those masks are bounded-consistent. A third spin-up is not
    # started; checksums record hydro vs moisture provenance.
    moisture = moisture_m2
    coupling["moisture_water_source"] = "h1_fractions_m2"
    coupling["published_lake_checksum"] = array_checksum(hydrology.lake_mask)
    coupling["published_moisture_precip_checksum"] = array_checksum(
        moisture.precipitation
    )
    coupling["hydro_input_precip_checksum"] = array_checksum(hydro_input_precip)
    coupling["moisture_vs_hydro_lake_jaccard"] = binary_jaccard(
        hydrology_h1.lake_mask, hydrology.lake_mask
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
    channel_jaccard = binary_jaccard(
        geomorphic,
        getattr(hydrology, "geomorphic_channel_mask", hydrology.channel_mask),
    )
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
        "stream_power_k": float(params.stream_power_k),
        "stream_power_k_role": "final_river_incision",
        "stream_power_max_step_m": float(params.stream_power_max_step_m),
        "stream_power_macro_blend": float(params.stream_power_macro_blend),
        "micro_fill_max_depth_m": float(params.micro_fill_max_depth_m),
        "median_abs_fluvial_delta_m": float(fluvial_stats["median_abs_delta_land_m"]),
        "p90_abs_fluvial_delta_m": float(fluvial_stats["p90_abs_delta_land_m"]),
        "fluvial_erosion_nontrivial": fluvial_nontrivial,
        "fluvial_corridor_mean_abs_delta_m": corridor_mean,
        **fluvial_proc_stats,
        "geomorphic_channel_jaccard_pre_post": float(channel_jaccard),
        "conditioning_separate_ok": bool(
            fluvial_proc_stats.get("conditioning_separate_ok", False)
        ),
        "ocean_mask_unchanged": bool(np.array_equal(elev_v2[ocean], erosion_v1.elevation_m[ocean])),
        "climate_land_elev_min_m": float(np.min(climate_c.elevation_m[~climate_c.ocean_mask]))
        if np.any(~climate_c.ocean_mask)
        else 0.0,
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
        "hydro_evap_iteration": int(coupling.get("hydro_evap_iteration", 1)),
        "hydro_evap_blend": float(coupling.get("hydro_evap_blend", 0.0)),
        "lake_mask_jaccard": float(coupling.get("lake_mask_jaccard", 1.0)),
        "effective_q_rel_change": float(coupling.get("effective_q_rel_change", 0.0)),
        "coupling_converged": bool(coupling.get("coupling_converged", False)),
        "coupling_damped_pass": bool(coupling.get("coupling_damped_pass", False)),
        "coupling_nonconverged": bool(coupling.get("coupling_nonconverged", False)),
        "h1_lake_checksum": coupling.get("h1_lake_checksum"),
        "published_lake_checksum": coupling.get("published_lake_checksum"),
        "m2_precip_checksum": coupling.get("m2_precip_checksum"),
        "published_moisture_precip_checksum": coupling.get(
            "published_moisture_precip_checksum"
        ),
        "moisture_water_source": coupling.get("moisture_water_source"),
        "hydro_precip_source": coupling.get("hydro_precip_source"),
        "fluvial_min_mean_abs_delta_m": fluvial_min_required,
        "erosion_algorithm": "pc4_process_deltas_v1",
        "micro_depressions_conditioned": True,
        "slope_algorithm": "metric_gridmetrics_v1",
        "final_stage_acceptance_ok": bool(
            stable
            and no_catastrophe
            and landforms_ok
            and fluvial_nontrivial
            and bool(fluvial_proc_stats.get("conditioning_excluded_from_erosion_acceptance"))
            and bool(fluvial_proc_stats.get("erosion_delta_identity_ok", False))
        ),
        "acceptance_ok": bool(
            stable
            and no_catastrophe
            and landforms_ok
            and fluvial_nontrivial
            and bool(fluvial_proc_stats.get("conditioning_excluded_from_erosion_acceptance"))
            and bool(fluvial_proc_stats.get("erosion_delta_identity_ok", False))
        ),
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
