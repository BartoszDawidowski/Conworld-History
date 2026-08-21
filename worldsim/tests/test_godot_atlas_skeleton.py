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
        "atlas/LegendPanel.gd",
        "atlas/LandformLayerRenderer.gd",
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
    assert "LandformCheck" in main
    assert "LegendPanel.gd" in main
    assert "LastWorldBtn" in main
    assert "InspectorTabs" in main
    assert '[node name="MapPane" type="Control"' in main
    assert "MapColumn" not in main
    assert "LegendRow" not in main
    assert "ZoomBox" in main
    assert "LegendHeader" in main
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
    assert '"biome_v2"' in modes
    assert '"landforms"' in modes
    insp = (GODOT / "atlas" / "InspectorPanel.gd").read_text(encoding="utf-8")
    assert "_format_hex" in insp
    assert "HEX_TAB_ORDER" in insp
    assert "temperature_annual_c" in insp
    assert "holdridge_id" in insp
    assert "biome_v2_dominant" in insp
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
    assert "set_landform_overlay" in atlas_gd
    assert "inspect_feature" in atlas_gd
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
    assert "spinup_max_years:" in main_gd
    assert "advect_max_substeps:" in main_gd
    assert "moisture_advect_steps" in main_gd
    assert "folding_ratio" in main_gd
    assert "land_scale_m" in main_gd
    assert "orogeny_boost" in main_gd
    assert "continentality_scale_km: 500.0" in main_gd
    assert "monsoon_regional_mean_km: 500.0" in main_gd
    assert "mountain_score_threshold:" in main_gd
    assert "river_acc_fraction: 0.10" in main_gd or "river_acc_fraction:" in main_gd
    assert "bed_loss_m3_per_km_month" in main_gd
    assert "_ensure_pc6_advanced_groups" in main_gd
    assert "Hydrology physics (PC6)" in main_gd
    assert "water_state" in vectors
    assert "func _lake_is_liquid" in vectors
    assert "fail-closed" in vectors
    assert "precip_scale_mm" in main_gd
    main_tscn = (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    assert "BaseTempSpin" in main_tscn
    assert "PrecipScaleSpin" in main_tscn
    assert "_generation_knobs" in main_gd
    assert "advanced_popup" in main_gd
    assert "_setup_mode_buttons" in main_gd
    assert "_on_last_world" in main_gd
    assert "_save_last_world" in main_gd
    assert "last_world_path.txt" in main_gd
    assert "_sync_landform_overlay_visibility" in main_gd
    legend_gd = (GODOT / "atlas" / "LegendPanel.gd").read_text(encoding="utf-8")
    assert "Always store body" in legend_gd
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


def test_godot_planet_config_yaml_loads() -> None:
    """Regression: _write_planet_config placeholder order must match YAML template."""
    import re
    from pathlib import Path as PyPath

    from worldsim.config import load_planet_config

    root = PyPath(__file__).resolve().parents[2]
    main = (root / "godot" / "scenes" / "Main.gd").read_text(encoding="utf-8")
    start = main.index('var text := """') + len('var text := """')
    end = main.index('""" % [', start)
    template = main[start:end]
    args_start = main.index('""" % [', start) + len('""" % [')
    args_end = main.index("\n\t]", args_start)
    args_block = main[args_start:args_end]
    specs = re.findall(r"%[.\d]*[sdif]", template)
    args = [
        line.strip().rstrip(",")
        for line in args_block.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    assert len(specs) == len(args)

    # Unique sentinels so a swapped argument cannot silently pass.
    knobs = {
        "ocean_fraction": 0.7111,
        "sst_mix": 0.2811,
        "sst_inland_decay_km": 1201.0,
        "western_warm_c": 2.21,
        "eastern_cool_c": 1.81,
        "num_plates": 7,
        "cycle_count": 3,
        "folding_ratio": 0.011,
        "tectonics_sea_level": 0.651,
        "tectonics_erosion_period": 101,
        "detail_amplitude": 0.021,
        "land_scale_m": 9001.0,
        "ocean_scale_m": 10001.0,
        "orogeny_boost": 0.051,
        "activity_relief": 0.251,
        "boundary_relief": 0.351,
        "erosion_iterations": 5,
        "thermal_kappa": 0.0811,
        "fluvial_k": 8.11,
        "stream_power_k": 12.11,
        "stream_power_iterations": 4,
        "micro_fill_max_depth_m": 25.1,
        "base_temp_c": 25.1,
        "precip_scale_mm": 201.0,
        "moisture_advect_steps": 32,
        "moisture_advect_wind_scale": 0.201,
        "moisture_large_scale_frac": 0.151,
        "moisture_orographic_frac": 0.851,
        "moisture_convective_scale": 2.01,
        "moisture_ocean_evap_rate": 1.41,
        "moisture_land_et_rate": 0.41,
        "moisture_continentality_dry": 0.41,
        "moisture_lee_dry": 0.121,
        "moisture_plume_strength": 0.181,
        "moisture_land_store_capacity": 8.1,
        "moisture_itcz_convective_scale": 1.21,
        "moisture_itcz_width_deg": 8.1,
        "moisture_monsoon_strength": 0.351,
        "moisture_monsoon_lat_band_max_abs_deg": 32.1,
        "moisture_spinup_max_years": 48,
        "moisture_spinup_tolerance_relative": 0.021,
        "river_acc_fraction": 0.0351,
        "river_min_catchment_km2": 501.0,
        "river_discharge_candidate_quantile": 0.51,
        "channel_q_min_m3s": 0.051,
        "bed_loss_m3_per_km_month": 200001.0,
        "fill_max_depth_m": 25.1,
        "lake_storage_spinup_years": 24,
        "lake_storage_spinup_tol": 0.011,
        "runoff_spinup_years": 64,
        "runoff_spinup_tol": 0.012,
        "snow_threshold_c": 0.1,
        "snow_band_c": 2.1,
        "melt_factor_per_c": 0.081,
        "max_snow_store": 40.1,
        "soil_capacity": 1.1,
        "mountain_score_threshold": 0.61,
        "plateau_score_threshold": 0.41,
        "min_range_km2": 801.0,
        "min_plateau_km2": 2501.0,
    }
    vals: list[float | int] = []
    for line in args:
        if line.startswith("analysis."):
            vals.append(256 if ".x" in line else 128)
        elif line.startswith("float(knobs"):
            vals.append(float(knobs[line.split('"')[1]]))
        elif line.startswith("int(knobs"):
            vals.append(int(knobs[line.split('"')[1]]))
        else:
            raise AssertionError(f"unknown arg line: {line}")
    yaml_text = template % tuple(vals)
    tmp = PyPath(__file__).resolve().parent / "_godot_planet_config_probe.yaml"
    tmp.write_text(yaml_text, encoding="utf-8")
    try:
        cfg = load_planet_config(tmp)
        assert cfg.moisture_spinup_max_years == 48
        assert cfg.hydrology_bed_loss_m3_per_km_month == 200001.0
        # Critical parity: thermal vs fluvial must not be swapped (audit 7a7e70e).
        assert abs(float(cfg.erosion_thermal_kappa) - 0.0811) < 1e-6
        assert abs(float(cfg.erosion_fluvial_k) - 8.11) < 1e-6
        assert abs(float(cfg.erosion_stream_power_k) - 12.11) < 1e-6
        assert abs(float(cfg.hydrology_river_acc_fraction) - 0.0351) < 1e-6
        assert abs(float(cfg.sst_mix) - 0.2811) < 1e-6
        assert abs(float(cfg.precip_scale_mm) - 201.0) < 1e-6
    finally:
        tmp.unlink(missing_ok=True)


def test_godot_erosion_knob_order_and_c10_ranges() -> None:
    """UI ranges must admit C10 grids; YAML thermal/fluvial order must match args."""
    main = (GODOT / "scenes" / "Main.gd").read_text(encoding="utf-8")
    tscn = (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    # Argument order after erosion_iterations must be thermal then fluvial.
    erosion_args = main.split('int(knobs["erosion_iterations"]),', 1)[1]
    thermal_idx = erosion_args.find('float(knobs["thermal_kappa"])')
    fluvial_idx = erosion_args.find('float(knobs["fluvial_k"])')
    assert 0 <= thermal_idx < fluvial_idx
    assert "thermal_kappa: %.4f" in main
    assert "fluvial_k: %.4f" in main
    # C10 ranges must be reachable from Advanced spins.
    assert '"thermal_kappa"' in main and "100.0" in main.split('"thermal_kappa"', 1)[1][:200]
    assert '"stream_power_k"' in main and "1500.0" in main.split('"stream_power_k"', 1)[1][:200]
    # sst_mix default 0.28 requires step ≤ 0.01 (was 0.05 → snapped to 0.30).
    sst_block = tscn.split('[node name="SstMixSpin"', 1)[1].split("[node name=", 1)[0]
    assert "step = 0.01" in sst_block
    assert "value = 0.28" in sst_block
    assert "snappedf" in main



def test_project_declares_godot_47() -> None:
    text = (GODOT / "project.godot").read_text(encoding="utf-8")
    assert "4.7" in text
    assert "res://scenes/Main.tscn" in text
