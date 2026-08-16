"""Migrate legacy cell-count length knobs to physical kilometres (PR-1).

Old ``*_cells`` names remain readable for one schema transition. Values are
converted using the **source profile** they were tuned against (Atlas climate
grid by default). Never silently reinterpret a cell count as kilometres.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Mapping

from worldsim.spatial.metrics import EARTH_RADIUS_KM, GridMetrics, grid_metrics
from worldsim.validation.physical_realism.seed_suites import PROFILE_GRIDS

LENGTH_UNITS_SCHEMA_VERSION = 1
DEFAULT_SOURCE_PROFILE = "atlas"


@dataclass(frozen=True)
class ResolvedLength:
    """One physical length after migration."""

    name_km: str
    value_km: float
    source: str  # "km" | "cells_converted" | "default_km"
    legacy_cells: float | None = None
    source_profile: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class EffectiveLengthConfig:
    """Bundle stored on the world manifest / run diagnostics."""

    length_units_schema_version: int
    source_profile: str
    radius_km: float
    grid_width: int
    grid_height: int
    resolved: dict[str, ResolvedLength]

    def to_dict(self) -> dict[str, Any]:
        return {
            "length_units_schema_version": self.length_units_schema_version,
            "source_profile": self.source_profile,
            "radius_km": self.radius_km,
            "conversion_grid": [self.grid_width, self.grid_height],
            "resolved": {
                k: {
                    "name_km": v.name_km,
                    "value_km": v.value_km,
                    "source": v.source,
                    "legacy_cells": v.legacy_cells,
                    "source_profile": v.source_profile,
                    "warning": v.warning,
                }
                for k, v in self.resolved.items()
            },
        }


def metrics_for_profile(
    profile: str,
    *,
    radius_km: float = EARTH_RADIUS_KM,
    grid: str = "climate",
) -> GridMetrics:
    if profile not in PROFILE_GRIDS:
        raise ValueError(f"unknown profile {profile!r}")
    w, h = PROFILE_GRIDS[profile][grid]
    return grid_metrics(w, h, radius_km=radius_km)


def resolve_length(
    *,
    name_km: str,
    km_value: float | None,
    cells_value: float | None,
    legacy_name_cells: str,
    metrics: GridMetrics,
    source_profile: str,
    default_km: float | None = None,
) -> ResolvedLength:
    """Prefer explicit km; else convert cells; else default_km."""
    if km_value is not None:
        return ResolvedLength(
            name_km=name_km,
            value_km=float(km_value),
            source="km",
            legacy_cells=float(cells_value) if cells_value is not None else None,
            source_profile=source_profile,
        )
    if cells_value is not None:
        value_km = metrics.km_from_cells_isotropic_midlat(float(cells_value))
        msg = (
            f"{legacy_name_cells}={cells_value} converted to {name_km}={value_km:.6g} km "
            f"using {source_profile} climate mid-latitude EW spacing "
            f"({metrics.width}×{metrics.height})"
        )
        return ResolvedLength(
            name_km=name_km,
            value_km=float(value_km),
            source="cells_converted",
            legacy_cells=float(cells_value),
            source_profile=source_profile,
            warning=msg,
        )
    if default_km is not None:
        return ResolvedLength(
            name_km=name_km,
            value_km=float(default_km),
            source="default_km",
            source_profile=source_profile,
        )
    raise ValueError(f"no value for {name_km} / {legacy_name_cells}")


def resolve_planet_lengths(
    raw: Mapping[str, Any] | None,
    *,
    inland_decay_cells: float,
    source_profile: str = DEFAULT_SOURCE_PROFILE,
    radius_km: float = EARTH_RADIUS_KM,
    continentality_scale_cells: float = 24.0,
    western_boundary_width_cells: float = 3.0,
) -> EffectiveLengthConfig:
    """Resolve SST inland decay, continentality, and boundary width."""
    data = dict(raw or {})
    ocean = data.get("ocean") if isinstance(data.get("ocean"), dict) else {}
    climate = data.get("climate") if isinstance(data.get("climate"), dict) else {}

    metrics = metrics_for_profile(source_profile, radius_km=radius_km, grid="climate")

    sst_km = ocean.get("sst_inland_decay_km", ocean.get("inland_decay_km"))
    cont_km = climate.get("continentality_scale_km")
    west_km = ocean.get("western_boundary_width_km")

    resolved = {
        "sst_inland_decay_km": resolve_length(
            name_km="sst_inland_decay_km",
            km_value=float(sst_km) if sst_km is not None else None,
            cells_value=float(inland_decay_cells),
            legacy_name_cells="inland_decay_cells",
            metrics=metrics,
            source_profile=source_profile,
        ),
        "continentality_scale_km": resolve_length(
            name_km="continentality_scale_km",
            km_value=float(cont_km) if cont_km is not None else None,
            cells_value=float(continentality_scale_cells),
            legacy_name_cells="continentality_scale_cells",
            metrics=metrics,
            source_profile=source_profile,
        ),
        "western_boundary_width_km": resolve_length(
            name_km="western_boundary_width_km",
            km_value=float(west_km) if west_km is not None else None,
            cells_value=float(western_boundary_width_cells),
            legacy_name_cells="western_boundary_width_cells",
            metrics=metrics,
            source_profile=source_profile,
        ),
    }
    return EffectiveLengthConfig(
        length_units_schema_version=LENGTH_UNITS_SCHEMA_VERSION,
        source_profile=source_profile,
        radius_km=float(radius_km),
        grid_width=metrics.width,
        grid_height=metrics.height,
        resolved=resolved,
    )


_EMITTED_WARNINGS: set[str] = set()


def emit_length_migration_warnings(effective: EffectiveLengthConfig) -> None:
    """Emit UserWarning once per distinct cells→km conversion message."""
    for item in effective.resolved.values():
        if item.warning and item.warning not in _EMITTED_WARNINGS:
            _EMITTED_WARNINGS.add(item.warning)
            warnings.warn(item.warning, UserWarning, stacklevel=2)
