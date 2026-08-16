"""Milestone 8 — ocean circulation orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.pipeline import AtmosphereResult
from worldsim.physical.climate.pipeline import ClimateResult, replace_climate_temperature
from worldsim.physical.ocean.currents import build_monthly_currents
from worldsim.physical.ocean.sst import (
    build_monthly_sst,
    couple_temperature_with_sst_inland,
)
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import EARTH_RADIUS_KM, grid_metrics
from worldsim.spatial.units_migration import resolve_planet_lengths


@dataclass(frozen=True)
class OceanParams:
    months: int = 12
    sst_mix: float = 0.4
    inland_decay_cells: float = 60.0
    inland_decay_km: float | None = None
    western_boundary_width_km: float | None = None
    western_boundary_width_cells: int = 3
    western_warm_c: float = 2.2
    eastern_cool_c: float = 1.8
    planet_radius_km: float = EARTH_RADIUS_KM


@dataclass
class OceanResult:
    extent: SpatialExtent
    current_u: NDArray[np.float64]
    current_v: NDArray[np.float64]
    sst_c: NDArray[np.float64]
    temperature_coupled_c: NDArray[np.float64]
    ocean_basin_id: NDArray[np.int32]
    western_boundary: NDArray[np.bool_]
    eastern_boundary: NDArray[np.bool_]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "ocean_circulation.npz",
            current_u=self.current_u,
            current_v=self.current_v,
            sst_c=self.sst_c,
            temperature_coupled_c=self.temperature_coupled_c,
            ocean_basin_id=self.ocean_basin_id,
            western_boundary=self.western_boundary.astype(np.uint8),
            eastern_boundary=self.eastern_boundary.astype(np.uint8),
        )
        (directory / "ocean_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _resolve_ocean_lengths(params: OceanParams) -> tuple[float, float]:
    """Return ``(inland_decay_km, western_boundary_width_km)``."""
    if params.inland_decay_km is not None and params.western_boundary_width_km is not None:
        return float(params.inland_decay_km), float(params.western_boundary_width_km)
    effective = resolve_planet_lengths(
        {
            "ocean": {
                **(
                    {"sst_inland_decay_km": params.inland_decay_km}
                    if params.inland_decay_km is not None
                    else {}
                ),
                **(
                    {"western_boundary_width_km": params.western_boundary_width_km}
                    if params.western_boundary_width_km is not None
                    else {}
                ),
            }
        },
        inland_decay_cells=params.inland_decay_cells,
        western_boundary_width_cells=float(params.western_boundary_width_cells),
        radius_km=params.planet_radius_km,
    )
    return (
        float(effective.resolved["sst_inland_decay_km"].value_km),
        float(effective.resolved["western_boundary_width_km"].value_km),
    )


def _ocean_diagnostics(
    *,
    current_u: NDArray[np.float64],
    current_v: NDArray[np.float64],
    sst_c: NDArray[np.float64],
    ocean_mask: NDArray[np.bool_],
    western: NDArray[np.bool_],
    eastern: NDArray[np.bool_],
    latitude_deg: NDArray[np.float64],
    basin_id: NDArray[np.int32],
) -> dict[str, Any]:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    speed = np.hypot(current_u, current_v)

    land_speed_max = float(speed[:, land].max()) if np.any(land) else 0.0
    no_land_crossing = land_speed_max < 1e-12

    june = 5
    eq = (np.abs(latitude_deg) < 8.0) & ocean
    equatorial_u = (
        float(current_u[june][eq].mean()) if np.any(eq) else float("nan")
    )
    equatorial_westward = bool(equatorial_u < 0.0) if np.any(eq) else False

    ocean_speed_mean = float(speed[june][ocean].mean()) if np.any(ocean) else 0.0
    coherent = ocean_speed_mean > 0.05 and no_land_crossing

    sst_land_nan = bool(np.all(np.isnan(sst_c[:, land]))) if np.any(land) else True
    sst_ocean_finite = (
        bool(np.all(np.isfinite(sst_c[:, ocean]))) if np.any(ocean) else False
    )

    subtrop = (np.abs(latitude_deg) > 15.0) & (np.abs(latitude_deg) < 40.0) & ocean
    w_mask = western & subtrop
    e_mask = eastern & subtrop
    western_warmer = True
    mean_sst_w = mean_sst_e = float("nan")
    if np.any(w_mask) and np.any(e_mask):
        mean_sst_w = float(np.nanmean(sst_c[june][w_mask]))
        mean_sst_e = float(np.nanmean(sst_c[june][e_mask]))
        western_warmer = mean_sst_w > mean_sst_e

    basin_count = int(len(np.unique(basin_id[basin_id > 0])))

    return {
        "no_land_crossing": no_land_crossing,
        "land_current_speed_max": land_speed_max,
        "equatorial_westward": equatorial_westward,
        "equatorial_u_june": equatorial_u,
        "ocean_speed_mean_june": ocean_speed_mean,
        "coherent_circulation": coherent,
        "sst_land_is_nan": sst_land_nan,
        "sst_ocean_finite": sst_ocean_finite,
        "western_boundary_warmer_than_eastern": western_warmer,
        "mean_sst_western_subtrop_june": mean_sst_w,
        "mean_sst_eastern_subtrop_june": mean_sst_e,
        "basin_count": basin_count,
        "western_boundary_cells": int(np.count_nonzero(western)),
        "eastern_boundary_cells": int(np.count_nonzero(eastern)),
        "acceptance_ok": bool(
            no_land_crossing
            and coherent
            and sst_land_nan
            and sst_ocean_finite
            and equatorial_westward
        ),
    }


def apply_ocean_temperature_to_climate(
    climate: ClimateResult,
    ocean: OceanResult,
) -> ClimateResult:
    """B1: copy coupled SST/inland temperatures into climate for ecology / atlas."""
    months = min(climate.temperature_c.shape[0], ocean.temperature_coupled_c.shape[0])
    temp = np.asarray(climate.temperature_c, dtype=np.float64).copy()
    temp[:months] = np.asarray(ocean.temperature_coupled_c[:months], dtype=np.float64)
    diag = dict(climate.diagnostics)
    prior = int(diag.get("sst_apply_count", 0) or 0)
    diag["ocean_temperature_applied"] = True
    diag["ocean_inland_decay_cells"] = ocean.diagnostics.get("inland_decay_cells")
    diag["ocean_inland_decay_km"] = ocean.diagnostics.get("inland_decay_km")
    diag["ocean_land_temp_delta_mean_abs"] = ocean.diagnostics.get(
        "land_temp_delta_mean_abs"
    )
    diag["sst_apply_count"] = prior + 1
    diag["temperature_state"] = "temperature_sst_coupled_c"
    diag["sst_owner"] = "ocean_coupling"
    return replace_climate_temperature(climate, temp, diagnostics=diag)


def build_ocean_circulation(
    *,
    climate: ClimateResult,
    atmosphere: AtmosphereResult,
    params: OceanParams | None = None,
    reporter: ProgressReporter | None = None,
) -> OceanResult:
    params = params or OceanParams()
    if reporter is not None:
        reporter.stage_started("ocean")
        reporter.progress("ocean", 0.1)

    months = min(
        params.months, atmosphere.wind_u.shape[0], climate.temperature_c.shape[0]
    )
    h, w = climate.ocean_mask.shape
    metrics = grid_metrics(w, h, radius_km=params.planet_radius_km)
    inland_km, boundary_km = _resolve_ocean_lengths(params)

    fields = build_monthly_currents(
        wind_u=atmosphere.wind_u[:months],
        wind_v=atmosphere.wind_v[:months],
        latitude_deg=climate.latitude_deg,
        ocean_mask=climate.ocean_mask,
        elevation_m=climate.elevation_m,
        months=months,
        boundary_width_km=boundary_km,
        metrics=metrics,
        planet_radius_km=params.planet_radius_km,
    )

    if reporter is not None:
        reporter.progress("ocean", 0.45)

    sst = build_monthly_sst(
        temperature_c=climate.temperature_c[:months],
        current_u=fields["current_u"],
        current_v=fields["current_v"],
        ocean_mask=climate.ocean_mask,
        western=fields["western_boundary"],
        eastern=fields["eastern_boundary"],
        latitude_deg=climate.latitude_deg,
        western_warm_c=params.western_warm_c,
        eastern_cool_c=params.eastern_cool_c,
        metrics=metrics,
        planet_radius_km=params.planet_radius_km,
    )

    if reporter is not None:
        reporter.progress("ocean", 0.7)

    base_temp = np.asarray(climate.temperature_c[:months], dtype=np.float64).copy()
    coupled, couple_diag = couple_temperature_with_sst_inland(
        temperature_c=base_temp,
        sst_c=sst,
        ocean_mask=climate.ocean_mask,
        mix=params.sst_mix,
        inland_decay_cells=None,
        inland_decay_km=inland_km,
        metrics=metrics,
    )
    # Do not mutate climate here — final recalculation applies writeback once so
    # climate_v1 stays the pre-ocean base for DEM lapse (avoids double-coupling).

    diagnostics = _ocean_diagnostics(
        current_u=fields["current_u"],
        current_v=fields["current_v"],
        sst_c=sst,
        ocean_mask=climate.ocean_mask,
        western=fields["western_boundary"],
        eastern=fields["eastern_boundary"],
        latitude_deg=climate.latitude_deg,
        basin_id=fields["ocean_basin_id"],
    )
    land = ~climate.ocean_mask
    delta = coupled - base_temp
    diagnostics.update(
        {
            "width": climate.extent.width,
            "height": climate.extent.height,
            "months": months,
            "coupled_temp_delta_mean_abs": float(np.mean(np.abs(delta))),
            "climate_temperature_writeback": False,
            "western_boundary_width_km": boundary_km,
            "sst_gradients": "metric_v1",
            "temperature_state": "temperature_sst_coupled_c",
            **couple_diag,
            "inland_decay_cells": float(params.inland_decay_cells),
            "inland_decay_km": inland_km,
        }
    )
    # Western vs eastern land contrast near subtropical coasts (biome diversity signal)
    lat = climate.latitude_deg
    june = min(5, months - 1)
    west_ocean = fields["western_boundary"]
    east_ocean = fields["eastern_boundary"]
    near_west = land & (
        np.roll(west_ocean, 1, axis=1)
        | np.roll(west_ocean, -1, axis=1)
        | np.concatenate(
            [west_ocean[1:, :], np.zeros_like(west_ocean[:1, :])], axis=0
        )
        | np.concatenate(
            [np.zeros_like(west_ocean[:1, :]), west_ocean[:-1, :]], axis=0
        )
    )
    near_east = land & (
        np.roll(east_ocean, 1, axis=1)
        | np.roll(east_ocean, -1, axis=1)
        | np.concatenate(
            [east_ocean[1:, :], np.zeros_like(east_ocean[:1, :])], axis=0
        )
        | np.concatenate(
            [np.zeros_like(east_ocean[:1, :]), east_ocean[:-1, :]], axis=0
        )
    )
    near_west = near_west & (np.abs(lat) > 15.0) & (np.abs(lat) < 40.0)
    near_east = near_east & (np.abs(lat) > 15.0) & (np.abs(lat) < 40.0)
    if np.any(near_west) and np.any(near_east):
        diagnostics["mean_land_temp_near_western_june"] = float(
            coupled[june][near_west].mean()
        )
        diagnostics["mean_land_temp_near_eastern_june"] = float(
            coupled[june][near_east].mean()
        )
        diagnostics["western_coast_land_warmer_than_eastern"] = bool(
            diagnostics["mean_land_temp_near_western_june"]
            > diagnostics["mean_land_temp_near_eastern_june"]
        )

    if reporter is not None:
        reporter.progress("ocean", 1.0)
        reporter.stage_complete("ocean")

    return OceanResult(
        extent=climate.extent,
        current_u=fields["current_u"],
        current_v=fields["current_v"],
        sst_c=sst,
        temperature_coupled_c=coupled,
        ocean_basin_id=fields["ocean_basin_id"],
        western_boundary=fields["western_boundary"],
        eastern_boundary=fields["eastern_boundary"],
        diagnostics=diagnostics,
    )
