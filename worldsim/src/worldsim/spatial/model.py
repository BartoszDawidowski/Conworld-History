"""WorldSpatialModel — canonical persistence + queries (Milestone 16)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.config import PlanetConfig
from worldsim.physical.climate.pipeline import (
    ClimateResult,
    climate_grid_land_elevation,
)
from worldsim.physical.ecology.pipeline import EcologyResult
from worldsim.physical.hydrology.pipeline import HydrologyResult
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.canonical_acceptance import (
    aggregate_canonical_acceptance,
    conjunction_from_gates,
)
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

    def mountain_range(self, range_id: int) -> dict[str, Any]:
        return self.queries.mountain_range(range_id)

    def plateau(self, plateau_id: int) -> dict[str, Any]:
        return self.queries.plateau(plateau_id)

    def river(self, river_id: int) -> dict[str, Any]:
        return self.queries.river(river_id)

    def lake(self, lake_id: int) -> dict[str, Any]:
        return self.queries.lake(lake_id)

    def basin(self, basin_id: int) -> dict[str, Any]:
        return self.queries.basin(basin_id)

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
    landforms: Any | None = None,
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
    if ecology.biome_v2_class is not None:
        store.put("ecology/biome_v2_class", ecology.biome_v2_class)
        store.put("ecology/frost_months", ecology.frost_months)
        store.put("ecology/growing_season_months", ecology.growing_season_months)
        store.put("ecology/water_deficit_mm", ecology.water_deficit_mm)
        store.put("ecology/soil_state", ecology.soil_state)
        store.put("ecology/thermal_regime_id", ecology.thermal_regime_id)
        store.put("ecology/moisture_regime_id", ecology.moisture_regime_id)

    if hydrology is not None:
        # Persist hydrology at its native resolution; climate sampling uses climate/*
        river_mask = getattr(hydrology, "river_mask", None)
        if river_mask is not None and np.asarray(river_mask).size:
            store.put(
                "hydrology/river_mask",
                np.asarray(river_mask).astype(np.uint8),
                extent_key="hydrology",
            )
        lake_mask = getattr(hydrology, "lake_mask", None)
        if lake_mask is not None and np.asarray(lake_mask).size:
            store.put("hydrology/lake_mask", np.asarray(lake_mask).astype(np.uint8))
        if getattr(hydrology, "basin_envelope_id", None) is not None and hydrology.basin_envelope_id.size:
            store.put("hydrology/basin_envelope_id", hydrology.basin_envelope_id)
        if getattr(hydrology, "water_fraction_mean", None) is not None and hydrology.water_fraction_mean.size:
            store.put(
                "hydrology/water_fraction_mean",
                hydrology.water_fraction_mean.astype(np.float32),
            )
        if getattr(hydrology, "water_fraction_monthly", None) is not None and hydrology.water_fraction_monthly.size:
            store.put(
                "hydrology/water_fraction_monthly",
                hydrology.water_fraction_monthly.astype(np.float32),
            )
        if getattr(hydrology, "ice_fraction_monthly", None) is not None and hydrology.ice_fraction_monthly.size:
            store.put(
                "hydrology/ice_fraction_monthly",
                hydrology.ice_fraction_monthly.astype(np.float32),
            )
        if getattr(hydrology, "river_water_fraction", None) is not None and hydrology.river_water_fraction.size:
            store.put(
                "hydrology/river_water_fraction",
                hydrology.river_water_fraction.astype(np.float32),
            )
        if getattr(hydrology, "channel_state", None) is not None and hydrology.channel_state.size:
            store.put("hydrology/channel_state", hydrology.channel_state)
        basin_id = getattr(hydrology, "basin_id", None)
        if basin_id is not None and np.asarray(basin_id).size:
            store.put("hydrology/basin_id", basin_id)
        if getattr(hydrology, "lake_id", None) is not None and np.asarray(hydrology.lake_id).size:
            store.put("hydrology/lake_id", hydrology.lake_id)
        flow_acc = getattr(hydrology, "flow_accumulation", None)
        if flow_acc is not None and np.asarray(flow_acc).size:
            store.put("hydrology/flow_accumulation", flow_acc)
        flow_dir = getattr(hydrology, "flow_direction", None)
        if flow_dir is not None and np.asarray(flow_dir).size:
            store.put("hydrology/flow_direction", np.asarray(flow_dir).astype(np.uint8))
        q_proxy = getattr(hydrology, "river_discharge_proxy", None)
        if q_proxy is not None and np.asarray(q_proxy).size:
            store.put("hydrology/river_discharge_proxy", q_proxy)
        q_gross = getattr(hydrology, "river_discharge_gross", None)
        if q_gross is not None and np.asarray(q_gross).size:
            store.put("hydrology/river_discharge_gross", q_gross)

    if elevation_terrain_m is not None:
        elev = np.asarray(elevation_terrain_m, dtype=np.float64)
        store.put("terrain/elevation_v2_m", elev, extent_key="terrain")
        ocean_t = (
            hydrology.ocean_mask
            if hydrology is not None and hydrology.ocean_mask.shape == elev.shape
            else elev < 0.0
        )
        dem_c = climate_grid_land_elevation(
            elev,
            ocean_t,
            climate.extent.width,
            climate.extent.height,
            climate_ocean_mask=climate.ocean_mask,
            ocean_elevation_m=climate.elevation_m,
        )
        store.put("terrain/elevation_climate_m", dem_c)

    if landforms is not None and getattr(landforms, "context_id", None) is not None:
        store.put("landforms/context_id", landforms.context_id, extent_key="landforms")
        store.put("landforms/local_form_id", landforms.local_form_id)
        store.put("landforms/provenance_id", landforms.provenance_id)
        store.put("landforms/confidence", landforms.confidence_u8)
        store.put("landforms/mountain_score", landforms.mountain_score_u8)
        store.put("landforms/plateau_score", landforms.plateau_score_u8)
        store.put("landforms/hill_score", landforms.hill_score_u8)
        store.put("landforms/mountain_range_id", landforms.mountain_range_id)
        store.put("landforms/plateau_id", landforms.plateau_id)
        thr = None
        if isinstance(getattr(landforms, "diagnostics", None), dict):
            thr = landforms.diagnostics.get("mountain_score_threshold")
        if thr is not None:
            store.notes["landforms/mountain_score_threshold"] = str(float(thr))

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
    landforms: Any | None = None,
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
        landforms=landforms,
    )
    if reporter is not None:
        reporter.progress("world", 0.4)

    vector_store = VectorStore.from_vector_geography(vectors)
    vector_store.attach_landforms(landforms)
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
    extra_meta = dict(metadata or {})
    report = aggregate_canonical_acceptance(
        moisture=moisture,
        hydrology=hydrology,
        vectors=vectors,
        ecology=ecology,
        landforms=landforms,
        hex_grid=hex_grid,
        erosion=extra_meta.get("erosion_diagnostics"),
        final=extra_meta.get("final_diagnostics"),
    )

    def _stage_ok(obj: Any) -> bool:
        diag = getattr(obj, "diagnostics", None) if obj is not None else None
        if not isinstance(diag, dict):
            return False
        return bool(diag.get("acceptance_ok"))

    hex_diag = getattr(hex_grid, "diagnostics", None)
    hex_prod = (
        hex_diag.get("production_acceptance_ok") if isinstance(hex_diag, dict) else None
    )
    extra = {
        k: extra_meta[k]
        for k in extra_meta
        if k not in {"erosion_diagnostics", "final_diagnostics"}
    }
    extra.update(
        {
            "hex_production_acceptance_ok": hex_prod,
            "vector_acceptance_ok": _stage_ok(vectors),
            "ecology_acceptance_ok": _stage_ok(ecology),
            "moisture_acceptance_ok": _stage_ok(moisture),
            "hydrology_acceptance_ok": _stage_ok(hydrology),
            "landforms_acceptance_ok": _stage_ok(landforms),
            "hex_layout_algorithm_version": HEX_LAYOUT_ALGORITHM_VERSION,
            "length_units": lengths.to_dict(),
            "planet_radius_km": float(config.planet_radius_km),
            "canonical_acceptance_version": report["version"],
            "canonical_acceptance": report,
            "overall_acceptance_ok": report["overall_acceptance_ok"],
            "moisture_spinup_ok": report["gates"]["moisture_spinup_ok"],
            "moisture_budget_ok": report["gates"]["moisture_budget_ok"],
            "hydrology_coupling_ok": report["gates"]["hydrology_ok"],
            "biome_v2_ok": report["gates"]["biome_v2_ok"],
            "landforms_ok": report["gates"]["landforms_ok"],
            "hex_layout_ok": report["gates"]["hex_layout_ok"],
            "failed_gates": list(report["failed_gates"]),
        }
    )
    manifest = WorldManifest(
        world_model_schema_version=WORLD_MODEL_SCHEMA_VERSION,
        master_seed=master_seed,
        stage="world",
        resolutions=resolutions,
        hex_n_cells=hex_grid.n_cells,
        acceptance_ok=bool(report["overall_acceptance_ok"]),
        extra=extra,
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
    model.metadata.setdefault(
        "categorical_legends",
        categorical_legends(ecology=ecology, landforms=landforms),
    )
    if hydrology is not None and getattr(hydrology, "lake_records", None):
        model.metadata.setdefault("hydrology_lake_records", list(hydrology.lake_records))

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
    landforms: Any | None = None,
) -> HexAnalysisResult:
    """Rebuild hex analysis grid from canonical stores / live stage results."""
    # Prefer live climate objects; vectors come from model SoT
    from worldsim.physical.vectorize.pipeline import VectorGeographyResult

    if landforms is None:
        landforms = landforms_from_rasters(model.rasters)
    if hydrology is None:
        hydrology = hydrology_from_rasters(
            model.rasters,
            lake_records=model.metadata.get("hydrology_lake_records"),
        )

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
        landforms=landforms,
        width=model.hex_grid.spec.width,
        height=model.hex_grid.spec.height,
    )
    model.hex_grid = hex_grid
    model._queries = None
    model.manifest.hex_n_cells = hex_grid.n_cells
    extra = dict(model.manifest.extra or {})
    prev = dict(extra.get("canonical_acceptance") or {})
    gates = dict(prev.get("gates") or {})
    if gates:
        gates["hex_layout_ok"] = bool(hex_grid.diagnostics.get("acceptance_ok"))
        report = conjunction_from_gates(gates)
    else:
        report = aggregate_canonical_acceptance(
            hex_grid=hex_grid,
            moisture=moisture,
            ecology=ecology,
            hydrology=hydrology,
            landforms=landforms,
            erosion=extra.get("erosion_diagnostics"),
            final=extra.get("final_diagnostics"),
        )
    extra["canonical_acceptance"] = report
    extra["overall_acceptance_ok"] = report["overall_acceptance_ok"]
    extra["hex_layout_ok"] = report["gates"]["hex_layout_ok"]
    extra["failed_gates"] = list(report["failed_gates"])
    extra["hex_production_acceptance_ok"] = hex_grid.diagnostics.get(
        "production_acceptance_ok"
    )
    model.manifest.extra = extra
    model.manifest.acceptance_ok = bool(report["overall_acceptance_ok"])
    return hex_grid


def categorical_legends(*, ecology: Any | None = None, landforms: Any | None = None) -> dict[str, Any]:
    from worldsim.physical.ecology.biome_v2 import (
        CLASS_NAMES,
        MOISTURE_NAMES,
        THERMAL_NAMES,
    )
    from worldsim.physical.ecology.holdridge import build_zone_legend
    from worldsim.physical.hydrology.channels import CHANNEL_STATE_NAME
    from worldsim.physical.landforms.classify import legend_payload

    soil = {"0": "ocean_or_dry", "1": "moist", "2": "wet", "3": "saturated"}
    payload = {
        "holdridge_zone": build_zone_legend(),
        "biome_v2_class": {str(k): v for k, v in CLASS_NAMES.items()},
        "thermal_regime": {str(k): v for k, v in THERMAL_NAMES.items()},
        "moisture_regime": {str(k): v for k, v in MOISTURE_NAMES.items()},
        "soil_state": soil,
        "landform": {
            key: {str(i): name for i, name in values.items()}
            for key, values in legend_payload().items()
        },
        "channel_state": {str(k): v for k, v in CHANNEL_STATE_NAME.items()},
    }
    if ecology is not None:
        names = getattr(ecology, "diagnostics", {}).get("class_names")
        if names:
            payload["biome_v2_class"] = {str(k): v for k, v in names.items()}
    _ = landforms
    return payload


def landforms_from_rasters(rasters: RasterStore) -> SimpleNamespace | None:
    if not rasters.has("landforms/context_id"):
        return None
    thr_note = rasters.notes.get("landforms/mountain_score_threshold")
    return SimpleNamespace(
        context_id=rasters.get("landforms/context_id"),
        local_form_id=rasters.get("landforms/local_form_id"),
        provenance_id=rasters.get("landforms/provenance_id"),
        confidence_u8=rasters.get("landforms/confidence"),
        mountain_score_u8=rasters.get("landforms/mountain_score"),
        plateau_score_u8=rasters.get("landforms/plateau_score"),
        hill_score_u8=rasters.get("landforms/hill_score"),
        mountain_range_id=rasters.get("landforms/mountain_range_id"),
        plateau_id=rasters.get("landforms/plateau_id"),
        mountain_ranges=[],
        plateaus=[],
        diagnostics={
            "mountain_score_threshold": float(thr_note) if thr_note else 0.60,
        },
    )


def hydrology_from_rasters(
    rasters: RasterStore,
    *,
    lake_records: list[dict[str, Any]] | None = None,
) -> SimpleNamespace | None:
    if not rasters.has("hydrology/basin_id"):
        return None

    def _opt(name: str) -> Any:
        return rasters.get(name) if rasters.has(name) else None

    ocean = (
        rasters.get("climate/ocean_mask").astype(bool)
        if rasters.has("climate/ocean_mask")
        else None
    )
    return SimpleNamespace(
        water_fraction_mean=_opt("hydrology/water_fraction_mean"),
        water_fraction_monthly=_opt("hydrology/water_fraction_monthly"),
        ice_fraction_monthly=_opt("hydrology/ice_fraction_monthly"),
        lake_mask=(_opt("hydrology/lake_mask").astype(bool) if rasters.has("hydrology/lake_mask") else None),
        channel_state=_opt("hydrology/channel_state"),
        river_discharge_proxy=_opt("hydrology/river_discharge_proxy"),
        basin_id=_opt("hydrology/basin_id"),
        lake_id=_opt("hydrology/lake_id"),
        lake_records=list(lake_records or []),
        ocean_mask=ocean if ocean is not None else np.zeros((1, 1), dtype=bool),
    )
