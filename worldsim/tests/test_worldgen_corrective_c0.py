"""C0 — product-contract hotfixes: lake schema, fail-closed draw, BiomeV2 units."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from worldsim.export.atlas_display import ATLAS_DISPLAY_SCHEMA, export_atlas_display
from worldsim.physical.ecology.biome_v2 import classify_biome_v2
from worldsim.physical.hydrology.lakes_meta import (
    LAKE_VECTOR_SCHEMA,
    atlas_lake_is_liquid,
    derive_lake_axes,
)
from worldsim.physical.vectorize.indexes import SpatialIndex
from worldsim.physical.vectorize.lakes import Lake, lake_atlas_properties
from worldsim.physical.vectorize.rivers import RiverNetwork, RiverNode, RiverSegment
from worldsim.spatial.extent import SpatialExtent
from worldsim.spatial.manifest import WORLD_MODEL_SCHEMA_VERSION
from worldsim.spatial.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[2]


def _square_lake(*, lid: int, basin_id: int, water_state: str) -> Lake:
    return Lake(
        id=lid,
        polygon=[
            (0.10, 0.10),
            (0.20, 0.10),
            (0.20, 0.20),
            (0.10, 0.20),
            (0.10, 0.10),
        ],
        surface_elevation=40.0,
        basin_id=basin_id,
        water_state=water_state,
        closed_basin=water_state != "open",
        area_cells=4,
    )


def test_world_model_schema_is_v3_for_lake_identity() -> None:
    assert WORLD_MODEL_SCHEMA_VERSION == 3
    assert LAKE_VECTOR_SCHEMA == "lake_vector_v1"
    assert ATLAS_DISPLAY_SCHEMA == "atlas_display_v2"


def test_lake_axes_round_trip_from_legacy_water_state() -> None:
    open_axes = derive_lake_axes(water_state="open", closed_basin=False)
    assert open_axes["outlet_type"] == "open_lake"
    assert open_axes["hydroperiod"] == "permanent"
    assert open_axes["ice_regime"] == "normally_liquid"
    assert open_axes["water_state"] == "open"

    playa = derive_lake_axes(water_state="seasonal_or_playa", closed_basin=True)
    assert playa["outlet_type"] == "closed_endorheic"
    assert playa["hydroperiod"] == "ephemeral_or_dry"
    assert playa["water_state"] == "seasonal_or_playa"

    frozen = derive_lake_axes(water_state="frozen_or_ice_covered", closed_basin=True)
    assert frozen["ice_regime"] == "perennially_frozen"
    assert frozen["water_state"] == "frozen_or_ice_covered"


def test_atlas_lake_is_liquid_fail_closed_missing_state() -> None:
    assert atlas_lake_is_liquid({}) is False
    assert atlas_lake_is_liquid({"id": 1, "closed_basin": True}) is False
    assert atlas_lake_is_liquid({"water_state": ""}) is False
    assert atlas_lake_is_liquid({"water_state": "open"}) is True
    assert atlas_lake_is_liquid({"water_state": "endorheic"}) is True
    assert atlas_lake_is_liquid({"water_state": "seasonal_or_playa"}) is False
    assert atlas_lake_is_liquid({"water_state": "frozen_or_ice_covered"}) is False


def test_atlas_export_preserves_lake_state_axes(tmp_path: Path) -> None:
    from test_atlas_export import _model

    model = _model()
    fixtures = [
        _square_lake(lid=1, basin_id=10, water_state="open"),
        _square_lake(lid=2, basin_id=11, water_state="endorheic"),
        _square_lake(lid=3, basin_id=12, water_state="seasonal_or_playa"),
        _square_lake(lid=4, basin_id=13, water_state="frozen_or_ice_covered"),
    ]
    model.vectors.lakes = fixtures
    out = tmp_path / "atlas_display"
    meta = export_atlas_display(model, out)
    assert meta["schema"] == "atlas_display_v2"
    assert meta["lake_vector_schema"] == LAKE_VECTOR_SCHEMA
    payload = json.loads((out / "lakes.geojson").read_text(encoding="utf-8"))
    assert payload["lake_vector_schema"] == LAKE_VECTOR_SCHEMA
    by_id = {int(f["properties"]["id"]): f["properties"] for f in payload["features"]}
    required = {
        "water_state",
        "outlet_type",
        "hydroperiod",
        "ice_regime",
        "feature_id",
        "water_body_id",
        "basin_id",
        "closed_basin",
    }
    for lid in (1, 2, 3, 4):
        props = by_id[lid]
        assert required.issubset(props.keys())
    assert atlas_lake_is_liquid(by_id[1]) is True
    assert atlas_lake_is_liquid(by_id[2]) is True
    assert atlas_lake_is_liquid(by_id[3]) is False
    assert atlas_lake_is_liquid(by_id[4]) is False
    assert by_id[1]["feature_id"] == 10
    assert by_id[1]["water_body_id"] == 1
    assert by_id[3]["water_body_id"] == 0
    assert by_id[4]["water_body_id"] == 0


def test_godot_renderer_fail_closed_missing_state() -> None:
    src = (ROOT / "godot" / "atlas" / "VectorLayerRenderer.gd").read_text(
        encoding="utf-8"
    )
    assert "func _lake_is_liquid" in src
    assert "push_warning" in src
    assert "fail-closed" in src
    # Legacy fail-open: empty state was treated as liquid.
    assert 'if state != "" and state != "open"' not in src
    assert 'poly.get("water_state", "")' in src


def test_biome_v2_balanced_monthly_p_pet_zero_deficit() -> None:
    h, w = 4, 6
    ocean = np.zeros((h, w), dtype=bool)
    temp = np.full((12, h, w), 12.0)
    scale = 200.0
    pet_m = 58.93 * 12.0 / 12.0
    precip = np.full((12, h, w), pet_m / scale)
    out = classify_biome_v2(
        temperature_c=temp,
        precipitation=precip,
        ocean_mask=ocean,
        precip_scale_mm=scale,
    )
    assert np.allclose(out["water_deficit_mm"], 0.0, atol=1e-6)
    annual = precip.sum(axis=0) * scale
    assert np.allclose(out["precipitation_annual_mm"], annual, atol=1e-9)
    # Factor-of-12 regression (dividing monthly P by n_m again) would leave ~11/12 of PET.
    annual_pet = pet_m * 12.0
    assert float(out["water_deficit_mm"][0, 0]) < 0.01 * annual_pet


def test_biome_v2_factor_of_twelve_guard() -> None:
    """A deliberate / n_m on monthly precip must not be the production formula."""
    src = (
        ROOT
        / "worldsim"
        / "src"
        / "worldsim"
        / "physical"
        / "ecology"
        / "biome_v2.py"
    ).read_text(encoding="utf-8")
    assert "precip * float(precip_scale_mm) / n_m" not in src
    assert "precip_mm_m = precip * float(precip_scale_mm)" in src


def test_vector_store_river_lake_relationship_roundtrip(tmp_path: Path) -> None:
    extent = SpatialExtent.from_shape(8, 8)
    lake = _square_lake(lid=7, basin_id=3, water_state="open")
    node = RiverNode(
        id=1,
        x=0.15,
        y=0.15,
        type="lake_outlet",
        row=2,
        col=2,
        lake_id=7,
    )
    segment = RiverSegment(
        id=9,
        from_node=1,
        to_node=2,
        geometry=[(0.15, 0.15), (0.40, 0.15)],
        strahler_order=2,
        mean_discharge=12.5,
        monthly_discharge=[1.0] * 12,
        basin_id=3,
        length=0.25,
        from_lake_id=7,
        to_lake_id=4,
    )
    store = VectorStore(
        extent=extent,
        rivers=RiverNetwork(nodes=[node], segments=[segment]),
        lakes=[lake],
        spatial_index=SpatialIndex(),
    )
    store.save(tmp_path)
    loaded = VectorStore.load(tmp_path)
    assert loaded.rivers.nodes[0].lake_id == 7
    assert loaded.rivers.segments[0].from_lake_id == 7
    assert loaded.rivers.segments[0].to_lake_id == 4
    assert loaded.lakes[0].id == 7
    assert loaded.lakes[0].feature_id == 3
    assert loaded.lakes[0].water_body_id == 7
    assert loaded.lakes[0].water_state == "open"
    assert loaded.lakes[0].outlet_type == "open_lake"


def test_cr6_cr9_notes_are_not_accepted_without_atlas() -> None:
    for name in ("cr6", "cr7", "cr8", "cr9"):
        path = ROOT / "docs" / "validation" / f"physical_realism_{name}.md"
        text = path.read_text(encoding="utf-8")
        status_lines = [
            line for line in text.splitlines()[:12] if line.startswith("**Status:**")
        ]
        assert status_lines, path
        assert "✅ **Accepted**" not in status_lines[0]
        assert "CORRECTION REQUIRED" in status_lines[0]


def test_lake_atlas_properties_include_identity() -> None:
    lake = _square_lake(lid=5, basin_id=8, water_state="endorheic")
    props = lake_atlas_properties(lake)
    assert "polygon" not in props
    assert props["feature_id"] == 8
    assert props["water_body_id"] == 5
    assert props["hydroperiod"] == "permanent"
    assert atlas_lake_is_liquid(props) is True
