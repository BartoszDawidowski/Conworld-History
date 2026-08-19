"""C9.1.5 — plateau interior/rim, range split at saddles, honest area floors."""

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
from worldsim.physical.landforms.objects import (
    _mask_contour_ring,
    _plateau_steep_rim_line,
    _split_component_at_saddles,
    extract_mountain_ranges,
)
from worldsim.physical.landforms.params import effective_min_cells_honest


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def test_algorithm_version_and_frozen_thresholds() -> None:
    assert LANDFORM_ALGORITHM_VERSION == "pc5_landform_acceptance_v1"
    p = LandformParams()
    assert p.mountain_score_threshold == 0.60
    assert p.plateau_score_threshold == 0.40
    cfg = load_planet_config(default_config_path())
    lp = cfg.to_landform_params()
    assert lp.mountain_score_threshold == 0.60
    assert lp.plateau_score_threshold == 0.40
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "worldsim"
        / "physical"
        / "landforms"
        / "params.py"
    ).read_text(encoding="utf-8")
    assert "mountain_score_threshold: float = 0.60" in src
    assert "plateau_score_threshold: float = 0.40" in src


def test_min_plateau_km2_not_silently_raised_by_min_component() -> None:
    """Atlas-scale cell (~15.6e3 km²) must not become a 4-cell / 62e3 km² floor."""
    atlas_cell = 4.0 * np.pi * (6371.0**2) / (256.0 * 128.0)
    cells, meta = effective_min_cells_honest(
        min_km2=2500.0,
        min_cells=24,
        cell_area_km2=atlas_cell,
        min_component_cells=4,
    )
    assert cells == 1
    assert meta["honesty_ok"] is True
    assert meta["representable_ok"] is False
    assert abs(float(meta["configured_km2"]) - 2500.0) < 1e-6
    assert abs(float(meta["representable_km2"]) - atlas_cell) < 1.0
    assert float(meta["representable_km2"]) < 4.0 * atlas_cell * 0.99

    fine_cell = 61.0
    cells_f, meta_f = effective_min_cells_honest(
        min_km2=2500.0,
        min_cells=24,
        cell_area_km2=fine_cell,
        min_component_cells=4,
    )
    assert cells_f == int(np.ceil(2500.0 / fine_cell))
    assert meta_f["representable_ok"] is True
    assert meta_f["honesty_ok"] is True


def test_diagnostics_report_configured_vs_representable() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 100.0)
    ocean = _ocean_frame(h, w)
    elev[14:34, 18:46] = 900.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(),
    )
    d = res.diagnostics
    assert d["min_plateau_km2_configured"] == 2500.0
    assert d["min_plateau_km2_representable"] >= d["cell_area_km2"]
    assert "plateau_area_floor_honesty_ok" in d
    assert "min_plateau_km2_representable_ok" in d
    assert d["mountain_score_threshold"] == 0.60


def test_dumbbell_splits_into_child_ranges_sharing_system_id() -> None:
    h, w = 36, 64
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:2, :] = True
    ocean[-2:, :] = True
    elev = np.full((h, w), 80.0)
    elev[8:20, 8:20] = 1900.0
    elev[8:20, 40:52] = 1900.0
    elev[13, 20:40] = 420.0
    elev = np.where(ocean, -200.0, elev)
    score = np.zeros((h, w), dtype=np.float64)
    score[(~ocean) & (elev >= 400.0)] = 1.0
    plat = np.zeros((h, w), dtype=np.float64)
    relief = np.full((h, w), 400.0)
    conf = np.ones((h, w), dtype=np.float64)
    prov = np.zeros((h, w), dtype=np.uint8)
    params = LandformParams(
        min_range_km2=None,
        min_range_cells=8,
        min_component_cells=4,
        mountain_score_threshold=0.50,
    )
    _ids, ranges = extract_mountain_ranges(
        mountain_score=score,
        plateau_score=plat,
        elevation_m=elev,
        ocean_mask=ocean,
        provenance_id=prov,
        confidence=conf,
        relief_meso=relief,
        params=params,
        cell_area_km2=1.0,
    )
    assert len(ranges) >= 2
    systems = {int(r.system_id or r.id) for r in ranges}
    assert len(systems) == 1


def test_split_at_width_constriction_keeps_unsplit_when_children_too_small() -> None:
    mask = np.zeros((12, 24), dtype=bool)
    mask[5, 4:20] = True
    elev = np.full((12, 24), 800.0)
    kids = _split_component_at_saddles(mask, elev, min_child_cells=8)
    assert len(kids) == 1
    assert int(np.count_nonzero(kids[0])) == int(np.count_nonzero(mask))


def test_plateau_interior_is_not_escarpment() -> None:
    h, w = 48, 64
    elev = np.full((h, w), 100.0)
    ocean = _ocean_frame(h, w)
    elev[14:34, 18:46] = 900.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(
            min_range_km2=None,
            min_plateau_km2=None,
            mountain_score_threshold=0.42,
            planet_radius_km=250.0,
            fine_radius_km=15.0,
            meso_radius_km=40.0,
            macro_radius_km=100.0,
            min_plateau_cells=20,
            plateau_score_threshold=0.35,
        ),
    )
    plat = res.context_id == int(BroadContext.PLATEAU)
    interior = res.context_id[20:28, 24:40]
    assert np.mean(interior == int(BroadContext.PLATEAU)) > 0.5
    interior_local = res.local_form_id[20:28, 24:40]
    assert np.mean(interior_local == int(LocalForm.ESCARPMENT)) < 0.15
    assert float(res.diagnostics["plateau_interior_escarpment_fraction"]) < 0.15
    assert res.diagnostics["plateau_interior_not_escarpment_ok"] is True
    if np.any(plat):
        assert not np.all(res.local_form_id[plat] == int(LocalForm.ESCARPMENT))


def test_plateau_rim_is_not_filled_outline() -> None:
    h, w = 32, 48
    mask = np.zeros((h, w), dtype=bool)
    mask[8:24, 10:38] = True
    slope = np.full((h, w), 0.01)
    slope[23, 10:38] = 0.20
    slope[8, 10:38] = 0.01
    params = LandformParams()
    rim = _plateau_steep_rim_line(mask, slope, params)
    outline = _mask_contour_ring(mask)
    assert len(rim) >= 2
    assert len(outline) >= 4
    assert rim != outline


def test_production_block_plateau_not_escarpment_dominated() -> None:
    h, w = 48, 64
    ocean = _ocean_frame(h, w)
    elev = np.full((h, w), 100.0)
    elev[14:34, 18:46] = 900.0
    elev = np.where(ocean, -200.0, elev)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(),
    )
    assert res.diagnostics["calibrated"] is True
    assert res.diagnostics["plateau_interior_not_escarpment_ok"] is True
    assert float(res.diagnostics["plateau_interior_escarpment_fraction"]) < 0.15
    assert res.diagnostics["landforms_geometry_ok"] is True
    assert len(res.plateaus) >= 1
    if res.diagnostics["plateau_fraction_alarm"] or res.diagnostics[
        "mountain_fraction_alarm"
    ]:
        assert res.diagnostics["acceptance_ok"] is False
    else:
        assert res.diagnostics["acceptance_ok"] is True
