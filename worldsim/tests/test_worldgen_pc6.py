"""PC6 — canonical products, effective config, Godot inspector contract."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.effective_config import (
    EFFECTIVE_CONFIG_SCHEMA_VERSION,
    build_effective_config,
    effective_config_checksum,
    write_effective_config,
)
from worldsim.export import export_atlas_display
from worldsim.spatial.canonical_acceptance import climate_summary_from_report
from worldsim.spatial.product_contracts import (
    INSPECTOR_CONTRACT_VERSION,
    PRODUCT_CONTRACT_VERSION,
)
from worldsim.validation.production_closure.product_parity import (
    hex_contract_parity,
    reexport_parity_probe,
    save_load_parity_probe,
    tier_mask_counts,
)

pytestmark = pytest.mark.pc6


def test_effective_config_schema_and_checksum(tmp_path: Path) -> None:
    config = load_planet_config(default_config_path())
    payload = build_effective_config(
        config=config,
        master_seed=183716,
        grids={"climate": [64, 32], "hex": [32, 16]},
        run_metadata={"stage": "world"},
    )
    assert payload["effective_config_schema_version"] == EFFECTIVE_CONFIG_SCHEMA_VERSION
    assert "precip_scale_mm" not in payload["display_only_lod"]
    assert float(payload["physical_groups"]["ecology_physics"]["precip_scale_mm"]) == float(
        config.precip_scale_mm
    )
    assert float(payload["physical_groups"]["hydrology_physics"]["precip_scale_mm"]) == float(
        config.precip_scale_mm
    )
    checksum = write_effective_config(tmp_path / "effective_config.json", payload)
    saved = json.loads((tmp_path / "effective_config.json").read_text(encoding="utf-8"))
    assert saved["effective_config_checksum"] == checksum
    assert checksum == effective_config_checksum(payload)


def test_tier_masks_save_load_and_reexport(tmp_path: Path) -> None:
    from test_worldgen_corrective_c8 import _bundle

    model, *_rest = _bundle()
    h, w = np.asarray(model.rasters.get("climate/elevation_m")).shape
    land = ~np.asarray(model.rasters.get("climate/ocean_mask")).astype(bool)
    ys, xs = np.where(land)
    physical = np.zeros((h, w), dtype=np.uint8)
    geo = np.zeros((h, w), dtype=np.uint8)
    display = np.zeros((h, w), dtype=np.uint8)
    flow = np.zeros((h, w), dtype=np.float64)
    if ys.size >= 3:
        physical[ys[0], xs[0]] = 1
        geo[ys[0], xs[0]] = geo[ys[1], xs[1]] = 1
        display[ys[0], xs[0]] = display[ys[1], xs[1]] = display[ys[2], xs[2]] = 1
        flow[land] = np.arange(int(np.count_nonzero(land)), dtype=np.float64) + 1.0
    model.rasters.put("hydrology/channel_mask", physical)
    model.rasters.put("hydrology/geomorphic_channel_mask", geo)
    model.rasters.put("hydrology/display_river_mask", display)
    model.rasters.put("hydrology/flow_accumulation", flow)

    before = tier_mask_counts(model)
    assert before["hydrology/display_river_mask"] >= 0

    probe = save_load_parity_probe(model, tmp_path / "world")
    assert probe["product_contract_version"] == PRODUCT_CONTRACT_VERSION
    assert probe["raster_parity_ok"]
    assert probe["tier_counts_before"] == probe["tier_counts_after"]

    export_probe = reexport_parity_probe(model, tmp_path / "atlas")
    assert export_probe["inspector_contract_version"] == INSPECTOR_CONTRACT_VERSION
    assert export_probe["hex_contract_fields_ok"]
    assert "log_catchment" in export_probe["diagnostic_layer_ids"]


def test_climate_summary_inspector_status_row() -> None:
    report = {
        "gates": {
            "moisture_spinup_ok": True,
            "moisture_budget_ok": True,
            "hydrology_ok": False,
            "erosion_or_fluvial_ok": False,
            "landforms_ok": False,
        },
        "failed_gates": ["hydrology_ok", "erosion_or_fluvial_ok", "landforms_ok"],
        "overall_acceptance_ok": False,
    }
    summary = climate_summary_from_report(report, snow_firn_ok=False)
    assert summary["inspector_contract_version"] == INSPECTOR_CONTRACT_VERSION
    status = summary["inspector_status"]
    assert status["moisture_ok"] is True
    assert status["snow_firn_ok"] is False
    assert status["hydrology_ok"] is False
    assert status["erosion_ok"] is False
    assert status["landforms_warning"] is True


def test_hex_contract_parity_on_c8_bundle() -> None:
    from test_worldgen_corrective_c8 import _bundle

    model, *_rest = _bundle()
    parity = hex_contract_parity(model)
    assert parity["ok"]
    assert parity["contract_version"] == PRODUCT_CONTRACT_VERSION


def test_godot_inspector_reads_inspector_status() -> None:
    root = Path(__file__).resolve().parents[2]
    panel = (root / "godot" / "atlas" / "InspectorPanel.gd").read_text(encoding="utf-8")
    assert "inspector_status" in panel
    assert "Snow/Firn" in panel
    assert "_mark_landforms" in panel


def test_godot_main_loads_effective_config() -> None:
    root = Path(__file__).resolve().parents[2]
    main = (root / "godot" / "scenes" / "Main.gd").read_text(encoding="utf-8")
    assert "_load_effective_config" in main
    assert "effective_config.json" in main
    assert "_ensure_pc6_advanced_groups" in main
    assert "Hydrology physics (PC6)" in main
    assert "_sync_advanced_from_effective_config" in main
    assert "bed_loss_m3_per_km_month" in main
    assert "lake_storage_spinup_years" in main


def test_g0_cryosphere_rasters_persist(tmp_path: Path) -> None:
    from test_worldgen_corrective_c8 import _bundle

    model, *_rest = _bundle()
    h, w = np.asarray(model.rasters.get("climate/elevation_m")).shape
    model.rasters.put("cryosphere/seasonal_snow_swe", np.ones((h, w), dtype=np.float32))
    model.rasters.put("cryosphere/firn_swe", np.zeros((h, w), dtype=np.float32))
    model.rasters.put("cryosphere/soil_water", np.full((h, w), 0.5, dtype=np.float32))
    probe = save_load_parity_probe(model, tmp_path / "world")
    for key in (
        "cryosphere/seasonal_snow_swe",
        "cryosphere/firn_swe",
        "cryosphere/soil_water",
    ):
        assert probe["raster_parity"].get(key, False)

    from test_worldgen_corrective_c8 import _bundle

    model, *_rest = _bundle()
    export_atlas_display(model, tmp_path)
    summary = json.loads((tmp_path / "climate_summary.json").read_text(encoding="utf-8"))
    assert "inspector_status" in summary
    assert "inspector_contract_version" in summary
