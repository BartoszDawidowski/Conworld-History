"""Soils and Holdridge ecology (Milestone 14 / Stages M–N)."""

from __future__ import annotations

from worldsim.physical.ecology.holdridge import HoldridgeOverride
from worldsim.physical.ecology.pipeline import EcologyParams, EcologyResult, build_ecology

__all__ = [
    "EcologyParams",
    "EcologyResult",
    "HoldridgeOverride",
    "build_ecology",
]
