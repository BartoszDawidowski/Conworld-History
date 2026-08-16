"""Ocean circulation (Milestone 8 / Stage G; Plan B1 inland SST coupling)."""

from __future__ import annotations

from worldsim.physical.ocean.pipeline import (
    OceanParams,
    OceanResult,
    apply_ocean_temperature_to_climate,
    build_ocean_circulation,
)
from worldsim.physical.ocean.sst import (
    couple_coastal_temperature,
    couple_temperature_with_sst_inland,
    inland_sst_blend_weight,
)

__all__ = [
    "OceanParams",
    "OceanResult",
    "apply_ocean_temperature_to_climate",
    "build_ocean_circulation",
    "couple_coastal_temperature",
    "couple_temperature_with_sst_inland",
    "inland_sst_blend_weight",
]
