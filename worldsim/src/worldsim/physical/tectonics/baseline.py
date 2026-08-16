"""PyPlatec baseline + extended result builders (Milestones 2–3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.diagnostics import (
    assert_no_ns_adjacency,
    build_tectonics_diagnostics,
)
from worldsim.physical.tectonics.engine import run_platec_simulation
from worldsim.physical.tectonics.params import PyPlatecParams
from worldsim.physical.tectonics.seam import (
    roll_ew,
    seam_edge_elevation_gap,
    select_ew_seam,
)
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent


@dataclass
class TectonicsBaselineResult:
    elevation_raw: NDArray[np.float64]
    plate_id: NDArray[np.int32]
    extent: SpatialExtent
    seed: int
    seam_column: int
    steps: int
    diagnostics: dict[str, Any]
    params: PyPlatecParams

    @property
    def shape(self) -> tuple[int, int]:
        return (self.extent.height, self.extent.width)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "tectonics_baseline.npz",
            elevation_raw=self.elevation_raw,
            plate_id=self.plate_id,
            seam_column=np.asarray([self.seam_column], dtype=np.int32),
            seed=np.asarray([self.seed], dtype=np.int64),
            steps=np.asarray([self.steps], dtype=np.int32),
        )
        (directory / "tectonics_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        meta = {
            "schema": "tectonics_baseline_v1",
            "width": self.extent.width,
            "height": self.extent.height,
            "seed": self.seed,
            "seam_column": self.seam_column,
            "params": {
                "sea_level": self.params.sea_level,
                "erosion_period": self.params.erosion_period,
                "folding_ratio": self.params.folding_ratio,
                "aggr_overlap_abs": self.params.aggr_overlap_abs,
                "aggr_overlap_rel": self.params.aggr_overlap_rel,
                "cycle_count": self.params.cycle_count,
                "num_plates": self.params.num_plates,
            },
        }
        (directory / "tectonics_meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


@dataclass
class TectonicsExtendedResult(TectonicsBaselineResult):
    """Baseline maps plus crust age and plate velocity fields."""

    crust_age: NDArray[np.uint32] | None = None
    plate_velocity_x: NDArray[np.float64] | None = None
    plate_velocity_y: NDArray[np.float64] | None = None
    plate_speed: NDArray[np.float64] | None = None
    metadata_source: str = "unknown"
    plate_unit_velocity: dict[int, tuple[float, float]] | None = None
    plate_speeds: dict[int, float] | None = None

    def save(self, directory: Path) -> None:
        super().save(directory)
        payload: dict[str, Any] = {
            "elevation_raw": self.elevation_raw,
            "plate_id": self.plate_id,
            "seam_column": np.asarray([self.seam_column], dtype=np.int32),
            "seed": np.asarray([self.seed], dtype=np.int64),
            "steps": np.asarray([self.steps], dtype=np.int32),
        }
        if self.crust_age is not None:
            payload["crust_age"] = self.crust_age
        if self.plate_velocity_x is not None:
            payload["plate_velocity_x"] = self.plate_velocity_x
        if self.plate_velocity_y is not None:
            payload["plate_velocity_y"] = self.plate_velocity_y
        if self.plate_speed is not None:
            payload["plate_speed"] = self.plate_speed
        np.savez_compressed(directory / "tectonics_extended.npz", **payload)
        extended_meta = {
            "schema": "tectonics_extended_v1",
            "metadata_source": self.metadata_source,
            "has_crust_age": self.crust_age is not None,
            "has_plate_velocity": self.plate_velocity_x is not None,
            "plate_unit_velocity": {
                str(k): list(v) for k, v in (self.plate_unit_velocity or {}).items()
            },
            "plate_speeds": {str(k): v for k, v in (self.plate_speeds or {}).items()},
            "diagnostics_extra": {
                "metadata_source": self.metadata_source,
            },
        }
        (directory / "tectonics_extended_meta.json").write_text(
            json.dumps(extended_meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _apply_seam_to_stack(
    elevation: NDArray[np.float64],
    plate_id: NDArray[np.int32],
    extras: list[NDArray | None],
) -> tuple[int, NDArray[np.float64], NDArray[np.int32], list[NDArray | None]]:
    seam_column = select_ew_seam(elevation)
    arrays: list[NDArray] = [elevation, plate_id]
    extra_index_map: list[int | None] = []
    for arr in extras:
        if arr is None:
            extra_index_map.append(None)
        else:
            extra_index_map.append(len(arrays))
            arrays.append(arr)
    rolled = roll_ew(tuple(arrays), seam_column)
    elevation_r = np.asarray(rolled[0], dtype=np.float64)
    plate_r = np.asarray(rolled[1], dtype=np.int32)
    extras_r: list[NDArray | None] = []
    for mapped in extra_index_map:
        if mapped is None:
            extras_r.append(None)
        else:
            extras_r.append(np.asarray(rolled[mapped]))
    return seam_column, elevation_r, plate_r, extras_r


def run_pyplatec_baseline(
    *,
    seed: int,
    width: int,
    height: int,
    params: PyPlatecParams | None = None,
    reporter: ProgressReporter | None = None,
    apply_seam: bool = True,
) -> TectonicsBaselineResult:
    """Run PyPlatec for height + plate_id (Milestone 2 contract)."""
    params = params or PyPlatecParams()
    extent = SpatialExtent.from_shape(width, height)
    assert_no_ns_adjacency(extent)

    def _progress(value: float) -> None:
        if reporter is not None:
            reporter.progress("tectonics", value)

    if reporter is not None:
        reporter.stage_started("tectonics")

    raw = run_platec_simulation(
        seed=seed,
        width=width,
        height=height,
        params=params,
        on_progress=_progress,
        prefer_extended=False,
    )
    elevation = raw.elevation
    plate_id = raw.plate_id
    gap_before = seam_edge_elevation_gap(elevation)
    seam_column = 0
    if apply_seam:
        if reporter is not None:
            reporter.stage_started("tectonics_seam")
        seam_column, elevation, plate_id, _ = _apply_seam_to_stack(
            elevation, plate_id, []
        )
        if reporter is not None:
            reporter.progress("tectonics_seam", 1.0)
            reporter.stage_complete("tectonics_seam")

    gap_after = seam_edge_elevation_gap(elevation)
    diagnostics = build_tectonics_diagnostics(
        elevation=elevation,
        plate_id=plate_id,
        seam_column=seam_column,
        seam_gap_before=gap_before,
        seam_gap_after=gap_after,
        seed=seed,
        steps=raw.steps,
    )
    result = TectonicsBaselineResult(
        elevation_raw=elevation,
        plate_id=plate_id,
        extent=extent,
        seed=int(seed),
        seam_column=int(seam_column),
        steps=int(raw.steps),
        diagnostics=diagnostics,
        params=params,
    )
    if reporter is not None:
        reporter.stage_complete("tectonics")
    return result


def run_pyplatec_extended(
    *,
    seed: int,
    width: int,
    height: int,
    params: PyPlatecParams | None = None,
    reporter: ProgressReporter | None = None,
    apply_seam: bool = True,
) -> TectonicsExtendedResult:
    """Run PyPlatec with crust age + plate velocity fields (Milestone 3)."""
    params = params or PyPlatecParams()
    extent = SpatialExtent.from_shape(width, height)
    assert_no_ns_adjacency(extent)

    def _progress(value: float) -> None:
        if reporter is not None:
            reporter.progress("tectonics", value)

    if reporter is not None:
        reporter.stage_started("tectonics")

    raw = run_platec_simulation(
        seed=seed,
        width=width,
        height=height,
        params=params,
        on_progress=_progress,
        prefer_extended=True,
    )
    elevation = raw.elevation
    plate_id = raw.plate_id
    crust_age = raw.crust_age
    vx = raw.plate_velocity_x
    vy = raw.plate_velocity_y
    speed = raw.plate_speed

    gap_before = seam_edge_elevation_gap(elevation)
    seam_column = 0
    if apply_seam:
        if reporter is not None:
            reporter.stage_started("tectonics_seam")
        seam_column, elevation, plate_id, extras = _apply_seam_to_stack(
            elevation,
            plate_id,
            [crust_age, vx, vy, speed],
        )
        crust_age, vx, vy, speed = extras  # type: ignore[misc]
        if crust_age is not None:
            crust_age = np.asarray(crust_age, dtype=np.uint32)
        if vx is not None:
            vx = np.asarray(vx, dtype=np.float64)
        if vy is not None:
            vy = np.asarray(vy, dtype=np.float64)
        if speed is not None:
            speed = np.asarray(speed, dtype=np.float64)
        if reporter is not None:
            reporter.progress("tectonics_seam", 1.0)
            reporter.stage_complete("tectonics_seam")

    gap_after = seam_edge_elevation_gap(elevation)
    diagnostics = build_tectonics_diagnostics(
        elevation=elevation,
        plate_id=plate_id,
        seam_column=seam_column,
        seam_gap_before=gap_before,
        seam_gap_after=gap_after,
        seed=seed,
        steps=raw.steps,
    )
    diagnostics["metadata_source"] = raw.metadata_source
    diagnostics["platec_capabilities"] = raw.capabilities
    diagnostics["velocity_plate_count_snapshot"] = len(raw.plate_unit_velocity)

    result = TectonicsExtendedResult(
        elevation_raw=elevation,
        plate_id=plate_id,
        extent=extent,
        seed=int(seed),
        seam_column=int(seam_column),
        steps=int(raw.steps),
        diagnostics=diagnostics,
        params=params,
        crust_age=crust_age,
        plate_velocity_x=vx,
        plate_velocity_y=vy,
        plate_speed=speed,
        metadata_source=raw.metadata_source,
        plate_unit_velocity=dict(raw.plate_unit_velocity),
        plate_speeds=dict(raw.plate_speeds),
    )
    if reporter is not None:
        reporter.stage_complete("tectonics")
    return result
