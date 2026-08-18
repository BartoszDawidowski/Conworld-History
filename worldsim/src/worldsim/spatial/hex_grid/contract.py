"""C8 hex environment contract — shared by queries and atlas export."""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

# Scalar / list field names that query and atlas export must share.
HEX_CONTRACT_SCALAR_FIELDS: tuple[str, ...] = (
    "hex_id",
    "center_x",
    "center_y",
    "latitude_deg",
    "cell_count",
    "land_fraction",
    "ocean_fraction",
    "elevation_mean_m",
    "elevation_min_m",
    "elevation_max_m",
    "elevation_std_m",
    "local_relief_mean_m",
    "slope_mean_deg",
    "temperature_annual_c",
    "precipitation_annual_mm",
    "biome_v2_dominant",
    "holdridge_dominant",
    "frost_months_mean",
    "growing_season_months_mean",
    "water_deficit_mm_mean",
    "soil_state_dominant",
    "permanent_water_fraction",
    "seasonal_water_fraction",
    "perennial_river_fraction",
    "seasonal_river_fraction",
    "wadi_fraction",
    "mean_effective_discharge",
    "context_dominant",
    "local_form_dominant",
    "mountain_score_mean",
    "plateau_score_mean",
    "mountain_terrain_fraction",
    "mountain_range_fraction",
    "plateau_context_fraction",
    "plateau_object_fraction",
    "terrain_barrier_strength",
)

HEX_CONTRACT_LIST_FIELDS: tuple[str, ...] = (
    "basin_ids",
    "river_ids",
    "lake_ids",
    "mountain_range_ids",
    "plateau_ids",
)

HEX_CONTRACT_FIELDS: tuple[str, ...] = HEX_CONTRACT_SCALAR_FIELDS + HEX_CONTRACT_LIST_FIELDS

# Score-mean fields must never be published under a *_fraction name.
SCORE_MEAN_FIELDS: frozenset[str] = frozenset(
    {"mountain_score_mean", "plateau_score_mean"}
)
FRACTION_FIELDS: frozenset[str] = frozenset(
    name for name in HEX_CONTRACT_FIELDS if name.endswith("_fraction")
)

_ATTR = {
    "elevation_mean_m": "elevation_mean",
    "elevation_min_m": "elevation_min",
    "elevation_max_m": "elevation_max",
    "elevation_std_m": "elevation_std",
}


def json_num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        fv = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(fv):
        return None
    return fv


def json_int(value: Any, *, nodata: int = -1) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
            return None
        iv = int(value)
    except (TypeError, ValueError):
        return None
    if iv == nodata:
        return None
    return iv


def json_id_list(value: Any) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for item in value:
        iv = json_int(item, nodata=0)
        if iv is not None and iv > 0:
            out.append(iv)
    return out


def _scalar_from_grid(grid: Any, name: str, index: int) -> Any:
    attr = _ATTR.get(name, name)
    arr = getattr(grid, attr, None)
    if name == "hex_id":
        return int(index)
    if arr is None:
        return None
    if name == "cell_count":
        return int(arr[index])
    if name in (
        "biome_v2_dominant",
        "holdridge_dominant",
        "soil_state_dominant",
        "context_dominant",
        "local_form_dominant",
    ):
        return json_int(arr[index], nodata=-1)
    return json_num(arr[index])


def hex_environment_record(grid: Any, hex_id_value: int) -> dict[str, Any]:
    """One hex as a JSON-ready dict using C8 contract names."""
    h = int(hex_id_value)
    if h < 0 or h >= int(grid.n_cells):
        raise IndexError(f"hex_id {h} out of range")
    rec: dict[str, Any] = {}
    for name in HEX_CONTRACT_SCALAR_FIELDS:
        rec[name] = _scalar_from_grid(grid, name, h)
    rec["basin_ids"] = json_id_list(_id_list_at(grid, "basin_ids", h))
    rec["river_ids"] = json_id_list(_id_list_at(grid, "river_ids", h))
    rec["lake_ids"] = json_id_list(_id_list_at(grid, "lake_ids", h))
    rec["mountain_range_ids"] = json_id_list(_id_list_at(grid, "mountain_range_ids", h))
    rec["plateau_ids"] = json_id_list(_id_list_at(grid, "plateau_ids", h))
    return rec


def _id_list_at(grid: Any, attr: str, index: int) -> list[Any]:
    payload = getattr(grid, attr, None)
    if payload is None or index >= len(payload):
        return []
    return list(payload[index] or [])


def hex_environment_columns(grid: Any) -> dict[str, Any]:
    """Columnar dump of the C8 contract (atlas inspector cache)."""
    n = int(grid.n_cells)
    records = [hex_environment_record(grid, i) for i in range(n)]
    out: dict[str, Any] = {}
    for name in HEX_CONTRACT_SCALAR_FIELDS:
        if name == "hex_id":
            continue
        out[name] = [records[i][name] for i in range(n)]
    for name in HEX_CONTRACT_LIST_FIELDS:
        sparse: dict[str, list[int]] = {}
        for i in range(n):
            ids = records[i][name]
            if ids:
                sparse[str(i)] = ids
        out[name] = sparse
    return out


def column_value(columns: Mapping[str, Any], name: str, hex_id_value: int) -> Any:
    """Read one hex from a columnar/sparse atlas dump."""
    if name == "hex_id":
        return int(hex_id_value)
    payload = columns[name]
    if isinstance(payload, dict):
        return list(payload.get(str(int(hex_id_value)), []))
    return payload[int(hex_id_value)]


def resample_nearest(arr: NDArray[Any], height: int, width: int) -> NDArray[Any]:
    src = np.asarray(arr)
    if src.ndim < 2:
        raise ValueError("resample_nearest expects a 2-D (or higher) array")
    sh, sw = int(src.shape[-2]), int(src.shape[-1])
    if sh == height and sw == width:
        return src
    rr = np.minimum((np.arange(height) * sh / max(height, 1)).astype(np.int32), sh - 1)
    cc = np.minimum((np.arange(width) * sw / max(width, 1)).astype(np.int32), sw - 1)
    return src[rr][:, cc]
