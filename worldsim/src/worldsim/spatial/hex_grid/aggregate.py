"""Aggregate canonical rasters onto the analytical hex grid."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.hex_grid.layout import HexGridSpec, hex_id, xy_to_hex


def _raster_cell_centers(extent: SpatialExtent) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    h, w = extent.height, extent.width
    # Vectorised centres matching SpatialExtent.cell_center_xy
    i = np.arange(w, dtype=np.float64)
    j = np.arange(h, dtype=np.float64)
    xs = (i + 0.5) / w
    ys = 1.0 - (j + 0.5) * 2.0 / h
    return np.broadcast_to(xs, (h, w)).copy(), np.broadcast_to(ys[:, None], (h, w)).copy()


def build_hex_of_climate_cells(
    climate_extent: SpatialExtent,
    spec: HexGridSpec,
) -> NDArray[np.int32]:
    """Map each raster cell centre to a hex id."""
    xs, ys = _raster_cell_centers(climate_extent)
    h, w = climate_extent.height, climate_extent.width
    out = np.empty((h, w), dtype=np.int32)
    for j in range(h):
        for i in range(w):
            q, r = xy_to_hex(
                float(xs[j, i]), float(ys[j, i]), width=spec.width, height=spec.height
            )
            out[j, i] = hex_id(q, r, width=spec.width)
    return out


def aggregate_scalar(
    values: NDArray[np.floating],
    hex_of_cell: NDArray[np.integer],
    *,
    n_hex: int,
    mask: NDArray[np.bool_] | None = None,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.int32],
]:
    """Return mean/min/max/std/count per hex for a 2D field."""
    vals = np.asarray(values, dtype=np.float64).ravel()
    hid = np.asarray(hex_of_cell, dtype=np.int32).ravel()
    if mask is None:
        m = np.ones(vals.shape, dtype=bool)
    else:
        m = np.asarray(mask, dtype=bool).ravel()
    hid_m = hid[m]
    vals_m = vals[m]
    counts = np.bincount(hid_m, minlength=n_hex).astype(np.int32)
    sums = np.bincount(hid_m, weights=vals_m, minlength=n_hex).astype(np.float64)
    sums2 = np.bincount(hid_m, weights=vals_m * vals_m, minlength=n_hex).astype(
        np.float64
    )
    mins = np.full(n_hex, np.inf, dtype=np.float64)
    maxs = np.full(n_hex, -np.inf, dtype=np.float64)
    if hid_m.size:
        np.minimum.at(mins, hid_m, vals_m)
        np.maximum.at(maxs, hid_m, vals_m)
    mins = np.where(counts > 0, mins, np.nan)
    maxs = np.where(counts > 0, maxs, np.nan)
    mean = np.zeros(n_hex, dtype=np.float64)
    std = np.zeros(n_hex, dtype=np.float64)
    ok = counts > 0
    mean[ok] = sums[ok] / counts[ok]
    std[ok] = np.sqrt(np.maximum(sums2[ok] / counts[ok] - mean[ok] ** 2, 0.0))
    return mean, mins, maxs, std, counts


def aggregate_fraction(
    boolean_field: NDArray[np.bool_],
    hex_of_cell: NDArray[np.integer],
    *,
    n_hex: int,
) -> NDArray[np.float64]:
    mean, _, _, _, _ = aggregate_scalar(
        boolean_field.astype(np.float64),
        hex_of_cell,
        n_hex=n_hex,
    )
    return mean


def aggregate_monthly(
    values: NDArray[np.floating],
    hex_of_cell: NDArray[np.integer],
    *,
    n_hex: int,
    mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.float64]:
    """``values[months,y,x]`` → ``out[n_hex, months]``."""
    arr = np.asarray(values, dtype=np.float64)
    months = arr.shape[0]
    out = np.zeros((n_hex, months), dtype=np.float64)
    for m in range(months):
        mean, _, _, _, _ = aggregate_scalar(
            arr[m], hex_of_cell, n_hex=n_hex, mask=mask
        )
        out[:, m] = mean
    return out


def dominant_int(
    values: NDArray[np.integer],
    hex_of_cell: NDArray[np.integer],
    *,
    n_hex: int,
    mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.int32]:
    """Mode of integer field per hex (via per-hex bincount of shifted ids)."""
    vals = np.asarray(values).ravel()
    hid = np.asarray(hex_of_cell, dtype=np.int32).ravel()
    if mask is None:
        m = np.ones(vals.shape, dtype=bool)
    else:
        m = np.asarray(mask, dtype=bool).ravel()
    hid_m = hid[m]
    vals_m = vals[m].astype(np.int64)
    out = np.zeros(n_hex, dtype=np.int32)
    if hid_m.size == 0:
        return out
    # Group by hex: sort then reduce
    order = np.argsort(hid_m, kind="mergesort")
    hid_s = hid_m[order]
    val_s = vals_m[order]
    # Find hex boundaries
    cuts = np.flatnonzero(hid_s[1:] != hid_s[:-1]) + 1
    starts = np.concatenate([[0], cuts])
    ends = np.concatenate([cuts, [hid_s.size]])
    for s, e in zip(starts.tolist(), ends.tolist()):
        hi = int(hid_s[s])
        chunk = val_s[s:e]
        # mode
        uniq, cnt = np.unique(chunk, return_counts=True)
        out[hi] = int(uniq[int(np.argmax(cnt))])
    return out
