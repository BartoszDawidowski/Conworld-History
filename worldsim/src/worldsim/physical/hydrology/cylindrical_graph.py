"""Canonical E–W periodic hydrology graph on the original H×W grid (PR-5).

PyFlwDir may still condition the DEM and propose D8 codes. All accumulation,
basins, stream order, routing, and river vectors must use this graph — not a
cropped non-periodic ``FlwdirRaster``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np
from numpy.typing import NDArray

# ArcGIS / PyFlwDir D8 → (d_row, d_col); row increases south.
D8_DELTAS: dict[int, tuple[int, int]] = {
    1: (0, 1),
    2: (1, 1),
    4: (1, 0),
    8: (1, -1),
    16: (0, -1),
    32: (-1, -1),
    64: (-1, 0),
    128: (-1, 1),
}

SINK = -1  # ocean contact, N–S edge, pit, or broken cycle


def flat_index(row: int, col: int, width: int) -> int:
    return int(row) * int(width) + int(col)


def unravel(flat: int, width: int) -> tuple[int, int]:
    return divmod(int(flat), int(width))


@dataclass
class CylindricalFlowGraph:
    """Single-downstream drainage graph with cylindrical E–W topology."""

    height: int
    width: int
    ocean_mask: NDArray[np.bool_]
    flow_direction: NDArray[np.uint8]
    downstream_flat: NDArray[np.int32]  # SINK / ocean → -1

    @property
    def size(self) -> int:
        return int(self.height) * int(self.width)

    def downstream_rc(self, row: int, col: int) -> tuple[int, int] | None:
        ds = int(self.downstream_flat[flat_index(row, col, self.width)])
        if ds < 0:
            return None
        return unravel(ds, self.width)

    def iter_land(self) -> Iterator[int]:
        ocean = self.ocean_mask.ravel()
        for i in range(self.size):
            if not ocean[i]:
                yield i


def neighbor_from_d8(
    row: int,
    col: int,
    code: int,
    *,
    height: int,
    width: int,
) -> tuple[int, int] | None:
    """Next cell for a D8 code with E–W wrap; ``None`` if N–S invalid."""
    if code not in D8_DELTAS:
        return None
    dr, dc = D8_DELTAS[code]
    nr = int(row) + int(dr)
    if nr < 0 or nr >= height:
        return None
    nc = (int(col) + int(dc)) % int(width)
    return nr, nc


def build_downstream_flat(
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
) -> NDArray[np.int32]:
    """Map each cell to flat downstream index (or ``SINK``)."""
    d8 = np.asarray(flow_direction, dtype=np.uint8)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    ds = np.full(h * w, SINK, dtype=np.int32)
    for r in range(h):
        for c in range(w):
            if ocean[r, c]:
                continue
            nxt = neighbor_from_d8(r, c, int(d8[r, c]), height=h, width=w)
            if nxt is None:
                continue
            nr, nc = nxt
            if ocean[nr, nc]:
                continue
            ds[flat_index(r, c, w)] = flat_index(nr, nc, w)
    return _break_cycles(ds, ocean.ravel())


def _break_cycles(
    downstream_flat: NDArray[np.int32],
    ocean_flat: NDArray[np.bool_],
) -> NDArray[np.int32]:
    """Deterministically break cycles: lowest flat index in each cycle → sink."""
    ds = np.asarray(downstream_flat, dtype=np.int32).copy()
    n = ds.size
    state = np.zeros(n, dtype=np.uint8)  # 0 unseen, 1 visiting, 2 done

    for start in range(n):
        if ocean_flat[start] or state[start] != 0:
            continue
        path: list[int] = []
        i = start
        while True:
            if i < 0 or i >= n or ocean_flat[i]:
                for p in path:
                    state[p] = 2
                break
            if state[i] == 2:
                for p in path:
                    state[p] = 2
                break
            if state[i] == 1:
                # Cycle: path[k..] where path[k]==i
                k = path.index(i)
                cycle = path[k:]
                sink_at = min(cycle)
                ds[sink_at] = SINK
                for p in path:
                    state[p] = 2
                break
            state[i] = 1
            path.append(i)
            nxt = int(ds[i])
            if nxt < 0:
                for p in path:
                    state[p] = 2
                break
            i = nxt
    return ds


def build_cylindrical_graph(
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
) -> CylindricalFlowGraph:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    d8 = np.asarray(flow_direction, dtype=np.uint8)
    if d8.shape != ocean.shape:
        raise ValueError("flow_direction and ocean_mask shape mismatch")
    ds = build_downstream_flat(d8, ocean)
    return CylindricalFlowGraph(
        height=int(ocean.shape[0]),
        width=int(ocean.shape[1]),
        ocean_mask=ocean,
        flow_direction=d8,
        downstream_flat=ds,
    )


def _upstream_adjacency(graph: CylindricalFlowGraph) -> list[list[int]]:
    n = graph.size
    ups: list[list[int]] = [[] for _ in range(n)]
    ds = graph.downstream_flat
    ocean = graph.ocean_mask.ravel()
    for i in range(n):
        if ocean[i]:
            continue
        j = int(ds[i])
        if j >= 0:
            ups[j].append(i)
    return ups


def topological_order_upstream_first(graph: CylindricalFlowGraph) -> NDArray[np.int32]:
    """Land cells ordered sources → outlets (Kahn)."""
    n = graph.size
    ds = graph.downstream_flat
    ocean = graph.ocean_mask.ravel()
    indeg = np.zeros(n, dtype=np.int32)
    for i in range(n):
        if ocean[i]:
            continue
        j = int(ds[i])
        if j >= 0:
            indeg[j] += 1
    q: deque[int] = deque(
        i for i in range(n) if (not ocean[i]) and indeg[i] == 0
    )
    order: list[int] = []
    while q:
        i = q.popleft()
        order.append(i)
        j = int(ds[i])
        if j >= 0:
            indeg[j] -= 1
            if indeg[j] == 0:
                q.append(j)
    # Orphans in cycles already broken; append any leftover land
    if len(order) < int(np.count_nonzero(~ocean)):
        seen = set(order)
        for i in range(n):
            if not ocean[i] and i not in seen:
                order.append(i)
    return np.asarray(order, dtype=np.int32)


def accumulate_weights(
    graph: CylindricalFlowGraph,
    weights: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Route ``weights`` downstream (includes local contribution)."""
    w = np.asarray(weights, dtype=np.float64)
    if w.shape != (graph.height, graph.width):
        raise ValueError("weights shape mismatch")
    ocean = graph.ocean_mask
    acc = np.where(ocean, 0.0, w).ravel().copy()
    ds = graph.downstream_flat
    for i in topological_order_upstream_first(graph):
        j = int(ds[i])
        if j >= 0:
            acc[j] += acc[i]
    out = acc.reshape(graph.height, graph.width)
    return np.where(ocean, 0.0, out)


