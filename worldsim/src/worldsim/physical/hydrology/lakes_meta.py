"""Lake water-state classification and graph inlet/outlet metadata (PR-6)."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.cylindrical_graph import (
    CylindricalFlowGraph,
    D8_DELTAS,
    flat_index,
    unravel,
)

WaterState = Literal["open", "endorheic", "seasonal_or_playa", "frozen_or_ice_covered"]


def spill_elevation_m(
    lake_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> float:
    """Minimum elevation on the land rim adjacent to the lake body."""
    body = np.asarray(lake_mask, dtype=np.bool_)
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = body.shape
    rim = []
    rows, cols = np.where(body)
    for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, (c + dc) % w
            if nr < 0 or nr >= h:
                continue
            if body[nr, nc] or ocean[nr, nc]:
                continue
            rim.append(float(elev[nr, nc]))
    if not rim:
        return float(np.min(elev[body])) if np.any(body) else float("nan")
    return float(min(rim))


def classify_lake_body(
    *,
    graph: CylindricalFlowGraph,
    lake_mask: NDArray[np.bool_],
    lake_id_value: int,
    elevation_m: NDArray[np.floating],
    discharge_effective: NDArray[np.floating],
    temperature_annual_c: NDArray[np.floating],
    precip_annual: NDArray[np.floating],
    frozen_temp_c: float = 1.0,
    playa_inflow_quantile: float = 0.35,
) -> dict[str, Any]:
    """Classify one lake body using the canonical drainage graph."""
    body = np.asarray(lake_mask, dtype=np.bool_)
    ocean = graph.ocean_mask
    h, w = body.shape
    ds = graph.downstream_flat
    elev = np.asarray(elevation_m, dtype=np.float64)
    q = np.asarray(discharge_effective, dtype=np.float64)
    temp = np.asarray(temperature_annual_c, dtype=np.float64)
    precip = np.asarray(precip_annual, dtype=np.float64)

    has_ocean_outlet = False
    has_land_outlet = False
    has_inland_sink = False
    outlet_rc: tuple[int, int] | None = None
    for r, c in zip(*np.where(body), strict=False):
        i = flat_index(r, c, w)
        j = int(ds[i])
        if j < 0:
            ocean_touch = False
            for _code, (dr, dc) in D8_DELTAS.items():
                nr, nc = r + dr, (c + dc) % w
                if 0 <= nr < h and ocean[nr, nc]:
                    ocean_touch = True
                    has_ocean_outlet = True
                    outlet_rc = (r, c)
                    break
            if not ocean_touch and r not in (0, h - 1):
                has_inland_sink = True
            continue
        nr, nc = unravel(j, w)
        if ocean[nr, nc]:
            has_ocean_outlet = True
            outlet_rc = (r, c)
        elif not body[nr, nc]:
            has_land_outlet = True
            outlet_rc = (r, c)

    # CR-4: fill-all lake geometry can include spill-side cells that still
    # drain outward in the unfilled routing graph. Closed iff an inland pit
    # remains and the body does not reach the ocean.
    closed_basin = bool(has_inland_sink and not has_ocean_outlet)
    mean_temp = float(np.mean(temp[body])) if np.any(body) else float("nan")
    mean_inflow = float(np.mean(q[body])) if np.any(body) else 0.0
    mean_precip = float(np.mean(precip[body])) if np.any(body) else 0.0
    spill = spill_elevation_m(body, elev, ocean)
    surface = float(np.mean(elev[body])) if np.any(body) else float("nan")

    land = ~ocean
    land_q = q[land]
    playa_thr = (
        float(np.quantile(land_q, playa_inflow_quantile)) if land_q.size else 0.0
    )

    if mean_temp < float(frozen_temp_c):
        state: WaterState = "frozen_or_ice_covered"
    elif closed_basin and mean_inflow <= max(playa_thr, 1e-9):
        state = "seasonal_or_playa"
    elif closed_basin:
        state = "endorheic"
    else:
        state = "open"

    return {
        "lake_id": int(lake_id_value),
        "water_state": state,
        "closed_basin": bool(closed_basin),
        "has_ocean_outlet": bool(has_ocean_outlet),
        "has_land_outlet": bool(has_land_outlet),
        "outlet_row": int(outlet_rc[0]) if outlet_rc else None,
        "outlet_col": int(outlet_rc[1]) if outlet_rc else None,
        "spill_elevation_m": spill,
        "surface_elevation_m": surface,
        "mean_effective_inflow": mean_inflow,
        "mean_precip": mean_precip,
        "mean_temp_c": mean_temp,
        "area_cells": int(np.count_nonzero(body)),
        "basin_id": 0,  # filled by caller from dominant basin
    }


def build_lake_records(
    *,
    graph: CylindricalFlowGraph,
    lake_id: NDArray[np.integer],
    lake_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    basin_id: NDArray[np.integer],
    discharge_effective: NDArray[np.floating],
    temperature_annual_c: NDArray[np.floating],
    precip_annual: NDArray[np.floating],
    frozen_temp_c: float = 1.0,
) -> list[dict[str, Any]]:
    """Per-lake metadata for hydrology diagnostics and vector round-trip."""
    ids = np.unique(np.asarray(lake_id)[np.asarray(lake_id) > 0])
    records: list[dict[str, Any]] = []
    for lid in ids:
        body = lake_id == int(lid)
        if not np.any(body):
            continue
        rec = classify_lake_body(
            graph=graph,
            lake_mask=body,
            lake_id_value=int(lid),
            elevation_m=elevation_m,
            discharge_effective=discharge_effective,
            temperature_annual_c=temperature_annual_c,
            precip_annual=precip_annual,
            frozen_temp_c=frozen_temp_c,
        )
        bids, counts = np.unique(basin_id[body], return_counts=True)
        rec["basin_id"] = int(bids[int(np.argmax(counts))]) if len(bids) else 0
        records.append(rec)
    return records
