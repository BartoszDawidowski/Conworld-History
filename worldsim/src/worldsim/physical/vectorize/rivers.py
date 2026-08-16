"""River node/segment network + polylines from PyFlwDir streams (Milestone 12).

Display policy (post-A4c): keep continuous river centreline through lakes;
opaque lake fills are drawn above rivers in the atlas.
``clip_polyline_outside_lakes`` remains available for tools/tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pyflwdir
from numpy.typing import NDArray

from worldsim.physical.vectorize.coords import (
    polyline_length_norm,
    pyflwdir_xy_to_norm,
)
from worldsim.spatial.extent import SpatialExtent

NodeType = Literal["source", "confluence", "lake_inlet", "lake_outlet", "mouth", "junction"]


@dataclass
class RiverNode:
    id: int
    x: float
    y: float
    type: NodeType
    row: int
    col: int
    lake_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "type": self.type,
            "row": self.row,
            "col": self.col,
            "lake_id": self.lake_id,
        }


@dataclass
class RiverSegment:
    id: int
    from_node: int
    to_node: int
    geometry: list[tuple[float, float]]
    strahler_order: int
    mean_discharge: float
    monthly_discharge: list[float]
    basin_id: int
    length: float
    ## A4c: lake left at start (outlet) / entered at end (inlet); 0 = none.
    from_lake_id: int = 0
    to_lake_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "geometry": [[float(x), float(y)] for x, y in self.geometry],
            "strahler_order": self.strahler_order,
            "mean_discharge": self.mean_discharge,
            "monthly_discharge": [float(v) for v in self.monthly_discharge],
            "basin_id": self.basin_id,
            "length": self.length,
            "from_lake_id": self.from_lake_id,
            "to_lake_id": self.to_lake_id,
        }


@dataclass
class RiverNetwork:
    nodes: list[RiverNode] = field(default_factory=list)
    segments: list[RiverSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "segments": [s.to_dict() for s in self.segments],
        }


@dataclass(frozen=True)
class ClippedRiverPiece:
    """Land-only polyline with optional shoreline snaps + lake ids (A4c)."""

    geometry: list[tuple[float, float]]
    from_lake_id: int = 0
    to_lake_id: int = 0


def _point_key(x: float, y: float, *, quant: float = 1e-5) -> tuple[int, int]:
    return (int(round(x / quant)), int(round(y / quant)))


def _norm_to_row_col(x: float, y: float, height: int, width: int) -> tuple[int, int]:
    col = int(np.clip(np.floor(x * width), 0, width - 1))
    row = int(np.clip(np.floor((1.0 - y) * 0.5 * height), 0, height - 1))
    return row, col


def _midpoint_norm(
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, float]:
    """Midpoint in normalised space with local E–W unwrap (shoreline snap)."""
    ax, ay = a
    bx, by = b
    dx = bx - ax
    if dx > 0.5:
        bx -= 1.0
    elif dx < -0.5:
        bx += 1.0
    mx = (ax + bx) * 0.5
    my = (ay + by) * 0.5
    mx = mx % 1.0
    if mx < 0.0:
        mx += 1.0
    return float(mx), float(my)


def _lake_id_at(
    x: float,
    y: float,
    lake_id: NDArray[np.integer],
    height: int,
    width: int,
) -> int:
    r, c = _norm_to_row_col(x, y, height, width)
    return int(lake_id[r, c])


def clip_polyline_outside_lakes(
    geom: list[tuple[float, float]],
    lake_mask: NDArray[np.bool_],
    lake_id: NDArray[np.integer] | None = None,
) -> list[ClippedRiverPiece]:
    """Split polyline outside lakes and snap ends to the land/lake shoreline.

    Shore snap = midpoint between consecutive land and lake vertices (shared
    cell edge). ``from_lake_id`` / ``to_lake_id`` come from the ``lake_id``
    raster at the lake contact cell (never nearest-centroid).
    """
    lakes = np.asarray(lake_mask, dtype=np.bool_)
    h, w = lakes.shape
    if lake_id is None:
        ids = lakes.astype(np.int32)
    else:
        ids = np.asarray(lake_id)

    pieces: list[ClippedRiverPiece] = []
    if len(geom) < 2:
        return pieces

    current: list[tuple[float, float]] = []
    from_lid = 0
    pending_outlet: tuple[tuple[float, float], int] | None = None

    def _flush(to_lid: int) -> None:
        nonlocal current, from_lid
        if len(current) >= 2:
            pieces.append(
                ClippedRiverPiece(
                    geometry=list(current),
                    from_lake_id=int(from_lid),
                    to_lake_id=int(to_lid),
                )
            )
        current = []
        from_lid = 0

    for pt in geom:
        x, y = float(pt[0]), float(pt[1])
        r, c = _norm_to_row_col(x, y, h, w)
        inside = bool(lakes[r, c])
        if inside:
            lid = int(ids[r, c])
            if current:
                # Land → lake: snap endpoint onto shoreline, then flush.
                snap = _midpoint_norm(current[-1], (x, y))
                if _point_key(snap[0], snap[1]) != _point_key(
                    current[-1][0], current[-1][1]
                ):
                    current.append(snap)
                _flush(to_lid=lid if lid > 0 else 1)
            pending_outlet = ((x, y), lid if lid > 0 else 1)
        else:
            if pending_outlet is not None:
                lake_pt, lid = pending_outlet
                snap = _midpoint_norm(lake_pt, (x, y))
                current = [snap, (x, y)]
                from_lid = lid
                pending_outlet = None
            else:
                current.append((x, y))

    _flush(to_lid=0)
    return pieces


def build_river_network(
    *,
    flow_direction: NDArray[np.uint8],
    river_mask: NDArray[np.bool_],
    stream_order: NDArray[np.integer],
    basin_id: NDArray[np.integer],
    ocean_mask: NDArray[np.bool_],
    lake_mask: NDArray[np.bool_],
    discharge_proxy: NDArray[np.floating],
    monthly_discharge: NDArray[np.floating],
    extent: SpatialExtent,
    lake_id: NDArray[np.integer] | None = None,
) -> RiverNetwork:
    """Build canonical river network from D8 + river mask (hex-independent)."""
    d8 = np.asarray(flow_direction)
    mask = np.asarray(river_mask, dtype=np.bool_)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    lakes = np.asarray(lake_mask, dtype=np.bool_)
    lid_raster = (
        np.asarray(lake_id, dtype=np.int32)
        if lake_id is not None
        else lakes.astype(np.int32)
    )
    h, w = mask.shape

    flw = pyflwdir.from_array(d8, ftype="d8", check_ftype=False)
    if not np.any(mask):
        return RiverNetwork()
    feats = flw.streams(mask=mask, direction="down")

    nodes_by_key: dict[tuple[int, int], RiverNode] = {}
    nodes: list[RiverNode] = []
    segments: list[RiverSegment] = []

    def get_node(
        nx: float,
        ny: float,
        hint: NodeType,
        *,
        node_lake_id: int = 0,
    ) -> RiverNode:
        key = _point_key(nx, ny)
        if key in nodes_by_key:
            node = nodes_by_key[key]
            if node_lake_id and not node.lake_id:
                node.lake_id = node_lake_id
            if hint in ("lake_inlet", "lake_outlet", "mouth", "source") and node.type in (
                "junction",
                "source",
            ):
                node.type = hint
            return node
        col = int(np.clip(np.floor(nx * w), 0, w - 1))
        row = int(np.clip(np.floor((1.0 - ny) * 0.5 * h), 0, h - 1))
        node = RiverNode(
            id=len(nodes) + 1,
            x=nx,
            y=ny,
            type=hint,
            row=row,
            col=col,
            lake_id=int(node_lake_id),
        )
        nodes.append(node)
        nodes_by_key[key] = node
        return node

    incoming: dict[int, int] = {}
    outgoing: dict[int, int] = {}

    for feat in feats:
        coords_raw = feat["geometry"]["coordinates"]
        if len(coords_raw) < 2:
            continue
        geom = [pyflwdir_xy_to_norm(float(x), float(y), extent) for x, y in coords_raw]
        cleaned: list[tuple[float, float]] = [geom[0]]
        for p in geom[1:]:
            if _point_key(p[0], p[1]) != _point_key(cleaned[-1][0], cleaned[-1][1]):
                cleaned.append(p)
        if len(cleaned) < 2:
            continue
        geom = cleaned
        if polyline_length_norm(geom) < 1e-12:
            continue

        mid = geom[len(geom) // 2]
        col = int(np.clip(np.floor(mid[0] * w), 0, w - 1))
        row = int(np.clip(np.floor((1.0 - mid[1]) * 0.5 * h), 0, h - 1))
        order = int(stream_order[row, col])
        bid = int(basin_id[row, col])
        mean_q = float(discharge_proxy[row, col])
        monthly = [
            float(monthly_discharge[m, row, col])
            for m in range(monthly_discharge.shape[0])
        ]

        # Continuous centreline (no clip through lakes). Atlas covers through-flow
        # by drawing opaque lakes above rivers.
        length = polyline_length_norm(geom)
        sr, sc = _norm_to_row_col(geom[0][0], geom[0][1], h, w)
        er, ec = _norm_to_row_col(geom[-1][0], geom[-1][1], h, w)
        from_lid = int(lid_raster[sr, sc]) if lakes[sr, sc] else 0
        to_lid = int(lid_raster[er, ec]) if lakes[er, ec] else 0

        start_t: NodeType = "lake_outlet" if from_lid else "source"
        end_t: NodeType = "lake_inlet" if to_lid else "junction"
        for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            rr, cc = er + dj, (ec + di) % w
            if 0 <= rr < h and ocean[rr, cc]:
                end_t = "mouth"
                to_lid = 0
                break

        p0 = get_node(geom[0][0], geom[0][1], start_t, node_lake_id=from_lid)
        p1 = get_node(geom[-1][0], geom[-1][1], end_t, node_lake_id=to_lid)
        if p0.id == p1.id:
            continue
        seg = RiverSegment(
            id=len(segments) + 1,
            from_node=p0.id,
            to_node=p1.id,
            geometry=geom,
            strahler_order=order,
            mean_discharge=mean_q,
            monthly_discharge=monthly,
            basin_id=bid,
            length=length,
            from_lake_id=from_lid,
            to_lake_id=to_lid,
        )
        segments.append(seg)
        outgoing[p0.id] = outgoing.get(p0.id, 0) + 1
        incoming[p1.id] = incoming.get(p1.id, 0) + 1

    used = {s.from_node for s in segments} | {s.to_node for s in segments}
    nodes = [n for n in nodes if n.id in used]
    incoming = {}
    outgoing = {}
    for s in segments:
        outgoing[s.from_node] = outgoing.get(s.from_node, 0) + 1
        incoming[s.to_node] = incoming.get(s.to_node, 0) + 1

    for node in nodes:
        inc = incoming.get(node.id, 0)
        out = outgoing.get(node.id, 0)
        if node.type == "junction":
            if inc >= 2:
                node.type = "confluence"
            elif inc == 0 and out >= 1:
                node.type = "source"
            elif out == 0 and inc >= 1:
                node.type = "mouth"

    return RiverNetwork(nodes=nodes, segments=segments)


def river_raster_consistency(
    network: RiverNetwork,
    river_mask: NDArray[np.bool_],
    flow_accumulation: NDArray[np.floating],
    *,
    samples_per_seg: int = 3,
) -> float:
    """Fraction of sampled polyline points on river_mask or high-accumulation cells."""
    mask = np.asarray(river_mask, dtype=np.bool_)
    acc = np.asarray(flow_accumulation, dtype=np.float64)
    h, w = mask.shape
    if not network.segments:
        return 0.0
    thr = float(np.median(acc[mask])) if np.any(mask) else 0.0
    ok = 0
    total = 0
    for seg in network.segments:
        pts = seg.geometry
        if len(pts) < 2:
            continue
        idxs = np.linspace(0, len(pts) - 1, num=min(samples_per_seg, len(pts)), dtype=int)
        for k in idxs:
            x, y = pts[int(k)]
            c = int(np.clip(np.floor(x * w), 0, w - 1))
            r = int(np.clip(np.floor((1.0 - y) * 0.5 * h), 0, h - 1))
            total += 1
            if mask[r, c] or acc[r, c] >= thr * 0.5:
                ok += 1
    return float(ok / max(total, 1))


def topology_valid(network: RiverNetwork) -> bool:
    """Basic topology: segment endpoints reference existing nodes; no empty segs."""
    if not network.segments:
        return True
    ids = {n.id for n in network.nodes}
    for s in network.segments:
        if s.from_node not in ids or s.to_node not in ids:
            return False
        if len(s.geometry) < 2:
            return False
        if s.from_node == s.to_node and s.length < 1e-12:
            return False
    return True