def accumulate_cells(graph: CylindricalFlowGraph) -> NDArray[np.float64]:
    """Upstream cell count (self included)."""
    ones = np.ones((graph.height, graph.width), dtype=np.float64)
    ones[graph.ocean_mask] = 0.0
    return accumulate_weights(graph, ones)


def label_basins(graph: CylindricalFlowGraph) -> NDArray[np.int32]:
    """Basin ID = remapped outlet flat index (deterministic, contiguous ≥ 1)."""
    h, w = graph.height, graph.width
    n = graph.size
    ds = graph.downstream_flat
    ocean = graph.ocean_mask.ravel()
    root = np.full(n, SINK, dtype=np.int32)

    def find_outlet(i: int) -> int:
        seen: list[int] = []
        while True:
            if root[i] >= 0:
                out = int(root[i])
                for s in seen:
                    root[s] = out
                return out
            seen.append(i)
            j = int(ds[i])
            if j < 0:
                out = i  # self is outlet / pit
                for s in seen:
                    root[s] = out
                return out
            i = j

    outlet_ids: set[int] = set()
    for i in range(n):
        if ocean[i]:
            continue
        outlet_ids.add(find_outlet(i))

    mapping = {oid: k + 1 for k, oid in enumerate(sorted(outlet_ids))}
    basins = np.zeros((h, w), dtype=np.int32)
    flat_b = basins.ravel()
    for i in range(n):
        if ocean[i]:
            continue
        flat_b[i] = mapping[find_outlet(i)]
    return basins


def stream_order_strahler(graph: CylindricalFlowGraph) -> NDArray[np.int16]:
    ups = _upstream_adjacency(graph)
    h, w = graph.height, graph.width
    order = np.zeros(h * w, dtype=np.int16)
    ocean = graph.ocean_mask.ravel()
    for i in topological_order_upstream_first(graph):
        if ocean[i]:
            continue
        parents = ups[i]
        if not parents:
            order[i] = 1
            continue
        po = [int(order[p]) for p in parents]
        m = max(po)
        if sum(1 for v in po if v == m) >= 2:
            order[i] = m + 1
        else:
            order[i] = m
    out = order.reshape(h, w)
    return np.where(graph.ocean_mask, 0, out).astype(np.int16)


