"""Raster resampling helpers with cylindrical E–W wrap (no N–S wrap)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def upsample_bilinear_cylindrical(
    source: NDArray[np.floating],
    out_width: int,
    out_height: int,
) -> NDArray[np.float64]:
    """Bilinear upsample; X wraps, Y is clamped at poles."""
    src = np.asarray(source, dtype=np.float64)
    if src.ndim != 2:
        raise ValueError("source must be 2D")
    in_h, in_w = src.shape
    if out_width <= 0 or out_height <= 0:
        raise ValueError("output dimensions must be positive")

    # Map output pixel centres into source continuous coordinates.
    xs = (np.arange(out_width, dtype=np.float64) + 0.5) * in_w / out_width - 0.5
    ys = (np.arange(out_height, dtype=np.float64) + 0.5) * in_h / out_height - 0.5

    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1
    wx = xs - x0
    wy = ys - y0

    x0w = np.mod(x0, in_w)
    x1w = np.mod(x1, in_w)
    y0c = np.clip(y0, 0, in_h - 1)
    y1c = np.clip(y1, 0, in_h - 1)

    # Broadcast to full grid.
    X0, Y0 = np.meshgrid(x0w, y0c)
    X1, Y1 = np.meshgrid(x1w, y1c)
    Wx, Wy = np.meshgrid(wx, wy)

    v00 = src[Y0, X0]
    v10 = src[Y0, X1]
    v01 = src[Y1, X0]
    v11 = src[Y1, X1]
    top = v00 * (1.0 - Wx) + v10 * Wx
    bot = v01 * (1.0 - Wx) + v11 * Wx
    return top * (1.0 - Wy) + bot * Wy


def upsample_nearest_cylindrical(
    source: NDArray,
    out_width: int,
    out_height: int,
) -> NDArray:
    src = np.asarray(source)
    in_h, in_w = src.shape
    xs = np.clip(
        ((np.arange(out_width) + 0.5) * in_w / out_width).astype(np.int64),
        0,
        in_w - 1,
    )
    ys = np.clip(
        ((np.arange(out_height) + 0.5) * in_h / out_height).astype(np.int64),
        0,
        in_h - 1,
    )
    return src[np.ix_(ys, xs)]
