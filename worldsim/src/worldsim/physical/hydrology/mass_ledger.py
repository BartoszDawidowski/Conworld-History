"""Hydrology mass ledger (PC1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class GlobalMonthLedger:
    """Aggregated monthly balance across lakes and land routing."""

    month: int
    lake_ledgers: list[LakeMonthLedger] = field(default_factory=list)
    land_local_runoff_m3: float = 0.0
    land_direct_precip_m3: float = 0.0
    land_bed_loss_m3: float = 0.0
    land_downstream_release_m3: float = 0.0

    def residual_m3(self) -> float:
        lake_res = sum(abs(led.residual_m3()) for led in self.lake_ledgers)
        return float(lake_res)

    def summary(self) -> dict[str, Any]:
        src = sum(led.sources_m3() for led in self.lake_ledgers)
        snk = sum(led.sinks_m3() + led.storage_change_m3() for led in self.lake_ledgers)
        return {
            "month": int(self.month),
            "lake_count": len(self.lake_ledgers),
            "lake_sources_m3": float(src),
            "lake_sinks_and_storage_m3": float(snk),
            "lake_residual_abs_m3": float(self.residual_m3()),
            "land_local_runoff_m3": float(self.land_local_runoff_m3),
            "land_bed_loss_m3": float(self.land_bed_loss_m3),
            "land_downstream_release_m3": float(self.land_downstream_release_m3),
        }
