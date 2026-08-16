from __future__ import annotations

import importlib.util
from pathlib import Path

from worldsim.environment_timeline import (
    ENVIRONMENT_TIMELINE_SCHEMA_VERSION,
    EnvironmentalAnomaly,
    SpatialScope,
    build_environment_timeline,
)


def _small_bundle():
    path = Path(__file__).resolve().parent / "test_world_spatial_model.py"
    spec = importlib.util.spec_from_file_location("_wsm_helpers", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._small_bundle()


def test_baseline_and_time_indexed_queries(tmp_path: Path) -> None:
    model, climate, _m, _e = _small_bundle()
    tl = build_environment_timeline(model)
    model.attach_environment_timeline(tl)

    x, y = climate.extent.cell_center_xy(10, 8)
    base = model.environment_at(x, y)
    assert base["source"] == "baseline"
    assert base["modifiers"]["temperature_offset_c"] == 0.0

    t0 = model.sample_climate(x, y, 0)
    # Same API with year but no anomalies yet → same temperature
    assert model.sample_climate(x, y, 0, year=-4000) == t0

    tl.add_anomaly(
        EnvironmentalAnomaly(
            id="holocene_warm_pulse",
            kind="temperature_offset",
            year_start=-5000,
            year_end=-3000,
            temperature_offset_c=2.5,
            precipitation_scale=0.9,
            sea_level_delta_m=1.0,
            scope=SpatialScope(),  # global
            notes="scaffold test anomaly",
        )
    )

    warm = model.environment_at(x, y, year=-4000)
    assert warm["source"] == "baseline+anomalies"
    assert warm["modifiers"]["temperature_offset_c"] == 2.5
    assert abs(float(warm["temperature_c_month0"]) - (t0 + 2.5)) < 1e-9
    assert abs(model.sample_climate(x, y, 0, year=-4000) - (t0 + 2.5)) < 1e-9

    # Outside anomaly years → baseline
    cold = model.environment_at(x, y, year=-10000)
    assert cold["modifiers"]["temperature_offset_c"] == 0.0
    assert abs(model.sample_climate(x, y, 0, year=-10000) - t0) < 1e-9

    elev0 = model.sample_elevation(x, y)
    elev_sl = model.sample_elevation(x, y, year=-4000)
    assert abs(elev_sl - (elev0 - 1.0)) < 1e-9


def test_timeline_round_trip_preserves_world_model(tmp_path: Path) -> None:
    model, climate, _m, _e = _small_bundle()
    tl = build_environment_timeline(model)
    tl.add_anomaly(
        EnvironmentalAnomaly(
            id="regional_dry",
            kind="precipitation_scale",
            year_start=-2000,
            year_end=-1000,
            precipitation_scale=0.5,
            scope=SpatialScope(x0=0.0, x1=0.5, y0=-0.5, y1=0.5),
        )
    )
    model.attach_environment_timeline(tl)
    root = tmp_path / "world"
    model.save(root)
    assert (root / "timeline" / "environment" / "timeline_manifest.json").is_file()
    assert (root / "timeline" / "environment" / "baseline.json").is_file()

    loaded = type(model).load(root)
    assert loaded.environment_timeline is not None
    assert loaded.environment_timeline.schema_version == ENVIRONMENT_TIMELINE_SCHEMA_VERSION
    assert len(loaded.environment_timeline.anomalies) == 1
    # WorldSpatialModel unchanged structurally
    assert loaded.hex_grid.n_cells == model.hex_grid.n_cells
    x, y = climate.extent.cell_center_xy(5, 5)
    assert "elevation_m" in loaded.environment_at(x, y)
    assert "modifiers" in loaded.environment_at(x, y, year=-1500)


def test_scoped_anomaly_does_not_apply_outside_bbox() -> None:
    model, climate, _m, _e = _small_bundle()
    tl = build_environment_timeline(model)
    model.attach_environment_timeline(tl)
    tl.add_anomaly(
        EnvironmentalAnomaly(
            id="local",
            kind="temperature_offset",
            year_start=0,
            year_end=100,
            temperature_offset_c=10.0,
            scope=SpatialScope(x0=0.0, x1=0.1, y0=-0.1, y1=0.1),
        )
    )
    inside = model.sample_climate(0.05, 0.0, 0, year=50)
    outside = model.sample_climate(0.9, 0.0, 0, year=50)
    base_out = model.sample_climate(0.9, 0.0, 0)
    assert abs(inside - (model.sample_climate(0.05, 0.0, 0) + 10.0)) < 1e-9
    assert abs(outside - base_out) < 1e-9
