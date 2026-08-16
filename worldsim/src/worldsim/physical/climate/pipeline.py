"""Milestone 6 — base seasonal climate (insolation + temperature)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.climate.insolation import monthly_insolation_field
from worldsim.physical.climate.temperature import build_monthly_temperature_c
from worldsim.physical.terrain.pipeline import TerrainOceanResult
from worldsim.progress import ProgressReporter
from worldsim.spatial.coordinates import y_to_lat
from worldsim.spatial.extent import SpatialExtent


@dataclass(frozen=True)
class ClimateParams:
    width: int
    height: int
    months: int = 12
    axial_tilt_deg: float = 23.44
    lapse_rate_c_per_km: float = 6.5
    base_temp_c: float = 15.0


@dataclass
class ClimateResult:
    extent: SpatialExtent
    latitude_deg: NDArray[np.float64]
    insolation: NDArray[np.float64]  # [12, y, x]
    temperature_c: NDArray[np.float64]  # [12, y, x]
    continentality: NDArray[np.float64]
    elevation_m: NDArray[np.float64]
    ocean_mask: NDArray[np.bool_]
    diagnostics: dict[str, Any]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "climate_base.npz",
            latitude_deg=self.latitude_deg,
            insolation=self.insolation,
            temperature_c=self.temperature_c,
            continentality=self.continentality,
            elevation_m=self.elevation_m,
            ocean_mask=self.ocean_mask.astype(np.uint8),
        )
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


def downsample_mode_bool(
    source: NDArray[np.bool_],
    out_width: int,
    out_height: int,
) -> NDArray[np.bool_]:
    src = np.asarray(source, dtype=np.float64)
    mean = downsample_mean(src, out_width, out_height)
    return mean >= 0.5


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
    elev = downsample_mean(terrain.elevation_m, params.width, params.height)
    ocean = downsample_mode_bool(terrain.ocean_mask, params.width, params.height)

    if reporter is not None:
        reporter.progress("climate", 0.35)

    insolation = monthly_insolation_field(
        lat_rad,
        axial_tilt_deg=params.axial_tilt_deg,
        months=params.months,
    )
    temperature_c, continentality = build_monthly_temperature_c(
        insolation=insolation,
        latitude_rad=lat_rad,
        elevation_m=elev,
        ocean_mask=ocean,
        lapse_rate_c_per_km=params.lapse_rate_c_per_km,
        base_temp_c=params.base_temp_c,
    )

    if reporter is not None:
        reporter.progress("climate", 0.85)

    # Diagnostics for acceptance: seasonal inversion + polar/elevation trends.
    june = 5
    december = 11
    # Northern mid-lat band ~45°N
    nh = (lat_deg > 40.0) & (lat_deg < 55.0)
    sh = (lat_deg < -40.0) & (lat_deg > -55.0)
    seasonal_inversion_ok = True
    if np.any(nh) and np.any(sh):
        nh_june = float(temperature_c[june][nh].mean())
        nh_dec = float(temperature_c[december][nh].mean())
        sh_june = float(temperature_c[june][sh].mean())
        sh_dec = float(temperature_c[december][sh].mean())
        seasonal_inversion_ok = (nh_june > nh_dec) and (sh_dec > sh_june)
    else:
        nh_june = nh_dec = sh_june = sh_dec = float("nan")

    # Poles colder than tropics (annual mean)
    trop = np.abs(lat_deg) < 15.0
    polar = np.abs(lat_deg) > 70.0
    annual = temperature_c.mean(axis=0)
    polar_colder = True
    if np.any(trop) and np.any(polar):
        polar_colder = float(annual[polar].mean()) < float(annual[trop].mean())

    # Elevation: high land colder than low land (annual)
    land = ~ocean
    elevation_trend_ok = True
    if np.count_nonzero(land) > 50:
        land_elev = elev[land]
        land_temp = annual[land]
        # Correlation should be negative
        if float(np.std(land_elev)) > 1.0:
            corr = float(np.corrcoef(land_elev, land_temp)[0, 1])
            elevation_trend_ok = corr < -0.2
        else:
            corr = float("nan")
    else:
        corr = float("nan")

    diagnostics = {
        "width": params.width,
        "height": params.height,
        "months": params.months,
        "axial_tilt_deg": params.axial_tilt_deg,
        "lapse_rate_c_per_km": params.lapse_rate_c_per_km,
        "base_temp_c": params.base_temp_c,
        "temperature_min_c": float(np.min(temperature_c)),
        "temperature_max_c": float(np.max(temperature_c)),
        "annual_mean_c": float(np.mean(annual)),
        "insolation_min": float(np.min(insolation)),
        "insolation_max": float(np.max(insolation)),
        "seasonal_inversion_ok": seasonal_inversion_ok,
        "nh_june_mean_c": nh_june,
        "nh_december_mean_c": nh_dec,
        "sh_june_mean_c": sh_june,
        "sh_december_mean_c": sh_dec,
        "polar_colder_than_tropics": polar_colder,
        "elevation_temperature_corr_land": corr,
        "elevation_trend_ok": elevation_trend_ok,
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
    )
