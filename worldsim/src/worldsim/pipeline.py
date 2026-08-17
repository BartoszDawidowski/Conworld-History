"""Generation pipeline orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from worldsim.config import PlanetConfig
from worldsim.physical.tectonics import (
    PyPlatecParams,
    run_pyplatec_extended,
    run_tectonic_interpretation,
)
from worldsim.physical.tectonics.interpretation import TectonicsInterpretationResult
from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.atmosphere.pipeline import AtmosphereResult
from worldsim.physical.climate import ClimateParams, build_base_climate
from worldsim.physical.climate.pipeline import ClimateResult
from worldsim.physical.ocean import OceanParams, OceanResult, build_ocean_circulation
from worldsim.physical.moisture import MoistureParams, MoistureResult, build_moisture
from worldsim.physical.erosion import ErosionParams, ErosionResult, build_erosion_pass_one
from worldsim.physical.hydrology import (
    HydrologyResult,
    build_hydrology,
)
from worldsim.physical.vectorize import VectorGeographyResult, build_vector_geography
from worldsim.physical.final import (
    FinalRecalcParams,
    FinalRecalcResult,
    build_final_recalculation,
)
from worldsim.physical.ecology import EcologyResult, build_ecology
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.progress import ProgressReporter
from worldsim.seeds import SeedManifest, build_seed_manifest
from worldsim.spatial.coordinates import CoordinateSystem
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.hex_grid import HexAnalysisResult, build_hex_analysis_grid
from worldsim.spatial.model import WorldSpatialModel, build_world_spatial_model
from worldsim.export import export_atlas_display
from worldsim.environment_timeline import build_environment_timeline
from worldsim.state import PhysicalWorldState

FOUNDATION_STAGES: tuple[str, ...] = (
    "bootstrap",
    "seed_manifest",
)


def _bootstrap_state(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    milestone: int,
    dry_run: bool,
) -> PhysicalWorldState:
    coordinates = CoordinateSystem(
        wrap_x=config.wrap_x,
        wrap_y=config.wrap_y,
        projection=config.projection,
    )
    extents = {
        "tectonics": SpatialExtent.from_planet_config(config, "tectonics"),
        "climate": SpatialExtent.from_planet_config(config, "climate"),
        "terrain": SpatialExtent.from_planet_config(config, "terrain_production"),
        "terrain_target": SpatialExtent.from_planet_config(config, "terrain_target"),
        "hydrology": SpatialExtent.from_planet_config(config, "hydrology"),
        "analysis": SpatialExtent.from_planet_config(config, "analysis"),
    }
    return PhysicalWorldState(
        config=config,
        seeds=build_seed_manifest(master_seed, schema_version=config.schema_version),
        coordinates=coordinates,
        extents=extents,
        metadata={
            "dry_run": dry_run,
            "milestone": milestone,
            "output_dir": str(output_dir),
        },
    )


def run_foundation(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    dry_run: bool = True,
) -> PhysicalWorldState:
    """Milestone 0 worker path: seeds + protocol + output skeleton."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reporter.started(seed=master_seed, schema_version=config.schema_version)

    reporter.stage_started("bootstrap")
    reporter.progress("bootstrap", 0.5)
    state = _bootstrap_state(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        milestone=0,
        dry_run=dry_run,
    )
    reporter.progress("bootstrap", 1.0)
    reporter.stage_complete("bootstrap")

    reporter.stage_started("seed_manifest")
    state.seeds.write_json(output_dir / "seed_manifest.json")
    (output_dir / "README.txt").write_text(
        "Foundation output (seeds + config extents).\n"
        "Use --stage tectonics for Milestone 2 PyPlatec baseline.\n",
        encoding="utf-8",
    )
    reporter.progress("seed_manifest", 1.0)
    reporter.stage_complete("seed_manifest")

    reporter.complete(str(output_dir))
    return state


def run_tectonics(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
) -> PhysicalWorldState:
    """Milestone 2–4 path: PyPlatec extended maps + tectonic interpretation."""
    state, _interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=4,
    )
    (output_dir / "README.txt").write_text(
        "Milestone 4 tectonics + interpretation output.\n"
        "See tectonics/ for elevation/plates/age/velocity and interpretation rasters.\n"
        f"metadata_source={state.metadata.get('tectonics_metadata_source')}\n"
        f"boundary_cells={state.metadata.get('boundary_cell_count')}\n"
        "High-resolution terrain (Milestone 5) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "tectonics",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "width": width,
                "height": height,
                "seam_column": state.metadata.get("seam_column"),
                "metadata_source": state.metadata.get("tectonics_metadata_source"),
                "interpretation": True,
                "boundary_cell_count": state.metadata.get("boundary_cell_count"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir.resolve()))
    return state


def _attach_terrain(
    state: PhysicalWorldState,
    terrain: TerrainOceanResult,
    *,
    tw: int,
    th: int,
) -> None:
    state.terrain = terrain
    state.rasters["elevation_m"] = terrain.elevation_m
    state.rasters["ocean_mask"] = terrain.ocean_mask
    state.rasters["ocean_depth_m"] = terrain.ocean_depth_m
    state.rasters["shelf_mask"] = terrain.shelf_mask
    state.rasters["water_body_id"] = terrain.water_body_id
    state.rasters["ocean_basin_id"] = terrain.ocean_basin_id
    state.rasters["coast_distance"] = terrain.coast_distance
    state.vectors["coastline"] = terrain.coastline_features
    state.metadata["terrain_resolution"] = [tw, th]
    state.metadata["ocean_fraction"] = terrain.ocean_fraction
    state.metadata["sea_level_raw"] = terrain.sea_level_raw
    state.metadata["coastline_feature_count"] = len(terrain.coastline_features)


