"""Low-level platec simulation runner shared by Milestone 2/3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.params import PyPlatecParams
from worldsim.physical.tectonics.capabilities import (
    PlatecCapabilities,
    detect_platec_capabilities,
)

ProgressCallback = Callable[[float], None]


@dataclass
class PlatecRawOutput:
    elevation: NDArray[np.float64]
    plate_id: NDArray[np.int32]
    steps: int
    crust_age: NDArray[np.uint32] | None = None
    plate_velocity_x: NDArray[np.float64] | None = None
    plate_velocity_y: NDArray[np.float64] | None = None
    plate_speed: NDArray[np.float64] | None = None
    plate_unit_velocity: dict[int, tuple[float, float]] = field(default_factory=dict)
    plate_speeds: dict[int, float] = field(default_factory=dict)
    metadata_source: str = "baseline"
    capabilities: dict[str, Any] = field(default_factory=dict)


def _snapshot_plate_motion(platec: Any, handle: Any) -> tuple[dict[int, tuple[float, float]], dict[int, float]]:
    count = int(platec.get_plate_count(handle))
    unit: dict[int, tuple[float, float]] = {}
    speeds: dict[int, float] = {}
    for index in range(count):
        ux, uy = platec.get_plate_velocity(handle, index)
        unit[index] = (float(ux), float(uy))
        speeds[index] = float(platec.get_plate_speed(handle, index))
    return unit, speeds


def _paint_velocity_fields(
    plate_id: NDArray[np.int32],
    unit: dict[int, tuple[float, float]],
    speeds: dict[int, float],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    height, width = plate_id.shape
    vx = np.zeros((height, width), dtype=np.float64)
    vy = np.zeros((height, width), dtype=np.float64)
    speed = np.zeros((height, width), dtype=np.float64)
    for index, (ux, uy) in unit.items():
        mask = plate_id == index
        if not np.any(mask):
            continue
        sp = float(speeds.get(index, 0.0))
        vx[mask] = ux * sp
        vy[mask] = uy * sp
        speed[mask] = sp
    return vx, vy, speed


def run_platec_simulation(
    *,
    seed: int,
    width: int,
    height: int,
    params: PyPlatecParams,
    on_progress: ProgressCallback | None = None,
    prefer_extended: bool = True,
) -> PlatecRawOutput:
    """Run platec and optionally capture age/velocity (Milestone 3)."""
    caps = detect_platec_capabilities()
    platec = caps.module

    handle = platec.create(
        int(seed),
        int(width),
        int(height),
        float(params.sea_level),
        int(params.erosion_period),
        float(params.folding_ratio),
        int(params.aggr_overlap_abs),
        float(params.aggr_overlap_rel),
        int(params.cycle_count),
        int(params.num_plates),
    )
    steps = 0
    last_unit: dict[int, tuple[float, float]] = {}
    last_speeds: dict[int, float] = {}
    try:
        while platec.is_finished(handle) == 0:
            if prefer_extended and caps.supports_extended_metadata:
                # Plate objects are destroyed when the run finishes; snapshot
                # motion while plates still exist.
                unit, speeds = _snapshot_plate_motion(platec, handle)
                if unit:
                    last_unit, last_speeds = unit, speeds
            platec.step(handle)
            steps += 1
            if on_progress is not None and steps % 25 == 0:
                on_progress(min(0.95, 1.0 - 1.0 / (1.0 + steps / 200.0)))

        heightmap = np.asarray(platec.get_heightmap(handle), dtype=np.float64)
        plates = np.asarray(platec.get_platesmap(handle), dtype=np.int32)
        crust_age = None
        if prefer_extended and caps.has_agemap:
            crust_age = np.asarray(platec.get_agemap(handle), dtype=np.uint32)
    finally:
        platec.destroy(handle)

    expected = width * height
    if heightmap.size != expected or plates.size != expected:
        raise RuntimeError(
            f"unexpected platec buffer size: heightmap={heightmap.size}, "
            f"plates={plates.size}, expected={expected}"
        )
    if crust_age is not None and crust_age.size != expected:
        raise RuntimeError(f"unexpected agemap size: {crust_age.size}, expected={expected}")

    elevation = heightmap.reshape((height, width))
    plate_id = plates.reshape((height, width))
    age = None if crust_age is None else crust_age.reshape((height, width))

    vx = vy = speed = None
    metadata_source = "baseline"
    if prefer_extended and caps.supports_extended_metadata and last_unit:
        vx, vy, speed = _paint_velocity_fields(plate_id, last_unit, last_speeds)
        metadata_source = "native_extended"
    elif prefer_extended:
        # Stable fallback object shape for downstream consumers.
        age = np.zeros((height, width), dtype=np.uint32) if age is None else age
        vx = np.zeros((height, width), dtype=np.float64)
        vy = np.zeros((height, width), dtype=np.float64)
        speed = np.zeros((height, width), dtype=np.float64)
        metadata_source = "fallback_inferred_zero"

    if on_progress is not None:
        on_progress(1.0)

    return PlatecRawOutput(
        elevation=elevation,
        plate_id=plate_id,
        steps=steps,
        crust_age=age,
        plate_velocity_x=vx,
        plate_velocity_y=vy,
        plate_speed=speed,
        plate_unit_velocity=last_unit,
        plate_speeds=last_speeds,
        metadata_source=metadata_source,
        capabilities={
            "has_agemap": caps.has_agemap,
            "has_plate_count": caps.has_plate_count,
            "has_plate_velocity": caps.has_plate_velocity,
            "has_plate_speed": caps.has_plate_speed,
            "module_file": caps.source,
            "supports_extended_metadata": caps.supports_extended_metadata,
        },
    )
