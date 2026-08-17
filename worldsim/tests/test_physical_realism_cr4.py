"""CR-4 — typed outlets / endorheism + canonical monthly effective Q."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.cylindrical_graph import (
    OUTLET_CLOSED,
    OUTLET_OCEAN,
    classify_outlets,
)
from worldsim.physical.hydrology.flow import run_pyflwdir_core
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.spatial.extent import SpatialExtent


def _closed_basin_dem(
    h: int = 28,
    w: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """East-draining land with a deep inland hole (pour depth ≫ 25 m)."""
    elev = np.linspace(40.0, 120.0, h, dtype=np.float64)[:, None] + np.linspace(
        180.0, 30.0, w, dtype=np.float64
    )[None, :]
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -4:] = True
    elev[ocean] = -80.0
    # High rim around a deep floor so pyflwdir keeps a pit at max_depth=25.
    elev[6:16, 6:16] = 200.0
    elev[8:14, 8:14] = 20.0
    return elev, ocean


def _synthetic_hydro_inputs(
    *,
    precip: float = 2.0,
    basin_precip: float = 2.0,
    temp_c: float = 12.0,
) -> tuple[ErosionResult, MoistureResult, np.ndarray]:
    elev, ocean = _closed_basin_dem()
    h, w = elev.shape
    extent = SpatialExtent.from_shape(h, w)
    zeros = np.zeros((h, w), dtype=np.float64)
    erosion = ErosionResult(
        extent=extent,
        elevation_before_m=elev.copy(),
        elevation_m=elev,
        erosion_delta_m=zeros,
        slope=zeros,
        rock_resistance=np.ones((h, w)),
        annual_precip_terrain=np.full((h, w), precip * 12.0),
        ocean_mask=ocean,
        diagnostics={},
    )
    p = np.full((12, h, w), precip, dtype=np.float64)
    p[:, 8:14, 8:14] = basin_precip
    p[:, ocean] = 0.0
    moisture = MoistureResult(
        extent=extent,
        atmospheric_moisture=p.copy(),
        evaporation=np.zeros_like(p),
        precipitation=p,
        humidity=np.ones_like(p),
        orographic_lift=np.zeros_like(p),
        convective_precip=np.zeros_like(p),
        annual_precipitation=p.sum(axis=0),
        diagnostics={},
    )
    temp = np.full((12, h, w), temp_c, dtype=np.float64)
    return erosion, moisture, temp


def test_finite_fill_keeps_closed_sink() -> None:
    elev, ocean = _closed_basin_dem()
    filled_all = run_pyflwdir_core(
        elevation_m=elev, ocean_mask=ocean, max_depth=-1.0
    )
    limited = run_pyflwdir_core(
        elevation_m=elev, ocean_mask=ocean, max_depth=25.0
    )
    hole = np.zeros(elev.shape, dtype=bool)
    hole[8:14, 8:14] = True
    ds_all = filled_all["graph"].downstream_flat.reshape(elev.shape)
    ds_lim = limited["graph"].downstream_flat.reshape(elev.shape)
    assert not np.any(ds_all[hole] < 0), "fill-all must drain the hole"
    assert np.any(ds_lim[hole] < 0), "finite fill must retain an inland pit"
    typed = classify_outlets(
        limited["graph"],
        accumulation=limited["flow_accumulation"],
        depression_depth_m=limited["depression_depth_m"],
        min_closed_cells=4,
        min_closed_depth_m=2.0,
    )
    assert typed["outlets_typed"] is True
    assert typed["closed_basin_outlet_count"] >= 1
    assert typed["outlet_type_counts"][OUTLET_OCEAN] >= 1
    assert typed["outlet_type_counts"][OUTLET_CLOSED] >= 1


def test_endorheic_and_playa_materialize() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs(
        precip=1.5, basin_precip=0.05, temp_c=14.0
    )
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    states = {r["water_state"] for r in hydro.lake_records}
    closed = [r for r in hydro.lake_records if r.get("closed_basin")]
    assert closed, "closed-basin lake records must exist"
    assert hydro.diagnostics["lake_endorheic_count"] + hydro.diagnostics[
        "lake_playa_count"
    ] >= 1
    assert states & {"endorheic", "seasonal_or_playa"}
    assert hydro.diagnostics["outlets_typed"] is True
    assert hydro.diagnostics["acceptance_ok"] is True


def test_frozen_closed_basin_kept() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs(
        precip=1.0, basin_precip=1.0, temp_c=-8.0
    )
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0, lake_min_mean_temp_c=1.0),
        temperature_c=temp,
    )
    assert hydro.diagnostics["lake_frozen_count"] >= 1
    assert any(r["water_state"] == "frozen_or_ice_covered" for r in hydro.lake_records)


def test_canonical_monthly_q_sums_to_annual() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    summed = hydro.monthly_discharge.sum(axis=0)
    assert np.allclose(summed, hydro.river_discharge_proxy, atol=1e-9)
    assert hydro.diagnostics["monthly_vs_annual_eff_rel_diff"] == pytest.approx(0.0)
    assert hydro.diagnostics["monthly_annual_consistent"] is True
    assert hydro.diagnostics["q_canonical"] == "sum_monthly_effective"
    # Independent annual routing may differ (PET/max nonlinearity) but must
    # not be the 80–91% mystery divergence used as the product Q.
    rel_ind = float(hydro.diagnostics["monthly_vs_independent_annual_rel_diff"])
    assert rel_ind < 0.80


def test_config_cr4_defaults() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.hydrology_fill_max_depth_m == pytest.approx(25.0)
    hp = cfg.to_hydrology_params()
    assert hp.fill_max_depth_m == pytest.approx(25.0)
    assert hp.transmission_rate == pytest.approx(0.45)