def outlet_points(graph: CylindricalFlowGraph) -> list[tuple[int, int]]:
    """Land cells whose downstream is a sink (ocean / edge / pit)."""
    pts: list[tuple[int, int]] = []
    ds = graph.downstream_flat
    ocean = graph.ocean_mask.ravel()
    w = graph.width
    for i in range(graph.size):
        if ocean[i]:
            continue
        if int(ds[i]) < 0:
            pts.append(unravel(i, w))
    return pts


def effective_discharge(
    graph: CylindricalFlowGraph,
    precip: NDArray[np.floating],
    sink: NDArray[np.floating],
) -> NDArray[np.float64]:
    """``q = max(0, precip + Σ upstream q − sink)`` on the canonical graph."""
    ocean = graph.ocean_mask
    p = np.where(ocean, 0.0, np.asarray(precip, dtype=np.float64)).ravel()
    s = np.where(ocean, 0.0, np.asarray(sink, dtype=np.float64)).ravel()
    ups = _upstream_adjacency(graph)
    q = np.zeros(graph.size, dtype=np.float64)
    for i in topological_order_upstream_first(graph):
        if ocean.ravel()[i]:
            continue
        total = float(p[i])
        for u in ups[i]:
            total += q[u]
        total -= float(s[i])
        q[i] = total if total > 0.0 else 0.0
    out = q.reshape(graph.height, graph.width)
    return np.where(ocean, 0.0, out)


def validate_graph(graph: CylindricalFlowGraph) -> dict[str, Any]:
    """Exhaustive topology checks (not a random 85% sample)."""
    h, w = graph.height, graph.width
    ds = graph.downstream_flat
    ocean = graph.ocean_mask
    d8 = graph.flow_direction
    n_land = int(np.count_nonzero(~ocean))
    issues: list[str] = []

    # Every land cell has at most one downstream; ocean is sink-coded.
    for i in range(graph.size):
        r, c = unravel(i, w)
        if ocean[r, c]:
            if int(ds[i]) != SINK:
                issues.append(f"ocean_cell_has_downstream@{r},{c}")
                break
            continue
        j = int(ds[i])
        if j < 0:
            continue
        if j >= graph.size:
            issues.append(f"downstream_oob@{r},{c}")
            break
        nr, nc = unravel(j, w)
        if ocean[nr, nc]:
            issues.append(f"downstream_is_ocean_cell@{r},{c}")
            break
        # Must match D8 neighbour (when D8 valid)
        code = int(d8[r, c])
        nxt = neighbor_from_d8(r, c, code, height=h, width=w)
        if nxt is not None and not ocean[nxt]:
            if flat_index(nxt[0], nxt[1], w) != j:
                issues.append(f"d8_mismatch@{r},{c}")
                break

    # No cycles
    state = np.zeros(graph.size, dtype=np.uint8)
    cycle_found = False
    for start in range(graph.size):
        if ocean.ravel()[start] or state[start]:
            continue
        i = start
        path_set: set[int] = set()
        while i >= 0 and not ocean.ravel()[i]:
            if state[i] == 2:
                break
            if i in path_set:
                cycle_found = True
                break
            path_set.add(i)
            state[i] = 1
            i = int(ds[i])
        for p in path_set:
            state[p] = 2
        if cycle_found:
            break
    if cycle_found:
        issues.append("cycle_detected")

    # Downstream accumulation non-decreasing along every land→land edge
    acc = accumulate_cells(graph)
    acc_flat = acc.ravel()
    bad_edges = 0
    edge_count = 0
    for i in range(graph.size):
        if ocean.ravel()[i]:
            continue
        j = int(ds[i])
        if j < 0:
            continue
        edge_count += 1
        if acc_flat[j] + 1e-9 < acc_flat[i]:
            bad_edges += 1
    if bad_edges:
        issues.append(f"acc_decreases_edges={bad_edges}")

    # Seam-crossing edges: D8 step wraps E–W; basin ID must match
    basins = label_basins(graph)
    seam_edges = 0
    seam_basin_mismatch = 0
    for i in range(graph.size):
        if ocean.ravel()[i]:
            continue
        j = int(ds[i])
        if j < 0:
            continue
        r, c = unravel(i, w)
        nr, nc = unravel(j, w)
        code = int(d8[r, c])
        if code not in D8_DELTAS:
            continue
        _dr, dc = D8_DELTAS[code]
        if dc == 0:
            continue
        if 0 <= c + dc < w:
            continue
        seam_edges += 1
        if int(basins[r, c]) != int(basins[nr, nc]):
            seam_basin_mismatch += 1

    if seam_basin_mismatch:
        issues.append(f"seam_basin_mismatch={seam_basin_mismatch}")

    return {
        "graph_algorithm": "cylindrical_v1",
        "land_cells": n_land,
        "edge_count": edge_count,
        "bad_accumulation_edges": bad_edges,
        "seam_crossing_edges": seam_edges,
        "seam_basin_mismatch": seam_basin_mismatch,
        "basin_count": int(len(np.unique(basins[basins > 0]))),
        "outlet_count": len(outlet_points(graph)),
        "issues": issues[:20],
        "graph_valid": len(issues) == 0 and n_land > 0,
        "downstream_accumulation_ok": bad_edges == 0 and edge_count > 0,
    }


