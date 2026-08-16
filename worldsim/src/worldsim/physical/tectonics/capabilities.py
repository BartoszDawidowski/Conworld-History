"""Capability detection for extended PyPlatec bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlatecCapabilities:
    module: Any
    has_agemap: bool
    has_plate_count: bool
    has_plate_velocity: bool
    has_plate_speed: bool
    source: str

    @property
    def supports_extended_metadata(self) -> bool:
        return (
            self.has_agemap
            and self.has_plate_count
            and self.has_plate_velocity
            and self.has_plate_speed
        )


def detect_platec_capabilities() -> PlatecCapabilities:
    try:
        import platec
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("platec module is not installed") from exc

    return PlatecCapabilities(
        module=platec,
        has_agemap=hasattr(platec, "get_agemap"),
        has_plate_count=hasattr(platec, "get_plate_count"),
        has_plate_velocity=hasattr(platec, "get_plate_velocity"),
        has_plate_speed=hasattr(platec, "get_plate_speed"),
        source=getattr(platec, "__file__", "unknown"),
    )
