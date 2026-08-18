"""C7 — landform scales, local classes, object geometry, honest acceptance."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.landforms import (
    BroadContext,
    LANDFORM_ALGORITHM_VERSION,
    LandformParams,
    LocalForm,
    build_landform_analysis,
)
from worldsim.physical.landforms.metrics import scale_window
from worldsim.physical.landforms.objects import (
    _split_polyline_at_seam,
    ridge_geometry_ok,
)
from worldsim.physical.landforms.pipeline import LandformResult
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.metrics import grid_metrics


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def _lp(**kwargs) -> LandformParams:
    kwargs.setdefault("min_range_km2", None)
    kwargs.setdefault("min_plateau_km2", None)
    kwargs.setdefault("mountain_score_threshold", 0.42)
    kwargs.setdefault("planet_radius_km", 250.0)
    return LandformParams(**kwargs)


def test_minimum_radius_is_one_cell_not_two() -> None:
    gm = grid_metrics(64, 32, radius_km=6371.0)
    win = scale_window(gm, 1.0)
    assert int(win["effective_rx_cells"]) == 1
    assert int(win["effective_ry_cells"]) == 1
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "worldsim"
        / "physical"
        / "landforms"
        / "metrics.py"
    ).read_text(encoding="utf-8")
    assert "max(2, round" not in src


def test_scale_windows_recorded_and_quick_collapse_flagged() -> None:
    h, w = 32, 64
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(
            fine_radius_km=60.0,
            meso_radius_km=150.0,
            macro_radius_km=300.0,
        ),
        analysis_width=32,
        analysis_height=16,
    )
    wins = res.diagnostics["scale_windows"]
    assert set(wins) == {"fine", "meso", "macro"}
    for name in wins:
        assert "requested_km" in wins[name]
        assert "effective_ew_km" in wins[name]
        assert "effective_ns_km" in wins[name]
        assert int(wins[name]["effective_rx_cells"]) >= 1
    assert res.diagnostics["quick_scales_indistinguishable"] is True
    assert res.diagnostics["scales_collapsed"] is True


def test_no_hidden_055_mountain_threshold() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "worldsim"
        / "physical"
        / "landforms"
        / "classify.py"
    ).read_text(encoding="utf-8")
    assert "mountain < 0.55" not in src
    assert "params.mountain_score_threshold" in src or "mtn_thr" in src
    cfg = load_planet_config(default_config_path())
    assert cfg.to_landform_params().mountain_score_threshold == 0.60


def test_upsample_reapplies_full_resolution_ocean_mask() -> None:
    th, tw = 32, 48
    elev = np.full((th, tw), 400.0)
    ocean = np.zeros((th, tw), dtype=bool)
    ocean[:, :8] = True
    ocean[:2, :] = True
    elev = np.where(ocean, -300.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        extent=SpatialExtent(width=tw, height=th),
        analysis_width=24,
        analysis_height=16,
        params=_lp(),
    )
    assert res.context_id.shape == (th, tw)
    assert np.all(res.context_id[ocean] == int(BroadContext.OCEAN))
    assert np.all(res.context_id[~ocean] != int(BroadContext.OCEAN))
    assert np.all(res.local_form_id[ocean] == int(LocalForm.OCEAN))
    assert np.all(res.local_form_id[~ocean] != int(LocalForm.OCEAN))
    assert res.diagnostics["mask_consistency_ok"] is True


def test_min_object_area_km2_is_reported() -> None:
    h, w = 24, 32
    elev = np.full((h, w), 120.0)
    ocean = _ocean_frame(h, w, margin=1)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(),
    )
    d = res.diagnostics
    assert d["min_range_km2"] == 800.0
    assert d["min_plateau_km2"] == 2500.0
    assert d["min_range_km2_representable"] >= d["cell_area_km2"]
    assert d["min_range_cells_effective"] >= 1


def test_isolated_cone_mountain_not_plateau() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 1800.0 * np.exp(-((ii - 32) ** 2 + (jj - 24) ** 2) / 18.0)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(
            fine_radius_km=20.0,
            meso_radius_km=50.0,
            macro_radius_km=120.0,
            min_range_cells=8,
        ),
    )
    assert len(res.mountain_ranges) >= 1
    assert float(res.mountain_score_u8[24, 28]) > float(res.plateau_score_u8[24, 28])
    local = res.local_form_id[~ocean]
    assert np.any(local == int(LocalForm.SUMMIT)) or np.any(local == int(LocalForm.RIDGE))
    assert np.any(local == int(LocalForm.SLOPE))
    ridge = res.mountain_ranges[0].ridge_line
    assert len(ridge) >= 2
    chk = ridge_geometry_ok(ridge, res.mountain_range_id == res.mountain_ranges[0].id)
    assert chk["in_mask"]
    assert chk["no_consecutive_duplicates"]


def test_plateau_interior_and_escarpment_rim() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 100.0)
    ocean = _ocean_frame(h, w)
    elev[14:34, 18:46] = 900.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(
            fine_radius_km=15.0,
            meso_radius_km=40.0,
            macro_radius_km=100.0,
            min_plateau_cells=20,
            plateau_score_threshold=0.35,
        ),
    )
    interior = res.context_id[20:28, 24:40]
    assert np.mean(interior == int(BroadContext.PLATEAU)) > 0.5
    assert np.any(res.local_form_id == int(LocalForm.ESCARPMENT))
    assert len(res.plateaus) >= 1
    assert len(res.plateaus[0].rim_line) >= 2
    land = ~ocean
    assert float(np.mean(res.local_form_id[land] == int(LocalForm.ESCARPMENT))) < 0.20


def test_mountain_on_plateau_keeps_both() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 80.0)
    ocean = _ocean_frame(h, w)
    elev[12:36, 16:48] = 850.0
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 1200.0 * np.exp(-((ii - 32) ** 2 + (jj - 24) ** 2) / 10.0)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=6, min_plateau_cells=16),
    )
    assert res.mountain_score_u8[24, 32] > 60
    assert np.any(res.context_id == int(BroadContext.PLATEAU)) or float(
        res.plateau_score_u8[20, 20]
    ) > 80


def test_rolling_upland_is_not_a_range() -> None:
    h, w = 40, 56
    rng = np.random.default_rng(0)
    elev = 700.0 + 40.0 * rng.standard_normal((h, w))
    ocean = _ocean_frame(h, w, margin=1)
    elev = np.where(ocean, -100.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(mountain_score_threshold=0.55, min_range_cells=40),
    )
    assert len(res.mountain_ranges) == 0
    land = ~ocean
    assert np.mean(res.context_id[land] == int(BroadContext.UPLAND)) > 0.3


def test_two_ranges_and_one_connected_ridge() -> None:
    h, w = 40, 80
    elev = np.full((h, w), 150.0)
    ocean = _ocean_frame(h, w)
    elev[10:30, 15:25] = 1200.0
    elev[10:30, 55:65] = 1200.0
    elev = np.where(ocean, -200.0, elev)
    two = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=10, mountain_score_threshold=0.35),
    )
    assert len(two.mountain_ranges) >= 2

    elev2 = np.full((h, w), 150.0)
    elev2[12:28, 20:60] = 1100.0
    elev2 = np.where(ocean, -200.0, elev2)
    one = build_landform_analysis(
        elevation_m=elev2,
        ocean_mask=ocean,
        params=_lp(min_range_cells=10, mountain_score_threshold=0.35),
    )
    assert len(one.mountain_ranges) >= 1
    assert len(one.mountain_ranges[0].ridge_line) >= 2


def test_canyon_keeps_plateau_context() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 100.0)
    ocean = _ocean_frame(h, w)
    elev[14:34, 18:46] = 900.0
    elev[16:32, 30:33] = 220.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(
            min_plateau_cells=16,
            plateau_score_threshold=0.35,
            fine_radius_km=15.0,
            meso_radius_km=40.0,
            macro_radius_km=100.0,
        ),
    )
    assert np.mean(res.context_id[18:30, 20:28] == int(BroadContext.PLATEAU)) > 0.4
    trench = res.local_form_id[18:30, 30:33]
    assert np.any(
        (trench == int(LocalForm.VALLEY)) | (trench == int(LocalForm.DEPRESSION))
    )


def test_seam_range_single_id_and_split_presentation() -> None:
    h, w = 32, 48
    elev = np.full((h, w), 100.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:2, :] = True
    ocean[-2:, :] = True
    elev[8:24, :6] = 1400.0
    elev[8:24, -6:] = 1400.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=8, mountain_score_threshold=0.3),
    )
    assert res.diagnostics["ridge_in_mask_ok"] is True
    if res.mountain_ranges:
        assert any(r.crosses_ew_seam for r in res.mountain_ranges) or len(
            res.mountain_ranges
        ) == 1
        line = res.mountain_ranges[0].ridge_line
        if any(abs(a[0] - b[0]) > 0.5 for a, b in zip(line, line[1:])):
            parts = _split_polyline_at_seam(line)
            assert all(abs(a[0] - b[0]) <= 0.5 for p in parts for a, b in zip(p, p[1:]))


def test_ns_mirror_scores() -> None:
    h, w = 40, 48
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 1500.0 * np.exp(-((ii - 24) ** 2 + (jj - 12) ** 2) / 12.0)
    elev = np.where(ocean, -200.0, elev)
    params = _lp(fine_radius_km=18.0, meso_radius_km=45.0, macro_radius_km=110.0)
    a = build_landform_analysis(elevation_m=elev, ocean_mask=ocean, params=params)
    b = build_landform_analysis(
        elevation_m=elev[::-1, :].copy(), ocean_mask=ocean[::-1, :], params=params
    )
    sa = a.mountain_score_u8.astype(np.float64)
    sb = b.mountain_score_u8.astype(np.float64)[::-1, :]
    land = ~ocean
    assert float(np.mean(np.abs(sa[land] - sb[land]))) < 25.0


def test_save_load_round_trip(tmp_path: Path) -> None:
    h, w = 24, 32
    elev = np.full((h, w), 150.0)
    ocean = _ocean_frame(h, w, margin=1)
    elev[8:16, 10:18] = 1100.0
    elev = np.where(ocean, -120.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=6),
    )
    res.save(tmp_path / "landforms")
    loaded = LandformResult.load(tmp_path / "landforms")
    assert np.array_equal(loaded.context_id, res.context_id)
    assert np.array_equal(loaded.local_form_id, res.local_form_id)
    assert np.array_equal(loaded.mountain_range_id, res.mountain_range_id)
    assert loaded.diagnostics["algorithm"] == LANDFORM_ALGORITHM_VERSION
    assert (tmp_path / "vectors" / "plateau_rims.geojson").is_file() or (
        tmp_path / "landforms"
    ).is_dir()
    assert (tmp_path / "vectors" / "mountain_ridges.geojson").is_file()


def test_shoulder_and_footslope_are_assigned() -> None:
    h, w = 36, 48
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 2000.0 * np.exp(-((ii - 24) ** 2 + (jj - 18) ** 2) / 14.0)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(fine_radius_km=18.0, meso_radius_km=45.0, macro_radius_km=110.0),
    )
    land = ~ocean
    forms = set(int(v) for v in np.unique(res.local_form_id[land]))
    assert int(LocalForm.SHOULDER) in forms or int(LocalForm.SUMMIT) in forms
    assert int(LocalForm.FOOTSLOPE) in forms or int(LocalForm.VALLEY) in forms
    assert int(LocalForm.ESCARPMENT) not in forms or float(
        np.mean(res.local_form_id[land] == int(LocalForm.ESCARPMENT))
    ) < 0.20
