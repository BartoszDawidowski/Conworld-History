"""Planet / generation configuration loader (architecture §17)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from worldsim import SCHEMA_VERSION


class ConfigError(ValueError):
    """Invalid or incomplete planet configuration."""


@dataclass(frozen=True)
class PlanetConfig:
    schema_version: int
    earth_like: bool
    axial_tilt_deg: float
    orbital_eccentricity: float
    solar_constant_relative: float
    rotation_period_hours: float
    year_days: float
    topology: str
    wrap_x: bool
    wrap_y: bool
    projection: str
    analysis_width: int
    analysis_height: int
    analysis_orientation: str
    tectonics_resolution: tuple[int, int]
    climate_resolution: tuple[int, int]
    terrain_target: tuple[int, int]
    terrain_production: tuple[int, int]
    hydrology_target: tuple[int, int]
    climate_months: int
    generation_quality: str
    ocean_fraction_target: float
    tectonics_num_plates: int
    tectonics_cycle_count: int
    terrain_detail_amplitude: float
    erosion_iterations: int
    erosion_fluvial_k: float
    # Plan B5 — tectonics / hypsometry (Atlas-tuned defaults 2026-08-15)
    tectonics_folding_ratio: float = 0.01
    tectonics_sea_level: float = 0.65
    tectonics_erosion_period: int = 100
    land_scale_m: float = 9000.0
    ocean_scale_m: float = 10000.0
    orogeny_boost: float = 0.05
    activity_relief: float = 0.25
    boundary_relief: float = 0.35
    # Plan B5 — ocean coupling (Atlas-tuned 2026-08-15)
    sst_mix: float = 0.4
    inland_decay_cells: float = 60.0
    western_warm_c: float = 2.2
    eastern_cool_c: float = 1.8
    # Plan B5 — moisture inland (Atlas-tuned 2026-08-15)
    moisture_advect_steps: int = 32
    moisture_advect_wind_scale: float = 0.2
    moisture_large_scale_frac: float = 0.15
    moisture_orographic_frac: float = 0.85
    moisture_convective_scale: float = 2.0
    moisture_ocean_evap_rate: float = 1.4
    moisture_lake_evap_rate: float = 0.75
    moisture_river_evap_rate: float = 0.40
    moisture_land_et_rate: float = 0.4
    moisture_continentality_dry: float = 0.4
    moisture_lee_dry: float = 0.12
    # Plan B7 — precip-aware hydro gates
    hydrology_river_acc_fraction: float = 0.02
    hydrology_lake_min_depth_m: float = 2.0
    hydrology_river_discharge_candidate_quantile: float = 0.50
    hydrology_lake_precip_land_quantile: float = 0.70
    hydrology_lake_arid_precip_land_quantile: float = 0.45
    hydrology_lake_min_mean_temp_c: float = 1.0
    hydrology_lake_inflow_land_quantile: float = 0.75
    hydrology_transmission_rate: float = 0.45
    # Plan B5 — climate mean / Holdridge precip scaling
    base_temp_c: float = 25.0
    precip_scale_mm: float = 200.0
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_ocean_params(self) -> "OceanParams":
        from worldsim.physical.ocean import OceanParams

        return OceanParams(
            months=self.climate_months,
            sst_mix=self.sst_mix,
            inland_decay_cells=self.inland_decay_cells,
            western_warm_c=self.western_warm_c,
            eastern_cool_c=self.eastern_cool_c,
        )

    def to_moisture_params(self) -> "MoistureParams":
        from worldsim.physical.moisture import MoistureParams

        return MoistureParams(
            months=self.climate_months,
            advect_steps=self.moisture_advect_steps,
            advect_wind_scale=self.moisture_advect_wind_scale,
            large_scale_frac=self.moisture_large_scale_frac,
            orographic_frac=self.moisture_orographic_frac,
            convective_scale=self.moisture_convective_scale,
            ocean_evap_rate=self.moisture_ocean_evap_rate,
            lake_evap_rate=self.moisture_lake_evap_rate,
            river_evap_rate=self.moisture_river_evap_rate,
            land_et_rate=self.moisture_land_et_rate,
            continentality_dry=self.moisture_continentality_dry,
            lee_dry=self.moisture_lee_dry,
        )

    def to_ecology_params(self) -> "EcologyParams":
        from worldsim.physical.ecology import EcologyParams

        return EcologyParams(precip_scale_mm=self.precip_scale_mm)

    def to_hydrology_params(self) -> "HydrologyParams":
        from worldsim.physical.hydrology import HydrologyParams

        return HydrologyParams(
            months=self.climate_months,
            river_acc_fraction=self.hydrology_river_acc_fraction,
            lake_min_depth_m=self.hydrology_lake_min_depth_m,
            river_discharge_candidate_quantile=self.hydrology_river_discharge_candidate_quantile,
            lake_precip_land_quantile=self.hydrology_lake_precip_land_quantile,
            lake_arid_precip_land_quantile=self.hydrology_lake_arid_precip_land_quantile,
            lake_min_mean_temp_c=self.hydrology_lake_min_mean_temp_c,
            lake_inflow_land_quantile=self.hydrology_lake_inflow_land_quantile,
            transmission_rate=self.hydrology_transmission_rate,
            precip_scale_mm=self.precip_scale_mm,
        )

    def to_pyplatec_params(self) -> "PyPlatecParams":
        from worldsim.physical.tectonics.params import PyPlatecParams

        return PyPlatecParams(
            num_plates=self.tectonics_num_plates,
            cycle_count=self.tectonics_cycle_count,
            folding_ratio=self.tectonics_folding_ratio,
            sea_level=self.tectonics_sea_level,
            erosion_period=self.tectonics_erosion_period,
        )

    @property
    def is_earth_like_cylindrical(self) -> bool:
        return (
            self.earth_like
            and self.topology == "cylindrical"
            and self.wrap_x
            and not self.wrap_y
        )


def _require_mapping(data: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(data, dict):
        raise ConfigError(f"{label} must be a mapping")
    return data


def _pair(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigError(f"{label} must be a [width, height] pair")
    width, height = int(value[0]), int(value[1])
    if width <= 0 or height <= 0:
        raise ConfigError(f"{label} dimensions must be positive")
    return width, height


def planet_config_from_dict(data: Mapping[str, Any]) -> PlanetConfig:
    schema_version = int(data.get("schema_version", SCHEMA_VERSION))
    if schema_version != SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported schema_version {schema_version}; expected {SCHEMA_VERSION}"
        )

    planet = _require_mapping(data.get("planet"), "planet")
    map_cfg = _require_mapping(data.get("map"), "map")
    analysis = _require_mapping(data.get("analysis_grid"), "analysis_grid")
    resolution = _require_mapping(data.get("resolution"), "resolution")
    climate = _require_mapping(data.get("climate"), "climate")
    generation = _require_mapping(data.get("generation"), "generation")
    ocean_cfg = data.get("ocean") or {}
    if ocean_cfg is None:
        ocean_cfg = {}
    if not isinstance(ocean_cfg, dict):
        raise ConfigError("ocean must be a mapping when provided")
    tectonics_cfg = data.get("tectonics") or {}
    if tectonics_cfg is None:
        tectonics_cfg = {}
    if not isinstance(tectonics_cfg, dict):
        raise ConfigError("tectonics must be a mapping when provided")
    terrain_cfg = data.get("terrain") or {}
    if terrain_cfg is None:
        terrain_cfg = {}
    if not isinstance(terrain_cfg, dict):
        raise ConfigError("terrain must be a mapping when provided")
    erosion_cfg = data.get("erosion") or {}
    if erosion_cfg is None:
        erosion_cfg = {}
    if not isinstance(erosion_cfg, dict):
        raise ConfigError("erosion must be a mapping when provided")

    earth_like = bool(planet.get("earth_like", True))
    if not earth_like:
        raise ConfigError("only earth_like planets are supported in v1")

    wrap_y = bool(map_cfg.get("wrap_y", False))
    if wrap_y:
        raise ConfigError("wrap_y must be false (no north–south wrapping)")

    months = int(climate.get("months", 12))
    if months != 12:
        raise ConfigError("climate.months must be 12 for v1")
    base_temp_c = float(climate.get("base_temp_c", 25.0))
    if not -20.0 <= base_temp_c <= 40.0:
        raise ConfigError("climate.base_temp_c must be in [-20, 40]")

    ecology_cfg = data.get("ecology") or {}
    if ecology_cfg is None:
        ecology_cfg = {}
    if not isinstance(ecology_cfg, dict):
        raise ConfigError("ecology must be a mapping when provided")
    precip_scale_mm = float(ecology_cfg.get("precip_scale_mm", 200.0))
    if precip_scale_mm <= 0.0:
        raise ConfigError("ecology.precip_scale_mm must be > 0")

    terrain_target = _pair(
        resolution.get("terrain_target", [4096, 2048]), "terrain_target"
    )
    # Production resolution is locked by Milestone 5 benchmark; default to
    # fallback until explicitly set in config.
    terrain_production = _pair(
        resolution.get("terrain_production", [2048, 1024]), "terrain_production"
    )
    ocean_fraction_target = float(ocean_cfg.get("fraction_target", 0.71))
    if not 0.0 < ocean_fraction_target < 1.0:
        raise ConfigError("ocean.fraction_target must be in (0, 1)")

    tectonics_num_plates = int(tectonics_cfg.get("num_plates", 7))
    if tectonics_num_plates < 1:
        raise ConfigError("tectonics.num_plates must be >= 1")
    tectonics_cycle_count = int(tectonics_cfg.get("cycle_count", 3))
    if tectonics_cycle_count < 1:
        raise ConfigError("tectonics.cycle_count must be >= 1")
    terrain_detail_amplitude = float(terrain_cfg.get("detail_amplitude", 0.02))
    if terrain_detail_amplitude < 0.0:
        raise ConfigError("terrain.detail_amplitude must be >= 0")
    land_scale_m = float(terrain_cfg.get("land_scale_m", 9000.0))
    if land_scale_m <= 0.0:
        raise ConfigError("terrain.land_scale_m must be > 0")
    ocean_scale_m = float(terrain_cfg.get("ocean_scale_m", 10000.0))
    if ocean_scale_m <= 0.0:
        raise ConfigError("terrain.ocean_scale_m must be > 0")
    orogeny_boost = float(terrain_cfg.get("orogeny_boost", 0.05))
    if orogeny_boost < 0.0:
        raise ConfigError("terrain.orogeny_boost must be >= 0")
    activity_relief = float(terrain_cfg.get("activity_relief", 0.25))
    if activity_relief < 0.0:
        raise ConfigError("terrain.activity_relief must be >= 0")
    boundary_relief = float(terrain_cfg.get("boundary_relief", 0.35))
    if boundary_relief < 0.0:
        raise ConfigError("terrain.boundary_relief must be >= 0")

    tectonics_folding_ratio = float(tectonics_cfg.get("folding_ratio", 0.01))
    if tectonics_folding_ratio < 0.0:
        raise ConfigError("tectonics.folding_ratio must be >= 0")
    tectonics_sea_level = float(tectonics_cfg.get("sea_level", 0.65))
    if not 0.0 < tectonics_sea_level < 1.0:
        raise ConfigError("tectonics.sea_level must be in (0, 1)")
    tectonics_erosion_period = int(tectonics_cfg.get("erosion_period", 100))
    if tectonics_erosion_period < 1:
        raise ConfigError("tectonics.erosion_period must be >= 1")

    erosion_iterations = int(erosion_cfg.get("iterations", 5))
    if erosion_iterations < 1:
        raise ConfigError("erosion.iterations must be >= 1")
    erosion_fluvial_k = float(erosion_cfg.get("fluvial_k", 8.0))
    if erosion_fluvial_k < 0.0:
        raise ConfigError("erosion.fluvial_k must be >= 0")

    sst_mix = float(ocean_cfg.get("sst_mix", 0.4))
    if not 0.0 <= sst_mix <= 1.0:
        raise ConfigError("ocean.sst_mix must be in [0, 1]")
    inland_decay_cells = float(ocean_cfg.get("inland_decay_cells", 60.0))
    if inland_decay_cells <= 0.0:
        raise ConfigError("ocean.inland_decay_cells must be > 0")
    western_warm_c = float(ocean_cfg.get("western_warm_c", 2.2))
    eastern_cool_c = float(ocean_cfg.get("eastern_cool_c", 1.8))

    moisture_cfg = data.get("moisture") or {}
    if moisture_cfg is None:
        moisture_cfg = {}
    if not isinstance(moisture_cfg, dict):
        raise ConfigError("moisture must be a mapping when provided")

    moisture_advect_steps = int(moisture_cfg.get("advect_steps", 32))
    if moisture_advect_steps < 1:
        raise ConfigError("moisture.advect_steps must be >= 1")
    moisture_advect_wind_scale = float(moisture_cfg.get("advect_wind_scale", 0.2))
    if moisture_advect_wind_scale < 0.0:
        raise ConfigError("moisture.advect_wind_scale must be >= 0")
    moisture_large_scale_frac = float(moisture_cfg.get("large_scale_frac", 0.15))
    if moisture_large_scale_frac < 0.0:
        raise ConfigError("moisture.large_scale_frac must be >= 0")
    moisture_orographic_frac = float(moisture_cfg.get("orographic_frac", 0.85))
    if moisture_orographic_frac < 0.0:
        raise ConfigError("moisture.orographic_frac must be >= 0")
    moisture_convective_scale = float(moisture_cfg.get("convective_scale", 2.0))
    if moisture_convective_scale < 0.0:
        raise ConfigError("moisture.convective_scale must be >= 0")
    moisture_ocean_evap_rate = float(moisture_cfg.get("ocean_evap_rate", 1.4))
    if moisture_ocean_evap_rate < 0.0:
        raise ConfigError("moisture.ocean_evap_rate must be >= 0")
    moisture_lake_evap_rate = float(moisture_cfg.get("lake_evap_rate", 0.75))
    if moisture_lake_evap_rate < 0.0:
        raise ConfigError("moisture.lake_evap_rate must be >= 0")
    moisture_river_evap_rate = float(moisture_cfg.get("river_evap_rate", 0.40))
    if moisture_river_evap_rate < 0.0:
        raise ConfigError("moisture.river_evap_rate must be >= 0")
    moisture_land_et_rate = float(moisture_cfg.get("land_et_rate", 0.4))
    if moisture_land_et_rate < 0.0:
        raise ConfigError("moisture.land_et_rate must be >= 0")
    moisture_continentality_dry = float(moisture_cfg.get("continentality_dry", 0.4))
    if not 0.0 <= moisture_continentality_dry <= 1.0:
        raise ConfigError("moisture.continentality_dry must be in [0, 1]")
    moisture_lee_dry = float(moisture_cfg.get("lee_dry", 0.12))
    if moisture_lee_dry < 0.0:
        raise ConfigError("moisture.lee_dry must be >= 0")

    hydro_cfg = data.get("hydrology") or {}
    if hydro_cfg is None:
        hydro_cfg = {}
    if not isinstance(hydro_cfg, dict):
        raise ConfigError("hydrology must be a mapping when provided")
    hydrology_river_acc_fraction = float(hydro_cfg.get("river_acc_fraction", 0.02))
    if not 0.0 < hydrology_river_acc_fraction <= 1.0:
        raise ConfigError("hydrology.river_acc_fraction must be in (0, 1]")
    hydrology_lake_min_depth_m = float(hydro_cfg.get("lake_min_depth_m", 2.0))
    if hydrology_lake_min_depth_m < 0.0:
        raise ConfigError("hydrology.lake_min_depth_m must be >= 0")
    # Prefer candidate quantile; accept legacy land_quantile key as alias.
    if "river_discharge_candidate_quantile" in hydro_cfg:
        hydrology_river_discharge_candidate_quantile = float(
            hydro_cfg["river_discharge_candidate_quantile"]
        )
    else:
        hydrology_river_discharge_candidate_quantile = float(
            hydro_cfg.get("river_discharge_land_quantile", 0.50)
        )
    if not 0.0 <= hydrology_river_discharge_candidate_quantile <= 1.0:
        raise ConfigError(
            "hydrology.river_discharge_candidate_quantile must be in [0, 1]"
        )
    hydrology_lake_precip_land_quantile = float(
        hydro_cfg.get("lake_precip_land_quantile", 0.70)
    )
    if not 0.0 <= hydrology_lake_precip_land_quantile <= 1.0:
        raise ConfigError("hydrology.lake_precip_land_quantile must be in [0, 1]")
    hydrology_lake_arid_precip_land_quantile = float(
        hydro_cfg.get("lake_arid_precip_land_quantile", 0.45)
    )
    if not 0.0 <= hydrology_lake_arid_precip_land_quantile <= 1.0:
        raise ConfigError("hydrology.lake_arid_precip_land_quantile must be in [0, 1]")
    hydrology_lake_min_mean_temp_c = float(
        hydro_cfg.get("lake_min_mean_temp_c", 1.0)
    )
    hydrology_lake_inflow_land_quantile = float(
        hydro_cfg.get("lake_inflow_land_quantile", 0.75)
    )
    if not 0.0 <= hydrology_lake_inflow_land_quantile <= 1.0:
        raise ConfigError("hydrology.lake_inflow_land_quantile must be in [0, 1]")
    hydrology_transmission_rate = float(hydro_cfg.get("transmission_rate", 0.45))
    if hydrology_transmission_rate < 0.0:
        raise ConfigError("hydrology.transmission_rate must be >= 0")

    return PlanetConfig(
        schema_version=schema_version,
        earth_like=earth_like,
        axial_tilt_deg=float(planet.get("axial_tilt_deg", 23.44)),
        orbital_eccentricity=float(planet.get("orbital_eccentricity", 0.0167)),
        solar_constant_relative=float(planet.get("solar_constant_relative", 1.0)),
        rotation_period_hours=float(planet.get("rotation_period_hours", 24.0)),
        year_days=float(planet.get("year_days", 365.2422)),
        topology=str(map_cfg.get("topology", "cylindrical")),
        wrap_x=bool(map_cfg.get("wrap_x", True)),
        wrap_y=wrap_y,
        projection=str(map_cfg.get("projection", "cylindrical_equal_area")),
        analysis_width=int(analysis.get("width", 256)),
        analysis_height=int(analysis.get("height", 128)),
        analysis_orientation=str(analysis.get("orientation", "flat_top")),
        tectonics_resolution=_pair(resolution.get("tectonics", [1024, 512]), "tectonics"),
        climate_resolution=_pair(resolution.get("climate", [1024, 512]), "climate"),
        terrain_target=terrain_target,
        terrain_production=terrain_production,
        hydrology_target=_pair(
            resolution.get("hydrology_target", [4096, 2048]), "hydrology_target"
        ),
        climate_months=months,
        generation_quality=str(generation.get("quality", "final")),
        ocean_fraction_target=ocean_fraction_target,
        tectonics_num_plates=tectonics_num_plates,
        tectonics_cycle_count=tectonics_cycle_count,
        terrain_detail_amplitude=terrain_detail_amplitude,
        erosion_iterations=erosion_iterations,
        erosion_fluvial_k=erosion_fluvial_k,
        tectonics_folding_ratio=tectonics_folding_ratio,
        tectonics_sea_level=tectonics_sea_level,
        tectonics_erosion_period=tectonics_erosion_period,
        land_scale_m=land_scale_m,
        ocean_scale_m=ocean_scale_m,
        orogeny_boost=orogeny_boost,
        activity_relief=activity_relief,
        boundary_relief=boundary_relief,
        sst_mix=sst_mix,
        inland_decay_cells=inland_decay_cells,
        western_warm_c=western_warm_c,
        eastern_cool_c=eastern_cool_c,
        moisture_advect_steps=moisture_advect_steps,
        moisture_advect_wind_scale=moisture_advect_wind_scale,
        moisture_large_scale_frac=moisture_large_scale_frac,
        moisture_orographic_frac=moisture_orographic_frac,
        moisture_convective_scale=moisture_convective_scale,
        moisture_ocean_evap_rate=moisture_ocean_evap_rate,
        moisture_lake_evap_rate=moisture_lake_evap_rate,
        moisture_river_evap_rate=moisture_river_evap_rate,
        moisture_land_et_rate=moisture_land_et_rate,
        moisture_continentality_dry=moisture_continentality_dry,
        moisture_lee_dry=moisture_lee_dry,
        hydrology_river_acc_fraction=hydrology_river_acc_fraction,
        hydrology_lake_min_depth_m=hydrology_lake_min_depth_m,
        hydrology_river_discharge_candidate_quantile=hydrology_river_discharge_candidate_quantile,
        hydrology_lake_precip_land_quantile=hydrology_lake_precip_land_quantile,
        hydrology_lake_arid_precip_land_quantile=hydrology_lake_arid_precip_land_quantile,
        hydrology_lake_min_mean_temp_c=hydrology_lake_min_mean_temp_c,
        hydrology_lake_inflow_land_quantile=hydrology_lake_inflow_land_quantile,
        hydrology_transmission_rate=hydrology_transmission_rate,
        base_temp_c=base_temp_c,
        precip_scale_mm=precip_scale_mm,
        raw=dict(data),
    )


def load_planet_config(path: Path | str) -> PlanetConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        raise ConfigError(f"config file is empty: {config_path}")
    return planet_config_from_dict(_require_mapping(loaded, "root"))


def default_config_path() -> Path:
    from worldsim.runtime_paths import resource_path

    return resource_path("configs", "default_planet.yaml")
