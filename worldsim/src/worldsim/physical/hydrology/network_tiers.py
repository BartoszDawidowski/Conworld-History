"""Physical, geomorphic, and display channel tiers (PC2)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.channels import (
    CHANNEL_PERENNIAL,
    CHANNEL_SEASONAL,
    display_channel_candidates,
)
from worldsim.physical.hydrology.rivers import (
    gate_river_mask_by_discharge,
    propagate_downstream_on_mask,
)


def geomorphic_channel_mask(
    physical_mask: NDArray[np.bool_],
    monthly_q_m3s: NDArray[np.floating],
    channel_state: NDArray[np.integer],
    *,
    q_min_m3s: float = 0.05,
    min_wet_months: int = 3,
) -> NDArray[np.bool_]:
    """Persistent/significant channels for erosion — no display quantile."""
    physical = np.asarray(physical_mask, dtype=np.bool_)
    q = np.asarray(monthly_q_m3s, dtype=np.float64)
    state = np.asarray(channel_state, dtype=np.uint8)
    if q.ndim != 3:
        raise ValueError("monthly_q_m3s must be [months, y, x]")
    floor = max(float(q_min_m3s), 0.0)
    wet = np.sum(q > floor, axis=0) >= max(int(min_wet_months), 1)
    persistent_state = state >= CHANNEL_SEASONAL
    return physical & (wet | persistent_state)


def build_display_river_mask(
    *,
    physical_mask: NDArray[np.bool_],
    flow_accumulation: NDArray[np.floating],
    discharge_effective: NDArray[np.floating],
    flow_direction: NDArray[np.uint8],
    ocean_mask: NDArray[np.bool_],
    acc_fraction: float,
    candidate_quantile: float = 0.50,
    min_effective_discharge: float | None = None,
    trace_downstream: bool = True,
) -> tuple[NDArray[np.bool_], dict[str, Any]]:
    """Display LOD after final effective Q; optional downstream trace to terminals."""
    candidates = display_channel_candidates(
        physical_mask,
        flow_accumulation,
        fraction=acc_fraction,
    )
    seeds, gate_diag = gate_river_mask_by_discharge(
        candidates,
        discharge_effective,
        flow_direction,
        ocean_mask,
        candidate_quantile=candidate_quantile,
        min_effective_discharge=min_effective_discharge,
        inherit_downstream=False,
    )
    if trace_downstream and np.any(seeds):
        display = propagate_downstream_on_mask(
            seeds,
            flow_direction,
            ocean_mask,
            limit_mask=candidates,
        )
        display |= seeds
    else:
        display = seeds
    diag = {
        **gate_diag,
        "display_trace_downstream": bool(trace_downstream),
        "display_candidate_cell_count": int(np.count_nonzero(candidates)),
        "display_after_discharge_gate": int(np.count_nonzero(seeds)),
        "display_after_trace": int(np.count_nonzero(display)),
    }
    return display.astype(bool), diag


def channel_tier_diagnostics(
    *,
    physical_mask: NDArray[np.bool_],
    geomorphic_mask: NDArray[np.bool_],
    display_mask: NDArray[np.bool_],
) -> dict[str, int | float]:
    physical_n = int(np.count_nonzero(physical_mask))
    geomorphic_n = int(np.count_nonzero(geomorphic_mask))
    display_n = int(np.count_nonzero(display_mask))
    return {
        "channel_physical_cell_count": physical_n,
        "channel_geomorphic_cell_count": geomorphic_n,
        "channel_display_cell_count": display_n,
        "channel_display_candidate_cell_count": display_n,
        "channel_physical_not_display_count": int(
            np.count_nonzero(physical_mask & ~display_mask)
        ),
        "channel_geomorphic_not_display_count": int(
            np.count_nonzero(geomorphic_mask & ~display_mask)
        ),
        "channel_display_subset_of_physical": bool(
            not np.any(display_mask & ~physical_mask)
        ),
        "channel_geomorphic_subset_of_physical": bool(
            not np.any(geomorphic_mask & ~physical_mask)
        ),
    }
