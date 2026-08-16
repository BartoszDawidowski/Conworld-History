"""Effective discharge with channel transmission losses (Plan B §6.3.1)."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.conditioning import ew_crop, ew_pad


def transmission_sink(
    precip: NDArray[np.floating],
    temperature_annual_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    transmission_rate: float = 0.45,
    precip_scale_mm: float = 200.0,
) -> NDArray[np.float64]:
    """Local channel loss in precip-proxy units: rate × max(0, PET − P).

    PET ≈ 58.93 × biotemp (Holdridge); avoid importing ecology (circular).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    p = np.asarray(precip, dtype=np.float64)
    t = np.asarray(temperature_annual_c, dtype=np.float64)
    bio = np.clip(t, 0.0, 30.0)
    pet_mm = 58.93 * bio
    precip_mm = np.maximum(p, 0.0) * float(precip_scale_mm)
    demand_mm = np.maximum(pet_mm - precip_mm, 0.0)
    demand = demand_mm / max(float(precip_scale_mm), 1e-6)
    sink = float(transmission_rate) * demand
    return np.where(ocean, 0.0, sink)


def effective_discharge_with_transmission(
    flw: object,
    *,
    pad: int,
    width: int,
    ocean_mask: NDArray[np.bool_],
    precip: NDArray[np.floating],
    sink: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Route precip − transmission sink along D8 (upstream → downstream).

    ``q[cell] = max(0, precip + Σ upstream q − sink)``. Strong upstream Q can
    survive an arid corridor (Nil); weak Q evaporates (wadi).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    precip_p = ew_pad(np.asarray(precip, dtype=np.float64), pad)
    sink_p = ew_pad(np.asarray(sink, dtype=np.float64), pad)
    ocean_p = ew_pad(ocean, pad)
    hp, wp = precip_p.shape
    ds = np.asarray(flw.idxs_ds, dtype=np.int32)
    seq = np.asarray(flw.idxs_seq, dtype=np.int32)
    ups: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(ds)):
        j = int(ds[idx])
        if j >= 0:
            ups[j].append(idx)

    q = np.zeros((hp, wp), dtype=np.float64)
    # idxs_seq is downstream→upstream; reverse ⇒ process sources first.
    for idx in seq[::-1]:
        idx_i = int(idx)
        r, c = divmod(idx_i, wp)
        if ocean_p[r, c]:
            continue
        total = float(precip_p[r, c])
        for u in ups[idx_i]:
            ur, uc = divmod(int(u), wp)
            total += q[ur, uc]
        total -= float(sink_p[r, c])
        q[r, c] = total if total > 0.0 else 0.0

    out = ew_crop(q, pad, width)
    return np.where(ocean, 0.0, out)
