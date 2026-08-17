from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GODOT = ROOT / "godot"


def test_godot_project_skeleton_exists() -> None:
    assert (GODOT / "project.godot").is_file()
    assert (GODOT / "scenes" / "Main.tscn").is_file()
    assert (GODOT / "scenes" / "Main.gd").is_file()
    for rel in (
        "atlas/WorldAtlas.gd",
        "atlas/RasterLayerRenderer.gd",
        "atlas/VectorLayerRenderer.gd",
        "atlas/HexOverlayRenderer.gd",
        "atlas/MapModeController.gd",
        "atlas/InspectorPanel.gd",
        "atlas/TimelineController.gd",
        "simulation_bridge/SimulationRunner.gd",
        "simulation_bridge/SimulationProtocol.gd",
        "simulation_bridge/ProgressController.gd",
    ):
        assert (GODOT / rel).is_file(), rel
    main = (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    assert "TopBar" in main
    assert "BottomBar" in main
    assert "ModeBox" in main
    assert "ZoomSlider" in main
    assert "ZoomFitBtn" in main
    assert "AdvancedPopup" in main
    assert "AdvancedBtn" in main
    assert "ProfileOption" in main
    assert "Generate world" in main
    assert "OceanFractionSpin" in main
    assert "NumPlatesSpin" in main
    assert "DetailAmplitudeSpin" in main
    assert "ErosionIterSpin" in main
    assert "FluvialKSpin" in main
    assert "FoldingRatioSpin" in main
    assert "LandScaleSpin" in main
    assert "OrogenyBoostSpin" in main
    assert "SstMixSpin" in main
    assert "InlandDecaySpin" in main
    assert "MoistAdvectStepsSpin" in main
    assert "MoistLargeScaleSpin" in main
    assert "WesternWarmSpin" in main
    assert "FlowCheck" in main
    assert "CoastCheck" in main
    assert "RiversCheck" in main
    assert "LakesCheck" in main
    assert "HexCheck" in main
    assert "ModeOption" not in main
    assert "AdvancedToggle" not in main
    atlas = (GODOT / "atlas" / "WorldAtlas.gd").read_text(encoding="utf-8")
    assert "handle_map_gui_input" in atlas
    assert "zoom_in" in atlas
    assert "set_zoom_factor" in atlas
    assert "ZOOM_FACTOR_MAX := 16.0" in atlas
    assert "zoom_factor_changed" in atlas
    assert "set_vector_layers" in atlas
    hexes = (GODOT / "atlas" / "HexOverlayRenderer.gd").read_text(encoding="utf-8")
    assert "draw_multiline" in hexes
    assert "_hex_pixels_qr" in hexes
    assert "_lod_step" in hexes
    assert "HEX_WIDTH_SCREEN" in hexes
    assert "0.75" in hexes
    assert "0.3" in hexes or "Color(0.86, 0.88, 0.95, 0.3)" in hexes
    assert "code / 10.0" in hexes
    assert "cell_count" in hexes
    assert "has_counts" in hexes
    assert "No data" in hexes
    modes = (GODOT / "atlas" / "MapModeController.gd").read_text(encoding="utf-8")
    assert "shaded_relief" not in modes
    assert 'current_mode: String = "elevation"' in modes
    insp = (GODOT / "atlas" / "InspectorPanel.gd").read_text(encoding="utf-8")
    assert "_format_hex" in insp
    assert "temperature_annual_c" in insp
    assert "holdridge_id" in insp
    raster = (GODOT / "atlas" / "RasterLayerRenderer.gd").read_text(encoding="utf-8")
    assert "TEXTURE_FILTER_LINEAR" in raster
    assert "set_land_composite_active" in raster
    land = (GODOT / "atlas" / "LandLayerRenderer.gd").read_text(encoding="utf-8")
    assert "land_mask.png" in land
    assert "bathymetry.png" in land
    assert "ocean_tex" in (GODOT / "atlas" / "land_composite.gdshader").read_text(
        encoding="utf-8"
    )
    assert "land_mask" in (GODOT / "atlas" / "land_composite.gdshader").read_text(
        encoding="utf-8"
    )
    atlas_gd = (GODOT / "atlas" / "WorldAtlas.gd").read_text(encoding="utf-8")
    assert "FlowLayerRenderer" in atlas_gd or "set_flow_overlay" in atlas_gd
    assert "set_flow_overlay" in atlas_gd
    assert "FlowLayerRenderer" in (GODOT / "atlas" / "FlowLayerRenderer.gd").read_text(
        encoding="utf-8"
    ) or (GODOT / "atlas" / "FlowLayerRenderer.gd").is_file()
    vectors = (GODOT / "atlas" / "VectorLayerRenderer.gd").read_text(encoding="utf-8")
    assert "show_coast" in vectors
    assert "_rebuild_coast_from_land_mask" in vectors
    assert "_chain_and_smooth_coast" in vectors
    assert "_chaikin_open_px" in vectors
    assert "_smooth_lake_ring_px" in vectors
    assert "_ring_triangulates" in vectors
    assert "_laplacian_smooth_closed_px" in vectors
    land = (GODOT / "atlas" / "land_composite.gdshader").read_text(encoding="utf-8")
    assert "filter_linear" in land
    assert "mode_blur_texels" in land
    assert "edge_soft" in land
    assert "show_coast" in land
    assert "coast_width_px" in land
    assert "fwidth(raw)" in land
    assert "elev_overlay_strength" in land
    land_gd = (GODOT / "atlas" / "LandLayerRenderer.gd").read_text(encoding="utf-8")
    assert 'mode == "elevation"' in land_gd
    assert "style\", 2" in land_gd or "style', 2" in land_gd
    world = (GODOT / "atlas" / "WorldAtlas.gd").read_text(encoding="utf-8")
    assert "set_show_coast" in world
    assert "_shallow_water" in vectors
    assert "COAST_WIDTH_SCREEN" in vectors
    assert "_screen_to_world_width" in vectors
    assert "RIVER_WIDTH_MIN_SCREEN" in vectors
    assert "RIVER_WIDTH_MAX_SCREEN" in vectors
    assert "river_width_for_strahler" in vectors
    assert "river_width_for_feature" in vectors
    assert "_discharge_log_max" in vectors
    assert "_strahler_max" in vectors
    assert "_sanitize_polygon_ring" in vectors
    assert "from_lake_id" in vectors
    assert "1.0" in vectors  # opaque river/lake colors
    assert "WATER_ALPHA" not in vectors
    assert "RIVER_WIDTH_MOUTH" not in vectors
    assert "_to_pixel_polylines" in vectors
    assert "draw_polyline(pts, COAST_COLOR, coast_w, false)" in vectors
    assert "_screen_to_world_width" in vectors
    assert "_min_draw_length" in vectors
    # rivers drawn before lakes
    draw_idx = vectors.find("func _draw")
    rivers_draw = vectors.find("if show_rivers:", draw_idx)
    lakes_draw = vectors.find("if show_lakes:", draw_idx)
    assert draw_idx >= 0 and rivers_draw > draw_idx and lakes_draw > rivers_draw
    main_gd = (GODOT / "scenes" / "Main.gd").read_text(encoding="utf-8")
    assert "Atlas — default" in main_gd
    assert "vp_scale" in main_gd
    assert "world_seed" in main_gd
    assert "_write_planet_config" in main_gd
    assert "sst_mix" in main_gd
    assert "sst_inland_decay_km" in main_gd
    assert "moisture_advect_steps" in main_gd
    assert "folding_ratio" in main_gd
    assert "land_scale_m" in main_gd
    assert "orogeny_boost" in main_gd
    assert "base_temp_c" in main_gd
    assert "precip_scale_mm" in main_gd
    main_tscn = (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    assert "BaseTempSpin" in main_tscn
    assert "PrecipScaleSpin" in main_tscn
    assert "_generation_knobs" in main_gd
    assert "advanced_popup" in main_gd
    assert "_setup_mode_buttons" in main_gd
    assert "ZOOM_MAX" in main_gd
    assert "width: %d" in main_gd
    assert "PROFILE_QUICK" in main_gd
    assert "Vector2i(128, 64)" in main_gd
    runner = (GODOT / "simulation_bridge" / "SimulationRunner.gd").read_text(
        encoding="utf-8"
    )
    assert 'PROFILE_FULL := "full"' in runner
    assert 'generation_profile: String = PROFILE_ATLAS' in runner
    assert 'PROFILE_QUICK := "quick"' in runner
    assert '"--climate-width", "128"' in runner
    assert '"--config"' in runner
    assert "config_path" in runner
    assert "__main__.py" in runner  # prefer source worldsim over stale packaged worker
    # Full must not force reduced climate when demo_resolution was the old default.
    assert "demo_resolution" not in runner
    assert "master_seed" in runner
    coast_doc = ROOT / "docs" / "validation" / "atlas_coast_artefact.md"
    assert coast_doc.is_file()
    assert "presentation" in coast_doc.read_text(encoding="utf-8").lower()
    a4b_doc = ROOT / "docs" / "validation" / "milestone_a4b.md"
    assert a4b_doc.is_file()
    assert "0.58" in a4b_doc.read_text(encoding="utf-8")
    a6_doc = ROOT / "docs" / "validation" / "milestone_a6.md"
    assert a6_doc.is_file()
    assert "ocean" in a6_doc.read_text(encoding="utf-8").lower()
    a7_doc = ROOT / "docs" / "validation" / "milestone_a7.md"
    assert a7_doc.is_file()
    assert "flat-top" in a7_doc.read_text(encoding="utf-8").lower()
    a8_doc = ROOT / "docs" / "validation" / "milestone_a8.md"
    assert a8_doc.is_file()
    assert "holdridge" in a8_doc.read_text(encoding="utf-8").lower()
    b2_doc = ROOT / "docs" / "validation" / "milestone_b2.md"
    assert b2_doc.is_file()
    assert "top bar" in b2_doc.read_text(encoding="utf-8").lower()
    b4_doc = ROOT / "docs" / "validation" / "milestone_b4.md"
    assert b4_doc.is_file()
    assert "land" in b4_doc.read_text(encoding="utf-8").lower()


def test_project_declares_godot_47() -> None:
    text = (GODOT / "project.godot").read_text(encoding="utf-8")
    assert "4.7" in text
    assert "res://scenes/Main.tscn" in text
