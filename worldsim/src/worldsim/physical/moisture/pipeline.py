"""Milestone 9 — moisture / precipitation orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.atmosphere.pipeline import AtmosphereResult
from worldsim.physical.atmosphere.monsoon import apply_monsoon_wind_anomaly
from worldsim.physical.climate.pipeline import ClimateResult
from worldsim.physical.moisture.transport import build_monthly_moisture
from worldsim.physical.ocean.pipeline import OceanResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent


@dataclass(frozen=True)
class MoistureParams:
    months: int = 12
    advect_steps: int = 32
    advect_wind_scale: float = 0.2
    large_scale_frac: float = 0.15
    orographic_frac: float = 0.85
    convective_scale: float = 2.0
    ocean_evap_rate: float = 1.4
    lake_evap_rate: float = 0.75
    river_evap_rate: float = 0.40
    land_et_rate: float = 0.4
    continentality_dry: float = 0.4
    lee_dry: float = 0.12
    diffusion_mix_per_month: float = 0.08
    spinup_max_years: int = 4
    spinup_tolerance_relative: float = 0.02
    spinup_tolerance_absolute: float = 1e-3
    # PR-7 / revised B8
    plume_strength: float = 0.18
    land_store_capacity: float = 8.0
    itcz_convective_scale: float = 1.2
    itcz_width_deg: float = 8.0
    # PR-8 / revised B9 — monsoon transport
    monsoon_strength: float = 0.4
    monsoon_lat_band_min_abs_deg: float = 5.0
    monsoon_lat_band_max_abs_deg: float = 32.0
    monsoon_max_anomaly_ms: float = 3.5
    monsoon_coast_reach_cells: float = 10.0
    monsoon_temp_scale_c: float = 8.0


@dataclass
class MoistureResult:
    extent: SpatialExtent
    atmospheric_moisture: NDArray[np.float64]
    evaporation: NDArray[np.float64]
    precipitation: NDArray[np.float64]
    humidity: NDArray[np.float64]
    orographic_lift: NDArray[np.float64]
    convective_precip: NDArray[np.float64]
    annual_precipitation: NDArray[np.float64]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "moisture.npz",
            atmospheric_moisture=self.atmospheric_moisture,
            evaporation=self.evaporation,
            precipitation=self.precipitation,
            humidity=self.humidity,
            orographic_lift=self.orographic_lift,
            convective_precip=self.convective_precip,
            annual_precipitation=self.annual_precipitation,
        )
        (directory / "moisture_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _moisture_diagnostics(
    *,
    precipitation: NDArray[np.float64],
    atmospheric_moisture: NDArray[np.float64],
    evaporation: NDArray[np.float64],
    orographic_lift: NDArray[np.float64],
    wind_u: NDArray[np.float64],
    ocean_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.float64],
    latitude_deg: NDArray[np.float64],
) -> dict[str, Any]:
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    land = ~ocean
    june = 5
    annual = precipitation.sum(axis=0)

    # Downwind moisture: ocean cells should evaporate more than deep interior land
    evap_ocean = float(evaporation[june][ocean].mean()) if np.any(ocean) else 0.0
    if np.any(land):
        # high continentality proxy: far from coast via elev land interior
        interior = land & (elevation_m > np.nanpercentile(elevation_m[land], 40))
        if not np.any(interior):
            interior = land
        moisture_interior = float(atmospheric_moisture[june][interior].mean())
        moisture_ocean = float(atmospheric_moisture[june][ocean].mean())
    else:
        moisture_interior = moisture_ocean = float("nan")
    downwind_ok = bool(
        evap_ocean > 0.0 and moisture_ocean >= moisture_interior * 0.85
    )

    # Windward / leeward on significant terrain
    high = elevation_m > (np.nanpercentile(elevation_m, 75) if np.any(land) else 500.0)
    high &= land
    lift = orographic_lift[june]
    windward = high & (lift > 0.15)
    leeward = high & (lift < -0.15)
    precip_w = precip_l = float("nan")
    windward_leeward_ok = True
    if np.count_nonzero(windward) >= 5 and np.count_nonzero(leeward) >= 5:
        precip_w = float(precipitation[june][windward].mean())
        precip_l = float(precipitation[june][leeward].mean())
        windward_leeward_ok = precip_w > precip_l * 1.05

    # Earth-like wet/dry: tropics wetter than subtropical dry band (annual)
    trop = (np.abs(latitude_deg) < 12.0) & land
    subtrop = (np.abs(latitude_deg) > 18.0) & (np.abs(latitude_deg) < 32.0) & land
    trop_p = subt_p = float("nan")
    wet_dry_ok = True
    if np.count_nonzero(trop) >= 5 and np.count_nonzero(subtrop) >= 5:
        trop_p = float(annual[trop].mean())
        subt_p = float(annual[subtrop].mean())
        wet_dry_ok = trop_p > subt_p * 1.02
    elif np.any(ocean):
        # Fallback: equatorial precip > subtropical ocean precip
        trop_o = np.abs(latitude_deg) < 10.0
        subt_o = (np.abs(latitude_deg) > 20.0) & (np.abs(latitude_deg) < 35.0)
        trop_p = float(annual[trop_o].mean())
        subt_p = float(annual[subt_o].mean())
        wet_dry_ok = trop_p > subt_p * 1.02

    # Moisture should vary downwind of mean easterlies in tropics (zonal gradient)
    # Simple coherence: precipitation not pure noise (zonal std moderate)
    lon_std = float(np.mean(np.std(precipitation[june], axis=1)))
    coherent = lon_std < float(np.mean(precipitation[june]) + 1.0) * 3.0

    heuristic_ok = bool(
        downwind_ok and windward_leeward_ok and wet_dry_ok and coherent
    )
    return {
        "downwind_moisture_transport_ok": downwind_ok,
        "evaporation_ocean_june": evap_ocean,
        "moisture_ocean_june": moisture_ocean,
        "moisture_interior_june": moisture_interior,
        "windward_leeward_ok": windward_leeward_ok,
        "precip_windward_june": precip_w,
        "precip_leeward_june": precip_l,
        "earth_like_wet_dry_ok": wet_dry_ok,
        "annual_precip_tropics": trop_p,
        "annual_precip_subtropics": subt_p,
        "precipitation_min": float(np.min(precipitation)),
        "precipitation_max": float(np.max(precipitation)),
        "annual_precip_mean": float(np.mean(annual)),
        "coherent_fields": coherent,
        "heuristic_fields_ok": heuristic_ok,
        # CR-1: acceptance_ok filled after budget merge (requires spinup_converged).
        "acceptance_ok": heuristic_ok,
    }


def build_moisture(
    *,
    climate: ClimateResult,
    atmosphere: AtmosphereResult,
    ocean: OceanResult | None = None,
    params: MoistureParams | None = None,
    lake_mask: NDArray[np.bool_] | None = None,
    river_mask: NDArray[np.bool_] | None = None,
    reporter: ProgressReporter | None = None,
) -> MoistureResult:
    params = params or MoistureParams()
    if reporter is not None:
        reporter.stage_started("moisture")
        reporter.progress("moisture", 0.1)

    months = min(
        params.months,
        climate.temperature_c.shape[0],
        atmosphere.wind_u.shape[0],
    )
    temp = (
        ocean.temperature_coupled_c[:months]
        if ocean is not None
        else climate.temperature_c[:months]
    )
    sst = ocean.sst_c[:months] if ocean is not None else None

    wind_u = np.asarray(atmosphere.wind_u[:months], dtype=np.float64)
    wind_v = np.asarray(atmosphere.wind_v[:months], dtype=np.float64)
    monsoon_diag: dict[str, Any] = {"b9_terms_active": False, "monsoon_strength": 0.0}
    if (
        ocean is not None
        and sst is not None
        and float(params.monsoon_strength) > 0.0
    ):
        wind_u, wind_v, monsoon_diag = apply_monsoon_wind_anomaly(
            wind_u,
            wind_v,
            land_temperature_c=temp,
            sst_c=sst,
            ocean_mask=climate.ocean_mask,
            latitude_deg=climate.latitude_deg,
            strength=params.monsoon_strength,
            lat_band_min_abs_deg=params.monsoon_lat_band_min_abs_deg,
            lat_band_max_abs_deg=params.monsoon_lat_band_max_abs_deg,
            max_anomaly_ms=params.monsoon_max_anomaly_ms,
            coast_reach_cells=params.monsoon_coast_reach_cells,
            temp_scale_c=params.monsoon_temp_scale_c,
        )

    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wind_u,
        wind_v=wind_v,
        elevation_m=climate.elevation_m,
        ocean_mask=climate.ocean_mask,
        latitude_deg=climate.latitude_deg,
        sst_c=sst,
        continentality=climate.continentality,
        lake_mask=lake_mask,
        river_mask=river_mask,
        months=months,
        advect_steps=params.advect_steps,
        advect_wind_scale=params.advect_wind_scale,
        diffusion_mix_per_month=params.diffusion_mix_per_month,
        large_scale_frac=params.large_scale_frac,
        orographic_frac=params.orographic_frac,
        convective_scale=params.convective_scale,
        ocean_evap_rate=params.ocean_evap_rate,
        lake_evap_rate=params.lake_evap_rate,
        river_evap_rate=params.river_evap_rate,
        land_et_rate=params.land_et_rate,
        continentality_dry=params.continentality_dry,
        lee_dry=params.lee_dry,
        spinup_max_years=params.spinup_max_years,
        spinup_tolerance_relative=params.spinup_tolerance_relative,
        spinup_tolerance_absolute=params.spinup_tolerance_absolute,
        plume_strength=params.plume_strength,
        land_store_capacity=params.land_store_capacity,
        itcz_latitude_deg=atmosphere.itcz_latitude_deg[:months],
        itcz_convective_scale=params.itcz_convective_scale,
        itcz_width_deg=params.itcz_width_deg,
    )

    if reporter is not None:
        reporter.progress("moisture", 0.75)

    annual = fields["precipitation"].sum(axis=0)
    diagnostics = _moisture_diagnostics(
        precipitation=fields["precipitation"],
        atmospheric_moisture=fields["atmospheric_moisture"],
        evaporation=fields["evaporation"],
        orographic_lift=fields["orographic_lift"],
        wind_u=wind_u,
        ocean_mask=climate.ocean_mask,
        elevation_m=climate.elevation_m,
        latitude_deg=climate.latitude_deg,
    )
    diagnostics.update(
        {
            "width": climate.extent.width,
            "height": climate.extent.height,
            "months": months,
            "advect_steps": params.advect_steps,
            "advect_wind_scale": params.advect_wind_scale,
            "large_scale_frac": params.large_scale_frac,
            "orographic_frac": params.orographic_frac,
            "convective_scale": params.convective_scale,
            "ocean_evap_rate": params.ocean_evap_rate,
            "lake_evap_rate": params.lake_evap_rate,
            "river_evap_rate": params.river_evap_rate,
            "land_et_rate": params.land_et_rate,
            "continentality_dry": params.continentality_dry,
            "lee_dry": params.lee_dry,
            "diffusion_mix_per_month": params.diffusion_mix_per_month,
            "spinup_max_years": params.spinup_max_years,
            "plume_strength": params.plume_strength,
            "land_store_capacity": params.land_store_capacity,
            "itcz_convective_scale": params.itcz_convective_scale,
            "itcz_width_deg": params.itcz_width_deg,
            "b8_terms_active": bool(
                params.plume_strength > 0.0
                or params.land_store_capacity > 0.0
                or params.itcz_convective_scale > 0.0
            ),
            "monsoon_strength": params.monsoon_strength,
            "monsoon_lat_band_min_abs_deg": params.monsoon_lat_band_min_abs_deg,
            "monsoon_lat_band_max_abs_deg": params.monsoon_lat_band_max_abs_deg,
            **monsoon_diag,
            "inland_water_sources": bool(
                lake_mask is not None or river_mask is not None
            ),
            "lake_cell_count": int(np.count_nonzero(lake_mask))
            if lake_mask is not None
            else 0,
            "river_cell_count": int(np.count_nonzero(river_mask))
            if river_mask is not None
            else 0,
            "moisture_role": (
                "moisture_ecology" if lake_mask is not None or river_mask is not None
                else "moisture_hydrology_input"
            ),
            **(fields["budget"] if isinstance(fields.get("budget"), dict) else {}),
        }
    )
    # CR-1: hard gate is periodic spin-up convergence. Spatial heuristics remain
    # reported (`heuristic_fields_ok`) but are not sufficient alone; land-store
    # closure stays a CR-3 gate (F-04).
    spinup_ok = bool(diagnostics.get("spinup_converged", False))
    heuristic_ok = bool(diagnostics.get("heuristic_fields_ok", False))
    diagnostics["acceptance_ok"] = bool(spinup_ok)
    diagnostics["acceptance_requires_spinup"] = True
    diagnostics["heuristic_fields_ok"] = heuristic_ok
    diagnostics["land_store_closure_gated"] = False

    if reporter is not None:
        reporter.progress("moisture", 1.0)
        reporter.stage_complete("moisture")

    return MoistureResult(
        extent=climate.extent,
        atmospheric_moisture=fields["atmospheric_moisture"],
        evaporation=fields["evaporation"],
        precipitation=fields["precipitation"],
        humidity=fields["humidity"],
        orographic_lift=fields["orographic_lift"],
        convective_precip=fields["convective_precip"],
        annual_precipitation=annual,
        diagnostics=diagnostics,
    )
