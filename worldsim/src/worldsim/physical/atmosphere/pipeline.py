"""Milestone 7 — atmospheric circulation orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.circulation import (
    ZONE_NAMES,
    CirculationZone,
    build_monthly_atmosphere,
)
from worldsim.physical.climate.pipeline import ClimateResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent


@dataclass(frozen=True)
class AtmosphereParams:
    axial_tilt_deg: float = 23.44
    months: int = 12


@dataclass
class AtmosphereResult:
    extent: SpatialExtent
    pressure_proxy: NDArray[np.float64]
    wind_u: NDArray[np.float64]
    wind_v: NDArray[np.float64]
    circulation_zone: NDArray[np.int16]
    itcz_latitude_deg: NDArray[np.float64]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "atmosphere.npz",
            pressure_proxy=self.pressure_proxy,
            wind_u=self.wind_u,
            wind_v=self.wind_v,
            circulation_zone=self.circulation_zone,
            itcz_latitude_deg=self.itcz_latitude_deg,
        )
        (directory / "atmosphere_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "circulation_zone_legend.json").write_text(
            json.dumps(ZONE_NAMES, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _zonal_tendency_diagnostics(
    *,
    latitude_deg: NDArray[np.float64],
    wind_u: NDArray[np.float64],
    wind_v: NDArray[np.float64],
    circulation_zone: NDArray[np.int16],
    itcz: NDArray[np.float64],
) -> dict[str, Any]:
    """Check expected zonal tendencies (trades easterly, Ferrel westerly, …)."""
    # Use June (5) and December (11) for seasonal ITCZ shift.
    june, december = 5, 11
    lat = latitude_deg

    def mean_u(month: int, mask: NDArray[np.bool_]) -> float:
        if not np.any(mask):
            return float("nan")
        return float(wind_u[month][mask].mean())

    # Hadley / trades near equator relative to annual-mean ITCZ≈0 for annual check;
    # use month-local zones.
    hadley_j = circulation_zone[june] == int(CirculationZone.HADLEY)
    ferrel_j = circulation_zone[june] == int(CirculationZone.FERREL)
    polar_j = circulation_zone[june] == int(CirculationZone.POLAR)

    trades_easterly = mean_u(june, hadley_j) < 0.0
    ferrel_westerly = mean_u(june, ferrel_j) > 0.0
    polar_easterly = mean_u(june, polar_j) < 0.0

    # ITCZ migrates: June north of December
    itcz_migrates = float(itcz[june]) > float(itcz[december])

    # Coherence: wind field should vary smoothly in longitude (low zonal std
    # relative to magnitude for base zonal flow).
    speed = np.hypot(wind_u, wind_v)
    lon_std = float(np.mean(np.std(wind_u[june], axis=1)))
    coherent = lon_std < 3.0  # topo adds some, but not random arrows

    # Meridional Hadley: mean v should point toward ITCZ in Hadley belt.
    if np.any(hadley_j):
        toward = -np.sign(lat - float(itcz[june]))
        v_hadley = wind_v[june][hadley_j]
        t_hadley = toward[hadley_j]
        hadley_meridional_ok = float(np.mean(v_hadley * t_hadley)) > 0.0
    else:
        hadley_meridional_ok = False

    return {
        "trades_easterly": trades_easterly,
        "ferrel_westerly": ferrel_westerly,
        "polar_easterly": polar_easterly,
        "itcz_migrates_nh_summer_north": itcz_migrates,
        "itcz_june_deg": float(itcz[june]),
        "itcz_december_deg": float(itcz[december]),
        "mean_u_hadley_june": mean_u(june, hadley_j),
        "mean_u_ferrel_june": mean_u(june, ferrel_j),
        "mean_u_polar_june": mean_u(june, polar_j),
        "hadley_meridional_toward_itcz": hadley_meridional_ok,
        "zonal_coherence_ok": coherent,
        "june_wind_speed_mean": float(speed[june].mean()),
        "expected_zonal_tendencies_ok": bool(
            trades_easterly and ferrel_westerly and polar_easterly and itcz_migrates
        ),
    }


def build_atmosphere(
    *,
    climate: ClimateResult,
    params: AtmosphereParams | None = None,
    reporter: ProgressReporter | None = None,
) -> AtmosphereResult:
    params = params or AtmosphereParams()
    if reporter is not None:
        reporter.stage_started("atmosphere")
        reporter.progress("atmosphere", 0.15)

    lat_rad = np.radians(climate.latitude_deg)
    fields = build_monthly_atmosphere(
        latitude_deg=climate.latitude_deg,
        latitude_rad=lat_rad,
        elevation_m=climate.elevation_m,
        axial_tilt_deg=params.axial_tilt_deg,
        months=params.months,
    )

    if reporter is not None:
        reporter.progress("atmosphere", 0.75)

    zonal = _zonal_tendency_diagnostics(
        latitude_deg=climate.latitude_deg,
        wind_u=fields["wind_u"],
        wind_v=fields["wind_v"],
        circulation_zone=fields["circulation_zone"],
        itcz=fields["itcz_latitude_deg"],
    )

    # Zone occupancy (June)
    june_zones = fields["circulation_zone"][5]
    zone_counts = {
        ZONE_NAMES[int(z)]: int(np.sum(june_zones == int(z)))
        for z in CirculationZone
        if int(z) != 0
    }

    diagnostics: dict[str, Any] = {
        "width": climate.extent.width,
        "height": climate.extent.height,
        "months": params.months,
        "axial_tilt_deg": params.axial_tilt_deg,
        "june_zone_counts": zone_counts,
        "pressure_min": float(np.min(fields["pressure_proxy"])),
        "pressure_max": float(np.max(fields["pressure_proxy"])),
        **zonal,
    }

    if reporter is not None:
        reporter.progress("atmosphere", 1.0)
        reporter.stage_complete("atmosphere")

    return AtmosphereResult(
        extent=climate.extent,
        pressure_proxy=fields["pressure_proxy"],
        wind_u=fields["wind_u"],
        wind_v=fields["wind_v"],
        circulation_zone=fields["circulation_zone"],
        itcz_latitude_deg=fields["itcz_latitude_deg"],
        diagnostics=diagnostics,
    )
