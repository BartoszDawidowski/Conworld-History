"""EnvironmentTimeline — baseline + sparse anomalies (Milestone 19)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from worldsim.environment_timeline.baseline import BaselineEnvironmentSnapshot
from worldsim.environment_timeline.schema import (
    ENVIRONMENT_TIMELINE_SCHEMA_VERSION,
    EnvironmentalAnomaly,
    EnvironmentModifiers,
    aggregate_modifiers,
)
from worldsim.spatial.model import WorldSpatialModel


class EnvironmentTimelineProtocol(Protocol):
    """Stable interface for history / atlas time-indexed environment reads."""

    def modifiers_at(self, x: float, y: float, year: int) -> EnvironmentModifiers: ...

    def environment_at(
        self, x: float, y: float, *, year: int | None = None
    ) -> dict[str, Any]: ...

    def sample_climate(
        self, x: float, y: float, month: int, *, year: int | None = None
    ) -> float: ...

    def sample_elevation(
        self, x: float, y: float, *, year: int | None = None
    ) -> float: ...


@dataclass
class EnvironmentTimeline:
    """Time-dependent environmental layer over a static WorldSpatialModel.

    V1 scaffold: baseline climatology + anomaly log. No full palaeoclimate
    recompute, ice sheets, or coastline redraw yet — schema reserves room.
    """

    baseline: BaselineEnvironmentSnapshot
    anomalies: list[EnvironmentalAnomaly] = field(default_factory=list)
    schema_version: int = ENVIRONMENT_TIMELINE_SCHEMA_VERSION
    # Weak binding: timeline queries need the live model for baseline samples.
    _model: WorldSpatialModel | None = field(default=None, repr=False)

    def bind(self, model: WorldSpatialModel) -> None:
        self._model = model

    def add_anomaly(self, anomaly: EnvironmentalAnomaly) -> None:
        self.anomalies.append(anomaly)

    def modifiers_at(self, x: float, y: float, year: int) -> EnvironmentModifiers:
        return aggregate_modifiers(self.anomalies, x=x, y=y, year=year)

    def environment_at(
        self, x: float, y: float, *, year: int | None = None
    ) -> dict[str, Any]:
        model = self._require_model()
        base = model.environment_at(x, y)
        if year is None:
            base["year"] = None
            base["modifiers"] = EnvironmentModifiers().to_dict()
            base["source"] = "baseline"
            return base
        mod = self.modifiers_at(x, y, year)
        out = dict(base)
        out["year"] = int(year)
        out["source"] = "baseline+anomalies"
        out["modifiers"] = mod.to_dict()
        # Apply temperature offset to month-0 sample already in environment_at
        if "temperature_c_month0" in out:
            out["temperature_c_month0"] = (
                float(out["temperature_c_month0"]) + mod.temperature_offset_c
            )
        if "elevation_m" in out:
            out["elevation_m"] = float(out["elevation_m"]) - mod.sea_level_delta_m
            # Rising sea level → effective land elevation relative to sea decreases
        return out

    def sample_climate(
        self, x: float, y: float, month: int, *, year: int | None = None
    ) -> float:
        model = self._require_model()
        t = model.sample_climate(x, y, month)
        if year is None:
            return t
        return t + self.modifiers_at(x, y, year).temperature_offset_c

    def sample_elevation(
        self, x: float, y: float, *, year: int | None = None
    ) -> float:
        model = self._require_model()
        elev = model.sample_elevation(x, y)
        if year is None:
            return elev
        # Positive sea_level_delta_m lowers relative elevation vs sea.
        return elev - self.modifiers_at(x, y, year).sea_level_delta_m

    def sample_precipitation_proxy(
        self, x: float, y: float, month: int, *, year: int | None = None
    ) -> float:
        """Baseline monthly precip × anomaly scale (scaffold helper)."""
        model = self._require_model()
        precip = np.asarray(model.rasters.get("moisture/precipitation"), dtype=float)
        if month < 0 or month >= precip.shape[0]:
            raise ValueError(f"month must be in [0, {precip.shape[0]})")
        idx = model.climate_extent.xy_to_index(x, y, clamp_ns=True)
        val = float(precip[month, idx.j, idx.i])
        if year is None:
            return val
        return val * self.modifiers_at(x, y, year).precipitation_scale

    def _require_model(self) -> WorldSpatialModel:
        if self._model is None:
            raise RuntimeError("EnvironmentTimeline is not bound to a WorldSpatialModel")
        return self._model

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "baseline": self.baseline.to_dict(),
            "anomalies": [a.to_dict() for a in self.anomalies],
        }

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.baseline.save(directory / "baseline.json")
        (directory / "anomalies.json").write_text(
            json.dumps(
                {"anomalies": [a.to_dict() for a in self.anomalies]},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "timeline_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": self.schema_version,
                    "anomaly_count": len(self.anomalies),
                    "palaeoclimate_implemented": False,
                    "notes": (
                        "Scaffold only: anomalies modify baseline queries; "
                        "no full palaeoclimate engine."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path, *, model: WorldSpatialModel | None = None) -> EnvironmentTimeline:
        directory = Path(directory)
        manifest = json.loads(
            (directory / "timeline_manifest.json").read_text(encoding="utf-8")
        )
        version = int(manifest.get("schema_version", 0))
        if version != ENVIRONMENT_TIMELINE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported environment timeline schema {version}; "
                f"expected {ENVIRONMENT_TIMELINE_SCHEMA_VERSION}"
            )
        baseline = BaselineEnvironmentSnapshot.load(directory / "baseline.json")
        anom_data = json.loads((directory / "anomalies.json").read_text(encoding="utf-8"))
        anomalies = [
            EnvironmentalAnomaly.from_dict(item)
            for item in anom_data.get("anomalies", [])
        ]
        tl = cls(baseline=baseline, anomalies=anomalies, schema_version=version)
        if model is not None:
            tl.bind(model)
        return tl


def build_environment_timeline(
    model: WorldSpatialModel,
    *,
    anomalies: list[EnvironmentalAnomaly] | None = None,
) -> EnvironmentTimeline:
    """Create scaffold timeline from a finished world (stable baseline)."""
    baseline = BaselineEnvironmentSnapshot(
        climate_width=model.climate_extent.width,
        climate_height=model.climate_extent.height,
        hex_n_cells=model.hex_grid.n_cells,
        extra={
            "world_model_schema_version": model.manifest.world_model_schema_version,
            "master_seed": model.manifest.master_seed,
        },
    )
    tl = EnvironmentTimeline(
        baseline=baseline,
        anomalies=list(anomalies or []),
    )
    tl.bind(model)
    return tl
