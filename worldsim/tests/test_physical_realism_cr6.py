"""CR-6 — monthly PET fraction, liquid lakes, land-outlet closed_basin, contours."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.erosion.pipeline import ErosionResult
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.cylindrical_graph import build_cylindrical_graph
from worldsim.physical.hydrology.lakes_meta import (
    LIQUID_WATER_STATES,
    classify_lake_body,
    liquid_lake_mask,
)
from worldsim.physical.hydrology.transmission import (
    month_pet_fraction,
    transmission_sink,
)
from worldsim.physical.moisture.pipeline import MoistureResult
from worldsim.physical.moisture.transport import evaporation_components
from worldsim.physical.hydrology.discharge import month_weighted_mean_m3s
from worldsim.physical.vectorize.lakes import _directed_outline_rings, build_lakes
from worldsim.spatial.extent import SpatialExtent


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


def test_month_pet_fractions_sum_to_one() -> None:
    total = sum(month_pet_fraction(m) for m in range(12))
    assert total == pytest.approx(1.0)


def test_monthly_pet_is_not_annual_applied_twelve_times() -> None:
    precip = np.ones((4, 4), dtype=np.float64) * 0.1
    temp = np.full((4, 4), 20.0)
    ocean = np.zeros((4, 4), dtype=bool)
    annual = transmission_sink(precip * 12.0, temp, ocean, pet_year_fraction=1.0)
    monthly = transmission_sink(
        precip, temp, ocean, pet_year_fraction=month_pet_fraction(0)
    )
    # January is 31/365 of annual PET, not the full annual total.
    assert float(monthly.mean()) < float(annual.mean()) * 0.2
    assert float(monthly.mean()) == pytest.approx(
        float(annual.mean()) * month_pet_fraction(0), rel=0.15
    )


def test_land_outlet_is_not_closed_basin() -> None:
    h, w = 8, 10
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-1, :] = True
    d8 = np.full((h, w), 4, dtype=np.uint8)  # south
    d8[-1, :] = 0
    body = np.zeros((h, w), dtype=bool)
    body[2:5, 2:5] = True
    d8[3, 3] = 0  # pit inside the body
    # Other body cells drain south onto land (row 5), not ocean.
    elev = np.full((h, w), 80.0)
    elev[body] = 40.0
    graph = build_cylindrical_graph(d8, ocean)
    rec = classify_lake_body(
        graph=graph,
        lake_mask=body,
        lake_id_value=1,
        elevation_m=elev,
        discharge_effective=np.ones((h, w)),
        temperature_annual_c=np.full((h, w), 12.0),
        precip_annual=np.ones((h, w)),
    )
    assert rec["has_land_outlet"] is True
    assert rec["closed_basin"] is False
    assert rec["water_state"] == "open"


def test_playa_and_ice_excluded_from_liquid_mask() -> None:
    lake_id = np.zeros((6, 6), dtype=np.int32)
    lake_id[1:3, 1:3] = 1
    lake_id[1:3, 4:6] = 2
    records = [
        {"lake_id": 1, "water_state": "seasonal_or_playa"},
        {"lake_id": 2, "water_state": "open"},
    ]
    liquid = liquid_lake_mask(lake_id, records)
    assert not np.any(liquid[1:3, 1:3])
    assert np.all(liquid[1:3, 4:6])
    assert "seasonal_or_playa" not in LIQUID_WATER_STATES


def test_frozen_closed_basin_not_in_product_lake_mask() -> None:
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
    frozen_ids = {
        int(r["lake_id"])
        for r in hydro.lake_records
        if r.get("water_state") == "frozen_or_ice_covered"
    }
    for lid in frozen_ids:
        assert not np.any(hydro.lake_mask & (hydro.lake_id == lid))


def test_canonical_q_tracks_independent_annual_after_pet_fraction() -> None:
    erosion, moisture, temp = _synthetic_hydro_inputs()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(fill_max_depth_m=25.0),
        temperature_c=temp,
    )
    assert np.allclose(
        month_weighted_mean_m3s(hydro.monthly_discharge),
        hydro.river_discharge_proxy,
        atol=1e-9,
    )
    rel_ind = float(hydro.diagnostics["monthly_vs_independent_annual_rel_diff"])
    # Real physical check (not identity-by-construction). PET×12 used to be ~0.89.
    assert rel_ind < 0.35


def test_concave_lake_outline_is_not_centroid_star() -> None:
    mask = np.zeros((10, 12), dtype=bool)
    mask[2:6, 2:4] = True
    mask[4:6, 2:8] = True  # L / concave
    rings = _directed_outline_rings(mask)
    assert rings
    ring = max(rings, key=len)
    area = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        area += x0 * y1 - x1 * y0
    assert abs(area) / 2.0 == pytest.approx(float(np.count_nonzero(mask)))
    # Consecutive corners share an axis (no diagonal centroid chords).
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        assert (x0 == x1) or (y0 == y1)


def test_lake_fraction_scales_evaporation() -> None:
    ocean = np.zeros((3, 3), dtype=bool)
    temp = np.full((3, 3), 20.0)
    full = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        lake_mask=np.ones((3, 3), dtype=bool),
        lake_rate=0.75,
    )["lake_evaporation"]
    half = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        lake_fraction=np.full((3, 3), 0.25),
        lake_rate=0.75,
    )["lake_evaporation"]
    assert float(half.mean()) == pytest.approx(float(full.mean()) * 0.25, rel=1e-6)


def test_config_cr6_defaults() -> None:
    cfg = load_planet_config(default_config_path())
    assert cfg.hydrology_river_acc_fraction == pytest.approx(0.035)
    assert cfg.continentality_scale_km == pytest.approx(500.0)
    hp = cfg.to_hydrology_params()
    assert hp.river_acc_fraction == pytest.approx(0.035)


def test_build_lakes_keeps_water_state() -> None:
    extent = SpatialExtent.from_shape(8, 8)
    lake_id = np.zeros((8, 8), dtype=np.int32)
    lake_id[2:5, 2:5] = 1
    lakes = build_lakes(
        lake_id=lake_id,
        lake_mask=lake_id > 0,
        elevation_m=np.full((8, 8), 50.0),
        basin_id=np.ones((8, 8), dtype=np.int32),
        extent=extent,
        lake_records=[
            {
                "lake_id": 1,
                "water_state": "open",
                "closed_basin": False,
                "spill_elevation_m": 55.0,
                "surface_elevation_m": 48.0,
                "mean_effective_inflow": 12.0,
                "basin_id": 1,
            }
        ],
    )
    assert lakes
    assert lakes[0].water_state == "open"
    assert len(lakes[0].polygon) >= 5