def rotate_longitude(
    array: NDArray,
    shift_cols: int,
) -> NDArray:
    """Roll columns east by ``shift_cols`` (positive → content moves east)."""
    return np.roll(np.asarray(array), int(shift_cols), axis=1)


def unwrap_column_path(cols: list[int], width: int) -> list[float]:
    """Make column indices continuous across the E–W seam."""
    if not cols:
        return []
    out = [float(cols[0])]
    w = float(width)
    for c in cols[1:]:
        prev = out[-1]
        # Choose c + k*W closest to prev
        best = float(c)
        best_dist = abs(best - prev)
        for k in (-2, -1, 1, 2):
            cand = float(c) + k * w
            d = abs(cand - prev)
            if d < best_dist:
                best, best_dist = cand, d
        out.append(best)
    return out


def cell_path_to_norm_geometry(
    rows: list[int],
    cols: list[int],
    *,
    height: int,
    width: int,
) -> list[tuple[float, float]]:
    """Polyline in normalised cylindrical space with seam unwrap."""
    if len(rows) < 2:
        return []
    ucols = unwrap_column_path(cols, width)
    geom: list[tuple[float, float]] = []
    for r, c in zip(rows, ucols, strict=True):
        x = (float(c) + 0.5) / float(width)
        y = 1.0 - (float(r) + 0.5) * 2.0 / float(height)
        geom.append((float(x), float(y)))
    return geom


def extract_river_cell_paths(
    graph: CylindricalFlowGraph,
    river_mask: NDArray[np.bool_],
) -> list[list[tuple[int, int]]]:
    """Maximal non-branching river paths (split at heads / confluences / mouths)."""
    mask = np.asarray(river_mask, dtype=np.bool_) & ~graph.ocean_mask
    w = graph.width
    ds = graph.downstream_flat
    n = graph.size

    def in_river(flat: int) -> bool:
        r, c = unravel(flat, w)
        return bool(mask[r, c])

    river_indeg = np.zeros(n, dtype=np.int32)
    for i in range(n):
        if not in_river(i):
            continue
        j = int(ds[i])
        if j >= 0 and in_river(j):
            river_indeg[j] += 1

    paths: list[list[tuple[int, int]]] = []
    for i in range(n):
        if not in_river(i):
            continue
        j = int(ds[i])
        if j < 0 or not in_river(j):
            continue
        # Start segment at heads (indeg 0) and confluences (indeg ≥ 2), and
        # also at cells that begin a unique chain after a split (indeg != 1).
        if int(river_indeg[i]) == 1:
            continue
        path: list[tuple[int, int]] = [unravel(i, w)]
        cur = i
        guard = 0
        while guard < n + 2:
            nxt = int(ds[cur])
            if nxt < 0 or not in_river(nxt):
                break
            path.append(unravel(nxt, w))
            cur = nxt
            guard += 1
            if int(river_indeg[cur]) != 1:
                break
        if len(path) >= 2:
            paths.append(path)
    return paths


def graph_products(
    graph: CylindricalFlowGraph,
) -> dict[str, Any]:
    """Accumulation, basins, order, outlets, validation."""
    acc = accumulate_cells(graph)
    basins = label_basins(graph)
    order = stream_order_strahler(graph)
    outlets = outlet_points(graph)
    diag = validate_graph(graph)
    return {
        "flow_accumulation": acc,
        "basin_id": basins,
        "watershed_id": basins.copy(),
        "stream_order": order,
        "outlet_points": outlets,
        "graph_diagnostics": diag,
    }
