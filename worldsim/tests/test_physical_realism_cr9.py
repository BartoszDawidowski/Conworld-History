"""CR-9 — metric erosion, landform score retune, BiomeV2."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.ecology.biome_v2 import BiomeV2Class, classify_biome_v2
from worldsim.physical.erosion.pass_one import (
    condition_micro_depressions,
    count_land_local_minima,
    slope_magnitude,
)
from worldsim.physical.landforms import LandformParams, LocalForm, build_landform_analysis
from worldsim.physical.landforms.params import (
    LANDFORM_ALGORITHM_VERSION,
    params_are_calibrated,
)
from worldsim.spatial.metrics import grid_metrics


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def test_slope_is_metric_not_1km_cells() -> None:
    h, w = 16, 32
    elev = np.zeros((h, w))
    elev[:, w // 2 :] = 1000.0
    gm = grid_metrics(w, h)
    s = slope_magnitude(elev, planet_radius_km=gm.radius_km)
    # 1 km leftover would be ~1.0; metric slope on planetary cells is ≪ 0.1
    assert float(np.max(s)) < 0.05
    assert float(np.max(s)) > 1e-6


def test_micro_depressions_fill_shallow_not_deep() -> None:
    h, w = 12, 16
    elev = np.full((h, w), 200.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[-1, :] = True
    elev[4, 8] = 195.0  # 5 m pit
    elev[6, 10] = 160.0  # 40 m pit
    before = count_land_local_minima(elev, ocean)
    out = condition_micro_depressions(elev, ocean, max_depth_m=25.0, passes=4)
    after = count_land_local_minima(out, ocean)
    assert after < before
    assert out[4, 8] > elev[4, 8]
    assert out[6, 10] == pytest.approx(160.0)


def test_calibrated_not_constant_true() -> None:
    assert params_are_calibrated(LandformParams()) is True
    assert params_are_calibrated(LandformParams(mountain_score_threshold=0.42)) is False
    assert params_are_calibrated(LandformParams(enabled=False)) is False
    assert params_are_calibrated(LandformParams(min_range_km2=None)) is False


def test_hilly_land_not_majority_mountain() -> None:
    """Score retune: moderate hills stay below 0.60 on a metric grid."""
    h, w = 48, 96
    rng = np.random.default_rng(7)
    elev = 400.0 + 180.0 * rng.standard_normal((h, w))
    ocean = _ocean_frame(h, w)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(),
    )
    assert res.diagnostics["algorithm"] == LANDFORM_ALGORITHM_VERSION
    assert res.diagnostics["calibrated"] is True
    assert res.diagnostics["mountain_land_fraction"] < 0.25


def test_cone_and_plateau_survive_cr9_threshold() -> None:
    h, w = 48, 64
    ocean = _ocean_frame(h, w)
    plat = np.full((h, w), 100.0)
    plat[14:34, 18:46] = 900.0
    plat = np.where(ocean, -200.0, plat)
    pres = build_landform_analysis(elevation_m=plat, ocean_mask=ocean)
    assert len(pres.plateaus) >= 1
    assert np.any(pres.local_form_id == int(LocalForm.ESCARPMENT))

    cone = np.full((h, w), 200.0)
    jj, ii = np.ogrid[:h, :w]
    cone = cone + 2200.0 * np.exp(-((ii - 32) ** 2 + (jj - 24) ** 2) / 12.0)
    cone = np.where(ocean, -200.0, cone)
    cres = build_landform_analysis(
        elevation_m=cone,
        ocean_mask=ocean,
        params=LandformParams(
            min_range_km2=None,
            fine_radius_km=20.0,
            meso_radius_km=50.0,
            macro_radius_km=120.0,
        ),
    )
    assert len(cres.mountain_ranges) >= 1
    assert len(cres.mountain_ranges[0].ridge_line) >= 2
    assert cres.diagnostics["calibrated"] is False  # km² floor disabled


def test_config_cr9_landform_threshold() -> None:
    cfg = load_planet_config(default_config_path())
    lf = cfg.to_landform_params()
    assert lf.mountain_score_threshold == pytest.approx(0.60)
    assert params_are_calibrated(lf) is True


def test_biome_v2_frost_and_deficit() -> None:
    h, w = 8, 12
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :2] = True
    temp = np.full((12, h, w), 12.0)
    temp[:4] = -5.0
    precip = np.full((12, h, w), 0.2)
    soil = np.full((h, w), 0.3)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        soil_moisture=soil,
    )
    land = ~ocean
    assert int(out["frost_months"][land].mean()) == 4
    assert int(out["growing_season_months"][land].min()) >= 8
    assert float(out["water_deficit_mm"][land].mean()) > 0.0
    assert np.all(out["biome_v2_class"][ocean] == int(BiomeV2Class.OCEAN))
    assert np.all(out["biome_v2_class"][land] != int(BiomeV2Class.OCEAN))
    assert out["diagnostics"]["holdridge_role"] == "annual_diagnostic"
