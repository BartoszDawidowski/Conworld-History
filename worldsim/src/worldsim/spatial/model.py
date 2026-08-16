"""WorldSpatialModel — canonical persistence + queries (Milestone 16)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.config import PlanetConfig
from worldsim.physical.climate.pipeline import ClimateResult, downsample_mean
from worldsim.physical.ecology.pipeline import EcologyResult
from worldsim.physical.hydrology.pipeline import HydrologyResult
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.coordinates import CoordinateSystem
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.hex_grid.intersections import river_edge_mask
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult, build_hex_analysis_grid
from worldsim.spatial.manifest import WORLD_MODEL_SCHEMA_VERSION, WorldManifest
from worldsim.spatial.queries import SpatialQueries
from worldsim.spatial.raster_store import RasterStore
from worldsim.spatial.vector_store import VectorStore


@dataclass
class WorldSpatialModel:
    """Finished physical world substrate for history / Godot / offline tools.

    Raster + vector are canonical SoT. Hex analysis grid is a derived cache.
    """

    coordinates: CoordinateSystem
    rasters: RasterStore
    vectors: VectorStore
    hex_grid: HexAnalysisResult
    climate_extent: SpatialExtent
    manifest: WorldManifest
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    environment_timeline: Any = None
    _queries: SpatialQueries | None = field(default=None, repr=False)

    @property
    def queries(self) -> SpatialQueries:
        if self._queries is None:
            self._queries = SpatialQueries(
                rasters=self.rasters,
                vectors=self.vectors,
                hex_grid=self.hex_grid,
                climate_extent=self.climate_extent,
            )
        return self._queries

    # --- query façade (architecture §35 / §37 time-indexed) ---
    def environment_at(
        self, x: float, y: float, *, year: int | None = None
    ) -> dict[str, Any]:
        if year is not None and self.environment_timeline is not None:
            return self.environment_timeline.environment_at(x, y, year=year)
        base = self.queries.environment_at(x, y)
        base["year"] = None
        base["source"] = "baseline"
        base["modifiers"] = {
            "temperature_offset_c": 0.0,
            "precipitation_scale": 1.0,
            "sea_level_delta_m": 0.0,
            "anomaly_ids": [],
        }
        return base

    def hex_at(self, x: float, y: float) -> int:
        return self.queries.hex_at(x, y)

    def rivers_in_bbox(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> list[int]:
        return self.queries.rivers_in_bbox(x0, y0, x1, y1)

    def lakes_in_bbox(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> list[int]:
        return self.queries.lakes_in_bbox(x0, y0, x1, y1)

    def coast_distance(self, x: float, y: float) -> float:
        return self.queries.coast_distance(x, y)

    def sample_elevation(
        self, x: float, y: float, *, year: int | None = None
    ) -> float:
        if year is not None and self.environment_timeline is not None:
            return self.environment_timeline.sample_elevation(x, y, year=year)
        return self.queries.sample_elevation(x, y)

    def sample_climate(
        self, x: float, y: float, month: int, *, year: int | None = None
    ) -> float:
        if year is not None and self.environment_timeline is not None:
            return self.environment_timeline.sample_climate(x, y, month, year=year)
        return self.queries.sample_climate(x, y, month)

    def hex_environment(self, hex_id: int) -> dict[str, Any]:
        return self.queries.hex_environment(hex_id)

    def neighbour_hexes(self, hex_id: int) -> list[int | None]:
        return self.queries.neighbour_hexes(hex_id)

    def rivers_crossing_hex(self, hex_id: int) -> list[int]:
        return self.queries.rivers_crossing_hex(hex_id)

    def rebuild_river_edge_mask(self) -> NDArray[np.uint8]:
        """Rebuild optional hex river-crossing cache from canonical vectors."""
        mask = river_edge_mask(self.vectors.rivers.segments, self.hex_grid.spec)
        self.hex_grid.river_edge_mask = mask
        self._queries = None
        return mask

    def rebuild_spatial_index(self) -> None:
        self.vectors.rebuild_spatial_index()
        self._queries = None

    def attach_environment_timeline(self, timeline: Any) -> None:
        self.environment_timeline = timeline
        if timeline is not None and hasattr(timeline, "bind"):
            timeline.bind(self)

    def save(self, directory: Path) -> None:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / "config.json").write_text(
            json.dumps(self.config_snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.rasters.save(root / "physical" / "rasters")
        self.vectors.save(root / "physical" / "vectors")
        self.hex_grid.save(root / "physical" / "analysis_grid")
        if self.environment_timeline is not None:
            self.environment_timeline.save(root / "timeline" / "environment")
            self.manifest.paths["environment_timeline"] = "timeline/environment"
        self.manifest.save(root / "manifest.json")
        (root / "metadata.json").write_text(
            json.dumps(self.metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> WorldSpatialModel:
        root = Path(directory)
        manifest = WorldManifest.load(root / "manifest.json")
        config_snapshot = json.loads((root / "config.json").read_text(encoding="utf-8"))
        meta_path = root / "metadata.json"
        metadata = (
            json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.is_file()
            else {}
        )
        rasters = RasterStore.load(root / "physical" / "rasters")
        vectors = VectorStore.load(root / "physical" / "vectors")
        hex_grid = HexAnalysisResult.load(root / "physical" / "analysis_grid")
        climate_extent = SpatialExtent.from_shape(
            int(rasters.extents.get("climate", {}).get("width", 0))
            or int(np.asarray(rasters.get("climate/elevation_m")).shape[1]),
            int(rasters.extents.get("climate", {}).get("height", 0))
            or int(np.asarray(rasters.get("climate/elevation_m")).shape[0]),
        )
        model = cls(
            coordinates=CoordinateSystem(),
            rasters=rasters,
            vectors=vectors,
            hex_grid=hex_grid,
            climate_extent=climate_extent,
            manifest=manifest,
            config_snapshot=config_snapshot,
            metadata=metadata,
        )
        tl_rel = manifest.paths.get("environment_timeline", "timeline/environment")
        tl_dir = root / tl_rel
        if (tl_dir / "timeline_manifest.json").is_file():
            from worldsim.environment_timeline import EnvironmentTimeline

            model.attach_environment_timeline(EnvironmentTimeline.load(tl_dir, model=model))
        return model


def _fill_rasters(
    store: RasterStore,
    *,
    climate: ClimateResult,
    moisture: MoistureResult,
    ecology: EcologyResult,
    hydrology: HydrologyResult | None,
    elevation_terrain_m: NDArray[np.floating] | None,
) -> SpatialExtent:
    store.put("climate/elevation_m", climate.elevation_m, extent_key="climate")
    store.put("climate/ocean_mask", climate.ocean_mask.astype(np.uint8))
    store.put("climate/temperature_c", climate.temperature_c)
    store.put("climate/latitude_deg", climate.latitude_deg)
    store.put("climate/insolation", climate.insolation)
    store.put("climate/continentality", climate.continentality)

    store.put("moisture/precipitation", moisture.precipitation, extent_key="moisture")
    store.put("moisture/humidity", moisture.humidity)
    store.put("moisture/annual_precipitation", moisture.annual_precipitation)

    store.put("ecology/permeability", ecology.permeability, extent_key="ecology")
    store.put("ecology/soil_depth", ecology.soil_depth)
    store.put("ecology/soil_moisture", ecology.soil_moisture)
    store.put("ecology/fertility_proxy", ecology.fertility_proxy)
    store.put("ecology/holdridge_zone_id", ecology.holdridge_zone_id)
    store.put("ecology/biotemperature_c", ecology.biotemperature_c)
    store.put("ecology/pet_ratio", ecology.pet_ratio)

    if hydrology is not None:
        # Persist hydrology at its native resolution; climate sampling uses climate/*
        store.put(
            "hydrology/river_mask",
            hydrology.river_mask.astype(np.uint8),
            extent_key="hydrology",
        )
        store.put("hydrology/lake_mask", hydrology.lake_mask.astype(np.uint8))
        store.put("hydrology/basin_id", hydrology.basin_id)
        store.put("hydrology/flow_accumulation", hydrology.flow_accumulation)
        store.put(
            "hydrology/flow_direction",
            hydrology.flow_direction.astype(np.uint8),
        )
        store.put("hydrology/river_discharge_proxy", hydrology.river_discharge_proxy)
        store.put("hydrology/river_discharge_gross", hydrology.river_discharge_gross)

    if elevation_terrain_m is not None:
        elev = np.asarray(elevation_terrain_m, dtype=np.float64)
        store.put("terrain/elevation_v2_m", elev, extent_key="terrain")
        # Convenience climate-res DEM for tools that only open climate group
        dem_c = downsample_mean(elev, climate.extent.width, climate.extent.height)
        dem_c = np.where(climate.ocean_mask, climate.elevation_m, dem_c)
        store.put("terrain/elevation_climate_m", dem_c)

    return climate.extent


def build_world_spatial_model(
    *,
    config: PlanetConfig,
    climate: ClimateResult,
    moisture: MoistureResult,
    ecology: EcologyResult,
    vectors: VectorGeographyResult,
    hex_grid: HexAnalysisResult,
    hydrology: HydrologyResult | None = None,
    elevation_terrain_m: NDArray[np.floating] | None = None,
    master_seed: int | None = None,
    metadata: dict[str, Any] | None = None,
    reporter: ProgressReporter | None = None,
) -> WorldSpatialModel:
    if reporter is not None:
        reporter.stage_started("world")
        reporter.progress("world", 0.1)

    rasters = RasterStore()
    climate_extent = _fill_rasters(
        rasters,
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        hydrology=hydrology,
        elevation_terrain_m=elevation_terrain_m,
    )
    if reporter is not None:
        reporter.progress("world", 0.4)

    vector_store = VectorStore.from_vector_geography(vectors)
    if reporter is not None:
        reporter.progress("world", 0.7)

    resolutions = {
        "climate": [climate.extent.width, climate.extent.height],
        "hex": [hex_grid.spec.width, hex_grid.spec.height],
        "vectors": [vectors.extent.width, vectors.extent.height],
    }
    if elevation_terrain_m is not None:
        th, tw = np.asarray(elevation_terrain_m).shape
        resolutions["terrain"] = [int(tw), int(th)]

    from worldsim.spatial.hex_grid.layout import HEX_LAYOUT_ALGORITHM_VERSION
    from worldsim.spatial.units_migration import emit_length_migration_warnings

    lengths = config.resolve_length_units(source_profile="atlas")
    emit_length_migration_warnings(lengths)
    manifest = WorldManifest(
        world_model_schema_version=WORLD_MODEL_SCHEMA_VERSION,
        master_seed=master_seed,
        stage="world",
        resolutions=resolutions,
        hex_n_cells=hex_grid.n_cells,
        acceptance_ok=bool(hex_grid.diagnostics.get("acceptance_ok")),
        extra={
            "hex_production_acceptance_ok": hex_grid.diagnostics.get(
                "production_acceptance_ok"
            ),
            "vector_acceptance_ok": vectors.diagnostics.get("acceptance_ok"),
            "ecology_acceptance_ok": ecology.diagnostics.get("acceptance_ok"),
            "hex_layout_algorithm_version": HEX_LAYOUT_ALGORITHM_VERSION,
            "length_units": lengths.to_dict(),
            "planet_radius_km": float(config.planet_radius_km),
        },
    )

    model = WorldSpatialModel(
        coordinates=CoordinateSystem(
            wrap_x=config.wrap_x,
            wrap_y=config.wrap_y,
            projection=config.projection,
        ),
        rasters=rasters,
        vectors=vector_store,
        hex_grid=hex_grid,
        climate_extent=climate_extent,
        manifest=manifest,
        config_snapshot=dict(config.raw) if getattr(config, "raw", None) else {},
        metadata=dict(metadata or {}),
    )

    if reporter is not None:
        reporter.progress("world", 1.0)
        reporter.stage_complete("world")
    return model


def rebuild_hex_analysis_cache(
    model: WorldSpatialModel,
    *,
    climate: ClimateResult,
    moisture: MoistureResult,
    ecology: EcologyResult,
    hydrology: HydrologyResult | None = None,
    elevation_terrain_m: NDArray[np.floating] | None = None,
) -> HexAnalysisResult:
    """Rebuild hex analysis grid from canonical stores / live stage results."""
    # Prefer live climate objects; vectors come from model SoT
    from worldsim.physical.vectorize.pipeline import VectorGeographyResult

    vectors = VectorGeographyResult(
        extent=model.vectors.extent,
        coastline=model.vectors.coastline,
        rivers=model.vectors.rivers,
        lakes=model.vectors.lakes,
        basins=model.vectors.basins,
        spatial_index=model.vectors.spatial_index,
        diagnostics={},
    )
    hex_grid = build_hex_analysis_grid(
        climate=climate,
        moisture=moisture,
        ecology=ecology,
        hydrology=hydrology,
        vectors=vectors,
        elevation_terrain_m=elevation_terrain_m,
        width=model.hex_grid.spec.width,
        height=model.hex_grid.spec.height,
    )
    model.hex_grid = hex_grid
    model._queries = None
    model.manifest.hex_n_cells = hex_grid.n_cells
    model.manifest.acceptance_ok = bool(hex_grid.diagnostics.get("acceptance_ok"))
    return hex_grid
