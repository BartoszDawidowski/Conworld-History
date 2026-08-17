"""Elevation unit conversion to metres relative to calibrated sea level."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

HYPSOMETRY_ALGORITHM_VERSION = 2
HYPSOMETRY_MODES = ("legacy_max", "power_tail_v2")


def power_tail_v2_curve(
    x: NDArray[np.floating],
    *,
    body_exponent: float,
    asymptote_ratio: float,
    tail_softness: float = 1.0,
) -> NDArray[np.float64]:
    """Dimensionless land curve ``f(x)`` continuous at the anchor ``x=1``.

    - ``x <= 1``: ``x ** body_exponent`` (body; ``p>1`` compresses mid-land)
    - ``x > 1``: exponential approach to ``asymptote_ratio``
    - ``tail_softness`` stretches the tail length scale (``1`` = PR-2 identity,
      C1 join; ``>1`` softer / longer tail, C0 only)
    """
    xx = np.asarray(x, dtype=np.float64)
    p = float(body_exponent)
    m = float(asymptote_ratio)
    s = max(float(tail_softness), 1e-6)
    if p <= 0.0:
        raise ValueError("body_exponent must be > 0")
    if m <= 1.0:
        raise ValueError("asymptote_ratio must be > 1")
    out = np.empty_like(xx)
    body = xx <= 1.0
    out[body] = np.power(np.maximum(xx[body], 0.0), p)
    span = m - 1.0
    t = xx[~body] - 1.0
    rate = p / (span * s)
    out[~body] = 1.0 + span * (1.0 - np.exp(-t * rate))
    return out


def power_tail_v2_land_m(
    elevation_raw: NDArray[np.floating],
    sea_level_raw: float,
    ocean_mask: NDArray[np.bool_],
    *,
    anchor_quantile: float = 0.95,
    anchor_elevation_m: float = 3000.0,
    body_exponent: float = 1.5,
    max_elevation_m: float = 9000.0,
    tail_softness: float = 1.0,
    epsilon: float = 1e-12,
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Map land raw heights to metres via robust quantile + soft tail.

    Ocean cells are left at 0.0 here; callers apply the ocean branch separately.
    ``ocean_mask`` must already be frozen (sea-level calibration).
    """
    elev = np.asarray(elevation_raw, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    u = np.maximum(elev - float(sea_level_raw), 0.0)
    out = np.zeros_like(elev)

    diag: dict[str, Any] = {
        "hypsometry_mode": "power_tail_v2",
        "hypsometry_algorithm_version": HYPSOMETRY_ALGORITHM_VERSION,
        "anchor_quantile": float(anchor_quantile),
        "anchor_elevation_m": float(anchor_elevation_m),
        "body_exponent": float(body_exponent),
        "tail_softness": float(tail_softness),
        "max_elevation_m": float(max_elevation_m),
        "land_cells": int(land.sum()),
    }

    if not np.any(land):
        diag["anchor_raw"] = 0.0
        diag["asymptote_ratio"] = float(
            max_elevation_m / max(anchor_elevation_m, epsilon)
        )
        return out, diag

    u_land = u[land]
    q = float(np.clip(anchor_quantile, 0.5, 0.999))
    anchor_raw = float(np.quantile(u_land, q))
    if anchor_raw <= epsilon:
        anchor_raw = float(np.max(u_land)) if float(np.max(u_land)) > epsilon else 1.0
    x = u_land / anchor_raw
    m = float(max_elevation_m) / max(float(anchor_elevation_m), epsilon)
    if m <= 1.0:
        m = 1.0 + 1e-6
    curve = power_tail_v2_curve(
        x,
        body_exponent=body_exponent,
        asymptote_ratio=m,
        tail_softness=tail_softness,
    )
    land_m = float(anchor_elevation_m) * curve
    out[land] = land_m

    diag.update(
        {
            "anchor_raw": anchor_raw,
            "asymptote_ratio": m,
            "land_max_m": float(land_m.max()),
            "land_mean_m": float(land_m.mean()),
            "x_max": float(x.max()),
            "exceeds_max_guardrail": bool(
                float(land_m.max()) > float(max_elevation_m) + 1.0
            ),
        }
    )
    return out, diag


def raw_to_elevation_m_with_diagnostics(
    elevation_raw: NDArray[np.floating],
    sea_level_raw: float,
    *,
    land_scale_m: float = 6000.0,
    ocean_scale_m: float = 5000.0,
    ocean_mask: NDArray[np.bool_] | None = None,
    hypsometry_mode: str = "power_tail_v2",
    hypsometry_anchor_quantile: float = 0.95,
    hypsometry_anchor_elevation_m: float = 3000.0,
    hypsometry_body_exponent: float = 1.5,
    hypsometry_max_elevation_m: float | None = None,
    hypsometry_tail_softness: float = 1.0,
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Map raw elevation to metres; return diagnostics for the land transform."""
    elev = np.asarray(elevation_raw, dtype=np.float64)
    centered = elev - float(sea_level_raw)
    if ocean_mask is None:
        ocean = centered < 0.0
    else:
        ocean = np.asarray(ocean_mask, dtype=bool)
    land = ~ocean
    out = np.zeros_like(elev)
    mode = str(hypsometry_mode)
    if mode not in HYPSOMETRY_MODES:
        raise ValueError(
            f"unknown hypsometry_mode {mode!r}; expected one of {HYPSOMETRY_MODES}"
        )

    max_guard = (
        float(hypsometry_max_elevation_m)
        if hypsometry_max_elevation_m is not None
        else float(land_scale_m)
    )

    if mode == "power_tail_v2":
        land_m, diag = power_tail_v2_land_m(
            elev,
            sea_level_raw,
            ocean,
            anchor_quantile=hypsometry_anchor_quantile,
            anchor_elevation_m=hypsometry_anchor_elevation_m,
            body_exponent=hypsometry_body_exponent,
            max_elevation_m=max_guard,
            tail_softness=hypsometry_tail_softness,
        )
        out[land] = land_m[land]
    else:
        diag = {
            "hypsometry_mode": "legacy_max",
            "hypsometry_algorithm_version": 1,
            "land_scale_m": float(land_scale_m),
        }
        if np.any(land):
            land_max = float(np.max(centered[land]))
            if land_max <= 1e-12:
                land_max = 1.0
            out[land] = centered[land] / land_max * float(land_scale_m)
            diag["land_max_m"] = float(out[land].max())
            diag["anchor_raw"] = land_max

    if np.any(ocean):
        ocean_min = float(np.min(centered[ocean]))
        if ocean_min >= -1e-12:
            ocean_min = -1.0
        out[ocean] = centered[ocean] / abs(ocean_min) * float(ocean_scale_m)

    diag["ocean_scale_m"] = float(ocean_scale_m)
    return out, diag


def raw_to_elevation_m(
    elevation_raw: NDArray[np.floating],
    sea_level_raw: float,
    *,
    land_scale_m: float = 6000.0,
    ocean_scale_m: float = 5000.0,
    ocean_mask: NDArray[np.bool_] | None = None,
    hypsometry_mode: str = "power_tail_v2",
    hypsometry_anchor_quantile: float = 0.95,
    hypsometry_anchor_elevation_m: float = 3000.0,
    hypsometry_body_exponent: float = 1.5,
    hypsometry_max_elevation_m: float | None = None,
    hypsometry_tail_softness: float = 1.0,
) -> NDArray[np.float64]:
    """Map raw tectonic elevation to metres with sea level at 0.

    Modes:

    - ``legacy_max``: land normalised by the seed maximum to ``land_scale_m``
    - ``power_tail_v2``: robust quantile body + soft tail (PR-2 / CR-5 default)
    """
    out, _diag = raw_to_elevation_m_with_diagnostics(
        elevation_raw,
        sea_level_raw,
        land_scale_m=land_scale_m,
        ocean_scale_m=ocean_scale_m,
        ocean_mask=ocean_mask,
        hypsometry_mode=hypsometry_mode,
        hypsometry_anchor_quantile=hypsometry_anchor_quantile,
        hypsometry_anchor_elevation_m=hypsometry_anchor_elevation_m,
        hypsometry_body_exponent=hypsometry_body_exponent,
        hypsometry_max_elevation_m=hypsometry_max_elevation_m,
        hypsometry_tail_softness=hypsometry_tail_softness,
    )
    return out
