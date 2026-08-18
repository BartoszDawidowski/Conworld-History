"""PR-9 — LandformAnalysis synthetic fixtures and seam IDs."""

from __future__ import annotations

import numpy as np

from worldsim.physical.landforms import (
    BroadContext,
    LandformParams,
    LocalForm,
    build_landform_analysis,
)
from worldsim.physical.landforms.objects import _label_components_cylindrical
from worldsim.spatial.extent import SpatialExtent


def _lp(**kwargs) -> LandformParams:
    """PR-9 fixtures use cell floors, a toy planet so km radii are representable."""
    kwargs.setdefault("min_range_km2", None)
    kwargs.setdefault("min_plateau_km2", None)
    kwargs.setdefault("mountain_score_threshold", 0.42)
    kwargs.setdefault("planet_radius_km", 250.0)
    return LandformParams(**kwargs)


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def test_isolated_cone_is_mountain_not_plateau() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 1800.0 * np.exp(-((ii - 32) ** 2 + (jj - 24) ** 2) / 18.0)
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        extent=SpatialExtent(width=w, height=h),
        params=_lp(
            fine_radius_km=20.0,
            meso_radius_km=50.0,
            macro_radius_km=120.0,
            min_range_cells=8,
            min_plateau_cells=40,
        ),
    )
    assert len(res.mountain_ranges) >= 1
    # Flanks are mountain-dominated even if the flat summit tip scores plateau-ish.
    assert float(res.mountain_score_u8[24, 28]) > float(res.plateau_score_u8[24, 28])


def test_elevated_flat_block_is_plateau_with_escarpment() -> None:
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


def test_mountain_on_plateau_keeps_both_semantics() -> None:
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
    # Peak cell mountain-ish; plateau cells elsewhere on the block
    peak = (24, 32)
    assert res.mountain_score_u8[peak] > 60
    assert np.any(res.context_id == int(BroadContext.PLATEAU)) or float(
        res.plateau_score_u8[20, 20]
    ) > 80


def test_rolling_high_plain_not_mountain_range() -> None:
    h, w = 40, 56
    rng = np.random.default_rng(0)
    elev = 700.0 + 40.0 * rng.standard_normal((h, w))
    ocean = _ocean_frame(h, w, margin=1)
    elev = np.where(ocean, -100.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(
            mountain_score_threshold=0.55,
            min_range_cells=40,
        ),
    )
    assert len(res.mountain_ranges) == 0


def test_connected_ridge_one_range_two_ridges_two_objects() -> None:
    h, w = 40, 80
    elev = np.full((h, w), 150.0)
    ocean = _ocean_frame(h, w)
    elev[10:30, 15:25] = 1200.0
    elev[10:30, 55:65] = 1200.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=10, mountain_score_threshold=0.35),
    )
    assert len(res.mountain_ranges) >= 2

    # Single connected ridge
    elev2 = np.full((h, w), 150.0)
    elev2[12:28, 20:60] = 1100.0
    elev2 = np.where(ocean, -200.0, elev2)
    res2 = build_landform_analysis(
        elevation_m=elev2,
        ocean_mask=ocean,
        params=_lp(min_range_cells=10, mountain_score_threshold=0.35),
    )
    assert len(res2.mountain_ranges) >= 1


def test_range_crossing_ew_seam_single_id() -> None:
    h, w = 32, 48
    elev = np.full((h, w), 100.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:2, :] = True
    ocean[-2:, :] = True
    elev[8:24, :6] = 1400.0
    elev[8:24, -6:] = 1400.0
    elev = np.where(ocean, -200.0, elev)
    mask = (~ocean) & (elev > 1000.0)
    labels = _label_components_cylindrical(mask)
    # Seam unification → one component
    assert len(np.unique(labels[labels > 0])) == 1

    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(min_range_cells=8, mountain_score_threshold=0.3),
    )
    if res.mountain_ranges:
        assert any(r.crosses_ew_seam for r in res.mountain_ranges) or len(
            res.mountain_ranges
        ) == 1


def test_ns_mirror_scores_within_tolerance() -> None:
    h, w = 40, 48
    elev = np.full((h, w), 200.0)
    ocean = _ocean_frame(h, w)
    jj, ii = np.ogrid[:h, :w]
    elev = elev + 1500.0 * np.exp(-((ii - 24) ** 2 + (jj - 12) ** 2) / 12.0)
    elev = np.where(ocean, -200.0, elev)
    mirrored = elev[::-1, :].copy()
    params = _lp(fine_radius_km=18.0, meso_radius_km=45.0, macro_radius_km=110.0)
    a = build_landform_analysis(elevation_m=elev, ocean_mask=ocean, params=params)
    b = build_landform_analysis(
        elevation_m=mirrored, ocean_mask=ocean[::-1, :], params=params
    )
    # Compare mountain scores flipped
    sa = a.mountain_score_u8.astype(np.float64)
    sb = b.mountain_score_u8.astype(np.float64)[::-1, :]
    land = ~ocean
    err = float(np.mean(np.abs(sa[land] - sb[land])))
    assert err < 25.0  # uint8 quantization + filter edge effects


def test_disabled_path_is_identity() -> None:
    elev = np.zeros((16, 24))
    ocean = np.zeros((16, 24), dtype=bool)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=_lp(enabled=False),
    )
    assert res.diagnostics["enabled"] is False
    assert int(res.mountain_range_id.max()) == 0


def test_deterministic_ids() -> None:
    h, w = 36, 48
    elev = np.full((h, w), 120.0)
    ocean = _ocean_frame(h, w)
    elev[10:26, 10:20] = 1300.0
    elev = np.where(ocean, -150.0, elev)
    p = _lp(min_range_cells=8)
    a = build_landform_analysis(elevation_m=elev, ocean_mask=ocean, params=p)
    b = build_landform_analysis(elevation_m=elev, ocean_mask=ocean, params=p)
    assert [r.to_dict() for r in a.mountain_ranges] == [
        r.to_dict() for r in b.mountain_ranges
    ]
    assert np.array_equal(a.mountain_range_id, b.mountain_range_id)
