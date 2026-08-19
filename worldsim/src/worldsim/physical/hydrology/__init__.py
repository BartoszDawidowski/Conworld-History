"""Hydrology with PyFlwDir (Milestone 11 / Stage J)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "HydrologyParams",
    "HydrologyResult",
    "build_hydrology",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from worldsim.physical.hydrology import pipeline as _pipeline

        return getattr(_pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
