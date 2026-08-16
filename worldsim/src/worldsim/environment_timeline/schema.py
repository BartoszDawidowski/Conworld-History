"""EnvironmentTimeline schema (Milestone 19 scaffold — no full palaeoclimate)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ENVIRONMENT_TIMELINE_SCHEMA_VERSION = 1

AnomalyKind = Literal[
    "temperature_offset",
    "precipitation_scale",
    "sea_level_delta",
    "generic",
]


@dataclass(frozen=True)
class SpatialScope:
    """Optional normalised cylindrical bbox. ``None`` fields mean global."""

    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None

    def contains(self, x: float, y: float) -> bool:
        if self.x0 is None and self.y0 is None and self.x1 is None and self.y1 is None:
            return True
        x0 = -1e9 if self.x0 is None else float(self.x0)
        x1 = 1e9 if self.x1 is None else float(self.x1)
        y0 = -1e9 if self.y0 is None else float(self.y0)
        y1 = 1e9 if self.y1 is None else float(self.y1)
        # Simple AABB; E–W wrap not expanded in v1 scaffold.
        return x0 <= x <= x1 and y0 <= y <= y1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SpatialScope:
        if not data:
            return cls()
        return cls(
            x0=data.get("x0"),
            y0=data.get("y0"),
            x1=data.get("x1"),
            y1=data.get("y1"),
        )


@dataclass
class EnvironmentalAnomaly:
    """Sparse time-dependent modifier — not a full climate recompute.

    Do not store a duplicate of all high-resolution rasters per year (§38).
    """

    id: str
    kind: AnomalyKind
    year_start: int
    year_end: int
    # Kind-specific payload
    temperature_offset_c: float = 0.0
    precipitation_scale: float = 1.0
    sea_level_delta_m: float = 0.0
    scope: SpatialScope = field(default_factory=SpatialScope)
    notes: str = ""

    def active_in(self, year: int) -> bool:
        return int(self.year_start) <= int(year) <= int(self.year_end)

    def applies_at(self, x: float, y: float, year: int) -> bool:
        return self.active_in(year) and self.scope.contains(x, y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "year_start": self.year_start,
            "year_end": self.year_end,
            "temperature_offset_c": self.temperature_offset_c,
            "precipitation_scale": self.precipitation_scale,
            "sea_level_delta_m": self.sea_level_delta_m,
            "scope": self.scope.to_dict(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentalAnomaly:
        return cls(
            id=str(data["id"]),
            kind=str(data.get("kind", "generic")),  # type: ignore[arg-type]
            year_start=int(data["year_start"]),
            year_end=int(data["year_end"]),
            temperature_offset_c=float(data.get("temperature_offset_c", 0.0)),
            precipitation_scale=float(data.get("precipitation_scale", 1.0)),
            sea_level_delta_m=float(data.get("sea_level_delta_m", 0.0)),
            scope=SpatialScope.from_dict(data.get("scope")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class EnvironmentModifiers:
    """Aggregated anomaly effect at one point/time."""

    temperature_offset_c: float = 0.0
    precipitation_scale: float = 1.0
    sea_level_delta_m: float = 0.0
    anomaly_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature_offset_c": self.temperature_offset_c,
            "precipitation_scale": self.precipitation_scale,
            "sea_level_delta_m": self.sea_level_delta_m,
            "anomaly_ids": list(self.anomaly_ids),
        }


def aggregate_modifiers(
    anomalies: list[EnvironmentalAnomaly],
    *,
    x: float,
    y: float,
    year: int,
) -> EnvironmentModifiers:
    mod = EnvironmentModifiers()
    scale = 1.0
    for a in anomalies:
        if not a.applies_at(x, y, year):
            continue
        mod.anomaly_ids.append(a.id)
        mod.temperature_offset_c += float(a.temperature_offset_c)
        mod.sea_level_delta_m += float(a.sea_level_delta_m)
        scale *= float(a.precipitation_scale)
    mod.precipitation_scale = scale
    return mod
