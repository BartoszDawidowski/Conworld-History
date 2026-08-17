"""Convert runoff-proxy accumulation to physical discharge (CR-7)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.transmission import MONTH_DAYS, YEAR_DAYS

SECONDS_PER_DAY = 86400.0


def month_days(month_index: int) -> int:
    """Civil days in ``month_index`` (0 = January, non-leap)."""
    return int(MONTH_DAYS[int(month_index) % 12])


def runoff_proxy_to_m3s(
    proxy: NDArray[np.floating],
    *,
    cell_area_km2: float,
    precip_scale_mm: float,
    days: float,
) -> NDArray[np.float64]:
    """Accumulated runoff proxy → discharge in m³/s for a period of ``days``.

    Equal-area cells: each unit of proxy is ``precip_scale_mm`` millimetres over
    one cell, so summed upstream proxy × cell area is a volume.
    """
    mm = np.asarray(proxy, dtype=np.float64) * float(precip_scale_mm)
    volume_m3 = (mm / 1000.0) * (float(cell_area_km2) * 1e6)
    seconds = max(float(days) * SECONDS_PER_DAY, 1.0)
    return volume_m3 / seconds


def month_weighted_mean_m3s(monthly_m3s: NDArray[np.floating]) -> NDArray[np.float64]:
    """Annual mean discharge from monthly m³/s (weights = civil month lengths)."""
    q = np.asarray(monthly_m3s, dtype=np.float64)
    if q.ndim != 3:
        raise ValueError("monthly_m3s must be [months, y, x]")
    n = int(q.shape[0])
    weights = np.array(MONTH_DAYS[:n], dtype=np.float64)
    if weights.size != n:
        weights = np.full(n, float(YEAR_DAYS) / max(n, 1), dtype=np.float64)
    total_days = float(np.sum(weights))
    return np.tensordot(weights, q, axes=(0, 0)) / max(total_days, 1.0)
