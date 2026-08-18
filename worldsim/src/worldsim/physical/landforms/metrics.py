"""Multi-scale terrain metric fields for LandformAnalysis (PR-9B)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.metrics import GridMetrics, grid_metrics


def scale_window(metrics: GridMetrics, radius_km: float) -> dict[str, float | int]:
    """Requested km radius → effective 1-cell-minimum E–W/N–S window."""
    mid = int(metrics.height // 2)
    raw_x = float(metrics.cells_from_km_ew(radius_km, mid))
    raw_y = float(metrics.cells_from_km_ns(radius_km, mid))
    rx = 1 if not np.isfinite(raw_x) else int(max(1, round(raw_x)))
    ry = 1 if not np.isfinite(raw_y) else int(max(1, round(raw_y)))
    rx = min(rx, max(1, metrics.width // 4))
    ry = min(ry, max(1, metrics.height // 4))
    return {
        "requested_km": float(radius_km),
        "effective_rx_cells": int(rx),
        "effective_ry_cells": int(ry),
        "effective_ew_km": float(metrics.km_from_cells_ew(rx, row=mid)),
        "effective_ns_km": float(metrics.km_from_cells_ns(ry, row=mid)),
        "raw_cells_ew": float(raw_x) if np.isfinite(raw_x) else float("inf"),
        "raw_cells_ns": float(raw_y) if np.isfinite(raw_y) else float("inf"),
    }


def box_mean_cylindrical(
    field: NDArray[np.floating],
    *,
    rx: int,
    ry: int,
) -> NDArray[np.float64]:
    """Separable box mean; E–W wrap, N–S edge clamp."""
    a = np.asarray(field, dtype=np.float64)
    h, w = a.shape
    rx = max(int(rx), 0)
    ry = max(int(ry), 0)
    if rx == 0 and ry == 0:
        return a.copy()

    if rx > 0:
        kernel = 2 * rx + 1
        pad = np.concatenate([a[:, -rx:], a, a[:, :rx]], axis=1)
        c = np.cumsum(pad, axis=1)
        # padded centre of original i is at i+rx; window [i, i+2rx]
        hi = c[:, 2 * rx : 2 * rx + w]
        lo = np.concatenate([np.zeros((h, 1), dtype=np.float64), c[:, : w - 1]], axis=1)
        # window sum = c[i+2rx] - c[i-1] with c[-1]=0 for i=0 → use:
        # at padded index p=i+rx: sum = c[p+rx] - c[p-rx-1]
        sums = np.empty((h, w), dtype=np.float64)
        for i in range(w):
            p = i + rx
            sums[:, i] = c[:, p + rx] - (c[:, p - rx - 1] if p - rx > 0 else 0.0)
        a = sums / float(kernel)

    if ry > 0:
        kernel = 2 * ry + 1
        pad = np.pad(a, ((ry, ry), (0, 0)), mode="edge")
        c = np.cumsum(pad, axis=0)
        sums = np.empty((h, w), dtype=np.float64)
        for j in range(h):
            p = j + ry
            sums[j, :] = c[p + ry, :] - (c[p - ry - 1, :] if p - ry > 0 else 0.0)
        a = sums / float(kernel)
    return a



def box_max_cylindrical(
    field: NDArray[np.floating], *, rx: int, ry: int
) -> NDArray[np.float64]:
    a = np.asarray(field, dtype=np.float64).copy()
    nan_mask = ~np.isfinite(a)
    a = np.where(nan_mask, -np.inf, a)
    h, w = a.shape
    rx = max(int(rx), 0)
    ry = max(int(ry), 0)
    out = a.copy()
    if rx > 0:
        acc = out.copy()
        for s in range(1, rx + 1):
            acc = np.maximum(acc, np.roll(out, s, axis=1))
            acc = np.maximum(acc, np.roll(out, -s, axis=1))
        out = acc
    if ry > 0:
        acc = out.copy()
        for s in range(1, ry + 1):
            up = np.pad(out[:-s, :], ((s, 0), (0, 0)), mode="edge")
            dn = np.pad(out[s:, :], ((0, s), (0, 0)), mode="edge")
            acc = np.maximum(acc, np.maximum(up, dn))
        out = acc
    out = np.where(np.isfinite(out) & (out > -1e30), out, np.nan)
    return out


def box_min_cylindrical(
    field: NDArray[np.floating], *, rx: int, ry: int
) -> NDArray[np.float64]:
    a = np.asarray(field, dtype=np.float64)
    return -box_max_cylindrical(np.where(np.isfinite(a), -a, np.nan), rx=rx, ry=ry)


def compute_metric_fields(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    fine_radius_km: float,
    meso_radius_km: float,
    macro_radius_km: float,
    planet_radius_km: float = 6371.0,
    metrics: GridMetrics | None = None,
) -> tuple[dict[str, NDArray[np.float64]], dict[str, dict[str, float | int]]]:
    """Fine / meso / macro metric layers on the analysis grid.

    Coastal roughness and mean slope are divided by the window land fraction so
    ocean zeros do not dilute the statistic. Returns ``(fields, scale_windows)``.
    """
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    h, w = elev.shape
    metrics = metrics or grid_metrics(w, h, radius_km=planet_radius_km)

    slope = metrics.metric_slope(elev)
    slope = np.where(ocean, 0.0, slope)

    # Land-only elevation so ocean cliffs do not inflate relief windows.
    elev_land = np.where(ocean, np.nan, elev)
    land_w = (~ocean).astype(np.float64)

    scales = {
        "fine": fine_radius_km,
        "meso": meso_radius_km,
        "macro": macro_radius_km,
    }
    out: dict[str, NDArray[np.float64]] = {
        "slope": slope.astype(np.float64),
    }
    scale_windows: dict[str, dict[str, float | int]] = {}

    for name, r_km in scales.items():
        win = scale_window(metrics, r_km)
        scale_windows[name] = win
        rx = int(win["effective_rx_cells"])
        ry = int(win["effective_ry_cells"])
        land_f = box_mean_cylindrical(land_w, rx=rx, ry=ry)
        land_f_safe = np.maximum(land_f, 1e-6)

        def _land_mean(field: NDArray[np.floating]) -> NDArray[np.float64]:
            acc = box_mean_cylindrical(np.where(ocean, 0.0, field), rx=rx, ry=ry)
            return np.where(land_f > 1e-6, acc / land_f_safe, 0.0)

        mean = _land_mean(elev)
        mean = np.where(land_f > 1e-6, mean, elev)
        relief = box_max_cylindrical(elev_land, rx=rx, ry=ry) - box_min_cylindrical(
            elev_land, rx=rx, ry=ry
        )
        relief = np.where(ocean | ~np.isfinite(relief), 0.0, relief)
        tpi = np.where(ocean, 0.0, elev - mean)
        resid = np.where(ocean, 0.0, elev - mean)
        rough = np.sqrt(np.maximum(_land_mean(resid * resid), 0.0))
        rough = np.where(ocean, 0.0, rough)
        mean_slope = np.where(ocean, 0.0, _land_mean(slope))
        out[f"relief_{name}"] = relief
        out[f"tpi_{name}"] = tpi
        out[f"roughness_{name}"] = rough
        out[f"mean_slope_{name}"] = mean_slope
        out[f"mean_elev_{name}"] = mean

    out["flatness_meso"] = np.where(
        ocean, 0.0, 1.0 / (1.0 + 40.0 * out["mean_slope_meso"])
    )
    return out, scale_windows
