"""Milestone 6 — base seasonal climate (insolation + temperature)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.insolation import monthly_insolation_field
from worldsim.physical.climate.temperature import (
    TEMPERATURE_STATE_BASE,
    TEMPERATURE_STATE_EQUILIBRIUM,
    build_monthly_temperature_c,
    temperature_diagnostics,
)
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.coordinates import y_to_lat
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import EARTH_RADIUS_KM, grid_metrics
from worldsim.spatial.units_migration import resolve_planet_lengths


@dataclass(frozen=True)
class ClimateParams:
    width: int
    height: int
    months: int = 12
    axial_tilt_deg: float = 23.44
    lapse_rate_c_per_km: float = 6.5
    base_temp_c: float = 15.0
    continentality_scale_km: float | None = None
    continentality_scale_cells: float = 24.0
    planet_radius_km: float = EARTH_RADIUS_KM
    continental_seasonality_gain: float = 0.0


@dataclass
class ClimateResult:
    extent: SpatialExtent
    latitude_deg: NDArray[np.float64]
    insolation: NDArray[np.float64]  # [12, y, x]
    temperature_c: NDArray[np.float64]  # [12, y, x] — current surface T
    continentality: NDArray[np.float64]
    elevation_m: NDArray[np.float64]
    ocean_mask: NDArray[np.bool_]
    diagnostics: dict[str, Any]
    # PR-3 named states / subgrid contract (optional for older callers)
    temperature_equilibrium_c: NDArray[np.float64] | None = None
    temperature_base_c: NDArray[np.float64] | None = None
    elev_p10_m: NDArray[np.float64] | None = None
    elev_p90_m: NDArray[np.float64] | None = None
    elev_ridge_m: NDArray[np.float64] | None = None
    elev_slope_rms: NDArray[np.float64] | None = None

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, NDArray] = {
            "latitude_deg": self.latitude_deg,
            "insolation": self.insolation,
            "temperature_c": self.temperature_c,
            "continentality": self.continentality,
            "elevation_m": self.elevation_m,
            "ocean_mask": self.ocean_mask.astype(np.uint8),
        }
        if self.temperature_equilibrium_c is not None:
            payload["temperature_equilibrium_c"] = self.temperature_equilibrium_c
        if self.temperature_base_c is not None:
            payload["temperature_base_c"] = self.temperature_base_c
        if self.elev_p10_m is not None:
            payload["elev_p10_m"] = self.elev_p10_m
        if self.elev_p90_m is not None:
            payload["elev_p90_m"] = self.elev_p90_m
        if self.elev_ridge_m is not None:
            payload["elev_ridge_m"] = self.elev_ridge_m
        if self.elev_slope_rms is not None:
            payload["elev_slope_rms"] = self.elev_slope_rms
        np.savez_compressed(directory / "climate_base.npz", **payload)
        (directory / "climate_diagnostics.json").write_text(
            json.dumps(self.diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def latitude_grid(height: int, width: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Cell-centre latitude degrees and radians for equal-area cylindrical grid."""
    extent = SpatialExtent.from_shape(width, height)
    lat_deg = np.empty((height, width), dtype=np.float64)
    for j in range(height):
        _x, y = extent.cell_center_xy(0, j)
        lat = y_to_lat(y)
        lat_deg[j, :] = lat
    lat_rad = np.radians(lat_deg)
    return lat_deg, lat_rad