def _build_terrain_for_state(
    state: PhysicalWorldState,
    interpretation: TectonicsInterpretationResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
    terrain_width: int | None,
    terrain_height: int | None,
) -> tuple[TerrainOceanResult, int, int]:
    assert state.tectonics is not None
    tw = int(terrain_width if terrain_width is not None else config.terrain_production[0])
    th = int(
        terrain_height if terrain_height is not None else config.terrain_production[1]
    )
    detail_seed = int(state.seeds.modules["terrain_detail"]) & 0xFFFFFFFF
    terrain = build_terrain_ocean(
        tectonics=state.tectonics,
        interpretation=interpretation,
        params=TerrainParams(
            width=tw,
            height=th,
            ocean_fraction_target=config.ocean_fraction_target,
            detail_amplitude=config.terrain_detail_amplitude,
            land_scale_m=config.land_scale_m,
            ocean_scale_m=config.ocean_scale_m,
            orogeny_boost=config.orogeny_boost,
            activity_relief=config.activity_relief,
            boundary_relief=config.boundary_relief,
            hypsometry_mode=config.hypsometry_mode,
            hypsometry_anchor_quantile=config.hypsometry_anchor_quantile,
            hypsometry_anchor_elevation_m=config.hypsometry_anchor_elevation_m,
            hypsometry_body_exponent=config.hypsometry_body_exponent,
            hypsometry_max_elevation_m=config.hypsometry_max_elevation_m,
            hypsometry_tail_softness=config.hypsometry_tail_softness,
        ),
        detail_seed=detail_seed,
        reporter=reporter,
    )
    return terrain, tw, th


def run_terrain(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 5 path: tectonics + interpretation + high-res terrain/ocean."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=5,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    (output_dir / "README.txt").write_text(
        "Milestone 5 terrain/ocean output.\n"
        "See tectonics/ and terrain/ artefacts.\n"
        f"terrain_resolution={tw}x{th}\n"
        f"ocean_fraction={terrain.ocean_fraction:.4f} "
        f"(target {config.ocean_fraction_target})\n"
        f"coastline_features={len(terrain.coastline_features)}\n"
        "Climate (Milestone 6) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "terrain",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "ocean_fraction": terrain.ocean_fraction,
                "ocean_fraction_target": config.ocean_fraction_target,
                "seam_gap_relative": terrain.diagnostics.get("seam_gap_relative"),
                "coastline_feature_count": len(terrain.coastline_features),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_climate(
    state: PhysicalWorldState,
    climate: ClimateResult,
    *,
    cw: int,
    ch: int,
) -> None:
    state.climate = climate
    state.rasters["temperature_c"] = climate.temperature_c
    state.rasters["insolation"] = climate.insolation
    state.rasters["latitude_deg"] = climate.latitude_deg
    state.rasters["continentality"] = climate.continentality
    state.metadata["climate_resolution"] = [cw, ch]
    state.metadata["seasonal_inversion_ok"] = climate.diagnostics.get(
        "seasonal_inversion_ok"
    )


def _build_climate_for_state(
    state: PhysicalWorldState,
    terrain: TerrainOceanResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
    climate_width: int | None,
    climate_height: int | None,
) -> tuple[ClimateResult, int, int]:
    cw = int(climate_width if climate_width is not None else config.climate_resolution[0])
    ch = int(
        climate_height if climate_height is not None else config.climate_resolution[1]
    )
    lengths = config.resolve_length_units()
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(
            width=cw,
            height=ch,
            months=config.climate_months,
            axial_tilt_deg=config.axial_tilt_deg,
            base_temp_c=config.base_temp_c,
            continentality_scale_km=float(
                lengths.resolved["continentality_scale_km"].value_km
            ),
            planet_radius_km=config.planet_radius_km,
        ),
        reporter=reporter,
    )
    return climate, cw, ch


