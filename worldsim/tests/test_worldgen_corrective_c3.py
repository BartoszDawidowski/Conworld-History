"""C3 — metric erosion lower bound, separate knobs, land-only climate elevation."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.climate.pipeline import (
    climate_grid_land_elevation,
    downsample_land_elevation_mean,
)
from worldsim.physical.erosion.fluvial import apply_fluvial_erosion
from worldsim.physical.erosion.pass_one import (
    apply_erosion_pass_one,
    erosion_nontrivial_gate,
    land_elevation_delta_stats,
    rock_resistance_proxy,
)
from worldsim.physical.erosion.pipeline import ErosionParams
from worldsim.physical.final.pipeline import FinalRecalcParams
from worldsim.spatial.metrics import EARTH_RADIUS_KM

ROOT = Path(__file__).resolve().parents[2]


def _ridge_dem(height: int, width: int, *, seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Smooth macro-relief without pits (pit-fill must not fake a lower bound)."""
    _ = seed
    elev = np.linspace(120.0, 1800.0, height, dtype=np.float64)[:, None] * np.ones(
        (1, width)
    )
    xs = np.linspace(-1.0, 1.0, width)
    ys = np.linspace(-1.0, 1.0, height)
    elev = elev + 1600.0 * np.exp(-((xs - 0.15) ** 2) / 0.04)[None, :]
    elev = elev + 90.0 * np.sin(xs * 6.0 * np.pi)[None, :]
    elev = elev + 50.0 * np.sin(ys * 8.0 * np.pi)[:, None]
    ocean = np.zeros((height, width), dtype=bool)
    ocean[-max(4, height // 16) :, :] = True
    elev[ocean] = -400.0
    return elev, ocean


def _macro_corr(before: np.ndarray, after: np.ndarray, ocean: np.ndarray) -> float:
    land = ~ocean
    return float(np.corrcoef(before[land], after[land])[0, 1])


def test_defaults_are_not_the_calibration_centre() -> None:
    assert ErosionParams().thermal_kappa == pytest.approx(0.08)
    assert ErosionParams().fluvial_k == pytest.approx(8.0)
    assert FinalRecalcParams().stream_power_k == pytest.approx(12.0)
    cfg = load_planet_config(default_config_path())
    assert cfg.erosion_thermal_kappa == pytest.approx(0.08)
    assert cfg.erosion_fluvial_k == pytest.approx(8.0)
    assert cfg.erosion_stream_power_k == pytest.approx(12.0)
    assert cfg.to_erosion_params().fluvial_k != pytest.approx(
        cfg.to_final_recalc_params().stream_power_k
    )


def test_noop_erosion_fails_lower_bound() -> None:
    elev, ocean = _ridge_dem(64, 96)
    precip = np.full(elev.shape, 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=elev.shape
    )
    after, _delta = apply_erosion_pass_one(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resist,
        iterations=5,
        thermal_kappa=0.0,
        fluvial_k=0.0,
    )
    stats = land_elevation_delta_stats(elev, after, ocean)
    nontrivial, required = erosion_nontrivial_gate(
        float(stats["mean_abs_delta_land_m"]),
        float(stats["elev_range_land_m"]),
    )
    assert required >= 1.0
    assert nontrivial is False
    assert stats["ocean_unchanged"] is True


def test_production_kappa_is_noop_on_earth_scale_fixture() -> None:
    elev, ocean = _ridge_dem(128, 256)
    precip = np.full(elev.shape, 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=elev.shape
    )
    after, _delta = apply_erosion_pass_one(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resist,
        iterations=5,
        thermal_kappa=0.08,
        fluvial_k=8.0,
        planet_radius_km=EARTH_RADIUS_KM,
    )
    stats = land_elevation_delta_stats(elev, after, ocean)
    nontrivial, _required = erosion_nontrivial_gate(
        float(stats["mean_abs_delta_land_m"]),
        float(stats["elev_range_land_m"]),
    )
    assert stats["ocean_unchanged"] is True
    assert _macro_corr(elev, after, ocean) >= 0.97
    # Atlas-class cell size: metric conversion left production k as a no-op.
    assert nontrivial is False
    assert float(stats["mean_abs_delta_land_m"]) < 1.0


def test_experimental_centre_is_nontrivial_without_erasing_macro() -> None:
    """``thermal_kappa`` is a 1 km-cell coefficient; prove it on that scale.

    Earth-radius coarse fixtures stay below the 1 m land-mean gate even at
    kappa=50 — that is recorded in the calibration grid, not a retune.
    """
    h, w = 128, 256
    elev, ocean = _ridge_dem(h, w)
    radius_1km = w / (2.0 * np.pi)
    precip = np.full(elev.shape, 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=elev.shape
    )
    after, _delta = apply_erosion_pass_one(
        elevation_m=elev,
        ocean_mask=ocean,
        annual_precip=precip,
        resistance=resist,
        iterations=5,
        thermal_kappa=50.0,
        fluvial_k=8.0,
        planet_radius_km=radius_1km,
    )
    stats = land_elevation_delta_stats(elev, after, ocean)
    nontrivial, _required = erosion_nontrivial_gate(
        float(stats["mean_abs_delta_land_m"]),
        float(stats["elev_range_land_m"]),
    )
    assert stats["ocean_unchanged"] is True
    assert np.array_equal(after[ocean], elev[ocean])
    assert _macro_corr(elev, after, ocean) >= 0.97
    assert nontrivial is True


def test_calibration_grid_first_pass_recorded() -> None:
    elev, ocean = _ridge_dem(256, 512)
    precip = np.full(elev.shape, 2.0)
    resist = rock_resistance_proxy(
        orogenic_potential=None, tectonic_activity=None, shape=elev.shape
    )
    rows = []
    for kappa in (0.08, 20.0, 50.0, 80.0):
        t0 = time.perf_counter()
        after, _delta = apply_erosion_pass_one(
            elevation_m=elev,
            ocean_mask=ocean,
            annual_precip=precip,
            resistance=resist,
            iterations=5,
            thermal_kappa=kappa,
            fluvial_k=8.0,
            planet_radius_km=EARTH_RADIUS_KM,
        )
        elapsed = time.perf_counter() - t0
        stats = land_elevation_delta_stats(elev, after, ocean)
        nontrivial, required = erosion_nontrivial_gate(
            float(stats["mean_abs_delta_land_m"]),
            float(stats["elev_range_land_m"]),
        )
        rows.append(
            {
                "thermal_kappa": kappa,
                **{k: stats[k] for k in stats},
                "corr": _macro_corr(elev, after, ocean),
                "nontrivial": nontrivial,
                "required_m": required,
                "runtime_s": elapsed,
            }
        )
    by_k = {r["thermal_kappa"]: r for r in rows}
    assert by_k[0.08]["nontrivial"] is False
    assert by_k[50.0]["mean_abs_delta_land_m"] > by_k[0.08]["mean_abs_delta_land_m"]
    assert by_k[80.0]["mean_abs_delta_land_m"] > by_k[50.0]["mean_abs_delta_land_m"]
    assert all(r["ocean_unchanged"] is True for r in rows)
    assert all(r["corr"] >= 0.97 for r in rows)
    test_calibration_grid_first_pass_recorded.rows = rows  # type: ignore[attr-defined]


def test_calibration_grid_stream_power_recorded() -> None:
    h, w = 128, 256
    elev = np.linspace(2400.0, 40.0, h)[:, None] * np.ones((1, w))
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-6:, :] = True
    elev[ocean] = -300.0
    river = np.zeros((h, w), dtype=bool)
    river[:, w // 2] = True
    river[ocean] = False
    q = np.where(river, 80.0, 1.0)
    q[ocean] = 0.0
    resist = np.ones((h, w), dtype=np.float64)
    rows = []
    for k in (12.0, 500.0, 1000.0, 1500.0):
        t0 = time.perf_counter()
        after, _delta = apply_fluvial_erosion(
            elevation_m=elev,
            ocean_mask=ocean,
            river_mask=river,
            discharge_proxy=q,
            resistance=resist,
            iterations=4,
            stream_power_k=k,
            planet_radius_km=EARTH_RADIUS_KM,
        )
        elapsed = time.perf_counter() - t0
        stats = land_elevation_delta_stats(elev, after, ocean)
        nontrivial, required = erosion_nontrivial_gate(
            float(stats["mean_abs_delta_land_m"]),
            float(stats["elev_range_land_m"]),
        )
        river_mean = (
            float(np.mean(np.abs((after - elev)[river]))) if np.any(river) else 0.0
        )
        rows.append(
            {
                "stream_power_k": k,
                **{k2: stats[k2] for k2 in stats},
                "corr": _macro_corr(elev, after, ocean),
                "nontrivial": nontrivial,
                "required_m": required,
                "river_mean_abs_delta_m": river_mean,
                "runtime_s": elapsed,
            }
        )
    by_k = {r["stream_power_k"]: r for r in rows}
    assert by_k[12.0]["nontrivial"] is False
    assert by_k[1000.0]["ocean_unchanged"] is True
    assert by_k[1000.0]["corr"] >= 0.95
    assert (
        by_k[1000.0]["river_mean_abs_delta_m"] > by_k[12.0]["river_mean_abs_delta_m"]
    )
    test_calibration_grid_stream_power_recorded.rows = rows  # type: ignore[attr-defined]


def test_climate_land_cell_never_negative_from_coastal_mix() -> None:
    h, w = 8, 16
    elev = np.full((h, w), 450.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :6] = True
    elev[:, :6] = -2800.0
    mixed, ocean_out = downsample_land_elevation_mean(elev, ocean, 4, 2)
    # Coarse col 1 is mixed (terrain cols 4–7: ocean+land). Land-only must stay +ve.
    assert float(mixed[0, 1]) == pytest.approx(450.0)
    climate_ocean = np.zeros((2, 4), dtype=bool)
    climate_ocean[:, 0] = True
    # Force the mixed block to be treated as climate land.
    climate_ocean[:, 1] = False
    ocean_elev = np.full((2, 4), -2800.0)
    out = climate_grid_land_elevation(
        elev,
        ocean,
        4,
        2,
        climate_ocean_mask=climate_ocean,
        ocean_elevation_m=ocean_elev,
    )
    land = ~climate_ocean
    assert np.all(out[land] >= 0.0)
    assert float(out[0, 1]) == pytest.approx(450.0)
    assert float(out[0, 0]) == pytest.approx(-2800.0)
    assert bool(ocean_out[0, 0]) is True


def test_godot_does_not_present_fluvial_k_as_final_incision() -> None:
    tscn = (ROOT / "godot" / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    assert "Does not control final stream-power" in tscn
    gd = (ROOT / "godot" / "scenes" / "Main.gd").read_text(encoding="utf-8")
    assert "stream_power_k: 12.0" in gd
    assert "thermal_kappa: 0.08" in gd
