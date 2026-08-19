"""CR-7 — soil bucket, Q in m³/s, per-km transmission, channel states, basin storage."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.channels import (
    CHANNEL_PERENNIAL,
    CHANNEL_SEASONAL,
    CHANNEL_WADI,
    classify_channel_states,
    display_channel_candidates,
    physical_channel_mask,
)
from worldsim.physical.hydrology.discharge import (
    month_weighted_mean_m3s,
    runoff_proxy_to_m3s,
)
from worldsim.physical.hydrology.runoff import build_monthly_runoff
from worldsim.physical.hydrology.transmission import transmission_sink
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics


def _closed_basin_dem(
    h: int = 28,
    w: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    elev = np.linspace(40.0, 120.0, h, dtype=np.float64)[:, None] + np.linspace(
        180.0, 30.0, w, dtype=np.float64
    )[None, :]
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -4:] = True
    elev[ocean] = -80.0
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


def test_soil_bucket_et_reduces_runoff_below_rain_plus_melt() -> None:
    precip = np.full((12, 6, 6), 1.5)
    temp = np.full((12, 6, 6), 18.0)
    ocean = np.zeros((6, 6), dtype=bool)
    out = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
        soil_capacity=1.0,
        soil_quickflow_frac=0.20,
    )
    rain_melt = np.asarray(out["rain"]) + np.asarray(out["melt"])
    runoff = np.asarray(out["runoff"])
    assert float(np.sum(runoff)) < float(np.sum(rain_melt))
    assert float(np.sum(out["soil_et"])) > 0.0
    assert out["diagnostics"]["runoff_algorithm"] == "soil_bucket_periodic_v1"


def test_cold_month_still_holds_snow_before_soil() -> None:
    precip = np.full((12, 6, 6), 2.0)
    temp = np.full((12, 6, 6), -10.0)
    ocean = np.zeros((6, 6), dtype=bool)
    out = build_monthly_runoff(
        precipitation=precip,
        temperature_c=temp,
        ocean_mask=ocean,
    )
    assert float(out["runoff"][0].mean()) < float(out["snowfall"][0].mean()) * 0.5
    assert float(out["snow_store"][0].mean()) > 0.5


def test_q_m3s_scales_with_cell_area() -> None:
    proxy = np.ones((4, 4), dtype=np.float64)
    small = runoff_proxy_to_m3s(
        proxy, cell_area_km2=100.0, precip_scale_mm=200.0, days=30.0
    )
    large = runoff_proxy_to_m3s(
        proxy, cell_area_km2=400.0, precip_scale_mm=200.0, days=30.0
    )
    assert float(large.mean()) == pytest.approx(float(small.mean()) * 4.0)


def test_transmission_loss_grows_with_path_length() -> None:
    precip = np.ones((5, 5), dtype=np.float64) * 0.1
    temp = np.full((5, 5), 25.0)
    ocean = np.zeros((5, 5), dtype=bool)
    short = np.full((5, 5), 10.0)
    long = np.full((5, 5), 80.0)
    s_short = transmission_sink(
        precip, temp, ocean, path_length_km=short, transmission_ref_km=50.0
    )
    s_long = transmission_sink(
        precip, temp, ocean, path_length_km=long, transmission_ref_km=50.0
    )
    assert float(s_long.mean()) > float(s_short.mean())
    assert float(s_long.mean() / s_short.mean()) == pytest.approx(8.0, rel=1e-6)


def test_physical_mask_precedes_display_quantile() -> None:
    acc = np.arange(16, dtype=np.float64).reshape(4, 4)
    ocean = np.zeros((4, 4), dtype=bool)
    physical = physical_channel_mask(acc, ocean, min_cells=4)
    display = display_channel_candidates(physical, acc, fraction=0.25)
    assert int(np.count_nonzero(physical)) >= int(np.count_nonzero(display))
    assert np.all(display <= physical)


def test_channel_states_partition_wet_months() -> None:
    q = np.zeros((12, 3, 3), dtype=np.float64)
    q[:, 0, 0] = 2.0
    q[:6, 0, 1] = 2.0
    q[0, 0, 2] = 2.0
    network = np.ones((3, 3), dtype=bool)
    state, diag = classify_channel_states(q, network, q_min_m3s=0.5)
    assert int(state[0, 0]) == CHANNEL_PERENNIAL
    assert int(state[0, 1]) == CHANNEL_SEASONAL
    assert int(state[0, 2]) == CHANNEL_WADI
    assert diag["channel_perennial_count"] == 1
    assert diag["channel_seasonal_count"] == 1
    assert diag["channel_wadi_count"] == 1


def test_build_hydrology_cr7_units_and_states() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    assert hydro.diagnostics["hydrology_algorithm"] == "c91_2_periodic_runoff_storage_v1"
    assert hydro.diagnostics["q_units"] == "m3_s"
    assert hydro.diagnostics["q_canonical"] == "mean_monthly_m3s"
    assert hydro.diagnostics["runoff_algorithm"] == "soil_bucket_periodic_v1"
    assert np.allclose(
        month_weighted_mean_m3s(hydro.monthly_discharge),
        hydro.river_discharge_proxy,
        atol=1e-9,
    )
    assert float(hydro.diagnostics["monthly_vs_independent_annual_rel_diff"]) < 0.35
    assert hydro.channel_mask.shape == hydro.river_mask.shape
    assert int(np.count_nonzero(hydro.channel_mask)) >= int(
        np.count_nonzero(hydro.river_mask)
    )
    assert np.all(~hydro.river_mask | hydro.channel_mask)
    assert hydro.channel_state.shape == hydro.river_mask.shape
    assert hydro.soil_store.shape == hydro.ocean_mask.shape
    assert float(np.max(hydro.river_discharge_proxy)) > 0.0
    states = hydro.channel_state[hydro.river_mask | (hydro.channel_state > 0)]
    if states.size:
        assert set(np.unique(states)).issubset(
            {CHANNEL_WADI, CHANNEL_SEASONAL, CHANNEL_PERENNIAL}
        )


def test_closed_basin_storage_has_twelve_scalars() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs(
        precip=2.0, basin_precip=2.0, temp_c=14.0
    )
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    closed = [r for r in hydro.lake_records if r.get("closed_basin")]
    assert closed
    stored = [r for r in closed if "storage_m3" in r]
    assert stored, "closed basins must receive A–V–h scalars"
    rec = stored[0]
    assert len(rec["storage_m3"]) == 12
    assert len(rec["level_m"]) == 12
    assert rec["storage_curve"] == "discrete_avh_v1"
    assert hydro.diagnostics["basin_storage_stepped_count"] >= 1


def test_d8_step_length_field_matches_scalar() -> None:
    gm = grid_metrics(32, 16)
    d8 = np.full((16, 32), 1, dtype=np.uint8)  # east
    field = gm.d8_step_length_km_field(d8)
    for j in (0, 8, 15):
        assert float(field[j, 0]) == pytest.approx(gm.d8_step_length_km(j, 1))
