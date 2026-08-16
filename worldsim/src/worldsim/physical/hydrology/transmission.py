"""Effective discharge with channel transmission losses (Plan B §6.3.1 / PR-5)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.conditioning import ew_crop, ew_pad
from worldsim.physical.hydrology.cylindrical_graph import (
    CylindricalFlowGraph,
    build_cylindrical_graph,
    effective_discharge,
)


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
    graph: CylindricalFlowGraph | None = None,
) -> NDArray[np.float64]:
    """Route precip − transmission sink on the canonical cylindrical graph."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    if graph is None:
        d8_p = flw.to_array(ftype="d8")  # type: ignore[attr-defined]
        d8 = ew_crop(d8_p, pad, width).astype(np.uint8)
        graph = build_cylindrical_graph(d8, ocean)
    return effective_discharge(graph, precip, sink)
