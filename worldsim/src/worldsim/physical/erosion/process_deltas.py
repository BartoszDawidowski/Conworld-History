"""Process delta tracking (PC4)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


def accumulate_conditioning_delta(
    before: NDArray[np.floating],
    after: NDArray[np.floating],
    accumulator: NDArray[np.floating],
    *,
    land_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.float64]:
    """Add ``after - before`` into ``accumulator`` (land-only when mask given)."""
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    acc = np.asarray(accumulator, dtype=np.float64).copy()
    delta = a - b
    if land_mask is not None:
        delta = np.where(np.asarray(land_mask, dtype=bool), delta, 0.0)
    return acc + delta


@dataclass
class ProcessDeltas:
    """Independent erosion/conditioning rasters (addendum §8.1)."""

    thermal_or_hillslope_delta_m: NDArray[np.float64]
    first_fluvial_delta_m: NDArray[np.float64]
    conditioning_or_pit_fill_delta_m: NDArray[np.float64]
    final_stream_power_delta_m: NDArray[np.float64]
    total_erosion_delta_m: NDArray[np.float64]
    total_dem_adjustment_m: NDArray[np.float64]

    @classmethod
    def zeros(cls, shape: tuple[int, ...]) -> ProcessDeltas:
        z = np.zeros(shape, dtype=np.float64)
        return cls(
            thermal_or_hillslope_delta_m=z.copy(),
            first_fluvial_delta_m=z.copy(),
            conditioning_or_pit_fill_delta_m=z.copy(),
            final_stream_power_delta_m=z.copy(),
            total_erosion_delta_m=z.copy(),
            total_dem_adjustment_m=z.copy(),
        )

    def merge_first_pass(
        self,
        *,
        thermal: NDArray[np.floating],
        first_fluvial: NDArray[np.floating],
        conditioning: NDArray[np.floating],
    ) -> None:
        self.thermal_or_hillslope_delta_m = np.asarray(thermal, dtype=np.float64)
        self.first_fluvial_delta_m = np.asarray(first_fluvial, dtype=np.float64)
        self.conditioning_or_pit_fill_delta_m = np.asarray(conditioning, dtype=np.float64)
        erosion = self.thermal_or_hillslope_delta_m + self.first_fluvial_delta_m
        self.total_erosion_delta_m = erosion
        self.total_dem_adjustment_m = erosion + self.conditioning_or_pit_fill_delta_m

    def merge_final_fluvial(
        self,
        *,
        stream_power: NDArray[np.floating],
        conditioning: NDArray[np.floating],
    ) -> None:
        self.final_stream_power_delta_m = np.asarray(stream_power, dtype=np.float64)
        self.conditioning_or_pit_fill_delta_m = np.asarray(conditioning, dtype=np.float64)
        self.total_erosion_delta_m = self.final_stream_power_delta_m.copy()
        self.total_dem_adjustment_m = (
            self.final_stream_power_delta_m + self.conditioning_or_pit_fill_delta_m
        )
