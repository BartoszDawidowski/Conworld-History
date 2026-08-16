"""PyFlwDir DEM conditioning + canonical cylindrical graph products (PR-5)."""

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
from worldsim.physical.hydrology.cylindrical_graph import (
    CylindricalFlowGraph,
    accumulate_weights,
    build_cylindrical_graph,
    graph_products,
)


def run_pyflwdir_core(
    *,
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    nodata: float = NODATA,
    max_depth: float = -1.0,
) -> dict[str, Any]:
    """Fill DEM on a padded domain, crop D8, then build the canonical graph.

    Accumulation / basins / stream order come from
    :class:`~worldsim.physical.hydrology.cylindrical_graph.CylindricalFlowGraph`
    on the original width — not from cropping padded PyFlwDir products.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    pad = wrap_pad_cells(w)
    dem = dem_for_flow(elevation_m, ocean, nodata=nodata)
    dem_p = ew_pad(dem, pad)

    filled_p, d8_p = pyflwdir_dem.fill_depressions(
        dem_p, nodata=nodata, max_depth=max_depth, outlets="edge"
    )
    # Local Flwdir only for fill metadata / validity; not used for routing.
    flw = pyflwdir.from_array(
        d8_p, ftype="d8", check_ftype=False, latlon=False
    )

    flow_dir = ew_crop(flw.to_array(ftype="d8"), pad, w).astype(np.uint8)
    filled = ew_crop(filled_p, pad, w)

    graph = build_cylindrical_graph(flow_dir, ocean)
    products = graph_products(graph)

    return {
        "graph": graph,
        "flw": flw,
        "pad": pad,
        "dem_conditioned_m": filled,
        "flow_direction": flow_dir,
        "flow_accumulation": products["flow_accumulation"],
        "basin_id": products["basin_id"],
        "watershed_id": products["watershed_id"],
        "stream_order": products["stream_order"],
        "outlet_points": products["outlet_points"],
        "downstream_flat": graph.downstream_flat,
        "graph_diagnostics": products["graph_diagnostics"],
        "isvalid": bool(flw.isvalid) and bool(products["graph_diagnostics"]["graph_valid"]),
        "nnodes": int(np.count_nonzero(~ocean)),
    }


def accuflux_on_land(
    flw: Any,
    *,
    pad: int,
    width: int,
    ocean_mask: NDArray[np.bool_],
    weights: NDArray[np.floating],
    graph: CylindricalFlowGraph | None = None,
) -> NDArray[np.float64]:
    """Accumulate ``weights`` on the canonical graph (preferred).

    ``flw`` / ``pad`` remain for call-site compatibility but are unused when
    ``graph`` is provided. If ``graph`` is omitted, a graph is built from a
    cropped D8 derived from ``flw`` (legacy path — prefer passing ``graph``).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if graph is None:
        d8_p = flw.to_array(ftype="d8")
        d8 = ew_crop(d8_p, pad, width).astype(np.uint8)
        graph = build_cylindrical_graph(d8, ocean)
    return accumulate_weights(graph, weights)
