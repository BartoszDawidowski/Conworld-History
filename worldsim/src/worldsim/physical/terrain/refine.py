"""High-resolution terrain refinement from tectonic macrostructure."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.spatial.resample import (
    upsample_bilinear_cylindrical,
    upsample_nearest_cylindrical,
)


def _value_noise(
    height: int,
    width: int,
    rng: np.random.Generator,
    *,
    grid_y: int,
    grid_x: int,
) -> NDArray[np.float64]:
    """Low-amplitude smooth noise via coarse lattice + bilinear upsample."""
    coarse = rng.standard_normal((grid_y, grid_x))
    return upsample_bilinear_cylindrical(coarse, width, height)


def refine_terrain(
    *,
    elevation_raw: NDArray[np.floating],
    distance_to_boundary: NDArray[np.floating] | None = None,
    tectonic_activity: NDArray[np.floating] | None = None,
    volcanic_potential: NDArray[np.floating] | None = None,
    orogenic_potential: NDArray[np.floating] | None = None,
    out_width: int,
    out_height: int,
    detail_seed: int,
    detail_amplitude: float = 0.08,
    orogeny_boost: float = 0.05,
    activity_relief: float = 0.25,
    boundary_relief: float = 0.35,
) -> NDArray[np.float64]:
    """Upsample tectonic elevation and add controlled local relief.

    Macro-relief follows tectonics; detail noise amplitude is small relative to
    tectonic range so mountain chains are not relocated.
    """
    base = upsample_bilinear_cylindrical(elevation_raw, out_width, out_height)
    rng = np.random.default_rng(int(detail_seed) & 0xFFFFFFFF)

    tectonic_range = float(np.ptp(base))
    if tectonic_range <= 1e-12:
        tectonic_range = 1.0

    # Multi-scale low-amplitude noise (does not dominate macrostructure).
    n1 = _value_noise(out_height, out_width, rng, grid_y=32, grid_x=64)
    n2 = _value_noise(out_height, out_width, rng, grid_y=64, grid_x=128)
    noise = 0.65 * n1 + 0.35 * n2
    noise = noise / (np.std(noise) + 1e-12)

    relief_mod = np.ones_like(base)
    if distance_to_boundary is not None:
        dist = upsample_bilinear_cylindrical(
            distance_to_boundary, out_width, out_height
        )
        # Slightly more detail near boundaries, still bounded.
        relief_mod = relief_mod * (
            1.0 + float(boundary_relief) * np.exp(-dist / 12.0)
        )
    if tectonic_activity is not None:
        act = upsample_bilinear_cylindrical(
            tectonic_activity, out_width, out_height
        )
        act_n = act / (np.max(act) + 1e-12)
        relief_mod = relief_mod * (1.0 + float(activity_relief) * act_n)
    if volcanic_potential is not None:
        vol = upsample_bilinear_cylindrical(
            volcanic_potential, out_width, out_height
        )
        vol_n = vol / (np.max(vol) + 1e-12)
        base = base + 0.03 * tectonic_range * vol_n
    if orogenic_potential is not None:
        oro = upsample_bilinear_cylindrical(
            orogenic_potential, out_width, out_height
        )
        oro_n = oro / (np.max(oro) + 1e-12)
        base = base + float(orogeny_boost) * tectonic_range * oro_n

    detail = detail_amplitude * tectonic_range * noise * relief_mod
    return base + detail


def upsample_mask_field(
    field: NDArray,
    out_width: int,
    out_height: int,
    *,
    categorical: bool = False,
) -> NDArray:
    if categorical:
        return upsample_nearest_cylindrical(field, out_width, out_height)
    return upsample_bilinear_cylindrical(field, out_width, out_height)
