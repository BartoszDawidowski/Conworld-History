"""Current-output metrics for baseline capture (no physics changes)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def land_hypsometry_metrics(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> dict[str, Any]:
    """Percentiles and fractions for land elevations (metres)."""
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    if not np.any(land):
        return {"land_cells": 0}
    z = elev[land]
    qs = (10, 25, 50, 75, 90, 95, 99)
    pct = {f"p{q}": float(np.percentile(z, q)) for q in qs}
    return {
        "land_cells": int(land.sum()),
        "mean_m": float(z.mean()),
        "max_m": float(z.max()),
        "min_m": float(z.min()),
        **pct,
        "frac_above_1km": float(np.mean(z > 1000.0)),
        "frac_above_2km": float(np.mean(z > 2000.0)),
        "frac_above_3km": float(np.mean(z > 3000.0)),
        "frac_above_5km": float(np.mean(z > 5000.0)),
        "frac_above_7km": float(np.mean(z > 7000.0)),
        "frac_below_200m": float(np.mean(z < 200.0)),
        "frac_below_500m": float(np.mean(z < 500.0)),
    }


def moisture_annual_metrics(
    annual_precipitation: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
) -> dict[str, Any]:
    precip = np.asarray(annual_precipitation, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    if not np.any(land):
        return {"land_cells": 0}
    p = precip[land]
    coast = land & (
        np.roll(ocean, 1, axis=1)
        | np.roll(ocean, -1, axis=1)
        | np.pad(ocean[1:, :], ((0, 1), (0, 0)), constant_values=False)
        | np.pad(ocean[:-1, :], ((1, 0), (0, 0)), constant_values=False)
    )
    interior = land & ~coast
    out: dict[str, Any] = {
        "land_mean": float(p.mean()),
        "land_p50": float(np.percentile(p, 50)),
        "land_p90": float(np.percentile(p, 90)),
        "land_max": float(p.max()),
    }
    if np.any(coast) and np.any(interior):
        c = float(precip[coast].mean())
        i = float(precip[interior].mean())
        out["coast_mean"] = c
        out["interior_mean"] = i
        out["interior_coast_ratio"] = float(i / c) if c > 1e-12 else None
    return out


def hydrology_metrics(
    *,
    river_mask: NDArray[np.bool_] | None,
    lake_mask: NDArray[np.bool_] | None,
    flow_accumulation: NDArray[np.floating] | None,
    ocean_mask: NDArray[np.bool_],
) -> dict[str, Any]:
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    out: dict[str, Any] = {"land_cells": int(land.sum())}
    if river_mask is not None:
        riv = np.asarray(river_mask, dtype=bool) & land
        out["river_cells"] = int(riv.sum())
        out["river_land_fraction"] = float(riv.mean()) if land.any() else 0.0
    if lake_mask is not None:
        lake = np.asarray(lake_mask, dtype=bool) & land
        out["lake_cells"] = int(lake.sum())
    if flow_accumulation is not None:
        acc = np.asarray(flow_accumulation, dtype=np.float64)
        out["acc_land_max"] = float(acc[land].max()) if land.any() else 0.0
        out["acc_land_p90"] = (
            float(np.percentile(acc[land], 90)) if land.any() else 0.0
        )
    return out


def peak_rss_mb() -> float | None:
    """Best-effort peak resident set (MiB) on Unix."""
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS: ru_maxrss is bytes; Linux: kilobytes
        import sys

        rss = float(usage.ru_maxrss)
        if sys.platform == "darwin":
            return rss / (1024.0 * 1024.0)
        return rss / 1024.0
    except Exception:
        return None
