"""River node/segment network + polylines from PyFlwDir streams (Milestone 12).

Display policy (post-A4c): keep continuous river centreline through lakes;
opaque lake fills are drawn above rivers in the atlas.
``clip_polyline_outside_lakes`` remains available for tools/tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.channels import CHANNEL_STATE_NAME
from worldsim.physical.vectorize.coords import polyline_length_norm
from worldsim.spatial.extent import SpatialExtent

NodeType = Literal[
    "source",
    "confluence",
    "lake_inlet",
    "lake_outlet",
    "ocean_mouth",
    "endorheic_sink",
    "lod_cutoff",
    "junction",
    "mouth",  # legacy alias of ocean_mouth only
]
CANONICAL_TERMINALS = (
    "ocean_mouth",
    "lake_inlet",
    "lake_outlet",
    "endorheic_sink",
    "lod_cutoff",
)
_TERMINAL_HINTS = frozenset(
    {
        "lake_inlet",
        "lake_outlet",
        "ocean_mouth",
        "mouth",
        "source",
        "lod_cutoff",
        "endorheic_sink",
    }
)


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
        kind = "ocean_mouth" if self.type == "mouth" else str(self.type)
        payload: dict[str, Any] = {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "type": kind,
            "row": self.row,
            "col": self.col,
            "lake_id": self.lake_id,
        }
        if kind == "ocean_mouth":
            payload["legacy_type"] = "mouth"
        return payload


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
    channel_state: str = "none"
    catchment_km2: float = 0.0
    channel_length_km: float = 0.0
    monthly_bed_loss: list[float] = field(default_factory=list)
    bed_loss_mean: float = 0.0
    loss_limited: bool = False
    estimated_width_m: float = 0.0

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
            "channel_state": self.channel_state,
            "catchment_km2": float(self.catchment_km2),
            "channel_length_km": float(self.channel_length_km),
            "monthly_bed_loss": [float(v) for v in self.monthly_bed_loss],
            "bed_loss_mean": float(self.bed_loss_mean),
            "loss_limited": bool(self.loss_limited),
            "estimated_width_m": float(self.estimated_width_m),
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


def _ocean_adjacent(row: int, col: int, ocean: NDArray[np.bool_]) -> bool:
    h, w = ocean.shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr = int(row) + dr
            if rr < 0 or rr >= h:
                continue
            if bool(ocean[rr, (int(col) + dc) % w]):
                return True
    return False


def _canonical_node_type(hint: str) -> NodeType:
    if hint == "mouth":
        return "ocean_mouth"
    return hint  # type: ignore[return-value]


def classify_display_terminus(
    row: int,
    col: int,
    *,
    graph: Any,
    ocean: NDArray[np.bool_],
    lakes: NDArray[np.bool_],
    lake_id: NDArray[np.integer],
    display_mask: NDArray[np.bool_],
    physical_mask: NDArray[np.bool_] | None,
) -> tuple[NodeType, int]:
    """Terminal vocabulary for the last *display* channel cell (C9.1.3)."""
    from worldsim.physical.hydrology.cylindrical_graph import unravel

    r, c = int(row), int(col)
    to_lid = int(lake_id[r, c]) if lakes[r, c] else 0
    if to_lid > 0:
        return "lake_inlet", to_lid
    if _ocean_adjacent(r, c, ocean):
        return "ocean_mouth", 0
    j = int(graph.downstream_flat[r * graph.width + c])
    if j >= 0:
        nr, nc = unravel(j, graph.width)
        if ocean[nr, nc]:
            return "ocean_mouth", 0
        if lakes[nr, nc]:
            return "lake_inlet", int(lake_id[nr, nc])
        phys = bool(physical_mask[nr, nc]) if physical_mask is not None else False
        if phys and not bool(display_mask[nr, nc]):
            return "lod_cutoff", 0
    return "endorheic_sink", 0


def terminal_type_counts(network: RiverNetwork) -> dict[str, int]:
    counts = {k: 0 for k in CANONICAL_TERMINALS}
    counts["source"] = 0
    counts["confluence"] = 0
    counts["junction"] = 0
    counts["mouth_legacy"] = 0
    for node in network.nodes:
        kind = _canonical_node_type(str(node.type))
        if kind == "ocean_mouth":
            counts["ocean_mouth"] += 1
            if str(node.type) == "mouth":
                counts["mouth_legacy"] += 1
        elif kind in counts:
            counts[kind] += 1
    return counts


def ocean_mouth_ocean_adjacent_fraction(
    network: RiverNetwork, ocean: NDArray[np.bool_]
) -> float:
    mouths = [
        n
        for n in network.nodes
        if _canonical_node_type(str(n.type)) == "ocean_mouth"
    ]
    if not mouths:
        return 1.0
    ok = sum(1 for n in mouths if _ocean_adjacent(n.row, n.col, ocean))
    return float(ok) / float(len(mouths))


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
    channel_state: NDArray[np.integer] | None = None,
    channel_mask: NDArray[np.bool_] | None = None,
    flow_accumulation: NDArray[np.floating] | None = None,
    cell_area_km2: float | None = None,
    path_length_km: NDArray[np.floating] | None = None,
    monthly_bed_loss: NDArray[np.floating] | None = None,
    bed_loss_potential_m3s: NDArray[np.floating] | None = None,
) -> RiverNetwork:
    """Build canonical river network from the cylindrical D8 graph (PR-5).

    Does **not** reconstruct a non-periodic ``pyflwdir.FlwdirRaster`` from the
    cropped D8 raster (that created seam pits).
    """
    from worldsim.physical.hydrology.cylindrical_graph import (
        build_cylindrical_graph,
        cell_path_to_norm_geometry,
        extract_river_cell_paths,
    )

    d8 = np.asarray(flow_direction, dtype=np.uint8)
    mask = np.asarray(river_mask, dtype=np.bool_)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    lakes = np.asarray(lake_mask, dtype=np.bool_)
    lid_raster = (
        np.asarray(lake_id, dtype=np.int32)
        if lake_id is not None
        else lakes.astype(np.int32)
    )
    physical = (
        np.asarray(channel_mask, dtype=np.bool_)
        if channel_mask is not None and np.asarray(channel_mask).size
        else None
    )
    h, w = mask.shape
    if not np.any(mask):
        return RiverNetwork()

    graph = build_cylindrical_graph(d8, ocean)
    paths = extract_river_cell_paths(graph, mask)

    nodes_by_key: dict[tuple[int, int], RiverNode] = {}
    nodes: list[RiverNode] = []
    segments: list[RiverSegment] = []

    def get_node(
        nx: float,
        ny: float,
        hint: NodeType,
        *,
        node_lake_id: int = 0,
        row: int | None = None,
        col: int | None = None,
    ) -> RiverNode:
        key = _point_key(nx, ny)
        if key in nodes_by_key:
            node = nodes_by_key[key]
            if node_lake_id and not node.lake_id:
                node.lake_id = node_lake_id
            if hint in _TERMINAL_HINTS and node.type in (
                "junction",
                "source",
            ):
                node.type = _canonical_node_type(str(hint))
            return node
        if row is None or col is None:
            col_i = int(np.clip(np.floor((nx % 1.0) * w), 0, w - 1))
            row_i = int(np.clip(np.floor((1.0 - ny) * 0.5 * h), 0, h - 1))
        else:
            row_i, col_i = int(row), int(col) % w
        node = RiverNode(
            id=len(nodes) + 1,
            x=float(nx % 1.0) if np.isfinite(nx) else 0.0,
            y=ny,
            type=_canonical_node_type(str(hint)),
            row=row_i,
            col=col_i,
            lake_id=int(node_lake_id),
        )
        # Prefer storing unwrapped x for seam continuity in geometry; node x wrapped.
        nodes.append(node)
        nodes_by_key[key] = node
        return node

    for path in paths:
        rows = [p[0] for p in path]
        cols = [p[1] for p in path]
        geom = cell_path_to_norm_geometry(rows, cols, height=h, width=w)
        if len(geom) < 2:
            continue
        cleaned: list[tuple[float, float]] = [geom[0]]
        for p in geom[1:]:
            if _point_key(p[0], p[1]) != _point_key(cleaned[-1][0], cleaned[-1][1]):
                cleaned.append(p)
        if len(cleaned) < 2:
            continue
        geom = cleaned
        if polyline_length_norm(geom) < 1e-12:
            continue

        mid_i = len(path) // 2
        mr, mc = path[mid_i]
        order = int(stream_order[mr, mc])
        bid = int(basin_id[mr, mc])
        mean_q = float(discharge_proxy[mr, mc])
        monthly = [
            float(monthly_discharge[m, mr, mc])
            for m in range(monthly_discharge.shape[0])
        ]

        length = polyline_length_norm(geom)
        sr, sc = path[0]
        er, ec = path[-1]
        from_lid = int(lid_raster[sr, sc]) if lakes[sr, sc] else 0
        to_lid = int(lid_raster[er, ec]) if lakes[er, ec] else 0
        state_name = "none"
        if channel_state is not None and np.asarray(channel_state).size:
            state_name = CHANNEL_STATE_NAME.get(int(channel_state[mr, mc]), "none")
        catch_km2 = 0.0
        if flow_accumulation is not None and cell_area_km2 is not None:
            catch_km2 = float(flow_accumulation[mr, mc]) * float(cell_area_km2)
        length_km = 0.0
        if path_length_km is not None:
            length_km = float(
                sum(float(path_length_km[r, c]) for r, c in path)
            )
        monthly_loss = []
        if monthly_bed_loss is not None and monthly_bed_loss.size:
            monthly_loss = [
                float(monthly_bed_loss[m, mr, mc])
                for m in range(monthly_bed_loss.shape[0])
            ]
        loss_mean = float(np.mean(monthly_loss)) if monthly_loss else 0.0
        potential = 0.0
        if bed_loss_potential_m3s is not None and bed_loss_potential_m3s.size:
            potential = float(bed_loss_potential_m3s[mr, mc])
        available = mean_q + loss_mean
        loss_limited = bool(potential > available + 1e-12)
        width_est = float(min(400.0, 8.0 * math.sqrt(max(mean_q, 0.0))))

        start_t: NodeType = "lake_outlet" if from_lid else "source"
        end_t, end_lid = classify_display_terminus(
            er,
            ec,
            graph=graph,
            ocean=ocean,
            lakes=lakes,
            lake_id=lid_raster,
            display_mask=mask,
            physical_mask=physical,
        )
        if end_lid:
            to_lid = end_lid
        if end_t == "ocean_mouth":
            to_lid = 0

        p0 = get_node(
            geom[0][0], geom[0][1], start_t, node_lake_id=from_lid, row=sr, col=sc
        )
        p1 = get_node(
            geom[-1][0], geom[-1][1], end_t, node_lake_id=to_lid, row=er, col=ec
        )
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
            channel_state=state_name,
            catchment_km2=catch_km2,
            channel_length_km=length_km,
            monthly_bed_loss=monthly_loss,
            bed_loss_mean=loss_mean,
            loss_limited=loss_limited,
            estimated_width_m=width_est,
        )
        segments.append(seg)

    used = {s.from_node for s in segments} | {s.to_node for s in segments}
    nodes = [n for n in nodes if n.id in used]
    incoming: dict[int, int] = {}
    outgoing: dict[int, int] = {}
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
                kind, lid = classify_display_terminus(
                    node.row,
                    node.col,
                    graph=graph,
                    ocean=ocean,
                    lakes=lakes,
                    lake_id=lid_raster,
                    display_mask=mask,
                    physical_mask=physical,
                )
                node.type = kind
                if lid and not node.lake_id:
                    node.lake_id = lid
        # PC2: terminals only when outdegree=0.
        if out > 0 and node.type == "endorheic_sink":
            node.type = "confluence" if inc >= 2 else "junction"

    return RiverNetwork(nodes=nodes, segments=segments)


def validate_river_vector_topology(network: RiverNetwork) -> dict[str, int | bool]:
    """PC2 vector topology gates (addendum §6.3)."""
    outgoing: set[int] = {s.from_node for s in network.segments}
    incoming: dict[int, int] = {}
    for s in network.segments:
        incoming[s.to_node] = incoming.get(s.to_node, 0) + 1

    invalid_terminal = 0
    for node in network.nodes:
        out = 1 if node.id in outgoing else 0
        if node.type == "endorheic_sink" and out > 0:
            invalid_terminal += 1
        if node.type == "confluence" and out == 0 and incoming.get(node.id, 0) >= 2:
            invalid_terminal += 1

    counts = terminal_type_counts(network)
    ok = invalid_terminal == 0
    return {
        **counts,
        "invalid_terminal_with_outgoing_edge_count": int(invalid_terminal),
        "river_vector_topology_ok": bool(ok),
    }


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
