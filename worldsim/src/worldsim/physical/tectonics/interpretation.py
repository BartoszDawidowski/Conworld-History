"""Stage B — tectonic interpretation from plate maps + velocities.

Derives boundaries, normals, relative motion, classes, and activity proxies
from Milestone 3 extended tectonics outputs (architecture §19).

Classification uses relative velocity projected onto the boundary normal/tangent.
Labels are never random.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.tectonics.baseline import TectonicsExtendedResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent


class BoundaryType(IntEnum):
    NONE = 0
    WEAK_INACTIVE = 1
    DIVERGENT = 2
    CONVERGENT = 3
    TRANSFORM = 4
    OBLIQUE_DIVERGENT = 5
    OBLIQUE_CONVERGENT = 6


BOUNDARY_TYPE_NAMES: dict[int, str] = {
    int(BoundaryType.NONE): "none",
    int(BoundaryType.WEAK_INACTIVE): "weak/inactive",
    int(BoundaryType.DIVERGENT): "divergent",
    int(BoundaryType.CONVERGENT): "convergent",
    int(BoundaryType.TRANSFORM): "transform",
    int(BoundaryType.OBLIQUE_DIVERGENT): "oblique_divergent",
    int(BoundaryType.OBLIQUE_CONVERGENT): "oblique_convergent",
}


@dataclass(frozen=True)
class InterpretationParams:
    weak_speed: float = 1e-4
    transform_normal_fraction: float = 0.35
    oblique_tangent_fraction: float = 0.35
    influence_length_cells: float = 8.0
    ocean_percentile: float = 40.0


@dataclass
class TectonicsInterpretationResult:
    extent: SpatialExtent
    boundary_mask: NDArray[np.bool_]
    boundary_plate_a: NDArray[np.int32]
    boundary_plate_b: NDArray[np.int32]
    distance_to_boundary: NDArray[np.float64]
    boundary_normal_x: NDArray[np.float64]
    boundary_normal_y: NDArray[np.float64]
    relative_velocity_x: NDArray[np.float64]
    relative_velocity_y: NDArray[np.float64]
    relative_velocity_normal: NDArray[np.float64]
    relative_velocity_tangent: NDArray[np.float64]
    boundary_type: NDArray[np.int16]
    tectonic_activity: NDArray[np.float64]
    convergence_strength: NDArray[np.float64]
    divergence_strength: NDArray[np.float64]
    transform_strength: NDArray[np.float64]
    subduction_potential: NDArray[np.float64]
    orogenic_potential: NDArray[np.float64]
    volcanic_potential: NDArray[np.float64]
    earthquake_potential: NDArray[np.float64]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "tectonics_interpretation.npz",
            boundary_mask=self.boundary_mask.astype(np.uint8),
            boundary_plate_a=self.boundary_plate_a,
            boundary_plate_b=self.boundary_plate_b,
            distance_to_boundary=self.distance_to_boundary,
            boundary_normal_x=self.boundary_normal_x,
            boundary_normal_y=self.boundary_normal_y,
            relative_velocity_x=self.relative_velocity_x,
            relative_velocity_y=self.relative_velocity_y,
            relative_velocity_normal=self.relative_velocity_normal,
            relative_velocity_tangent=self.relative_velocity_tangent,
            boundary_type=self.boundary_type,
            tectonic_activity=self.tectonic_activity,
            convergence_strength=self.convergence_strength,
            divergence_strength=self.divergence_strength,
            transform_strength=self.transform_strength,
            subduction_potential=self.subduction_potential,
            orogenic_potential=self.orogenic_potential,
            volcanic_potential=self.volcanic_potential,
            earthquake_potential=self.earthquake_potential,
        )
        (directory / "tectonics_interpretation_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "boundary_type_legend.json").write_text(
            json.dumps(BOUNDARY_TYPE_NAMES, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def cylindrical_distance_to_mask(
    mask: NDArray[np.bool_],
) -> tuple[NDArray[np.float64], NDArray[np.int32], NDArray[np.int32]]:
    """BFS distance transform with E–W wrap; returns dist and nearest (i,j)."""
    height, width = mask.shape
    dist = np.full((height, width), np.inf, dtype=np.float64)
    nearest_i = np.full((height, width), -1, dtype=np.int32)
    nearest_j = np.full((height, width), -1, dtype=np.int32)
    queue: deque[tuple[int, int]] = deque()

    js, is_ = np.nonzero(mask)
    for j, i in zip(js.tolist(), is_.tolist(), strict=False):
        dist[j, i] = 0.0
        nearest_i[j, i] = i
        nearest_j[j, i] = j
        queue.append((i, j))

    while queue:
        i, j = queue.popleft()
        d0 = dist[j, i]
        candidates = (
            ((i + 1) % width, j),
            ((i - 1) % width, j),
        )
        if j + 1 < height:
            candidates = (*candidates, (i, j + 1))
        if j - 1 >= 0:
            candidates = (*candidates, (i, j - 1))
        for ni, nj in candidates:
            nd = d0 + 1.0
            if nd < dist[nj, ni]:
                dist[nj, ni] = nd
                nearest_i[nj, ni] = nearest_i[j, i]
                nearest_j[nj, ni] = nearest_j[j, i]
                queue.append((ni, nj))

    return dist, nearest_i, nearest_j


def classify_boundary(
    vn: float,
    vt: float,
    *,
    params: InterpretationParams,
) -> BoundaryType:
    speed = math.hypot(vn, vt)
    if speed < params.weak_speed:
        return BoundaryType.WEAK_INACTIVE
    normal_frac = abs(vn) / speed
    tangent_frac = abs(vt) / speed
    if normal_frac < params.transform_normal_fraction:
        return BoundaryType.TRANSFORM
    if vn > 0.0:
        if tangent_frac > params.oblique_tangent_fraction:
            return BoundaryType.OBLIQUE_DIVERGENT
        return BoundaryType.DIVERGENT
    if tangent_frac > params.oblique_tangent_fraction:
        return BoundaryType.OBLIQUE_CONVERGENT
    return BoundaryType.CONVERGENT


def _shift_ew(arr: NDArray, di: int) -> NDArray:
    return np.roll(arr, shift=-di, axis=1)


def _shift_ns(arr: NDArray, dj: int) -> NDArray:
    """Shift so ``out[j] = arr[j + dj]`` with polar edge clamp (no N–S wrap)."""
    if dj == 0:
        return arr
    out = np.empty_like(arr)
    if dj > 0:
        out[:-dj, :] = arr[dj:, :]
        out[-dj:, :] = arr[-1:, :]
    else:
        out[-dj:, :] = arr[:dj, :]
        out[:-dj, :] = arr[:1, :]
    return out


def interpret_tectonics(
    *,
    plate_id: NDArray[np.integer],
    elevation: NDArray[np.floating],
    plate_velocity_x: NDArray[np.floating],
    plate_velocity_y: NDArray[np.floating],
    params: InterpretationParams | None = None,
) -> TectonicsInterpretationResult:
    """Derive Stage B fields from plate id + velocity rasters."""
    params = params or InterpretationParams()
    plate_id = np.asarray(plate_id, dtype=np.int32)
    elevation = np.asarray(elevation, dtype=np.float64)
    vx = np.asarray(plate_velocity_x, dtype=np.float64)
    vy = np.asarray(plate_velocity_y, dtype=np.float64)
    if plate_id.shape != elevation.shape or plate_id.shape != vx.shape or plate_id.shape != vy.shape:
        raise ValueError("plate_id, elevation, and velocity rasters must share shape")

    height, width = plate_id.shape
    extent = SpatialExtent.from_shape(width, height)

    # Neighbour plate ids and velocities (E–W wrap; N–S clamped).
    neigh = {
        "e": (_shift_ew(plate_id, 1), _shift_ew(vx, 1), _shift_ew(vy, 1), _shift_ew(elevation, 1), 1.0, 0.0),
        "w": (_shift_ew(plate_id, -1), _shift_ew(vx, -1), _shift_ew(vy, -1), _shift_ew(elevation, -1), -1.0, 0.0),
        "s": (_shift_ns(plate_id, 1), _shift_ns(vx, 1), _shift_ns(vy, 1), _shift_ns(elevation, 1), 0.0, 1.0),
        "n": (_shift_ns(plate_id, -1), _shift_ns(vx, -1), _shift_ns(vy, -1), _shift_ns(elevation, -1), 0.0, -1.0),
    }

    # Deterministic partner = minimum foreign plate id among 4-neighbours.
    partner_ids = [
        np.where(pid_n != plate_id, pid_n, np.iinfo(np.int32).max)
        for _name, (pid_n, _vx_n, _vy_n, _elev_n, _dx, _dy) in neigh.items()
    ]
    partner = np.minimum.reduce(partner_ids)
    boundary_mask = partner < np.iinfo(np.int32).max

    # Build normal/partner velocity from matching neighbour direction(s).
    normal_x = np.zeros((height, width), dtype=np.float64)
    normal_y = np.zeros((height, width), dtype=np.float64)
    partner_vx = vx.copy()
    partner_vy = vy.copy()
    partner_elev = elevation.copy()
    for _name, (pid_n, vx_n, vy_n, elev_n, dx, dy) in neigh.items():
        match = boundary_mask & (pid_n == partner)
        normal_x = np.where(match, normal_x + dx, normal_x)
        normal_y = np.where(match, normal_y + dy, normal_y)
        partner_vx = np.where(match, vx_n, partner_vx)
        partner_vy = np.where(match, vy_n, partner_vy)
        partner_elev = np.where(match, elev_n, partner_elev)
        other = boundary_mask & (pid_n != plate_id) & (pid_n != partner)
        normal_x = np.where(other, normal_x + dx, normal_x)
        normal_y = np.where(other, normal_y + dy, normal_y)

    norm = np.hypot(normal_x, normal_y)
    # Fallback eastward normal if degenerate.
    degenerate = boundary_mask & (norm < 1e-12)
    normal_x = np.where(degenerate, 1.0, normal_x)
    normal_y = np.where(degenerate, 0.0, normal_y)
    norm = np.hypot(normal_x, normal_y)
    normal_x = np.where(boundary_mask, normal_x / np.maximum(norm, 1e-12), 0.0)
    normal_y = np.where(boundary_mask, normal_y / np.maximum(norm, 1e-12), 0.0)
    tangent_x = -normal_y
    tangent_y = normal_x

    rel_vx = np.where(boundary_mask, partner_vx - vx, 0.0)
    rel_vy = np.where(boundary_mask, partner_vy - vy, 0.0)
    rel_vn = rel_vx * normal_x + rel_vy * normal_y
    rel_vt = rel_vx * tangent_x + rel_vy * tangent_y

    plate_a = np.where(boundary_mask, plate_id, -1).astype(np.int32)
    plate_b = np.where(boundary_mask, partner, -1).astype(np.int32)

    # Vectorized classification.
    speed = np.hypot(rel_vn, rel_vt)
    btype = np.zeros((height, width), dtype=np.int16)
    weak = boundary_mask & (speed < params.weak_speed)
    strong = boundary_mask & ~weak
    normal_frac = np.zeros_like(speed)
    tangent_frac = np.zeros_like(speed)
    np.divide(np.abs(rel_vn), speed, out=normal_frac, where=strong)
    np.divide(np.abs(rel_vt), speed, out=tangent_frac, where=strong)

    transform = strong & (normal_frac < params.transform_normal_fraction)
    divergent = strong & ~transform & (rel_vn > 0.0)
    convergent = strong & ~transform & (rel_vn <= 0.0)
    obl_div = divergent & (tangent_frac > params.oblique_tangent_fraction)
    obl_conv = convergent & (tangent_frac > params.oblique_tangent_fraction)
    pure_div = divergent & ~obl_div
    pure_conv = convergent & ~obl_conv

    btype[weak] = int(BoundaryType.WEAK_INACTIVE)
    btype[transform] = int(BoundaryType.TRANSFORM)
    btype[pure_div] = int(BoundaryType.DIVERGENT)
    btype[pure_conv] = int(BoundaryType.CONVERGENT)
    btype[obl_div] = int(BoundaryType.OBLIQUE_DIVERGENT)
    btype[obl_conv] = int(BoundaryType.OBLIQUE_CONVERGENT)

    ocean_threshold = float(np.percentile(elevation, params.ocean_percentile))
    oceanic_a = elevation <= ocean_threshold
    oceanic_b = partner_elev <= ocean_threshold

    seed_activity = np.where(boundary_mask, speed, 0.0)
    seed_conv = np.where(boundary_mask, np.maximum(0.0, -rel_vn), 0.0)
    seed_div = np.where(boundary_mask, np.maximum(0.0, rel_vn), 0.0)
    seed_trans = np.where(boundary_mask, np.abs(rel_vt), 0.0)
    seed_subduction = seed_conv * np.where(oceanic_a | oceanic_b, 1.0, 0.25)
    seed_orogeny = seed_conv * np.where((~oceanic_a) & (~oceanic_b), 1.0, 0.25)
    seed_subduction = np.where(boundary_mask, seed_subduction, 0.0)
    seed_orogeny = np.where(boundary_mask, seed_orogeny, 0.0)

    type_counts = {int(t): int(np.sum(btype == int(t))) for t in BoundaryType}

    dist, nearest_i, nearest_j = cylindrical_distance_to_mask(boundary_mask)
    if not np.any(boundary_mask):
        dist[:] = float(max(width, height))
        zeros = np.zeros((height, width), dtype=np.float64)
        return TectonicsInterpretationResult(
            extent=extent,
            boundary_mask=boundary_mask,
            boundary_plate_a=plate_a,
            boundary_plate_b=plate_b,
            distance_to_boundary=dist,
            boundary_normal_x=normal_x,
            boundary_normal_y=normal_y,
            relative_velocity_x=rel_vx,
            relative_velocity_y=rel_vy,
            relative_velocity_normal=rel_vn,
            relative_velocity_tangent=rel_vt,
            boundary_type=btype,
            tectonic_activity=zeros,
            convergence_strength=zeros,
            divergence_strength=zeros,
            transform_strength=zeros,
            subduction_potential=zeros,
            orogenic_potential=zeros,
            volcanic_potential=zeros,
            earthquake_potential=zeros,
            diagnostics={
                "boundary_cell_count": 0,
                "boundary_type_counts": type_counts,
                "ocean_threshold": ocean_threshold,
                "warning": "no plate boundaries detected",
            },
        )

    length = max(params.influence_length_cells, 1e-6)
    decay = np.exp(-np.minimum(dist, 1e6) / length)

    def _propagate(seed: NDArray[np.float64]) -> NDArray[np.float64]:
        values = seed[nearest_j, nearest_i]
        out = values * decay
        out[nearest_i < 0] = 0.0
        return out

    activity = _propagate(seed_activity)
    convergence = _propagate(seed_conv)
    divergence = _propagate(seed_div)
    transform_f = _propagate(seed_trans)
    subduction = _propagate(seed_subduction)
    orogeny = _propagate(seed_orogeny)
    volcanic = subduction + 0.5 * divergence
    earthquake = activity * (1.0 + 0.5 * (transform_f + convergence))

    diagnostics = {
        "boundary_cell_count": int(boundary_mask.sum()),
        "boundary_fraction": float(boundary_mask.mean()),
        "boundary_type_counts": {
            BOUNDARY_TYPE_NAMES[k]: int(v)
            for k, v in type_counts.items()
            if k != int(BoundaryType.NONE)
        },
        "ocean_threshold": ocean_threshold,
        "mean_distance_to_boundary": float(np.mean(dist[np.isfinite(dist)])),
        "max_tectonic_activity": float(np.max(activity)),
        "correlation_checks": _correlation_diagnostics(
            elevation=elevation,
            convergence=convergence,
            divergence=divergence,
            transform=transform_f,
            boundary_mask=boundary_mask,
            rel_vn=rel_vn,
        ),
    }

    return TectonicsInterpretationResult(
        extent=extent,
        boundary_mask=boundary_mask,
        boundary_plate_a=plate_a,
        boundary_plate_b=plate_b,
        distance_to_boundary=dist,
        boundary_normal_x=normal_x,
        boundary_normal_y=normal_y,
        relative_velocity_x=rel_vx,
        relative_velocity_y=rel_vy,
        relative_velocity_normal=rel_vn,
        relative_velocity_tangent=rel_vt,
        boundary_type=btype,
        tectonic_activity=activity,
        convergence_strength=convergence,
        divergence_strength=divergence,
        transform_strength=transform_f,
        subduction_potential=subduction,
        orogenic_potential=orogeny,
        volcanic_potential=volcanic,
        earthquake_potential=earthquake,
        diagnostics=diagnostics,
    )


def _correlation_diagnostics(
    *,
    elevation: NDArray[np.float64],
    convergence: NDArray[np.float64],
    divergence: NDArray[np.float64],
    transform: NDArray[np.float64],
    boundary_mask: NDArray[np.bool_],
    rel_vn: NDArray[np.float64],
) -> dict[str, Any]:
    if not np.any(boundary_mask):
        return {"ok": False, "reason": "no_boundaries"}

    conv_cells = boundary_mask & (rel_vn < 0.0)
    div_cells = boundary_mask & (rel_vn > 0.0)
    out: dict[str, Any] = {"ok": True}
    if np.any(conv_cells) and np.any(div_cells):
        out["mean_elevation_convergent_boundary"] = float(elevation[conv_cells].mean())
        out["mean_elevation_divergent_boundary"] = float(elevation[div_cells].mean())
        out["convergent_vs_divergent_elevation_delta"] = (
            out["mean_elevation_convergent_boundary"]
            - out["mean_elevation_divergent_boundary"]
        )
    interior = ~boundary_mask
    out["activity_concentrated_near_boundaries"] = bool(
        float(convergence[boundary_mask].mean())
        >= float(convergence[interior].mean() if np.any(interior) else 0.0)
    )
    out["transform_nonnegative"] = bool(np.all(transform >= -1e-12))
    out["divergence_nonnegative"] = bool(np.all(divergence >= -1e-12))
    return out


def run_tectonic_interpretation(
    tectonics: TectonicsExtendedResult,
    *,
    params: InterpretationParams | None = None,
    reporter: ProgressReporter | None = None,
) -> TectonicsInterpretationResult:
    if reporter is not None:
        reporter.stage_started("tectonics_interpretation")
        reporter.progress("tectonics_interpretation", 0.1)

    if tectonics.plate_velocity_x is None or tectonics.plate_velocity_y is None:
        raise RuntimeError(
            "tectonic interpretation requires plate_velocity_x/y from Milestone 3"
        )

    result = interpret_tectonics(
        plate_id=tectonics.plate_id,
        elevation=tectonics.elevation_raw,
        plate_velocity_x=tectonics.plate_velocity_x,
        plate_velocity_y=tectonics.plate_velocity_y,
        params=params,
    )
    if reporter is not None:
        reporter.progress("tectonics_interpretation", 1.0)
        reporter.stage_complete("tectonics_interpretation")
    return result
