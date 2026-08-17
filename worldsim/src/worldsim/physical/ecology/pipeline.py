"""Milestone 14 — soils + Holdridge ecology orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.pipeline import ClimateResult, downsample_mean
from worldsim.physical.ecology.biome_v2 import classify_biome_v2
from worldsim.physical.ecology.biotemperature import (
    annual_biotemperature_c,
    holdridge_pet_mm,
    pet_ratio,
)
from worldsim.physical.ecology.holdridge import (
    HoldridgeOverride,
    build_zone_legend,
    classify_holdridge,
)
from worldsim.physical.ecology.soils import build_soil_layers
from worldsim.physical.hydrology.pipeline import HydrologyResult
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.resample import upsample_bilinear_cylindrical


@dataclass(frozen=True)
class EcologyParams:
    precip_scale_mm: float = 200.0
    alpine_elev_m: float = 3500.0


@dataclass
class EcologyResult:
    extent: SpatialExtent
    permeability: NDArray[np.float64]
    soil_depth: NDArray[np.float64]
    soil_moisture: NDArray[np.float64]
    fertility_proxy: NDArray[np.float64]
    erosion_risk: NDArray[np.float64]
    biotemperature_c: NDArray[np.float64]
    pet_mm: NDArray[np.float64]
    pet_ratio: NDArray[np.float64]
    holdridge_zone_id: NDArray[np.int16]
    ecology_override: NDArray[np.int16]
    diagnostics: dict[str, Any]
    frost_months: NDArray[np.int16] | None = None
    growing_season_months: NDArray[np.int16] | None = None
    water_deficit_mm: NDArray[np.float64] | None = None
    soil_state: NDArray[np.uint8] | None = None
    biome_v2_class: NDArray[np.uint8] | None = None

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "ecology.npz",
            permeability=self.permeability,
            soil_depth=self.soil_depth,
            soil_moisture=self.soil_moisture,
            fertility_proxy=self.fertility_proxy,
            erosion_risk=self.erosion_risk,
            biotemperature_c=self.biotemperature_c,
            pet_mm=self.pet_mm,
            pet_ratio=self.pet_ratio,
            holdridge_zone_id=self.holdridge_zone_id,
            ecology_override=self.ecology_override,
        )
        if self.biome_v2_class is not None:
            extra = {
                "frost_months": self.frost_months,
                "growing_season_months": self.growing_season_months,
                "water_deficit_mm": self.water_deficit_mm,
                "soil_state": self.soil_state,
                "biome_v2_class": self.biome_v2_class,
            }
            np.savez_compressed(
                directory / "biome_v2.npz",
                **{k: v for k, v in extra.items() if v is not None},
            )
        (directory / "holdridge_zone_legend.json").write_text(
            json.dumps(build_zone_legend(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (directory / "ecology_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_ecology(
    *,
    climate: ClimateResult,
    moisture: MoistureResult,
    hydrology: HydrologyResult | None = None,
    elevation_terrain_m: NDArray[np.floating] | None = None,
    params: EcologyParams | None = None,
    reporter: ProgressReporter | None = None,
) -> EcologyResult:
    params = params or EcologyParams()
    if reporter is not None:
        reporter.stage_started("ecology")
        reporter.progress("ecology", 0.1)

    ocean = climate.ocean_mask
    h, w = ocean.shape

    # Elevation on climate grid (prefer downsampled DEM v2 if provided)
    if elevation_terrain_m is not None:
        elev = downsample_mean(
            np.asarray(elevation_terrain_m, dtype=np.float64), w, h
        )
        elev = np.where(ocean, climate.elevation_m, elev)
    else:
        elev = climate.elevation_m

    # Lake mask on climate grid
    lake_mask = np.zeros((h, w), dtype=bool)
    if hydrology is not None:
        lake_t = hydrology.lake_mask
        # mode downsample
        from worldsim.physical.climate.pipeline import downsample_mode_bool

        lake_mask = downsample_mode_bool(lake_t, w, h)

    annual_precip = moisture.annual_precipitation
    if annual_precip.shape != (h, w):
        annual_precip = upsample_bilinear_cylindrical(annual_precip, w, h)

    soils = build_soil_layers(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precipitation=annual_precip,
        lake_mask=lake_mask,
    )

    if reporter is not None:
        reporter.progress("ecology", 0.4)

    biotemp = annual_biotemperature_c(climate.temperature_c)
    pet = holdridge_pet_mm(biotemp)
    ratio = pet_ratio(
        biotemperature_c=biotemp,
        annual_precipitation=annual_precip,
        precip_scale_mm=params.precip_scale_mm,
    )
    zones, override = classify_holdridge(
        biotemperature_c=biotemp,
        pet_ratio_field=ratio,
        ocean_mask=ocean,
        elevation_m=elev,
        lake_mask=lake_mask,
        alpine_elev_m=params.alpine_elev_m,
    )

    monthly_p = moisture.precipitation
    if monthly_p.ndim == 3 and monthly_p.shape[1:] != (h, w):
        monthly_p = np.stack(
            [upsample_bilinear_cylindrical(monthly_p[m], w, h) for m in range(monthly_p.shape[0])],
            axis=0,
        )
    soil_m = soils["soil_moisture"]
    if hydrology is not None and getattr(hydrology, "soil_store", None) is not None:
        store = np.asarray(hydrology.soil_store, dtype=np.float64)
        if store.size and store.ndim == 2:
            if store.shape != (h, w):
                store = downsample_mean(store, w, h)
            cap = float(getattr(hydrology, "diagnostics", {}).get("soil_capacity", 1.0) or 1.0)
            soil_m = np.clip(store / max(cap, 1e-6), 0.0, 1.0)
            soil_m = np.where(ocean, 0.0, soil_m)
    biome = classify_biome_v2(
        temperature_c=climate.temperature_c[: monthly_p.shape[0]],
        precipitation=monthly_p,
        ocean_mask=ocean,
        soil_moisture=soil_m,
        precip_scale_mm=params.precip_scale_mm,
    )

    if reporter is not None:
        reporter.progress("ecology", 0.85)

    land = ~ocean
    # Acceptance: every cell has a defined zone id; land cells are either
    # life-zone (≥10) or explicit override (lake/ice/alpine).
    all_defined = bool(np.all(zones >= 0))
    land_ok = True
    if np.any(land):
        land_zones = zones[land]
        land_ok = bool(
            np.all(
                (land_zones >= 10)
                | np.isin(
                    land_zones,
                    [
                        int(HoldridgeOverride.LAKE),
                        int(HoldridgeOverride.ICE),
                        int(HoldridgeOverride.ALPINE_BARE),
                    ],
                )
            )
        )
    ocean_ok = bool(np.all(zones[ocean] == int(HoldridgeOverride.OCEAN))) if np.any(ocean) else True

    unique, counts = np.unique(zones, return_counts=True)
    zone_counts = {str(int(z)): int(c) for z, c in zip(unique, counts)}

    diagnostics: dict[str, Any] = {
        "width": w,
        "height": h,
        "all_cells_classified": all_defined and land_ok and ocean_ok,
        "land_valid_or_override": land_ok,
        "ocean_override_ok": ocean_ok,
        "biotemperature_min_c": float(np.min(biotemp)),
        "biotemperature_max_c": float(np.max(biotemp)),
        "pet_ratio_min": float(np.min(ratio[land])) if np.any(land) else float("nan"),
        "pet_ratio_max": float(np.max(ratio[land])) if np.any(land) else float("nan"),
        "zone_counts": zone_counts,
        "precip_scale_mm": params.precip_scale_mm,
        "holdridge_role": "annual_diagnostic",
        **biome["diagnostics"],
        "acceptance_ok": bool(all_defined and land_ok and ocean_ok),
    }

    if reporter is not None:
        reporter.progress("ecology", 1.0)
        reporter.stage_complete("ecology")

    return EcologyResult(
        extent=climate.extent,
        permeability=soils["permeability"],
        soil_depth=soils["soil_depth"],
        soil_moisture=soils["soil_moisture"],
        fertility_proxy=soils["fertility_proxy"],
        erosion_risk=soils["erosion_risk"],
        biotemperature_c=biotemp,
        pet_mm=pet,
        pet_ratio=ratio,
        holdridge_zone_id=zones,
        ecology_override=override,
        frost_months=biome["frost_months"],
        growing_season_months=biome["growing_season_months"],
        water_deficit_mm=biome["water_deficit_mm"],
        soil_state=biome["soil_state"],
        biome_v2_class=biome["biome_v2_class"],
        diagnostics=diagnostics,
    )
