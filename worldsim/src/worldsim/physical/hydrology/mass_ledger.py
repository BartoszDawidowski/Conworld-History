"""Hydrology mass ledger (PC1 / pkg3 global closure)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.cylindrical_graph import (
    SINK,
    CylindricalFlowGraph,
    _touches_ocean,
    unravel,
)

# Absolute / relative residual gates (user audit pkg3).
GLOBAL_MASS_ABS_TOL_M3 = 1e-3
GLOBAL_MASS_REL_TOL = 1e-6
LAKE_INFLOW_CAPTURE_RATIO_MIN = 1.0 - 1e-6


@dataclass
class LakeMonthLedger:
    """Monthly water balance for one lake supernode (volumes in m³)."""

    lake_id: int
    month: int
    initial_storage_m3: float = 0.0
    local_land_runoff_m3: float = 0.0
    upstream_channel_inflow_m3: float = 0.0
    upstream_lake_release_m3: float = 0.0
    direct_precip_on_water_m3: float = 0.0
    final_storage_m3: float = 0.0
    downstream_release_m3: float = 0.0
    open_water_evaporation_m3: float = 0.0
    seepage_m3: float = 0.0
    channel_bed_loss_m3: float = 0.0
    other_sink_m3: float = 0.0

    def sources_m3(self) -> float:
        return (
            self.local_land_runoff_m3
            + self.upstream_channel_inflow_m3
            + self.upstream_lake_release_m3
            + self.direct_precip_on_water_m3
        )

    def sinks_m3(self) -> float:
        return (
            self.downstream_release_m3
            + self.open_water_evaporation_m3
            + self.seepage_m3
            + self.channel_bed_loss_m3
            + self.other_sink_m3
        )

    def storage_change_m3(self) -> float:
        return self.final_storage_m3 - self.initial_storage_m3

    def residual_m3(self) -> float:
        return (
            self.initial_storage_m3
            + self.sources_m3()
            - self.final_storage_m3
            - self.sinks_m3()
        )

    def to_dict(self) -> dict[str, float | int]:
        return {
            "lake_id": int(self.lake_id),
            "month": int(self.month),
            "initial_storage_m3": float(self.initial_storage_m3),
            "local_land_runoff_m3": float(self.local_land_runoff_m3),
            "upstream_channel_inflow_m3": float(self.upstream_channel_inflow_m3),
            "upstream_lake_release_m3": float(self.upstream_lake_release_m3),
            "direct_precip_on_water_m3": float(self.direct_precip_on_water_m3),
            "final_storage_m3": float(self.final_storage_m3),
            "downstream_release_m3": float(self.downstream_release_m3),
            "open_water_evaporation_m3": float(self.open_water_evaporation_m3),
            "seepage_m3": float(self.seepage_m3),
            "channel_bed_loss_m3": float(self.channel_bed_loss_m3),
            "other_sink_m3": float(self.other_sink_m3),
            "residual_m3": float(self.residual_m3()),
        }


def land_terminal_exports_m3s(
    graph: CylindricalFlowGraph,
    land_q_m3s: NDArray[np.floating],
    basin_envelope_id: NDArray[np.integer],
) -> tuple[float, float, float]:
    """Split land-cell SINK discharge into ocean / closed / N–S boundary (m³/s).

    Lake envelopes are excluded — their mass is tracked in lake ledgers.
    """
    q = np.asarray(land_q_m3s, dtype=np.float64)
    env = np.asarray(basin_envelope_id, dtype=np.int32)
    ds = graph.downstream_flat
    ocean = graph.ocean_mask
    h, w = graph.height, graph.width
    ocean_export = 0.0
    closed_retention = 0.0
    boundary_export = 0.0
    # Only iterate true land sinks outside lakes (typically ≪ grid size).
    land_sink = np.flatnonzero(
        (~ocean.ravel())
        & (env.ravel() <= 0)
        & (np.asarray(ds, dtype=np.int64) == SINK)
        & (q.ravel() > 0.0)
    )
    for i in land_sink.tolist():
        r, c = unravel(i, w)
        rate = float(q[r, c])
        if _touches_ocean(r, c, ocean):
            ocean_export += rate
        elif r == 0 or r == h - 1:
            boundary_export += rate
        else:
            closed_retention += rate
    return ocean_export, closed_retention, boundary_export


@dataclass
class GlobalMonthLedger:
    """Domain monthly balance: runoff, lake precip/storage/ET, bed loss, terminals."""

    month: int
    lake_ledgers: list[LakeMonthLedger] = field(default_factory=list)
    land_local_runoff_m3: float = 0.0
    land_direct_precip_m3: float = 0.0
    land_bed_loss_m3: float = 0.0
    land_downstream_release_m3: float = 0.0  # deprecated alias: sum of terminal exports
    ocean_export_m3: float = 0.0
    closed_retention_m3: float = 0.0
    boundary_export_m3: float = 0.0
    unassigned_spill_m3: float = 0.0
    lake_inflow_available_m3: float = 0.0
    lake_inflow_accounted_m3: float = 0.0

    def lake_residual_abs_m3(self) -> float:
        return float(sum(abs(led.residual_m3()) for led in self.lake_ledgers))

    def lake_precip_m3(self) -> float:
        return float(sum(led.direct_precip_on_water_m3 for led in self.lake_ledgers))

    def lake_storage_delta_m3(self) -> float:
        return float(sum(led.storage_change_m3() for led in self.lake_ledgers))

    def lake_et_seepage_m3(self) -> float:
        return float(
            sum(
                led.open_water_evaporation_m3 + led.seepage_m3 + led.other_sink_m3
                for led in self.lake_ledgers
            )
        )

    def sources_m3(self) -> float:
        return (
            float(self.land_local_runoff_m3)
            + float(self.land_direct_precip_m3)
            + self.lake_precip_m3()
        )

    def sinks_m3(self) -> float:
        return (
            float(self.land_bed_loss_m3)
            + float(self.ocean_export_m3)
            + float(self.closed_retention_m3)
            + float(self.boundary_export_m3)
            + self.lake_et_seepage_m3()
            + float(self.unassigned_spill_m3)
        )

    def residual_m3(self) -> float:
        """sources − sinks − Δstorage (lake-to-lake spill cancels inside ledgers)."""
        return self.sources_m3() - self.sinks_m3() - self.lake_storage_delta_m3()

    def residual_rel(self) -> float:
        denom = max(abs(self.sources_m3()), 1e-12)
        return float(abs(self.residual_m3()) / denom)

    def lake_inflow_capture_ratio(self) -> float:
        avail = float(self.lake_inflow_available_m3)
        got = float(self.lake_inflow_accounted_m3)
        if avail <= 1e-12:
            return 1.0 if got <= 1e-12 else 0.0
        return float(got / avail)

    def mass_balance_ok(
        self,
        *,
        abs_tol_m3: float = GLOBAL_MASS_ABS_TOL_M3,
        rel_tol: float = GLOBAL_MASS_REL_TOL,
    ) -> bool:
        return bool(
            abs(self.residual_m3()) <= float(abs_tol_m3)
            or self.residual_rel() <= float(rel_tol)
        ) and bool(self.lake_residual_abs_m3() <= float(abs_tol_m3))

    def capture_ok(
        self, *, min_ratio: float = LAKE_INFLOW_CAPTURE_RATIO_MIN
    ) -> bool:
        return bool(self.lake_inflow_capture_ratio() >= float(min_ratio))

    def summary(self) -> dict[str, Any]:
        return {
            "month": int(self.month),
            "lake_count": len(self.lake_ledgers),
            "sources_m3": float(self.sources_m3()),
            "sinks_m3": float(self.sinks_m3()),
            "lake_storage_delta_m3": float(self.lake_storage_delta_m3()),
            "lake_precip_m3": float(self.lake_precip_m3()),
            "lake_et_seepage_m3": float(self.lake_et_seepage_m3()),
            "land_local_runoff_m3": float(self.land_local_runoff_m3),
            "land_bed_loss_m3": float(self.land_bed_loss_m3),
            "ocean_export_m3": float(self.ocean_export_m3),
            "closed_retention_m3": float(self.closed_retention_m3),
            "boundary_export_m3": float(self.boundary_export_m3),
            "unassigned_spill_m3": float(self.unassigned_spill_m3),
            "land_downstream_release_m3": float(self.land_downstream_release_m3),
            "residual_m3": float(self.residual_m3()),
            "residual_rel": float(self.residual_rel()),
            "lake_residual_abs_m3": float(self.lake_residual_abs_m3()),
            "lake_inflow_available_m3": float(self.lake_inflow_available_m3),
            "lake_inflow_accounted_m3": float(self.lake_inflow_accounted_m3),
            "lake_inflow_capture_ratio": float(self.lake_inflow_capture_ratio()),
            "mass_balance_ok": bool(self.mass_balance_ok()),
            "capture_ok": bool(self.capture_ok()),
        }
