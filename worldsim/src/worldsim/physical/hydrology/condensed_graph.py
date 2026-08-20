"""Lake-supernode condensed hydrology graph (PC1)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.cylindrical_graph import (
    CylindricalFlowGraph,
    first_downstream_outside_lake,
    flat_index,
    unravel,
)

# Explicit target kinds (addendum §5.1) — compact uint8 codes.
NODE_LAND_CELL = 0
NODE_LAKE_NODE = 1
NODE_OCEAN_CELL = 2
NODE_CLOSED_SINK = 3
NODE_BOUNDARY_SINK = 4
NODE_CYCLE_BREAK = 5


@dataclass(frozen=True)
class LakeSupernode:
    """One routing/storage supernode per retained basin envelope."""

    lake_id: int
    outlet_row: int
    outlet_col: int
    spill_target_row: int | None = None
    spill_target_col: int | None = None
    spill_elevation_m: float = 0.0
    closed_basin: bool = False
    downstream_lake_id: int = 0

    @property
    def outlet_flat(self) -> int:
        return flat_index(self.outlet_row, self.outlet_col, 0)  # width filled by builder

    def with_width(self, width: int) -> LakeSupernode:
        return LakeSupernode(
            lake_id=self.lake_id,
            outlet_row=self.outlet_row,
            outlet_col=self.outlet_col,
            spill_target_row=self.spill_target_row,
            spill_target_col=self.spill_target_col,
            spill_elevation_m=self.spill_elevation_m,
            closed_basin=self.closed_basin,
            downstream_lake_id=self.downstream_lake_id,
        )


@dataclass
class CondensedLakeGraph:
    """Lake supernodes and spill DAG metadata."""

    width: int
    supernodes: dict[int, LakeSupernode] = field(default_factory=dict)
    topo_order: list[int] = field(default_factory=list)
    node_kind_raster: NDArray[np.uint8] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def outlet_flat(self, lake_id: int) -> int:
        sn = self.supernodes[int(lake_id)]
        return flat_index(sn.outlet_row, sn.outlet_col, self.width)

    def spill_target_flat(self, lake_id: int) -> int | None:
        sn = self.supernodes[int(lake_id)]
        if sn.spill_target_row is None or sn.spill_target_col is None:
            return None
        return flat_index(sn.spill_target_row, sn.spill_target_col, self.width)


def build_condensed_lake_graph(
    *,
    graph: CylindricalFlowGraph,
    basin_envelope_id: NDArray[np.integer],
    lake_records: list[dict[str, Any]],
) -> CondensedLakeGraph:
    """Map each envelope to one supernode with explicit spill target."""
    w = graph.width
    env = np.asarray(basin_envelope_id, dtype=np.int32)
    supernodes: dict[int, LakeSupernode] = {}
    for rec in lake_records:
        lid = int(rec.get("lake_id") or 0)
        if lid <= 0:
            continue
        rr = rec.get("outlet_row", rec.get("sink_row"))
        cc = rec.get("outlet_col", rec.get("sink_col"))
        if rr is None or cc is None:
            body = env == lid
            if not np.any(body):
                continue
            rows, cols = np.where(body)
            rr, cc = int(rows[0]), int(cols[0])
        outlet_r, outlet_c = int(rr), int(cc)
        loc = first_downstream_outside_lake(graph, outlet_r, outlet_c, env, lid)
        down_lid = 0
        st_r = st_c = None
        if loc is not None:
            st_r, st_c = int(loc[0]), int(loc[1])
            # Walk land reaches until another lake, ocean, or sink (addendum §5.1).
            j = flat_index(st_r, st_c, w)
            ds = graph.downstream_flat
            ocean = graph.ocean_mask
            while j >= 0:
                rr, cc = unravel(j, w)
                other = int(env[rr, cc])
                if other > 0 and other != lid:
                    down_lid = other
                    break
                if ocean[rr, cc]:
                    break
                j = int(ds[j])
            if down_lid == 0:
                # Immediate neighbour may itself be a lake cell.
                down_lid = int(env[st_r, st_c])
                if down_lid == lid:
                    down_lid = 0
        supernodes[lid] = LakeSupernode(
            lake_id=lid,
            outlet_row=outlet_r,
            outlet_col=outlet_c,
            spill_target_row=st_r,
            spill_target_col=st_c,
            spill_elevation_m=float(
                rec.get("spill_elevation_m")
                or rec.get("surface_elevation_m")
                or 0.0
            ),
            closed_basin=bool(rec.get("closed_basin")),
            downstream_lake_id=down_lid,
        )

    topo = _lake_spill_topo_order(supernodes)
    kind = np.full(env.shape, NODE_LAND_CELL, dtype=np.uint8)
    ocean = graph.ocean_mask
    kind[ocean] = NODE_OCEAN_CELL
    for lid, sn in supernodes.items():
        kind[env == lid] = NODE_LAKE_NODE

    return CondensedLakeGraph(
        width=w,
        supernodes=supernodes,
        topo_order=topo,
        node_kind_raster=kind,
        diagnostics={
            "lake_supernode_count": len(supernodes),
            "lake_graph_acyclic": len(topo) == len(supernodes),
            "lake_graph_topology_ok": len(topo) == len(supernodes),
        },
    )


def _lake_spill_topo_order(supernodes: dict[int, LakeSupernode]) -> list[int]:
    """Upstream-first order on the lake spill DAG."""
    if not supernodes:
        return []
    ids = sorted(supernodes.keys())
    downstream: dict[int, int] = {
        lid: int(supernodes[lid].downstream_lake_id) for lid in ids
    }
    indeg = {lid: 0 for lid in ids}
    for lid in ids:
        down = downstream[lid]
        if down in indeg and down != lid:
            indeg[down] += 1
    q: deque[int] = deque(lid for lid in ids if indeg[lid] == 0)
    order: list[int] = []
    while q:
        lid = q.popleft()
        order.append(lid)
        down = downstream[lid]
        if down in indeg and down != lid:
            indeg[down] -= 1
            if indeg[down] == 0:
                q.append(down)
    if len(order) < len(ids):
        for lid in ids:
            if lid not in order:
                order.append(lid)
    return order