def run_climate(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 6 path: terrain + base seasonal climate (no atmosphere yet)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=6,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    (output_dir / "README.txt").write_text(
        "Milestone 6 base seasonal climate output.\n"
        "See tectonics/, terrain/, and climate/ artefacts.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"temperature_range_c="
        f"[{climate.diagnostics['temperature_min_c']:.1f}, "
        f"{climate.diagnostics['temperature_max_c']:.1f}]\n"
        f"seasonal_inversion_ok={climate.diagnostics.get('seasonal_inversion_ok')}\n"
        "Atmosphere / winds (Milestone 7) are not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "climate",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "ocean_fraction": terrain.ocean_fraction,
                "seasonal_inversion_ok": climate.diagnostics.get(
                    "seasonal_inversion_ok"
                ),
                "polar_colder_than_tropics": climate.diagnostics.get(
                    "polar_colder_than_tropics"
                ),
                "elevation_trend_ok": climate.diagnostics.get("elevation_trend_ok"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def run_atmosphere(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 7 path: climate + atmospheric circulation (no ocean currents)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=7,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    (output_dir / "README.txt").write_text(
        "Milestone 7 atmosphere output.\n"
        "See tectonics/, terrain/, climate/, and atmosphere/ artefacts.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"itcz_june={atmosphere.diagnostics.get('itcz_june_deg'):.2f} "
        f"itcz_dec={atmosphere.diagnostics.get('itcz_december_deg'):.2f}\n"
        f"zonal_tendencies_ok="
        f"{atmosphere.diagnostics.get('expected_zonal_tendencies_ok')}\n"
        "Ocean circulation (Milestone 8) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "atmosphere",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "expected_zonal_tendencies_ok": atmosphere.diagnostics.get(
                    "expected_zonal_tendencies_ok"
                ),
                "trades_easterly": atmosphere.diagnostics.get("trades_easterly"),
                "ferrel_westerly": atmosphere.diagnostics.get("ferrel_westerly"),
                "polar_easterly": atmosphere.diagnostics.get("polar_easterly"),
                "itcz_june_deg": atmosphere.diagnostics.get("itcz_june_deg"),
                "itcz_december_deg": atmosphere.diagnostics.get("itcz_december_deg"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_atmosphere(state: PhysicalWorldState, atmosphere: AtmosphereResult) -> None:
    state.atmosphere = atmosphere
    state.rasters["pressure_proxy"] = atmosphere.pressure_proxy
    state.rasters["wind_u"] = atmosphere.wind_u
    state.rasters["wind_v"] = atmosphere.wind_v
    state.rasters["circulation_zone"] = atmosphere.circulation_zone
    state.metadata["expected_zonal_tendencies_ok"] = atmosphere.diagnostics.get(
        "expected_zonal_tendencies_ok"
    )


def _build_atmosphere_for_state(
    climate: ClimateResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
) -> AtmosphereResult:
    return build_atmosphere(
        climate=climate,
        params=AtmosphereParams(
            axial_tilt_deg=config.axial_tilt_deg,
            months=config.climate_months,
        ),
        reporter=reporter,
    )


def _attach_ocean(state: PhysicalWorldState, ocean: OceanResult) -> None:
    state.ocean = ocean
    state.rasters["current_u"] = ocean.current_u
    state.rasters["current_v"] = ocean.current_v
    state.rasters["sst_c"] = ocean.sst_c
    state.rasters["temperature_coupled_c"] = ocean.temperature_coupled_c
    state.rasters["ocean_basin_id_climate"] = ocean.ocean_basin_id
    state.metadata["ocean_no_land_crossing"] = ocean.diagnostics.get("no_land_crossing")
    state.metadata["ocean_acceptance_ok"] = ocean.diagnostics.get("acceptance_ok")


def run_ocean(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 8 path: atmosphere + ocean circulation / SST (no moisture)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=8,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    (output_dir / "README.txt").write_text(
        "Milestone 8 ocean circulation output.\n"
        "See tectonics/, terrain/, climate/, atmosphere/, and ocean/ artefacts.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"no_land_crossing={ocean.diagnostics.get('no_land_crossing')}\n"
        f"coherent_circulation={ocean.diagnostics.get('coherent_circulation')}\n"
        f"acceptance_ok={ocean.diagnostics.get('acceptance_ok')}\n"
        "Moisture / precipitation (Milestone 9) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "ocean",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "no_land_crossing": ocean.diagnostics.get("no_land_crossing"),
                "coherent_circulation": ocean.diagnostics.get("coherent_circulation"),
                "equatorial_westward": ocean.diagnostics.get("equatorial_westward"),
                "acceptance_ok": ocean.diagnostics.get("acceptance_ok"),
                "basin_count": ocean.diagnostics.get("basin_count"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _build_ocean_for_state(
    climate: ClimateResult,
    atmosphere: AtmosphereResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
) -> OceanResult:
    return build_ocean_circulation(
        climate=climate,
        atmosphere=atmosphere,
        params=config.to_ocean_params(),
        reporter=reporter,
    )


def _attach_moisture(state: PhysicalWorldState, moisture: MoistureResult) -> None:
    state.moisture = moisture
    state.rasters["atmospheric_moisture"] = moisture.atmospheric_moisture
    state.rasters["evaporation"] = moisture.evaporation
    state.rasters["precipitation"] = moisture.precipitation
    state.rasters["humidity"] = moisture.humidity
    state.rasters["annual_precipitation"] = moisture.annual_precipitation
    state.metadata["moisture_acceptance_ok"] = moisture.diagnostics.get("acceptance_ok")
    state.metadata["windward_leeward_ok"] = moisture.diagnostics.get(
        "windward_leeward_ok"
    )


def run_moisture(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 9 path: ocean + moisture transport / precipitation (no erosion)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=9,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    moisture = _build_moisture_for_state(
        climate, atmosphere, ocean, config=config, reporter=reporter
    )
    moisture.save(output_dir / "moisture")
    _attach_moisture(state, moisture)

    (output_dir / "README.txt").write_text(
        "Milestone 9 moisture / precipitation output.\n"
        "See tectonics/, terrain/, climate/, atmosphere/, ocean/, moisture/.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"windward_leeward_ok={moisture.diagnostics.get('windward_leeward_ok')}\n"
        f"earth_like_wet_dry_ok={moisture.diagnostics.get('earth_like_wet_dry_ok')}\n"
        f"acceptance_ok={moisture.diagnostics.get('acceptance_ok')}\n"
        "Erosion pass one (Milestone 10) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "moisture",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "downwind_moisture_transport_ok": moisture.diagnostics.get(
                    "downwind_moisture_transport_ok"
                ),
                "windward_leeward_ok": moisture.diagnostics.get("windward_leeward_ok"),
                "earth_like_wet_dry_ok": moisture.diagnostics.get(
                    "earth_like_wet_dry_ok"
                ),
                "acceptance_ok": moisture.diagnostics.get("acceptance_ok"),
                "annual_precip_mean": moisture.diagnostics.get("annual_precip_mean"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _build_moisture_for_state(
    climate: ClimateResult,
    atmosphere: AtmosphereResult,
    ocean: OceanResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
) -> MoistureResult:
    return build_moisture(
        climate=climate,
        atmosphere=atmosphere,
        ocean=ocean,
        params=config.to_moisture_params(),
        reporter=reporter,
    )


def _attach_erosion(state: PhysicalWorldState, erosion: ErosionResult) -> None:
    state.erosion = erosion
    state.rasters["dem_v1"] = erosion.elevation_m
    state.rasters["elevation_before_erosion_m"] = erosion.elevation_before_m
    state.rasters["erosion_delta_m"] = erosion.erosion_delta_m
    state.rasters["slope"] = erosion.slope
    state.rasters["rock_resistance"] = erosion.rock_resistance
    state.metadata["erosion_acceptance_ok"] = erosion.diagnostics.get("acceptance_ok")
    state.metadata["macro_relief_preserved"] = erosion.diagnostics.get(
        "macro_relief_preserved"
    )
    state.metadata["drainage_quality_improved"] = erosion.diagnostics.get(
        "drainage_quality_improved"
    )


def run_erosion(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 10 path: moisture + first erosion pass / DEM v1 (no hydrology)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=10,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    moisture = _build_moisture_for_state(
        climate, atmosphere, ocean, config=config, reporter=reporter
    )
    moisture.save(output_dir / "moisture")
    _attach_moisture(state, moisture)

    erosion = _build_erosion_for_state(
        terrain, moisture, interpretation, config=config, reporter=reporter
    )
    erosion.save(output_dir / "erosion")
    _attach_erosion(state, erosion)

    (output_dir / "README.txt").write_text(
        "Milestone 10 erosion pass one / DEM v1 output.\n"
        "See tectonics/ … moisture/ and erosion/ artefacts.\n"
        f"terrain_resolution={tw}x{th}\n"
        f"drainage_quality_improved="
        f"{erosion.diagnostics.get('drainage_quality_improved')}\n"
        f"macro_relief_preserved={erosion.diagnostics.get('macro_relief_preserved')}\n"
        f"acceptance_ok={erosion.diagnostics.get('acceptance_ok')}\n"
        "Hydrology / PyFlwDir (Milestone 11) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "erosion",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "drainage_quality_improved": erosion.diagnostics.get(
                    "drainage_quality_improved"
                ),
                "macro_relief_preserved": erosion.diagnostics.get(
                    "macro_relief_preserved"
                ),
                "roughness_reduced": erosion.diagnostics.get("roughness_reduced"),
                "local_minima_before": erosion.diagnostics.get("local_minima_before"),
                "local_minima_after": erosion.diagnostics.get("local_minima_after"),
                "acceptance_ok": erosion.diagnostics.get("acceptance_ok"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _build_erosion_for_state(
    terrain: TerrainOceanResult,
    moisture: MoistureResult,
    interpretation: TectonicsInterpretationResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
) -> ErosionResult:
    return build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(
            iterations=config.erosion_iterations,
            fluvial_k=config.erosion_fluvial_k,
        ),
        reporter=reporter,
    )


def _attach_hydrology(state: PhysicalWorldState, hydrology: HydrologyResult) -> None:
    state.hydrology = hydrology
    state.rasters["dem_conditioned_m"] = hydrology.dem_conditioned_m
    state.rasters["flow_direction"] = hydrology.flow_direction
    state.rasters["flow_accumulation"] = hydrology.flow_accumulation
    state.rasters["basin_id"] = hydrology.basin_id
    state.rasters["watershed_id"] = hydrology.watershed_id
    state.rasters["stream_order"] = hydrology.stream_order
    state.rasters["river_mask"] = hydrology.river_mask
    state.rasters["river_discharge_proxy"] = hydrology.river_discharge_proxy
    state.rasters["river_discharge_gross"] = hydrology.river_discharge_gross
    state.rasters["monthly_discharge"] = hydrology.monthly_discharge
    state.rasters["lake_mask"] = hydrology.lake_mask
    state.rasters["lake_id"] = hydrology.lake_id
    state.metadata["hydrology_acceptance_ok"] = hydrology.diagnostics.get(
        "acceptance_ok"
    )
    state.metadata["drainage_graph_valid"] = hydrology.diagnostics.get(
        "drainage_graph_valid"
    )


def run_hydrology(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 11 path: DEM v1 + PyFlwDir hydrology (no vector geography)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=11,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    moisture = _build_moisture_for_state(
        climate, atmosphere, ocean, config=config, reporter=reporter
    )
    moisture.save(output_dir / "moisture")
    _attach_moisture(state, moisture)

    erosion = _build_erosion_for_state(
        terrain, moisture, interpretation, config=config, reporter=reporter
    )
    erosion.save(output_dir / "erosion")
    _attach_erosion(state, erosion)

    hydrology = _build_hydrology_for_state(
        erosion, moisture, config=config, reporter=reporter, climate=climate
    )
    hydrology.save(output_dir / "hydrology")
    _attach_hydrology(state, hydrology)

    (output_dir / "README.txt").write_text(
        "Milestone 11 PyFlwDir hydrology output.\n"
        "See tectonics/ … erosion/ and hydrology/ artefacts.\n"
        f"terrain_resolution={tw}x{th}\n"
        f"drainage_graph_valid={hydrology.diagnostics.get('drainage_graph_valid')}\n"
        f"sensible_accumulation="
        f"{hydrology.diagnostics.get('sensible_accumulation_downstream')}\n"
        f"acceptance_ok={hydrology.diagnostics.get('acceptance_ok')}\n"
        "Canonical vector geography (Milestone 12) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "hydrology",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "drainage_graph_valid": hydrology.diagnostics.get(
                    "drainage_graph_valid"
                ),
                "downstream_accumulation_ok": hydrology.diagnostics.get(
                    "downstream_accumulation_ok"
                ),
                "sensible_accumulation_downstream": hydrology.diagnostics.get(
                    "sensible_accumulation_downstream"
                ),
                "basin_count": hydrology.diagnostics.get("basin_count"),
                "river_cell_count": hydrology.diagnostics.get("river_cell_count"),
                "lake_count": hydrology.diagnostics.get("lake_count"),
                "acceptance_ok": hydrology.diagnostics.get("acceptance_ok"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _build_hydrology_for_state(
    erosion: ErosionResult,
    moisture: MoistureResult,
    *,
    config: PlanetConfig,
    reporter: ProgressReporter,
    climate: ClimateResult | None = None,
) -> HydrologyResult:
    return build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=config.to_hydrology_params(),
        reporter=reporter,
        temperature_c=None if climate is None else climate.temperature_c,
    )


def _attach_vectors(state: PhysicalWorldState, vectors: VectorGeographyResult) -> None:
    state.vectors["coastline"] = vectors.coastline
    state.vectors["rivers"] = vectors.rivers
    state.vectors["lakes"] = vectors.lakes
    state.vectors["basins"] = vectors.basins
    state.vectors["spatial_index"] = vectors.spatial_index
    state.metadata["vector_acceptance_ok"] = vectors.diagnostics.get("acceptance_ok")
    state.metadata["river_topology_valid"] = vectors.diagnostics.get(
        "river_topology_valid"
    )


def run_vectors(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 12 path: hydrology + canonical vector geography (no fluvial feedback)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=12,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    moisture = _build_moisture_for_state(
        climate, atmosphere, ocean, config=config, reporter=reporter
    )
    moisture.save(output_dir / "moisture")
    _attach_moisture(state, moisture)

    erosion = _build_erosion_for_state(
        terrain, moisture, interpretation, config=config, reporter=reporter
    )
    erosion.save(output_dir / "erosion")
    _attach_erosion(state, erosion)

    hydrology = _build_hydrology_for_state(
        erosion, moisture, config=config, reporter=reporter, climate=climate
    )
    hydrology.save(output_dir / "hydrology")
    _attach_hydrology(state, hydrology)

    vectors = build_vector_geography(
        hydrology=hydrology,
        terrain=terrain,
        reporter=reporter,
    )
    vectors.save(output_dir / "vectors")
    _attach_vectors(state, vectors)

    (output_dir / "README.txt").write_text(
        "Milestone 12 canonical vector physical geography.\n"
        "See tectonics/ … hydrology/ and vectors/ artefacts.\n"
        f"terrain_resolution={tw}x{th}\n"
        f"river_segments={vectors.diagnostics.get('river_segment_count')}\n"
        f"river_topology_valid={vectors.diagnostics.get('river_topology_valid')}\n"
        f"acceptance_ok={vectors.diagnostics.get('acceptance_ok')}\n"
        "Second erosion / feedback (Milestone 13) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "vectors",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "coastline_feature_count": vectors.diagnostics.get(
                    "coastline_feature_count"
                ),
                "river_segment_count": vectors.diagnostics.get("river_segment_count"),
                "lake_count": vectors.diagnostics.get("lake_count"),
                "river_topology_valid": vectors.diagnostics.get("river_topology_valid"),
                "acceptance_ok": vectors.diagnostics.get("acceptance_ok"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_final(state: PhysicalWorldState, final: FinalRecalcResult) -> None:
    state.rasters["dem_v2"] = final.elevation_v2_m
    state.rasters["fluvial_delta_m"] = final.fluvial_delta_m
    state.climate = final.climate
    state.atmosphere = final.atmosphere
    state.ocean = final.ocean
    state.moisture = final.moisture
    state.hydrology = final.hydrology
    _attach_vectors(state, final.vectors)
    state.metadata["final_acceptance_ok"] = final.diagnostics.get("acceptance_ok")
    state.metadata["stable_final_geography"] = final.diagnostics.get(
        "stable_final_geography"
    )
    state.metadata["no_catastrophic_feedback"] = final.diagnostics.get(
        "no_catastrophic_feedback"
    )


def _pipeline_through_final(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None,
    height: int | None,
    params: PyPlatecParams | None,
    terrain_width: int | None,
    terrain_height: int | None,
    climate_width: int | None,
    climate_height: int | None,
    milestone: int,
) -> tuple[PhysicalWorldState, TerrainOceanResult, FinalRecalcResult, int, int, int, int]:
    """Shared path through Milestone 13 artefacts (no README / complete)."""
    output_dir = output_dir.resolve()
    state, interpretation = _generate_tectonics_bundle(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        milestone=milestone,
    )
    terrain, tw, th = _build_terrain_for_state(
        state,
        interpretation,
        config=config,
        reporter=reporter,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
    )
    terrain.save(output_dir / "terrain")
    _attach_terrain(state, terrain, tw=tw, th=th)

    climate, cw, ch = _build_climate_for_state(
        state,
        terrain,
        config=config,
        reporter=reporter,
        climate_width=climate_width,
        climate_height=climate_height,
    )
    climate.save(output_dir / "climate")
    _attach_climate(state, climate, cw=cw, ch=ch)

    atmosphere = _build_atmosphere_for_state(climate, config=config, reporter=reporter)
    atmosphere.save(output_dir / "atmosphere")
    _attach_atmosphere(state, atmosphere)

    ocean = _build_ocean_for_state(
        climate, atmosphere, config=config, reporter=reporter
    )
    ocean.save(output_dir / "ocean")
    _attach_ocean(state, ocean)

    moisture = _build_moisture_for_state(
        climate, atmosphere, ocean, config=config, reporter=reporter
    )
    moisture.save(output_dir / "moisture")
    _attach_moisture(state, moisture)

    erosion = _build_erosion_for_state(
        terrain, moisture, interpretation, config=config, reporter=reporter
    )
    erosion.save(output_dir / "erosion")
    _attach_erosion(state, erosion)

    hydrology = _build_hydrology_for_state(
        erosion, moisture, config=config, reporter=reporter, climate=climate
    )
    hydrology.save(output_dir / "hydrology")
    _attach_hydrology(state, hydrology)

    vectors = build_vector_geography(
        hydrology=hydrology,
        terrain=terrain,
        reporter=reporter,
    )
    vectors.save(output_dir / "vectors")
    _attach_vectors(state, vectors)

    final = build_final_recalculation(
        erosion_v1=erosion,
        hydrology_v1=hydrology,
        climate_v1=climate,
        terrain=terrain,
        interpretation=interpretation,
        params=FinalRecalcParams(
            months=config.climate_months,
            axial_tilt_deg=config.axial_tilt_deg,
            ocean=config.to_ocean_params(),
            moisture=config.to_moisture_params(),
            hydrology=config.to_hydrology_params(),
            landforms=config.to_landform_params(),
        ),
        reporter=reporter,
    )
    final.save(output_dir / "final")
    _attach_final(state, final)
    return state, terrain, final, tw, th, cw, ch


def run_final(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 13 path: fluvial erosion + climate/hydro/vector recalculation."""
    state, _terrain, final, tw, th, cw, ch = _pipeline_through_final(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
        climate_width=climate_width,
        climate_height=climate_height,
        milestone=13,
    )

    (output_dir / "README.txt").write_text(
        "Milestone 13 fluvial erosion + final physical recalculation.\n"
        "See tectonics/ … vectors/ and final/ (terrain v2 + refreshed layers).\n"
        f"terrain_resolution={tw}x{th}\n"
        f"stable_final_geography={final.diagnostics.get('stable_final_geography')}\n"
        f"no_catastrophic_feedback={final.diagnostics.get('no_catastrophic_feedback')}\n"
        f"acceptance_ok={final.diagnostics.get('acceptance_ok')}\n"
        "Soils / Holdridge ecology (Milestone 14) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "final",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "stable_final_geography": final.diagnostics.get(
                    "stable_final_geography"
                ),
                "no_catastrophic_feedback": final.diagnostics.get(
                    "no_catastrophic_feedback"
                ),
                "macro_relief_correlation_v1_v2": final.diagnostics.get(
                    "macro_relief_correlation_v1_v2"
                ),
                "acceptance_ok": final.diagnostics.get("acceptance_ok"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_ecology(state: PhysicalWorldState, ecology: EcologyResult) -> None:
    state.ecology = ecology
    state.rasters["permeability"] = ecology.permeability
    state.rasters["soil_depth"] = ecology.soil_depth
    state.rasters["soil_moisture"] = ecology.soil_moisture
    state.rasters["fertility_proxy"] = ecology.fertility_proxy
    state.rasters["erosion_risk"] = ecology.erosion_risk
    state.rasters["biotemperature_c"] = ecology.biotemperature_c
    state.rasters["pet_ratio"] = ecology.pet_ratio
    state.rasters["holdridge_zone_id"] = ecology.holdridge_zone_id
    if ecology.biome_v2_class is not None:
        state.rasters["biome_v2_class"] = ecology.biome_v2_class
        state.rasters["frost_months"] = ecology.frost_months
    state.metadata["ecology_acceptance_ok"] = ecology.diagnostics.get("acceptance_ok")


def run_ecology(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 14 path: final geography + soils / Holdridge ecology."""
    state, _terrain, final, tw, th, cw, ch = _pipeline_through_final(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
        climate_width=climate_width,
        climate_height=climate_height,
        milestone=14,
    )

    ecology = build_ecology(
        climate=final.climate,
        moisture=final.moisture,
        hydrology=final.hydrology,
        elevation_terrain_m=final.elevation_v2_m,
        params=config.to_ecology_params(),
        reporter=reporter,
    )
    ecology.save(output_dir / "ecology")
    _attach_ecology(state, ecology)

    (output_dir / "README.txt").write_text(
        "Milestone 14 soils + Holdridge ecology.\n"
        "See tectonics/ … final/ and ecology/ artefacts.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"all_cells_classified={ecology.diagnostics.get('all_cells_classified')}\n"
        f"acceptance_ok={ecology.diagnostics.get('acceptance_ok')}\n"
        "Analytical hex grid (Milestone 15) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "ecology",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "all_cells_classified": ecology.diagnostics.get("all_cells_classified"),
                "acceptance_ok": ecology.diagnostics.get("acceptance_ok"),
                "biotemperature_min_c": ecology.diagnostics.get("biotemperature_min_c"),
                "biotemperature_max_c": ecology.diagnostics.get("biotemperature_max_c"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_hex(state: PhysicalWorldState, hex_grid: HexAnalysisResult) -> None:
    state.analysis_grid = hex_grid
    state.metadata["hex_n_cells"] = hex_grid.n_cells
    state.metadata["hex_acceptance_ok"] = hex_grid.diagnostics.get("acceptance_ok")
    state.metadata["hex_production_acceptance_ok"] = hex_grid.diagnostics.get(
        "production_acceptance_ok"
    )


def run_hex(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 15 path: ecology + 256×128 analytical hex cache."""
    state, _terrain, final, tw, th, cw, ch = _pipeline_through_final(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
        climate_width=climate_width,
        climate_height=climate_height,
        milestone=15,
    )

    ecology = build_ecology(
        climate=final.climate,
        moisture=final.moisture,
        hydrology=final.hydrology,
        elevation_terrain_m=final.elevation_v2_m,
        params=config.to_ecology_params(),
        reporter=reporter,
    )
    ecology.save(output_dir / "ecology")
    _attach_ecology(state, ecology)

    hex_w = int(config.analysis_width)
    hex_h = int(config.analysis_height)
    hex_grid = build_hex_analysis_grid(
        climate=final.climate,
        moisture=final.moisture,
        ecology=ecology,
        hydrology=final.hydrology,
        vectors=final.vectors,
        elevation_terrain_m=final.elevation_v2_m,
        landforms=final.landforms,
        width=hex_w,
        height=hex_h,
        reporter=reporter,
    )
    hex_grid.save(output_dir / "hex")
    _attach_hex(state, hex_grid)

    (output_dir / "README.txt").write_text(
        "Milestone 15 analytical hex grid (derived cache).\n"
        "See tectonics/ … final/, ecology/, and hex/ artefacts.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"hex_resolution={hex_w}x{hex_h}\n"
        f"hex_n_cells={hex_grid.n_cells}\n"
        f"acceptance_ok={hex_grid.diagnostics.get('acceptance_ok')}\n"
        "WorldSpatialModel persistence (Milestone 16) is not included.\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "hex",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "hex_resolution": [hex_w, hex_h],
                "hex_n_cells": hex_grid.n_cells,
                "exact_32768": hex_grid.diagnostics.get("exact_32768"),
                "ew_wrap_ok": hex_grid.diagnostics.get("ew_wrap_ok"),
                "ns_nowrap_ok": hex_grid.diagnostics.get("ns_nowrap_ok"),
                "acceptance_ok": hex_grid.diagnostics.get("acceptance_ok"),
                "production_acceptance_ok": hex_grid.diagnostics.get(
                    "production_acceptance_ok"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(output_dir))
    return state


def _attach_world(state: PhysicalWorldState, model: WorldSpatialModel) -> None:
    state.metadata["world_model_schema_version"] = (
        model.manifest.world_model_schema_version
    )
    state.metadata["world_acceptance_ok"] = model.manifest.acceptance_ok
    # Keep analysis_grid pointer; also expose model under metadata for tools.
    state.metadata["world_root_ready"] = True
    state.analysis_grid = model.hex_grid


def run_world(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None = None,
    height: int | None = None,
    params: PyPlatecParams | None = None,
    terrain_width: int | None = None,
    terrain_height: int | None = None,
    climate_width: int | None = None,
    climate_height: int | None = None,
) -> PhysicalWorldState:
    """Milestone 16 path: hex + WorldSpatialModel persistence."""
    state, _terrain, final, tw, th, cw, ch = _pipeline_through_final(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        reporter=reporter,
        width=width,
        height=height,
        params=params,
        terrain_width=terrain_width,
        terrain_height=terrain_height,
        climate_width=climate_width,
        climate_height=climate_height,
        milestone=16,
    )

    ecology = build_ecology(
        climate=final.climate,
        moisture=final.moisture,
        hydrology=final.hydrology,
        elevation_terrain_m=final.elevation_v2_m,
        params=config.to_ecology_params(),
        reporter=reporter,
    )
    ecology.save(output_dir / "ecology")
    _attach_ecology(state, ecology)

    hex_w = int(config.analysis_width)
    hex_h = int(config.analysis_height)
    hex_grid = build_hex_analysis_grid(
        climate=final.climate,
        moisture=final.moisture,
        ecology=ecology,
        hydrology=final.hydrology,
        vectors=final.vectors,
        elevation_terrain_m=final.elevation_v2_m,
        landforms=final.landforms,
        width=hex_w,
        height=hex_h,
        reporter=reporter,
    )
    hex_grid.save(output_dir / "hex")
    _attach_hex(state, hex_grid)

    model = build_world_spatial_model(
        config=config,
        climate=final.climate,
        moisture=final.moisture,
        ecology=ecology,
        vectors=final.vectors,
        hex_grid=hex_grid,
        hydrology=final.hydrology,
        elevation_terrain_m=final.elevation_v2_m,
        master_seed=master_seed,
        metadata={
            "tectonics_seed": state.metadata.get("tectonics_seed"),
            "terrain_resolution": [tw, th],
            "climate_resolution": [cw, ch],
        },
        reporter=reporter,
    )
    world_root = output_dir / "world"
    timeline = build_environment_timeline(model)
    model.attach_environment_timeline(timeline)
    model.save(world_root)
    atlas_meta = export_atlas_display(model, world_root / "atlas_display")
    _attach_world(state, model)

    (output_dir / "README.txt").write_text(
        "Milestone 19 WorldSpatialModel + EnvironmentTimeline scaffold.\n"
        "Canonical dataset under world/; timeline under world/timeline/environment/.\n"
        "No full palaeoclimate engine — anomalies modify baseline queries only.\n"
        f"climate_resolution={cw}x{ch}\n"
        f"hex_n_cells={hex_grid.n_cells}\n"
        f"world_model_schema_version={model.manifest.world_model_schema_version}\n"
        f"atlas_schema={atlas_meta.get('schema')}\n"
        f"acceptance_ok={model.manifest.acceptance_ok}\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "stage": "world",
                "master_seed": master_seed,
                "tectonics_seed": state.metadata.get("tectonics_seed"),
                "terrain_resolution": [tw, th],
                "climate_resolution": [cw, ch],
                "hex_resolution": [hex_w, hex_h],
                "hex_n_cells": hex_grid.n_cells,
                "world_model_schema_version": model.manifest.world_model_schema_version,
                "world_root": "world",
                "atlas_display": "world/atlas_display",
                "environment_timeline": "world/timeline/environment",
                "atlas_schema": atlas_meta.get("schema"),
                "acceptance_ok": model.manifest.acceptance_ok,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reporter.complete(str(world_root.resolve()))
    return state


def _generate_tectonics_bundle(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    reporter: ProgressReporter,
    width: int | None,
    height: int | None,
    params: PyPlatecParams | None,
    milestone: int,
) -> tuple[PhysicalWorldState, TectonicsInterpretationResult]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reporter.started(seed=master_seed, schema_version=config.schema_version)
    reporter.stage_started("bootstrap")
    state = _bootstrap_state(
        config=config,
        master_seed=master_seed,
        output_dir=output_dir,
        milestone=milestone,
        dry_run=False,
    )
    state.seeds.write_json(output_dir / "seed_manifest.json")
    reporter.progress("bootstrap", 1.0)
    reporter.stage_complete("bootstrap")

    tectonics_extent = state.extents["tectonics"]
    width_i = int(width if width is not None else tectonics_extent.width)
    height_i = int(height if height is not None else tectonics_extent.height)
    tectonics_seed = int(state.seeds.modules["tectonics"]) & 0xFFFFFFFF

    result = run_pyplatec_extended(
        seed=tectonics_seed,
        width=width_i,
        height=height_i,
        params=params
        or config.to_pyplatec_params(),
        reporter=reporter,
        apply_seam=True,
    )
    tectonics_dir = output_dir / "tectonics"
    result.save(tectonics_dir)
    state.tectonics = result
    state.rasters["elevation_raw"] = result.elevation_raw
    state.rasters["plate_id"] = result.plate_id
    if result.crust_age is not None:
        state.rasters["crust_age"] = result.crust_age
    if result.plate_velocity_x is not None:
        state.rasters["plate_velocity_x"] = result.plate_velocity_x
    if result.plate_velocity_y is not None:
        state.rasters["plate_velocity_y"] = result.plate_velocity_y
    if result.plate_speed is not None:
        state.rasters["plate_speed"] = result.plate_speed
    state.metadata["tectonics_seed"] = tectonics_seed
    state.metadata["seam_column"] = result.seam_column
    state.metadata["tectonics_metadata_source"] = result.metadata_source

    interpretation = run_tectonic_interpretation(result, reporter=reporter)
    interpretation.save(tectonics_dir)
    state.metadata["tectonics_interpretation"] = True
    state.rasters["boundary_mask"] = interpretation.boundary_mask
    state.rasters["distance_to_boundary"] = interpretation.distance_to_boundary
    state.rasters["boundary_type"] = interpretation.boundary_type
    state.rasters["tectonic_activity"] = interpretation.tectonic_activity
    state.rasters["convergence_strength"] = interpretation.convergence_strength
    state.rasters["divergence_strength"] = interpretation.divergence_strength
    state.rasters["transform_strength"] = interpretation.transform_strength
    state.rasters["subduction_potential"] = interpretation.subduction_potential
    state.rasters["orogenic_potential"] = interpretation.orogenic_potential
    state.rasters["volcanic_potential"] = interpretation.volcanic_potential
    state.rasters["earthquake_potential"] = interpretation.earthquake_potential
    state.metadata["boundary_cell_count"] = interpretation.diagnostics.get(
        "boundary_cell_count"
    )
    return state, interpretation


def validate_seed_manifest_file(path: Path) -> SeedManifest:
    """Reload a written manifest for acceptance checks."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return SeedManifest(
        master_seed=int(data["master_seed"]),
        schema_version=int(data["schema_version"]),
        modules={str(k): int(v) for k, v in data["modules"].items()},
    )
