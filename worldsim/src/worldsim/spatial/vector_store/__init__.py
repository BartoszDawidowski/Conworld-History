"""Canonical vector feature store for WorldSpatialModel (Milestone 16)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from worldsim.physical.terrain.coastline import CoastlineFeature
from worldsim.physical.vectorize.basins import BasinMeta
from worldsim.physical.vectorize.indexes import SpatialIndex, build_spatial_index
from worldsim.physical.vectorize.lakes import Lake
from worldsim.physical.vectorize.pipeline import VectorGeographyResult
from worldsim.physical.vectorize.rivers import RiverNetwork, RiverNode, RiverSegment
from worldsim.spatial.extent import SpatialExtent


def _load_feature_collection(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return list(data.get("features", []))


def _dump_feature_collection(path: Path, features: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}) + "\n",
        encoding="utf-8",
    )


def _load_coastline(path: Path) -> list[CoastlineFeature]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[CoastlineFeature] = []
    for item in data.get("features", data if isinstance(data, list) else []):
        if isinstance(item, dict) and "geometry" in item and "properties" in item:
            props = item["properties"]
            coords = item["geometry"]["coordinates"]
            out.append(
                CoastlineFeature(
                    id=int(props["id"]),
                    geometry=[(float(a), float(b)) for a, b in coords],
                    water_body_id=int(props.get("water_body_id", 0)),
                )
            )
        else:
            out.append(
                CoastlineFeature(
                    id=int(item["id"]),
                    geometry=[(float(a), float(b)) for a, b in item["geometry"]],
                    water_body_id=int(item.get("water_body_id", 0)),
                )
            )
    return out


def _load_rivers(path: Path) -> RiverNetwork:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = [
        RiverNode(
            id=int(n["id"]),
            x=float(n["x"]),
            y=float(n["y"]),
            type=n["type"],
            row=int(n["row"]),
            col=int(n["col"]),
            lake_id=int(n.get("lake_id", 0)),
        )
        for n in data.get("nodes", [])
    ]
    segments = [
        RiverSegment(
            id=int(s["id"]),
            from_node=int(s["from_node"]),
            to_node=int(s["to_node"]),
            geometry=[(float(a), float(b)) for a, b in s["geometry"]],
            strahler_order=int(s["strahler_order"]),
            mean_discharge=float(s["mean_discharge"]),
            monthly_discharge=[float(v) for v in s.get("monthly_discharge", [])],
            basin_id=int(s["basin_id"]),
            length=float(s["length"]),
            from_lake_id=int(s.get("from_lake_id", 0)),
            to_lake_id=int(s.get("to_lake_id", 0)),
            channel_state=str(s.get("channel_state", "none")),
            catchment_km2=float(s.get("catchment_km2", 0.0)),
            channel_length_km=float(s.get("channel_length_km", 0.0)),
            monthly_bed_loss=[float(v) for v in s.get("monthly_bed_loss", [])],
            bed_loss_mean=float(s.get("bed_loss_mean", 0.0)),
            loss_limited=bool(s.get("loss_limited", False)),
            estimated_width_m=float(s.get("estimated_width_m", 0.0)),
        )
        for s in data.get("segments", [])
    ]
    return RiverNetwork(nodes=nodes, segments=segments)


def _load_lakes(path: Path) -> list[Lake]:
    data = json.loads(path.read_text(encoding="utf-8"))
    lakes: list[Lake] = []
    for item in data.get("lakes", []):
        lakes.append(
            Lake(
                id=int(item["id"]),
                polygon=[(float(a), float(b)) for a, b in item["polygon"]],
                surface_elevation=float(item["surface_elevation"]),
                basin_id=int(item["basin_id"]),
                inlet_river_ids=[int(v) for v in item.get("inlet_river_ids", [])],
                outlet_river_id=(
                    None
                    if item.get("outlet_river_id") is None
                    else int(item["outlet_river_id"])
                ),
                closed_basin=bool(item.get("closed_basin", True)),
                area_cells=int(item.get("area_cells", 0)),
                water_state=str(item.get("water_state", "endorheic")),
                spill_elevation=(
                    None
                    if item.get("spill_elevation") is None
                    else float(item["spill_elevation"])
                ),
                mean_effective_inflow=float(item.get("mean_effective_inflow", 0.0)),
                feature_id=int(item.get("feature_id", 0)),
                water_body_id=int(item.get("water_body_id", 0)),
                outlet_type=str(item.get("outlet_type", "")),
                hydroperiod=str(item.get("hydroperiod", "")),
                ice_regime=str(item.get("ice_regime", "")),
                envelope_area_km2=float(item.get("envelope_area_km2", 0.0)),
                mean_wet_area_km2=float(item.get("mean_wet_area_km2", 0.0)),
            )
        )
    return lakes


def _load_basins(path: Path) -> list[BasinMeta]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[BasinMeta] = []
    for item in data.get("basins", []):
        out.append(
            BasinMeta(
                id=int(item["id"]),
                area_cells=int(item["area_cells"]),
                mean_elevation_m=float(item["mean_elevation_m"]),
                max_accumulation=float(item["max_accumulation"]),
                outlet_row=item.get("outlet_row"),
                outlet_col=item.get("outlet_col"),
                outlet_x=item.get("outlet_x"),
                outlet_y=item.get("outlet_y"),
            )
        )
    return out


def _load_index(path: Path) -> SpatialIndex:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SpatialIndex(
        nx=int(data.get("nx", 32)),
        ny=int(data.get("ny", 16)),
        buckets=dict(data.get("buckets", {})),
    )


@dataclass
class VectorStore:
    """Canonical coastline / rivers / lakes / basins + landform objects."""

    extent: SpatialExtent
    coastline: list[CoastlineFeature] = field(default_factory=list)
    rivers: RiverNetwork = field(default_factory=RiverNetwork)
    lakes: list[Lake] = field(default_factory=list)
    basins: list[BasinMeta] = field(default_factory=list)
    spatial_index: SpatialIndex = field(default_factory=SpatialIndex)
    mountain_ranges: list[dict[str, Any]] = field(default_factory=list)
    mountain_ridges: list[dict[str, Any]] = field(default_factory=list)
    plateaus: list[dict[str, Any]] = field(default_factory=list)
    plateau_rims: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_vector_geography(cls, vectors: VectorGeographyResult) -> VectorStore:
        return cls(
            extent=vectors.extent,
            coastline=list(vectors.coastline),
            rivers=vectors.rivers,
            lakes=list(vectors.lakes),
            basins=list(vectors.basins),
            spatial_index=vectors.spatial_index,
        )

    def attach_landforms(self, landforms: Any) -> None:
        from worldsim.physical.landforms.objects import (
            components_to_geojson_polygons,
            components_to_geojson_ridges,
            components_to_geojson_rims,
        )

        if landforms is None:
            return
        self.mountain_ranges = components_to_geojson_polygons(
            landforms.mountain_range_id,
            list(getattr(landforms, "mountain_ranges", [])),
            kind="mountain_range",
        )
        self.plateaus = components_to_geojson_polygons(
            landforms.plateau_id,
            list(getattr(landforms, "plateaus", [])),
            kind="plateau",
        )
        self.mountain_ridges = components_to_geojson_ridges(
            list(getattr(landforms, "mountain_ranges", []))
        )
        self.plateau_rims = components_to_geojson_rims(
            list(getattr(landforms, "plateaus", []))
        )

    def rebuild_spatial_index(self, *, nx: int = 32, ny: int = 16) -> SpatialIndex:
        self.spatial_index = build_spatial_index(
            coastline=self.coastline,
            river_network=self.rivers,
            lakes=self.lakes,
            nx=nx,
            ny=ny,
        )
        return self.spatial_index

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "extent.json").write_text(
            json.dumps(
                {"width": self.extent.width, "height": self.extent.height},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "coastline.json").write_text(
            json.dumps(
                {"features": [f.to_dict() for f in self.coastline]},
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "river_network.json").write_text(
            json.dumps(self.rivers.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "lakes.json").write_text(
            json.dumps(
                {"lakes": [lake.to_dict() for lake in self.lakes]},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
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
        _dump_feature_collection(directory / "mountain_ranges.geojson", self.mountain_ranges)
        _dump_feature_collection(directory / "mountain_ridges.geojson", self.mountain_ridges)
        _dump_feature_collection(directory / "plateaus.geojson", self.plateaus)
        _dump_feature_collection(directory / "plateau_rims.geojson", self.plateau_rims)

    @classmethod
    def load(cls, directory: Path) -> VectorStore:
        extent_meta = json.loads((directory / "extent.json").read_text(encoding="utf-8"))
        extent = SpatialExtent.from_shape(
            int(extent_meta["width"]), int(extent_meta["height"])
        )
        return cls(
            extent=extent,
            coastline=_load_coastline(directory / "coastline.json"),
            rivers=_load_rivers(directory / "river_network.json"),
            lakes=_load_lakes(directory / "lakes.json"),
            basins=_load_basins(directory / "basins.json"),
            spatial_index=_load_index(directory / "spatial_index.json"),
            mountain_ranges=_load_feature_collection(directory / "mountain_ranges.geojson"),
            mountain_ridges=_load_feature_collection(directory / "mountain_ridges.geojson"),
            plateaus=_load_feature_collection(directory / "plateaus.geojson"),
            plateau_rims=_load_feature_collection(directory / "plateau_rims.geojson"),
        )
