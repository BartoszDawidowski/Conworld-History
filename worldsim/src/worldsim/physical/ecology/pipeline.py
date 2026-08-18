"""Milestone 14 — soils + Holdridge ecology orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.pipeline import (
    ClimateResult,
    climate_grid_land_elevation,
    downsample_mean,
)
from worldsim.physical.ecology.biome_v2 import (
    CLASS_NAMES,
    BiomeV2Class,
    classify_biome_v2,
)
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
    soil_moisture_growing_mean: NDArray[np.float64] | None = None
    thermal_regime_id: NDArray[np.uint8] | None = None
    moisture_regime_id: NDArray[np.uint8] | None = None

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
                "soil_moisture_growing_mean": self.soil_moisture_growing_mean,
                "thermal_regime_id": self.thermal_regime_id,
                "moisture_regime_id": self.moisture_regime_id,
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


def _to_climate_2d(
    arr: NDArray[np.floating],
    width: int,
    height: int,
) -> NDArray[np.float64]:
    src = np.asarray(arr, dtype=np.float64)
    if src.shape == (height, width):
        return src
    if src.shape[0] >= height and src.shape[1] >= width:
        return downsample_mean(src, width, height)
    return upsample_bilinear_cylindrical(src, width, height)


def _to_climate_monthly(
    arr: NDArray[np.floating],
    width: int,
    height: int,
) -> NDArray[np.float64]:
    src = np.asarray(arr, dtype=np.float64)
    if src.ndim != 3:
        raise ValueError("monthly field must be [months, y, x]")
    if src.shape[1:] == (height, width):
        return src
    return np.stack(
        [_to_climate_2d(src[m], width, height) for m in range(src.shape[0])],
        axis=0,
    )


def climate_liquid_lake_mask(
    hydrology: HydrologyResult | None,
    width: int,
    height: int,
    *,
    min_fraction: float = 0.05,
) -> NDArray[np.bool_]:
    """Holdridge/soil lake override from actual liquid fraction, not basin envelope."""
    if hydrology is None:
        return np.zeros((height, width), dtype=bool)
    frac = getattr(hydrology, "water_fraction_mean", None)
    if frac is not None and np.asarray(frac).size:
        frac_c = _to_climate_2d(np.asarray(frac, dtype=np.float64), width, height)
        return frac_c >= float(min_fraction)
    mask = np.asarray(getattr(hydrology, "lake_mask", np.zeros((0,))), dtype=bool)
    if mask.size == 0:
        return np.zeros((height, width), dtype=bool)
    from worldsim.physical.climate.pipeline import downsample_mode_bool

    if mask.shape == (height, width):
        return mask
    return downsample_mode_bool(mask, width, height)


def climatological_soil_monthly(
    moisture: MoistureResult,
    hydrology: HydrologyResult | None,
    width: int,
    height: int,
) -> NDArray[np.float64] | None:
    """Periodic monthly soil wetness in [0, 1]. Never a single last-month snapshot."""
    store = getattr(moisture, "land_store", None)
    cap_raw = (moisture.diagnostics or {}).get("land_store_capacity")
    cap = 8.0 if cap_raw is None else float(cap_raw)
    if (
        store is not None
        and np.asarray(store).ndim == 3
        and np.asarray(store).size
        and cap > 0.0
    ):
        arr = _to_climate_monthly(np.asarray(store, dtype=np.float64), width, height)
        return np.clip(arr / cap, 0.0, 1.0)
    if hydrology is None:
        return None
    monthly = getattr(hydrology, "soil_store_monthly", None)
    hydro_cap_raw = (hydrology.diagnostics or {}).get("soil_capacity", 1.0)
    hydro_cap = 1.0 if hydro_cap_raw is None else float(hydro_cap_raw)
    if (
        monthly is not None
        and np.asarray(monthly).ndim == 3
        and np.asarray(monthly).size
        and hydro_cap > 0.0
    ):
        arr = _to_climate_monthly(np.asarray(monthly, dtype=np.float64), width, height)
        return np.clip(arr / hydro_cap, 0.0, 1.0)
    return None


def biome_v2_acceptance(
    *,
    klass: NDArray[np.integer],
    ocean: NDArray[np.bool_],
    frost_months: NDArray[np.floating],
    growing_months: NDArray[np.floating],
    water_deficit_mm: NDArray[np.floating],
    soil_gs: NDArray[np.floating],
    legend: dict[str, str],
) -> dict[str, Any]:
    ocean_b = np.asarray(ocean, dtype=bool)
    finite = bool(
        np.all(np.isfinite(water_deficit_mm))
        and np.all(np.isfinite(frost_months))
        and np.all(np.isfinite(growing_months))
        and np.all(np.isfinite(soil_gs))
    )
    ids = {int(v) for v in np.unique(klass)}
    coverage = bool(ids.issubset(set(CLASS_NAMES)))
    expected_legend = {str(i): CLASS_NAMES[i] for i in range(len(CLASS_NAMES))}
    legend_exact = legend == expected_legend
    ocean_ok = bool(np.all(klass[ocean_b] == int(BiomeV2Class.OCEAN))) if np.any(ocean_b) else True
    land = ~ocean_b
    land_ok = bool(np.all(klass[land] != int(BiomeV2Class.OCEAN))) if np.any(land) else True
    all_classified = bool(np.all((klass >= 0) & (klass <= int(BiomeV2Class.WETLAND))))
    ok = bool(finite and coverage and legend_exact and ocean_ok and land_ok and all_classified)
    return {
        "biome_v2_finite": finite,
        "biome_v2_coverage_ok": coverage,
        "biome_v2_legend_exact": legend_exact,
        "biome_v2_ocean_mask_ok": ocean_ok,
        "biome_v2_land_not_ocean": land_ok,
        "biome_v2_all_classified": all_classified,
        "biome_v2_ok": ok,
    }


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
        src = np.asarray(elevation_terrain_m, dtype=np.float64)
        if hydrology is not None and hydrology.ocean_mask.shape == src.shape:
            terrain_ocean = hydrology.ocean_mask
        else:
            terrain_ocean = src < 0.0
        elev = climate_grid_land_elevation(
            src,
            terrain_ocean,
            w,
            h,
            climate_ocean_mask=ocean,
            ocean_elevation_m=climate.elevation_m,
        )
    else:
        elev = climate.elevation_m

    # Liquid fraction on the climate grid — never the topographic basin envelope.
    lake_mask = climate_liquid_lake_mask(hydrology, w, h)

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
        monthly_p = _to_climate_monthly(monthly_p, w, h)
    soil_m = climatological_soil_monthly(moisture, hydrology, w, h)
    if soil_m is not None:
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
    holdridge_ok = bool(all_defined and land_ok and ocean_ok)
    biome_acc = biome_v2_acceptance(
        klass=biome["biome_v2_class"],
        ocean=ocean,
        frost_months=biome["frost_months"],
        growing_months=biome["growing_season_months"],
        water_deficit_mm=biome["water_deficit_mm"],
        soil_gs=biome["soil_moisture_growing_mean"],
        legend=biome["diagnostics"]["class_names"],
    )

    unique, counts = np.unique(zones, return_counts=True)
    zone_counts = {str(int(z)): int(c) for z, c in zip(unique, counts)}
    lake_from_fraction = bool(
        hydrology is not None
        and getattr(hydrology, "water_fraction_mean", None) is not None
        and np.asarray(hydrology.water_fraction_mean).size
    )

    diagnostics: dict[str, Any] = {
        "width": w,
        "height": h,
        "all_cells_classified": holdridge_ok,
        "land_valid_or_override": land_ok,
        "ocean_override_ok": ocean_ok,
        "biotemperature_min_c": float(np.min(biotemp)),
        "biotemperature_max_c": float(np.max(biotemp)),
        "pet_ratio_min": float(np.min(ratio[land])) if np.any(land) else float("nan"),
        "pet_ratio_max": float(np.max(ratio[land])) if np.any(land) else float("nan"),
        "zone_counts": zone_counts,
        "precip_scale_mm": params.precip_scale_mm,
        "holdridge_role": "annual_diagnostic",
        "lake_override_source": "water_fraction_mean" if lake_from_fraction else "liquid_mask",
        **biome["diagnostics"],
        **biome_acc,
        "climate_land_elev_min_m": float(np.min(elev[land])) if np.any(land) else 0.0,
        "acceptance_ok": bool(holdridge_ok and biome_acc["biome_v2_ok"]),
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
        soil_moisture_growing_mean=biome["soil_moisture_growing_mean"],
        thermal_regime_id=biome["thermal_regime_id"],
        moisture_regime_id=biome["moisture_regime_id"],
        diagnostics=diagnostics,
    )
