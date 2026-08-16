"""Baseline environment snapshot for EnvironmentTimeline (Milestone 19)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from worldsim.spatial.extent import SpatialExtent


@dataclass
class BaselineEnvironmentSnapshot:
    """Stable climatology / geography references — not a yearly raster dump.

    Points at canonical WorldSpatialModel layers. Changing coastlines later can
    add anomalies / overlays without replacing this baseline schema.
    """

    climate_width: int
    climate_height: int
    hex_n_cells: int
    layers: dict[str, str] = field(
        default_factory=lambda: {
            "elevation": "climate/elevation_m",
            "ocean_mask": "climate/ocean_mask",
            "temperature_c": "climate/temperature_c",
            "precipitation": "moisture/precipitation",
            "holdridge": "ecology/holdridge_zone_id",
        }
    )
    notes: str = (
        "Baseline = static physical WorldSpatialModel. "
        "Time variation is expressed as sparse anomalies (Milestone 19 scaffold)."
    )
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def climate_extent(self) -> SpatialExtent:
        return SpatialExtent.from_shape(self.climate_width, self.climate_height)

    def to_dict(self) -> dict[str, Any]:
        return {
            "climate_width": self.climate_width,
            "climate_height": self.climate_height,
            "hex_n_cells": self.hex_n_cells,
            "layers": dict(self.layers),
            "notes": self.notes,
            "extra": dict(self.extra),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> BaselineEnvironmentSnapshot:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            climate_width=int(data["climate_width"]),
            climate_height=int(data["climate_height"]),
            hex_n_cells=int(data["hex_n_cells"]),
            layers=dict(data.get("layers", {})),
            notes=str(data.get("notes", "")),
            extra=dict(data.get("extra", {})),
        )