def downsample_mean(
    source: NDArray[np.floating],
    out_width: int,
    out_height: int,
) -> NDArray[np.float64]:
    """Area-average downsample (box filter) without E–W seam special casing."""
    src = np.asarray(source, dtype=np.float64)
    # Upsample path already exists; for downsampling use reshape block means when divisible.
    in_h, in_w = src.shape
    if in_h % out_height == 0 and in_w % out_width == 0:
        by = in_h // out_height
        bx = in_w // out_width
        return src.reshape(out_height, by, out_width, bx).mean(axis=(1, 3))
    # Fallback: sample via bilinear at climate centres from a normalised view.
    # Invert by treating climate as destination of upsample from climate→terrain
    # is wrong; use simple stride-nearest after slight blur via upsample of tiny.
    ys = ((np.arange(out_height) + 0.5) * in_h / out_height).astype(np.int64)
    xs = ((np.arange(out_width) + 0.5) * in_w / out_width).astype(np.int64)
    ys = np.clip(ys, 0, in_h - 1)
    xs = np.clip(xs, 0, in_w - 1)
    # Local mean in a window around each sample.
    out = np.empty((out_height, out_width), dtype=np.float64)
    ry = max(1, in_h // out_height // 2)
    rx = max(1, in_w // out_width // 2)
    for j, y in enumerate(ys):
        y0, y1 = max(0, y - ry), min(in_h, y + ry + 1)
        for i, x in enumerate(xs):
            x0, x1 = max(0, x - rx), min(in_w, x + rx + 1)
            out[j, i] = float(src[y0:y1, x0:x1].mean())
    return out


def downsample_land_elevation_mean(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    out_width: int,
    out_height: int,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Downsample DEM using land-only means so coasts are not mixed with bathymetry.

    Ocean coarse cells keep the mean of fine ocean elevations. Land coarse cells
    average only fine land elevations (CR-2 / F-13 mask hygiene).
    """
    elev = np.asarray(elevation_m, dtype=np.float64)
    ocean = np.asarray(ocean_mask, dtype=bool)
    in_h, in_w = elev.shape
    ocean_out = downsample_mean(ocean.astype(np.float64), out_width, out_height) >= 0.5
    out = np.empty((out_height, out_width), dtype=np.float64)

    if in_h % out_height == 0 and in_w % out_width == 0:
        by = in_h // out_height
        bx = in_w // out_width
        e_blocks = elev.reshape(out_height, by, out_width, bx).transpose(0, 2, 1, 3)
        o_blocks = ocean.reshape(out_height, by, out_width, bx).transpose(0, 2, 1, 3)
        flat_e = e_blocks.reshape(out_height, out_width, by * bx)
        flat_o = o_blocks.reshape(out_height, out_width, by * bx)
        for j in range(out_height):
            for i in range(out_width):
                land_f = ~flat_o[j, i]
                if np.any(land_f):
                    # Always land-only when any land exists (C3 coastal mix).
                    out[j, i] = float(np.mean(flat_e[j, i][land_f]))
                else:
                    out[j, i] = float(np.mean(flat_e[j, i]))
        return out, ocean_out

    # Non-divisible fallback: windowed land-only mean around each sample.
    ys = ((np.arange(out_height) + 0.5) * in_h / out_height).astype(np.int64)
    xs = ((np.arange(out_width) + 0.5) * in_w / out_width).astype(np.int64)
    ys = np.clip(ys, 0, in_h - 1)
    xs = np.clip(xs, 0, in_w - 1)
    ry = max(1, in_h // out_height // 2)
    rx = max(1, in_w // out_width // 2)
    for j, y in enumerate(ys):
        y0, y1 = max(0, y - ry), min(in_h, y + ry + 1)
        for i, x in enumerate(xs):
            x0, x1 = max(0, x - rx), min(in_w, x + rx + 1)
            block = elev[y0:y1, x0:x1]
            oblock = ocean[y0:y1, x0:x1]
            land_f = ~oblock
            if np.any(land_f):
                out[j, i] = float(np.mean(block[land_f]))
            else:
                out[j, i] = float(np.mean(block))
    return out, ocean_out


def climate_grid_land_elevation(
    elevation_m: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    out_width: int,
    out_height: int,
    *,
    climate_ocean_mask: NDArray[np.bool_],
    ocean_elevation_m: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Climate-grid elevation: land-only mean on land cells, climate bathymetry on ocean.

    Coastal land cells do not average negative bathymetry into the land height
    used for temperature or ecology (C3).
    """
    land_mean, _ocean_out = downsample_land_elevation_mean(
        elevation_m, ocean_mask, out_width, out_height
    )
    climate_ocean = np.asarray(climate_ocean_mask, dtype=bool)
    ocean_elev = np.asarray(ocean_elevation_m, dtype=np.float64)
    return np.where(climate_ocean, ocean_elev, land_mean)


def downsample_mode_bool(
    source: NDArray[np.bool_],
    out_width: int,
    out_height: int,
) -> NDArray[np.bool_]:
    src = np.asarray(source, dtype=np.float64)
    mean = downsample_mean(src, out_width, out_height)
    return mean >= 0.5


def downsample_elevation_subgrid_stats(
    elevation_m: NDArray[np.floating],
    out_width: int,
    out_height: int,
    *,
    planet_radius_km: float = EARTH_RADIUS_KM,
) -> dict[str, NDArray[np.float64]]:
    """Mean elev + inexpensive subgrid relief stats (PR-3 §9.5).

    Not applied to temperature by default — contract/provenance only until a
    justified orographic use appears.
    """
    src = np.asarray(elevation_m, dtype=np.float64)
    in_h, in_w = src.shape
    mean = downsample_mean(src, out_width, out_height)

    fine_metrics = grid_metrics(in_w, in_h, radius_km=planet_radius_km)
    slope = fine_metrics.metric_slope(src)

    p10 = np.empty((out_height, out_width), dtype=np.float64)
    p90 = np.empty((out_height, out_width), dtype=np.float64)
    ridge = np.empty((out_height, out_width), dtype=np.float64)
    rms = np.empty((out_height, out_width), dtype=np.float64)

    if in_h % out_height == 0 and in_w % out_width == 0:
        by = in_h // out_height
        bx = in_w // out_width
        # reshape → (out_h, by, out_w, bx); transpose so each coarse cell's
        # fine block is contiguous before flattening (CR-2 / F-10).
        blocks = src.reshape(out_height, by, out_width, bx).transpose(0, 2, 1, 3)
        slope_blocks = slope.reshape(out_height, by, out_width, bx).transpose(
            0, 2, 1, 3
        )
        flat_e = blocks.reshape(out_height, out_width, by * bx)
        flat_s = slope_blocks.reshape(out_height, out_width, by * bx)
        p10 = np.percentile(flat_e, 10, axis=2)
        p90 = np.percentile(flat_e, 90, axis=2)
        ridge = np.percentile(flat_e, 95, axis=2)
        rms = np.sqrt(np.mean(np.square(flat_s), axis=2))
    else:
        ys = ((np.arange(out_height) + 0.5) * in_h / out_height).astype(np.int64)
        xs = ((np.arange(out_width) + 0.5) * in_w / out_width).astype(np.int64)
        ys = np.clip(ys, 0, in_h - 1)
        xs = np.clip(xs, 0, in_w - 1)
        ry = max(1, in_h // out_height // 2)
        rx = max(1, in_w // out_width // 2)
        for j, y in enumerate(ys):
            y0, y1 = max(0, y - ry), min(in_h, y + ry + 1)
            for i, x in enumerate(xs):
                x0, x1 = max(0, x - rx), min(in_w, x + rx + 1)
                block = src[y0:y1, x0:x1]
                sblock = slope[y0:y1, x0:x1]
                p10[j, i] = float(np.percentile(block, 10))
                p90[j, i] = float(np.percentile(block, 90))
                ridge[j, i] = float(np.percentile(block, 95))
                rms[j, i] = float(np.sqrt(np.mean(np.square(sblock))))

    return {
        "elevation_m": mean,
        "elev_p10_m": p10,
        "elev_p90_m": p90,
        "elev_ridge_m": ridge,
        "elev_slope_rms": rms,
    }


def replace_climate_temperature(
    climate: ClimateResult,
    temperature_c: NDArray[np.floating],
    *,
    diagnostics: dict[str, Any] | None = None,
    elevation_m: NDArray[np.floating] | None = None,
    temperature_equilibrium_c: NDArray[np.floating] | None = None,
    temperature_base_c: NDArray[np.floating] | None = None,
) -> ClimateResult:
    """Copy climate with updated published T (and optional named states / elev).

    ``None`` named-state arguments keep the previous arrays. Pass an array to
    update a DEM-dependent state (C3T).
    """
    eq = climate.temperature_equilibrium_c
    if temperature_equilibrium_c is not None:
        eq = np.asarray(temperature_equilibrium_c, dtype=np.float64)
    base = climate.temperature_base_c
    if temperature_base_c is not None:
        base = np.asarray(temperature_base_c, dtype=np.float64)
    return ClimateResult(
        extent=climate.extent,
        latitude_deg=climate.latitude_deg,
        insolation=climate.insolation,
        temperature_c=np.asarray(temperature_c, dtype=np.float64),
        continentality=climate.continentality,
        elevation_m=(
            climate.elevation_m
            if elevation_m is None
            else np.asarray(elevation_m, dtype=np.float64)
        ),
        ocean_mask=climate.ocean_mask,
        diagnostics=diagnostics if diagnostics is not None else dict(climate.diagnostics),
        temperature_equilibrium_c=eq,
        temperature_base_c=base,
        elev_p10_m=climate.elev_p10_m,
        elev_p90_m=climate.elev_p90_m,
        elev_ridge_m=climate.elev_ridge_m,
        elev_slope_rms=climate.elev_slope_rms,
    )


def restamp_temperature_diagnostics(
    climate: ClimateResult,
    *,
    state_name: str,
    extra: dict[str, Any] | None = None,
) -> ClimateResult:
    """Replace temperature stats with values computed from ``climate.temperature_c``."""
    stats = temperature_diagnostics(
        climate.temperature_c,
        latitude_deg=climate.latitude_deg,
        elevation_m=climate.elevation_m,
        ocean_mask=climate.ocean_mask,
        state_name=state_name,
    )
    diag = {**dict(climate.diagnostics), **stats, **(extra or {})}
    diag["temperature_provenance"] = {
        "equilibrium": TEMPERATURE_STATE_EQUILIBRIUM,
        "pre_sst_base": TEMPERATURE_STATE_BASE,
        "published": str(state_name),
    }
    return replace_climate_temperature(climate, climate.temperature_c, diagnostics=diag)


def _resolve_continentality_km(params: ClimateParams) -> float:
    if params.continentality_scale_km is not None:
        return float(params.continentality_scale_km)
    effective = resolve_planet_lengths(
        None,
        inland_decay_cells=60.0,
        continentality_scale_cells=params.continentality_scale_cells,
        radius_km=params.planet_radius_km,
    )
    return float(effective.resolved["continentality_scale_km"].value_km)


def build_base_climate(
    *,
    terrain: TerrainOceanResult,
    params: ClimateParams,
    reporter: ProgressReporter | None = None,
) -> ClimateResult:
    if reporter is not None:
        reporter.stage_started("climate")
        reporter.progress("climate", 0.1)

    lat_deg, lat_rad = latitude_grid(params.height, params.width)
    ocean = downsample_mode_bool(terrain.ocean_mask, params.width, params.height)
    sub = downsample_elevation_subgrid_stats(
        terrain.elevation_m,
        params.width,
        params.height,
        planet_radius_km=params.planet_radius_km,
    )
    elev = climate_grid_land_elevation(
        terrain.elevation_m,
        terrain.ocean_mask,
        params.width,
        params.height,
        climate_ocean_mask=ocean,
        ocean_elevation_m=sub["elevation_m"],
    )
    sub = {**sub, "elevation_m": elev}
    metrics = grid_metrics(
        params.width, params.height, radius_km=params.planet_radius_km
    )
    cont_km = _resolve_continentality_km(params)

    if reporter is not None:
        reporter.progress("climate", 0.35)

    insolation = monthly_insolation_field(
        lat_rad,
        axial_tilt_deg=params.axial_tilt_deg,
        months=params.months,
    )
    temperature_c, continentality, t_eq, temp_diag = build_monthly_temperature_c(
        insolation=insolation,
        latitude_rad=lat_rad,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=params.lapse_rate_c_per_km,
        base_temp_c=params.base_temp_c,
        continentality_scale_km=cont_km,
        continentality_scale_cells=None,
        metrics=metrics,
        planet_radius_km=params.planet_radius_km,
        continental_seasonality_gain=params.continental_seasonality_gain,
    )

    if reporter is not None:
        reporter.progress("climate", 0.85)

    land = ~ocean
    stats = temperature_diagnostics(
        temperature_c,
        latitude_deg=lat_deg,
        elevation_m=elev,
        ocean_mask=ocean,
        state_name=TEMPERATURE_STATE_BASE,
    )
    diagnostics = {
        "width": params.width,
        "height": params.height,
        "months": params.months,
        "axial_tilt_deg": params.axial_tilt_deg,
        "lapse_rate_c_per_km": params.lapse_rate_c_per_km,
        "base_temp_c": params.base_temp_c,
        "insolation_min": float(np.min(insolation)),
        "insolation_max": float(np.max(insolation)),
        "climate_land_elev_min_m": float(np.min(elev[land])) if np.any(land) else 0.0,
        "climate_land_elev_source": "land_only_mean",
        "lapse_apply_count": 1,
        "sst_apply_count": 0,
        "subgrid_elev_stats": True,
        "subgrid_applied_to_temperature": False,
        "temperature_provenance": {
            "equilibrium": TEMPERATURE_STATE_EQUILIBRIUM,
            "pre_sst_base": TEMPERATURE_STATE_BASE,
            "published": TEMPERATURE_STATE_BASE,
        },
        **temp_diag,
        **stats,
    }

    if reporter is not None:
        reporter.progress("climate", 1.0)
        reporter.stage_complete("climate")

    return ClimateResult(
        extent=SpatialExtent.from_shape(params.width, params.height),
        latitude_deg=lat_deg,
        insolation=insolation,
        temperature_c=temperature_c,
        continentality=continentality,
        elevation_m=elev,
        ocean_mask=ocean,
        diagnostics=diagnostics,
        temperature_equilibrium_c=t_eq,
        temperature_base_c=temperature_c.copy(),
        elev_p10_m=sub["elev_p10_m"],
        elev_p90_m=sub["elev_p90_m"],
        elev_ridge_m=sub["elev_ridge_m"],
        elev_slope_rms=sub["elev_slope_rms"],
    )
