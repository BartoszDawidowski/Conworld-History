"""Basin metadata derived from hydrology rasters (Milestone 12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.vectorize.coords import cell_center_norm
from worldsim.spatial.extent import SpatialExtent


@dataclass
class BasinMeta:
    id: int
    area_cells: int
    mean_elevation_m: float
    max_accumulation: float
    outlet_row: int | None
    outlet_col: int | None
    outlet_x: float | None
    outlet_y: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "area_cells": self.area_cells,
            "mean_elevation_m": self.mean_elevation_m,
            "max_accumulation": self.max_accumulation,
            "outlet_row": self.outlet_row,
            "outlet_col": self.outlet_col,
            "outlet_x": self.outlet_x,
            "outlet_y": self.outlet_y,
        }


def build_basin_metadata(
    *,
    basin_id: NDArray[np.integer],
    elevation_m: NDArray[np.floating],
    flow_accumulation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    outlet_points: list[tuple[int, int]],
    extent: SpatialExtent,
) -> list[BasinMeta]:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    bids = np.unique(basin_id[(basin_id > 0) & ~ocean])
    metas: list[BasinMeta] = []
    for bid in bids:
        m = (basin_id == int(bid)) & ~ocean
        if not np.any(m):
            continue
        acc = flow_accumulation[m]
        true_idx = np.flatnonzero(m.ravel())
        best = int(true_idx[int(np.argmax(acc))])
        orow, ocol = divmod(best, m.shape[1])
        # Prefer recorded outlet if inside basin
        for r, c in outlet_points:
            if m[r, c]:
                orow, ocol = int(r), int(c)
                break
        ox, oy = cell_center_norm(float(ocol), float(orow), extent)
        metas.append(
            BasinMeta(
                id=int(bid),
                area_cells=int(np.count_nonzero(m)),
                mean_elevation_m=float(np.mean(elevation_m[m])),
                max_accumulation=float(np.max(flow_accumulation[m])),
                outlet_row=int(orow),
                outlet_col=int(ocol),
                outlet_x=ox,
                outlet_y=oy,
            )
        )
    return metas
