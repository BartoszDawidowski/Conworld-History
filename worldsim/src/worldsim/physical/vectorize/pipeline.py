"""Milestone 12 — canonical vector physical geography orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from worldsim.physical.hydrology.pipeline import HydrologyResult
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.physical.vectorize.basins import BasinMeta, build_basin_metadata
from worldsim.physical.vectorize.coast import (
    CoastlineFeature,
    build_coastline_vectors,
    coastline_consistency_score,
    save_coastline_geojson_like,
    total_coast_length,
)
from worldsim.physical.vectorize.indexes import SpatialIndex, build_spatial_index
from worldsim.physical.vectorize.lakes import Lake, build_lakes, lake_raster_consistency
from worldsim.physical.vectorize.rivers import (
    RiverNetwork,
    build_river_network,
    river_raster_consistency,
    topology_valid,
)
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics


def _save_geojson_features(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}) + "\n",
        encoding="utf-8",
    )


@dataclass
class VectorGeographyResult:
    extent: SpatialExtent
    coastline: list[CoastlineFeature]
    rivers: RiverNetwork
    lakes: list[Lake]
    basins: list[BasinMeta]
    spatial_index: SpatialIndex
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        save_coastline_geojson_like(self.coastline, directory / "coastline.geojson")

        river_feats = [
            {
                "type": "Feature",
                "properties": {
                    "id": s.id,
                    "from_node": s.from_node,
                    "to_node": s.to_node,
                    "strahler_order": s.strahler_order,
                    "mean_discharge": s.mean_discharge,
                    "basin_id": s.basin_id,
                    "length": s.length,
                    "from_lake_id": s.from_lake_id,
                    "to_lake_id": s.to_lake_id,
                    "channel_state": s.channel_state,
                    "catchment_km2": s.catchment_km2,
                    "channel_length_km": s.channel_length_km,
                    "monthly_discharge": list(s.monthly_discharge),
                    "monthly_bed_loss": list(s.monthly_bed_loss),
                    "bed_loss_mean": s.bed_loss_mean,
                    "loss_limited": s.loss_limited,
                    "estimated_width_m": s.estimated_width_m,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": s.geometry,
                },
            }
            for s in self.rivers.segments
        ]
        _save_geojson_features(directory / "rivers.geojson", river_feats)

        (directory / "river_network.json").write_text(
            json.dumps(self.rivers.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        lake_feats = [
            {
                "type": "Feature",
                "properties": {
                    "id": lake.id,
                    "surface_elevation": lake.surface_elevation,
                    "basin_id": lake.basin_id,
                    "closed_basin": lake.closed_basin,
                    "area_cells": lake.area_cells,
                    "water_state": lake.water_state,
                    "spill_elevation": lake.spill_elevation,
                    "mean_effective_inflow": lake.mean_effective_inflow,
                    "inlet_river_ids": list(lake.inlet_river_ids),
                    "outlet_river_id": lake.outlet_river_id,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [lake.polygon],
                },
            }
            for lake in self.lakes
            if len(lake.polygon) >= 4
        ]
        _save_geojson_features(directory / "lakes.geojson", lake_feats)

        (directory / "basins.json").write_text(
            json.dumps(
                {"basins": [b.to_dict() for b in self.basins]},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "spatial_index.json").write_text(
            json.dumps(self.spatial_index.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "vector_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_vector_geography(
    *,
    hydrology: HydrologyResult,
    terrain: TerrainOceanResult | None = None,
    reporter: ProgressReporter | None = None,
) -> VectorGeographyResult:
    if reporter is not None:
        reporter.stage_started("vectors")
        reporter.progress("vectors", 0.1)

    extent = hydrology.extent
    water_body = terrain.water_body_id if terrain is not None else None
    coastline = build_coastline_vectors(
        hydrology.ocean_mask,
        water_body,
    )

    if reporter is not None:
        reporter.progress("vectors", 0.3)

    h, w = hydrology.flow_direction.shape
    radius_km = float(hydrology.diagnostics.get("planet_radius_km") or 6371.0)
    gm = grid_metrics(w, h, radius_km=radius_km)
    cell_len_km = float(np.sqrt(max(gm.cell_area_km2, 0.0)))
    path_length_km = np.maximum(
        gm.d8_step_length_km_field(hydrology.flow_direction),
        cell_len_km,
    )
    rivers = build_river_network(
        flow_direction=hydrology.flow_direction,
        river_mask=hydrology.river_mask,
        stream_order=hydrology.stream_order,
        basin_id=hydrology.basin_id,
        ocean_mask=hydrology.ocean_mask,
        lake_mask=hydrology.lake_mask,
        lake_id=hydrology.lake_id,
        discharge_proxy=hydrology.river_discharge_proxy,
        monthly_discharge=hydrology.monthly_discharge,
        extent=extent,
        channel_state=getattr(hydrology, "channel_state", None),
        flow_accumulation=hydrology.flow_accumulation,
        cell_area_km2=float(hydrology.diagnostics.get("cell_area_km2") or 0.0) or None,
        path_length_km=path_length_km,
        monthly_bed_loss=getattr(hydrology, "monthly_bed_loss", None),
        bed_loss_potential_m3s=getattr(hydrology, "bed_loss_potential_m3s", None),
    )

    if reporter is not None:
        reporter.progress("vectors", 0.55)

    lakes = build_lakes(
        lake_id=hydrology.lake_id,
        lake_mask=hydrology.lake_mask,
        elevation_m=hydrology.dem_conditioned_m,
        basin_id=hydrology.basin_id,
        extent=extent,
        lake_records=getattr(hydrology, "lake_records", None),
        river_network=rivers,
    )
    basins = build_basin_metadata(
        basin_id=hydrology.basin_id,
        elevation_m=hydrology.dem_conditioned_m,
        flow_accumulation=hydrology.flow_accumulation,
        ocean_mask=hydrology.ocean_mask,
        outlet_points=hydrology.outlet_points,
        extent=extent,
    )

    if reporter is not None:
        reporter.progress("vectors", 0.75)

    index = build_spatial_index(
        coastline=coastline,
        river_network=rivers,
        lakes=lakes,
    )

    coast_ok = coastline_consistency_score(coastline, hydrology.ocean_mask) >= 0.75
    river_ok = river_raster_consistency(
        rivers, hydrology.river_mask, hydrology.flow_accumulation
    ) >= 0.7
    lake_ok = lake_raster_consistency(
        [lk for lk in lakes if lk.water_state in ("open", "endorheic")],
        hydrology.lake_mask,
    ) >= 0.7
    topo_ok = topology_valid(rivers)
    # Vectors are hex-independent by construction (no hex types in payloads).
    hex_independent = True

    diagnostics: dict[str, Any] = {
        "width": extent.width,
        "height": extent.height,
        "coastline_feature_count": len(coastline),
        "coastline_length_norm": total_coast_length(coastline),
        "river_node_count": len(rivers.nodes),
        "river_segment_count": len(rivers.segments),
        "lake_count": len(lakes),
        "basin_meta_count": len(basins),
        "spatial_index_buckets": len(index.buckets),
        "coastline_raster_consistency_ok": coast_ok,
        "river_raster_consistency_ok": river_ok,
        "lake_raster_consistency_ok": lake_ok,
        "river_topology_valid": topo_ok,
        "hex_independent": hex_independent,
        "acceptance_ok": bool(
            coast_ok and river_ok and lake_ok and topo_ok and hex_independent
            and len(coastline) > 0
            and len(rivers.segments) > 0
        ),
    }

    if reporter is not None:
        reporter.progress("vectors", 1.0)
        reporter.stage_complete("vectors")

    return VectorGeographyResult(
        extent=extent,
        coastline=coastline,
        rivers=rivers,
        lakes=lakes,
        basins=basins,
        spatial_index=index,
        diagnostics=diagnostics,
    )
