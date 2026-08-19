"""PC5 — landform representability, geometry, and catastrophe acceptance."""

from __future__ import annotations

import numpy as np
import pytest

from worldsim.physical.landforms import (
    LANDFORM_ALGORITHM_VERSION,
    LandformParams,
    build_landform_analysis,
)
from worldsim.physical.landforms.gates import (
    MAX_CANONICAL_MOUNTAIN_RANGES,
    canonical_extraction_min_cells,
    object_explosion_catastrophe,
)
from worldsim.physical.landforms.params import effective_min_cells_honest
from worldsim.validation.production_closure.fixtures import (
    landform_false_acceptance_on_object_explosion,
)

pytestmark = pytest.mark.pc5


def _ocean_frame(h: int, w: int, margin: int = 2) -> np.ndarray:
    ocean = np.ones((h, w), dtype=bool)
    ocean[margin : h - margin, margin : w - margin] = False
    return ocean


def test_pc5_algorithm_version() -> None:
    assert LANDFORM_ALGORITHM_VERSION == "pc5_landform_acceptance_v1"
    p = LandformParams()
    assert p.mountain_score_threshold == 0.60
    assert p.plateau_score_threshold == 0.40


def test_atlas_baseline_counts_trip_catastrophe_gate() -> None:
    probe = landform_false_acceptance_on_object_explosion()
    assert probe["mountain_range_count"] > MAX_CANONICAL_MOUNTAIN_RANGES
    assert probe["object_explosion_catastrophe"]
    assert probe["pc5_gates_would_fail"]


def test_coarse_grid_refuses_one_cell_canonical_ranges() -> None:
    """Atlas-scale cells must not mint hundreds of 1-cell MountainRange objects."""
    h, w = 32, 48
    elev = np.full((h, w), 120.0)
    ocean = _ocean_frame(h, w)
    rng = np.random.default_rng(7)
    land = ~ocean
    score_cells = rng.choice(np.flatnonzero(land), size=80, replace=False)
    elev_flat = elev.ravel()
    for idx in score_cells:
        elev_flat[idx] = 2200.0 + rng.normal(0, 40.0)
    elev = elev_flat.reshape(h, w)
    elev = np.where(ocean, -200.0, elev)
    atlas_cell = 4.0 * np.pi * (6371.0**2) / (256.0 * 128.0)
    res = build_landform_analysis(
        elevation_m=elev,
        ocean_mask=ocean,
        params=LandformParams(
            planet_radius_km=6371.0,
            min_range_km2=800.0,
            min_plateau_km2=2500.0,
            min_component_cells=4,
        ),
    )
    d = res.diagnostics
    assert d["min_plateau_km2_representable_ok"] is False
    assert int(d["mountain_range_count"]) < 80
    assert d["landforms_representability_ok"] is True
    assert d["object_count_catastrophe_ok"] is True


def test_catastrophe_counts_fail_acceptance() -> None:
    from worldsim.physical.landforms.gates import landform_acceptance_gates

    gates = landform_acceptance_gates(
        structural_ok=True,
        calibrated=True,
        mask_ok=True,
        local_coverage_ok=True,
        ridge_in_mask_ok=True,
        ridge_no_duplicate_ok=True,
        plateau_honesty_ok=True,
        plateau_interior_ok=True,
        escarpment_dominance_ok=True,
        mountain_fraction_ok=True,
        mountain_fraction_alarm=False,
        plateau_fraction_alarm=False,
        plateau_context_escarpment_ok=False,
        representability_ok=True,
        ridge_coverage_ok=True,
        plateau_rim_valid_ok=True,
        object_count_catastrophe_ok=False,
        zero_semantic_objects_ok=True,
    )
    assert gates["acceptance_ok"] is False
    assert gates["object_count_catastrophe_ok"] is False


def test_synthetic_plateau_passes_pc5_geometry_gates() -> None:
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
    assert d["landforms_geometry_ok"] is True
    assert d["plateau_interior_not_escarpment_ok"] is True
    assert d["ridge_coverage_ok"] is True
    assert d["object_count_catastrophe_ok"] is True
    if d["plateau_fraction_alarm"] or d["mountain_fraction_alarm"]:
        assert d["acceptance_ok"] is False
    else:
        assert d["acceptance_ok"] is True


def test_extraction_floor_when_km2_not_representable() -> None:
    atlas_cell = 4.0 * np.pi * (6371.0**2) / (256.0 * 128.0)
    cells, meta = effective_min_cells_honest(
        min_km2=800.0,
        min_cells=12,
        cell_area_km2=atlas_cell,
        min_component_cells=4,
    )
    assert cells == 1
    assert meta["representable_ok"] is False
    extraction = canonical_extraction_min_cells(
        floor_cells=cells,
        representable_ok=False,
        min_component_cells=4,
    )
    assert extraction == 4
