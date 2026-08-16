"""Shared PyPlatec parameter object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PyPlatecParams:
    """Parameters matching the upstream ``platec.create`` contract."""

    sea_level: float = 0.65
    erosion_period: int = 60
    folding_ratio: float = 0.02
    aggr_overlap_abs: int = 1_000_000
    aggr_overlap_rel: float = 0.33
    cycle_count: int = 2
    num_plates: int = 10
