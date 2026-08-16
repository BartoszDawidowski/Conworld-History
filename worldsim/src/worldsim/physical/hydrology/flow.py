"""PyFlwDir flow / accumulation / basins / streams (Milestone 11)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

import pyflwdir
from pyflwdir import dem as pyflwdir_dem

from worldsim.physical.hydrology.conditioning import (
    NODATA,
    dem_for_flow,
    ew_crop,
    ew_pad,
    wrap_pad_cells,
)


def run_pyflwdir_core(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    nodata: float = NODATA,
    max_depth: float = -1.0,
) -> dict[str, Any]:
    """Condition DEM and derive D8 flow products with E–W wrap padding.

    Returns rasters cropped to the original grid plus the actionable
    ``FlwdirRaster`` for further accumulation (also on the padded domain —
    callers that need ``accuflux`` should prefer :func:`accuflux_on_land`).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    pad = wrap_pad_cells(w)
    dem = dem_for_flow(elevation_m, ocean, nodata=nodata)
    dem_p = ew_pad(dem, pad)

    filled_p, d8_p = pyflwdir_dem.fill_depressions(
        dem_p, nodata=nodata, max_depth=max_depth, outlets="edge"
    )
    flw = pyflwdir.from_array(
        d8_p, ftype="d8", check_ftype=False, latlon=False
    )

    flow_dir = ew_crop(flw.to_array(ftype="d8"), pad, w)
    filled = ew_crop(filled_p, pad, w)
    # upstream area in cells; nodata on ocean
    upa_p = flw.upstream_area(unit="cell")
    flow_acc = ew_crop(upa_p.astype(np.float64), pad, w)
    flow_acc = np.where(ocean, 0.0, np.where(flow_acc < 0, 0.0, flow_acc))

    basins_p = flw.basins()
    basin_id = ew_crop(basins_p.astype(np.int32), pad, w)
    basin_id = np.where(ocean, 0, basin_id)

    order_p = flw.stream_order()
    stream_order = ew_crop(order_p.astype(np.int16), pad, w)
    stream_order = np.where(ocean, 0, stream_order)

    # Outlets / pits in padded index space → (row, col) original
    outlets: list[tuple[int, int]] = []
    for idx in list(flw.idxs_outlet) + list(flw.idxs_pit):
        row, col_p = divmod(int(idx), dem_p.shape[1])
        col = int(col_p) - pad
        if 0 <= col < w and 0 <= row < h and not ocean[row, col]:
            outlets.append((row, col))
    # unique preserve order
    seen: set[tuple[int, int]] = set()
    outlet_points: list[tuple[int, int]] = []
    for p in outlets:
        if p not in seen:
            seen.add(p)
            outlet_points.append(p)

    return {
        "flw": flw,
        "pad": pad,
        "dem_conditioned_m": filled,
        "flow_direction": flow_dir.astype(np.uint8),
        "flow_accumulation": flow_acc,
        "basin_id": basin_id,
        "watershed_id": basin_id.copy(),
        "stream_order": stream_order,
        "outlet_points": outlet_points,
        "isvalid": bool(flw.isvalid),
        "nnodes": int(flw.nnodes),
    }


def accuflux_on_land(
    flw: Any,
    *,
    pad: int,
    width: int,
    ocean_mask: NDArray[np.bool_],
    weights: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Accumulate ``weights`` along the padded flow graph; crop to grid."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    w_pad = ew_pad(np.asarray(weights, dtype=np.float64), pad)
    w_pad = np.where(ew_pad(ocean, pad), 0.0, w_pad)
    acc_p = flw.accuflux(w_pad)
    acc = ew_crop(np.asarray(acc_p, dtype=np.float64), pad, width)
    return np.where(ocean, 0.0, acc)
