"""Simple grid spatial index for vector features (Milestone 12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class SpatialIndex:
    """Uniform grid buckets over normalised cylindrical (x, y).

    Keys are ``\"ix:iy\"``; values list ``(layer, feature_id)``.
    Independent of any hex analysis grid.
    """

    nx: int = 32
    ny: int = 16
    buckets: dict[str, list[list[Any]]] = field(default_factory=dict)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        ix = int(x * self.nx) % self.nx
        # y in [-1, 1] → [0, ny)
        t = (float(y) + 1.0) * 0.5
        iy = int(max(0, min(self.ny - 1, t * self.ny)))
        return ix, iy

    def insert_point(self, layer: str, feature_id: int, x: float, y: float) -> None:
        ix, iy = self._cell(x, y)
        key = f"{ix}:{iy}"
        self.buckets.setdefault(key, []).append([layer, int(feature_id)])

    def insert_polyline(
        self,
        layer: str,
        feature_id: int,
        coords: Iterable[tuple[float, float]],
    ) -> None:
        seen: set[str] = set()
        for x, y in coords:
            ix, iy = self._cell(x, y)
            key = f"{ix}:{iy}"
            if key in seen:
                continue
            seen.add(key)
            self.buckets.setdefault(key, []).append([layer, int(feature_id)])

    def query_point(self, x: float, y: float) -> list[list[Any]]:
        ix, iy = self._cell(x, y)
        return list(self.buckets.get(f"{ix}:{iy}", []))

    def to_dict(self) -> dict[str, Any]:
        return {"nx": self.nx, "ny": self.ny, "buckets": self.buckets}


def build_spatial_index(
    *,
    coastline: list[Any],
    river_network: Any,
    lakes: list[Any],
    nx: int = 32,
    ny: int = 16,
) -> SpatialIndex:
    idx = SpatialIndex(nx=nx, ny=ny)
    for f in coastline:
        idx.insert_polyline("coastline", f.id, f.geometry)
    for s in river_network.segments:
        idx.insert_polyline("river_segment", s.id, s.geometry)
    for n in river_network.nodes:
        idx.insert_point("river_node", n.id, n.x, n.y)
    for lake in lakes:
        idx.insert_polyline("lake", lake.id, lake.polygon)
    return idx
