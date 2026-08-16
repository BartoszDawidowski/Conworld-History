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
    """Canonical coastline / rivers / lakes / basins + spatial index."""

    extent: SpatialExtent
    coastline: list[CoastlineFeature] = field(default_factory=list)
    rivers: RiverNetwork = field(default_factory=RiverNetwork)
    lakes: list[Lake] = field(default_factory=list)
    basins: list[BasinMeta] = field(default_factory=list)
    spatial_index: SpatialIndex = field(default_factory=SpatialIndex)

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
        )
