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

# Non-leap civil month lengths. Holdridge PET is an *annual* millimetre total.
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
YEAR_DAYS = 365
_MONTH_DAYS = MONTH_DAYS
_YEAR_DAYS = YEAR_DAYS


def month_pet_fraction(month_index: int) -> float:
    """Share of annual Holdridge PET that belongs to one calendar month."""
    return float(MONTH_DAYS[int(month_index) % 12]) / float(YEAR_DAYS)


NOMINAL_MONTH_DAYS = 30.0


def channel_bed_loss_potential_m3s(
    channel_length_km: NDArray[np.floating],
    *,
    loss_rate_m3_per_km_month: float,
    width_factor: NDArray[np.floating] | float = 1.0,
    channel_mask: NDArray[np.bool_] | None = None,
    ocean_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.float64]:
    """Potential channel-bed loss in m³/s from geometry, not full-cell PET.

    ``potential_loss_m3_month = rate × length_km × width_factor``. Converted
    with a 30-day nominal month so monthly and independent-annual sinks share
    the same m³/s semantics. Callers must cap by available Q during routing.
    """
    length = np.maximum(np.asarray(channel_length_km, dtype=np.float64), 0.0)
    width = np.maximum(np.asarray(width_factor, dtype=np.float64), 0.0)
    potential_m3_month = float(loss_rate_m3_per_km_month) * length * width
    seconds = float(NOMINAL_MONTH_DAYS) * 86400.0
    potential = potential_m3_month / max(seconds, 1.0)
    if channel_mask is not None:
        potential = np.where(np.asarray(channel_mask, dtype=np.bool_), potential, 0.0)
    if ocean_mask is not None:
        potential = np.where(np.asarray(ocean_mask, dtype=np.bool_), 0.0, potential)
    return potential.astype(np.float64, copy=False)


def transmission_sink(
    precip: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    *,
    transmission_rate: float = 0.45,
    precip_scale_mm: float = 200.0,
    pet_year_fraction: float = 1.0,
    path_length_km: NDArray[np.floating] | None = None,
    transmission_ref_km: float = 50.0,
    residual_pet_proxy: NDArray[np.floating] | None = None,
) -> NDArray[np.float64]:
    """Channel loss in runoff-proxy units.

    Default demand is rate × max(0, PET − local water) (CR-6). Monthly callers
    must pass ``pet_year_fraction = days_in_month / 365``.

    CR-7: ``path_length_km`` scales demand by ``length / transmission_ref_km``
    (per-km loss). ``residual_pet_proxy`` is PET left after the soil bucket so
    channel ET does not double-count land ET.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    p = np.asarray(precip, dtype=np.float64)
    t = np.asarray(temperature_c, dtype=np.float64)
    frac = max(float(pet_year_fraction), 0.0)
    scale = max(float(precip_scale_mm), 1e-6)
    if residual_pet_proxy is not None:
        demand = np.maximum(np.asarray(residual_pet_proxy, dtype=np.float64), 0.0)
    else:
        bio = np.clip(t, 0.0, 30.0)
        pet_mm = 58.93 * bio * frac
        precip_mm = np.maximum(p, 0.0) * scale
        demand = np.maximum(pet_mm - precip_mm, 0.0) / scale
    sink = float(transmission_rate) * demand
    if path_length_km is not None:
        length = np.maximum(np.asarray(path_length_km, dtype=np.float64), 0.0)
        ref = max(float(transmission_ref_km), 1e-6)
        sink = sink * (length / ref)
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
