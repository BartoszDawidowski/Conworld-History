extends Control
## Main atlas shell (Plan B2): top/bottom chrome, left inspector, Advanced popup.

const WorldAtlasScr = preload("res://atlas/WorldAtlas.gd")
const SimulationRunnerScr = preload("res://simulation_bridge/SimulationRunner.gd")
const ProgressControllerScr = preload("res://simulation_bridge/ProgressController.gd")
const MapModeControllerScr = preload("res://atlas/MapModeController.gd")
const TimelineControllerScr = preload("res://atlas/TimelineController.gd")
const SimulationProtocolScr = preload("res://simulation_bridge/SimulationProtocol.gd")

const ZOOM_MIN := 1.0
const ZOOM_MAX := 16.0

const _MODE_UI := {
	"elevation": {"icon": "El", "tip": "Elevation"},
	"bathymetry": {"icon": "Ba", "tip": "Bathymetry"},
	"temperature": {"icon": "Te", "tip": "Temperature"},
	"precipitation": {"icon": "Pr", "tip": "Precipitation"},
	"holdridge": {"icon": "Ho", "tip": "Holdridge"},
}

@onready var atlas_host: Node2D = %AtlasHost
@onready var progress_bar: ProgressBar = %ProgressBar
@onready var status_label: Label = %StatusLabel
@onready var month_spin: SpinBox = %MonthSpin
@onready var hex_check: CheckBox = %HexCheck
@onready var coast_check: CheckBox = %CoastCheck
@onready var rivers_check: CheckBox = %RiversCheck
@onready var lakes_check: CheckBox = %LakesCheck
@onready var flow_check: CheckBox = %FlowCheck
@onready var seed_spin: SpinBox = %SeedSpin
@onready var profile_option: OptionButton = %ProfileOption
@onready var ocean_fraction_spin: SpinBox = %OceanFractionSpin
@onready var num_plates_spin: SpinBox = %NumPlatesSpin
@onready var cycle_count_spin: SpinBox = %CycleCountSpin
@onready var detail_amplitude_spin: SpinBox = %DetailAmplitudeSpin
@onready var erosion_iter_spin: SpinBox = %ErosionIterSpin
@onready var fluvial_k_spin: SpinBox = %FluvialKSpin
@onready var folding_ratio_spin: SpinBox = %FoldingRatioSpin
@onready var tect_sea_level_spin: SpinBox = %TectSeaLevelSpin
@onready var tect_erosion_period_spin: SpinBox = %TectErosionPeriodSpin
@onready var land_scale_spin: SpinBox = %LandScaleSpin
@onready var ocean_scale_spin: SpinBox = %OceanScaleSpin
@onready var orogeny_boost_spin: SpinBox = %OrogenyBoostSpin
@onready var activity_relief_spin: SpinBox = %ActivityReliefSpin
@onready var boundary_relief_spin: SpinBox = %BoundaryReliefSpin
@onready var base_temp_spin: SpinBox = %BaseTempSpin
@onready var sst_mix_spin: SpinBox = %SstMixSpin
@onready var inland_decay_spin: SpinBox = %InlandDecaySpin
@onready var western_warm_spin: SpinBox = %WesternWarmSpin
@onready var eastern_cool_spin: SpinBox = %EasternCoolSpin
@onready var moist_advect_steps_spin: SpinBox = %MoistAdvectStepsSpin
@onready var moist_advect_wind_spin: SpinBox = %MoistAdvectWindSpin
@onready var moist_large_scale_spin: SpinBox = %MoistLargeScaleSpin
@onready var moist_oro_spin: SpinBox = %MoistOroSpin
@onready var moist_conv_spin: SpinBox = %MoistConvSpin
@onready var moist_ocean_evap_spin: SpinBox = %MoistOceanEvapSpin
@onready var moist_land_et_spin: SpinBox = %MoistLandEtSpin
@onready var moist_cont_dry_spin: SpinBox = %MoistContDrySpin
@onready var moist_lee_dry_spin: SpinBox = %MoistLeeDrySpin
@onready var moist_plume_spin: SpinBox = %MoistPlumeSpin
@onready var moist_land_store_spin: SpinBox = %MoistLandStoreSpin
@onready var moist_itcz_scale_spin: SpinBox = %MoistItczScaleSpin
@onready var moist_itcz_width_spin: SpinBox = %MoistItczWidthSpin
@onready var moist_monsoon_spin: SpinBox = %MoistMonsoonSpin
@onready var moist_monsoon_band_max_spin: SpinBox = %MoistMonsoonBandMaxSpin
@onready var precip_scale_spin: SpinBox = %PrecipScaleSpin
@onready var generate_btn: Button = %GenerateBtn
@onready var load_btn: Button = %LoadBtn
@onready var world_path_edit: LineEdit = %WorldPathEdit
@onready var inspector: PanelContainer = %InspectorPanel
@onready var map_viewport: SubViewport = %SubViewport
@onready var map_viewport_container: SubViewportContainer = %SubViewportContainer
@onready var zoom_slider: HSlider = %ZoomSlider
@onready var zoom_fit_btn: Button = %ZoomFitBtn
@onready var advanced_btn: Button = %AdvancedBtn
@onready var advanced_popup: PopupPanel = %AdvancedPopup
@onready var adv_close_btn: Button = %AdvCloseBtn
@onready var mode_box: HBoxContainer = %ModeBox

var atlas: Node2D
var runner: Node
var progress: Node
var modes: Node
var timeline: Node
var _mode_buttons: Dictionary = {}
var _updating_zoom_slider: bool = false
var _active_mode_style: StyleBoxFlat
var _idle_mode_style: StyleBoxFlat


func _ready() -> void:
	_build_mode_styles()
	atlas = WorldAtlasScr.new()
	atlas_host.add_child(atlas)
	atlas.inspect_terrain.connect(_on_inspect_terrain)
	atlas.inspect_river.connect(_on_inspect_river)
	atlas.inspect_hex.connect(_on_inspect_hex)
	if atlas.has_signal("zoom_factor_changed"):
		atlas.zoom_factor_changed.connect(_on_atlas_zoom_factor_changed)

	runner = SimulationRunnerScr.new()
	progress = ProgressControllerScr.new()
	modes = MapModeControllerScr.new()
	timeline = TimelineControllerScr.new()
	add_child(runner)
	add_child(progress)
	add_child(modes)
	add_child(timeline)

	runner.line_received.connect(_on_worker_line)
	runner.process_exited.connect(_on_worker_exit)
	progress.progress_changed.connect(_on_progress)
	progress.stage_started.connect(func(s): status_label.text = "Stage: %s" % s)
	progress.run_complete.connect(_on_run_complete)
	progress.run_error.connect(_on_run_error)
	modes.mode_selected.connect(_on_mode)
	timeline.month_changed.connect(_on_month)

	_setup_mode_buttons()
	month_spin.value_changed.connect(func(v): timeline.set_month(int(v)))
	hex_check.toggled.connect(func(v): atlas.set_hex_overlay(v))
	coast_check.toggled.connect(func(_v): _apply_vector_layers())
	rivers_check.toggled.connect(func(_v): _apply_vector_layers())
	lakes_check.toggled.connect(func(_v): _apply_vector_layers())
	flow_check.toggled.connect(func(v): atlas.set_flow_overlay(v))
	_setup_profile_option()
	advanced_btn.pressed.connect(_open_advanced_popup)
	adv_close_btn.pressed.connect(func(): advanced_popup.hide())
	generate_btn.pressed.connect(_on_generate)
	load_btn.pressed.connect(_on_load)
	zoom_slider.min_value = ZOOM_MIN
	zoom_slider.max_value = ZOOM_MAX
	zoom_slider.value = ZOOM_MIN
	zoom_slider.value_changed.connect(_on_zoom_slider)
	zoom_fit_btn.pressed.connect(_on_zoom_fit)
	map_viewport_container.gui_input.connect(_on_map_gui_input)
	map_viewport_container.mouse_filter = Control.MOUSE_FILTER_STOP
	map_viewport_container.resized.connect(_on_map_resized)
	map_viewport.transparent_bg = false
	map_viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
	map_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	map_viewport_container.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	call_deferred("_on_map_resized")

	var default_world := _default_world_hint()
	world_path_edit.text = default_world
	if inspector.has_method("clear_inspector"):
		inspector.clear_inspector()
	status_label.text = "Load a world/ folder or generate (default profile: Atlas)."
	if FileAccess.file_exists(default_world.path_join("atlas_display/atlas_meta.json")):
		_load_world(default_world)


func _build_mode_styles() -> void:
	_idle_mode_style = StyleBoxFlat.new()
	_idle_mode_style.bg_color = Color(0.16, 0.18, 0.22, 1)
	_idle_mode_style.set_border_width_all(2)
	_idle_mode_style.border_color = Color(0.35, 0.38, 0.42, 1)
	_idle_mode_style.set_corner_radius_all(4)
	_idle_mode_style.content_margin_left = 8
	_idle_mode_style.content_margin_right = 8
	_idle_mode_style.content_margin_top = 6
	_idle_mode_style.content_margin_bottom = 6

	_active_mode_style = _idle_mode_style.duplicate()
	_active_mode_style.border_color = Color(0.95, 0.72, 0.28, 1)
	_active_mode_style.bg_color = Color(0.22, 0.24, 0.28, 1)


func _setup_mode_buttons() -> void:
	for child in mode_box.get_children():
		child.queue_free()
	_mode_buttons.clear()
	var group := ButtonGroup.new()
	for mode in MapModeControllerScr.MODES:
		var ui: Dictionary = _MODE_UI.get(mode, {"icon": mode.substr(0, 2).capitalize(), "tip": mode.capitalize()})
		var btn := Button.new()
		btn.toggle_mode = true
		btn.button_group = group
		btn.text = str(ui["icon"])
		btn.tooltip_text = str(ui["tip"])
		btn.custom_minimum_size = Vector2(40, 32)
		btn.focus_mode = Control.FOCUS_NONE
		btn.add_theme_stylebox_override("normal", _idle_mode_style)
		btn.add_theme_stylebox_override("hover", _idle_mode_style)
		btn.add_theme_stylebox_override("pressed", _active_mode_style)
		btn.add_theme_stylebox_override("focus", _idle_mode_style)
		var mode_id := str(mode)
		btn.pressed.connect(func(): modes.select_mode(mode_id))
		mode_box.add_child(btn)
		_mode_buttons[mode_id] = btn


func _setup_profile_option() -> void:
	profile_option.clear()
	var entries := [
		["Quick — smoke", SimulationRunnerScr.PROFILE_QUICK],
		["Atlas — default", SimulationRunnerScr.PROFILE_ATLAS],
		["Full — production", SimulationRunnerScr.PROFILE_FULL],
	]
	for i in range(entries.size()):
		profile_option.add_item(entries[i][0])
		profile_option.set_item_metadata(i, entries[i][1])
	profile_option.select(1)


func _selected_profile() -> String:
	var idx := profile_option.selected
	if idx < 0:
		return SimulationRunnerScr.PROFILE_ATLAS
	return str(profile_option.get_item_metadata(idx))


func _open_advanced_popup() -> void:
	advanced_popup.popup_centered(Vector2i(420, 640))


func _generation_knobs() -> Dictionary:
	return {
		"ocean_fraction": float(ocean_fraction_spin.value),
		"num_plates": int(num_plates_spin.value),
		"cycle_count": int(cycle_count_spin.value),
		"detail_amplitude": float(detail_amplitude_spin.value),
		"erosion_iterations": int(erosion_iter_spin.value),
		"fluvial_k": float(fluvial_k_spin.value),
		"folding_ratio": float(folding_ratio_spin.value),
		"tectonics_sea_level": float(tect_sea_level_spin.value),
		"tectonics_erosion_period": int(tect_erosion_period_spin.value),
		"land_scale_m": float(land_scale_spin.value),
		"ocean_scale_m": float(ocean_scale_spin.value),
		"orogeny_boost": float(orogeny_boost_spin.value),
		"activity_relief": float(activity_relief_spin.value),
		"boundary_relief": float(boundary_relief_spin.value),
		"base_temp_c": float(base_temp_spin.value),
		"sst_mix": float(sst_mix_spin.value),
		"sst_inland_decay_km": float(inland_decay_spin.value),
		"western_warm_c": float(western_warm_spin.value),
		"eastern_cool_c": float(eastern_cool_spin.value),
		"moisture_advect_steps": int(moist_advect_steps_spin.value),
		"moisture_advect_wind_scale": float(moist_advect_wind_spin.value),
		"moisture_large_scale_frac": float(moist_large_scale_spin.value),
		"moisture_orographic_frac": float(moist_oro_spin.value),
		"moisture_convective_scale": float(moist_conv_spin.value),
		"moisture_ocean_evap_rate": float(moist_ocean_evap_spin.value),
		"moisture_land_et_rate": float(moist_land_et_spin.value),
		"moisture_continentality_dry": float(moist_cont_dry_spin.value),
		"moisture_lee_dry": float(moist_lee_dry_spin.value),
		"moisture_plume_strength": float(moist_plume_spin.value),
		"moisture_land_store_capacity": float(moist_land_store_spin.value),
		"moisture_itcz_convective_scale": float(moist_itcz_scale_spin.value),
		"moisture_itcz_width_deg": float(moist_itcz_width_spin.value),
		"moisture_monsoon_strength": float(moist_monsoon_spin.value),
		"moisture_monsoon_lat_band_max_abs_deg": float(moist_monsoon_band_max_spin.value),
		"precip_scale_mm": float(precip_scale_spin.value),
	}


func _write_planet_config(path: String, knobs: Dictionary, profile: String) -> Error:
	## Full planet YAML so worker --config replaces packaged defaults; profile
	## CLI size overrides still apply on top. Analysis grid must not exceed climate
	## resolution (Quick 128x64 + hex 256x128 left most hexes empty -> false Ocean).
	var analysis := Vector2i(256, 128)
	match profile:
		SimulationRunnerScr.PROFILE_QUICK:
			analysis = Vector2i(128, 64)
		SimulationRunnerScr.PROFILE_ATLAS:
			analysis = Vector2i(256, 128)
		_:
			analysis = Vector2i(256, 128)
	var text := """schema_version: 2

planet:
  earth_like: true
  axial_tilt_deg: 23.44
  orbital_eccentricity: 0.0167
  solar_constant_relative: 1.0
  rotation_period_hours: 24.0
  year_days: 365.2422

map:
  topology: cylindrical
  wrap_x: true
  wrap_y: false
  projection: cylindrical_equal_area

analysis_grid:
  width: %d
  height: %d
  orientation: flat_top

resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  terrain_production: [4096, 2048]
  hydrology_target: [4096, 2048]

ocean:
  fraction_target: %.4f
  sst_mix: %.4f
  sst_inland_decay_km: %.4f
  western_warm_c: %.4f
  eastern_cool_c: %.4f

tectonics:
  num_plates: %d
  cycle_count: %d
  folding_ratio: %.4f
  sea_level: %.4f
  erosion_period: %d

terrain:
  detail_amplitude: %.4f
  land_scale_m: %.1f
  ocean_scale_m: %.1f
  orogeny_boost: %.4f
  activity_relief: %.4f
  boundary_relief: %.4f

erosion:
  iterations: %d
  fluvial_k: %.4f

climate:
  months: 12
  base_temp_c: %.4f
  continentality_scale_km: 500.0

ecology:
  precip_scale_mm: %.1f

moisture:
  advect_steps: %d
  advect_wind_scale: %.4f
  large_scale_frac: %.4f
  orographic_frac: %.4f
  convective_scale: %.4f
  ocean_evap_rate: %.4f
  lake_evap_rate: 0.75
  river_evap_rate: 0.40
  land_et_rate: %.4f
  continentality_dry: %.4f
  lee_dry: %.4f
  diffusion_mix_per_month: 0.08
  spinup_max_years: 20
  spinup_tolerance_relative: 0.02
  spinup_tolerance_absolute: 0.001
  plume_strength: %.4f
  plume_mix_reach_km: 500.0
  land_store_capacity: %.4f
  itcz_convective_scale: %.4f
  itcz_width_deg: %.4f
  monsoon_strength: %.4f
  monsoon_lat_band_min_abs_deg: 5.0
  monsoon_lat_band_max_abs_deg: %.4f
  monsoon_max_anomaly_ms: 3.5
  monsoon_coast_reach_km: 800.0
  monsoon_temp_scale_c: 8.0
  monsoon_regional_mean_km: 500.0

hydrology:
  river_acc_fraction: 0.035
  river_min_catchment_km2: 500.0
  fill_max_depth_m: 25.0
  transmission_rate: 0.45

landforms:
  mountain_score_threshold: 0.60
  plateau_score_threshold: 0.40
  fine_radius_km: 60.0
  meso_radius_km: 150.0
  macro_radius_km: 300.0
  min_range_km2: 800.0
  min_plateau_km2: 2500.0

generation:
  quality: final
""" % [
		analysis.x,
		analysis.y,
		float(knobs["ocean_fraction"]),
		float(knobs["sst_mix"]),
		float(knobs["sst_inland_decay_km"]),
		float(knobs["western_warm_c"]),
		float(knobs["eastern_cool_c"]),
		int(knobs["num_plates"]),
		int(knobs["cycle_count"]),
		float(knobs["folding_ratio"]),
		float(knobs["tectonics_sea_level"]),
		int(knobs["tectonics_erosion_period"]),
		float(knobs["detail_amplitude"]),
		float(knobs["land_scale_m"]),
		float(knobs["ocean_scale_m"]),
		float(knobs["orogeny_boost"]),
		float(knobs["activity_relief"]),
		float(knobs["boundary_relief"]),
		int(knobs["erosion_iterations"]),
		float(knobs["fluvial_k"]),
		float(knobs["base_temp_c"]),
		float(knobs["precip_scale_mm"]),
		int(knobs["moisture_advect_steps"]),
		float(knobs["moisture_advect_wind_scale"]),
		float(knobs["moisture_large_scale_frac"]),
		float(knobs["moisture_orographic_frac"]),
		float(knobs["moisture_convective_scale"]),
		float(knobs["moisture_ocean_evap_rate"]),
		float(knobs["moisture_land_et_rate"]),
		float(knobs["moisture_continentality_dry"]),
		float(knobs["moisture_lee_dry"]),
		float(knobs["moisture_plume_strength"]),
		float(knobs["moisture_land_store_capacity"]),
		float(knobs["moisture_itcz_convective_scale"]),
		float(knobs["moisture_itcz_width_deg"]),
		float(knobs["moisture_monsoon_strength"]),
		float(knobs["moisture_monsoon_lat_band_max_abs_deg"]),
	]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(text)
	f.close()
	return OK


func _apply_vector_layers() -> void:
	if atlas == null or not atlas.has_method("set_vector_layers"):
		return
	atlas.set_vector_layers(
		coast_check.button_pressed,
		rivers_check.button_pressed,
		lakes_check.button_pressed,
	)


func _on_map_resized() -> void:
	if atlas != null and atlas.has_method("refresh_base_zoom_keep_factor"):
		var meta: Dictionary = atlas.get_atlas_meta() if atlas.has_method("get_atlas_meta") else {}
		if not meta.is_empty():
			atlas.refresh_base_zoom_keep_factor()
			_sync_zoom_slider_from_atlas()


func _on_map_gui_input(event: InputEvent) -> void:
	if atlas == null:
		return
	var cont_size := map_viewport_container.size
	if cont_size.x < 1.0 or cont_size.y < 1.0:
		return
	var vp_size := Vector2(map_viewport.size)
	var local := Vector2.ZERO
	var rel := Vector2.ZERO
	if event is InputEventMouse:
		var me := event as InputEventMouse
		local = me.position
		if event is InputEventMouseMotion:
			rel = (event as InputEventMouseMotion).relative
	var vp_scale := Vector2(vp_size.x / cont_size.x, vp_size.y / cont_size.y)
	var vp_pos := local * vp_scale
	if event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		mm.set_meta("vp_relative", rel * vp_scale)
		mm.set_meta("vp_relative_set", true)
	atlas.handle_map_gui_input(event, vp_pos)
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index in [
			MOUSE_BUTTON_WHEEL_UP,
			MOUSE_BUTTON_WHEEL_DOWN,
			MOUSE_BUTTON_LEFT,
		]:
			map_viewport_container.accept_event()
			_sync_zoom_slider_from_atlas()


func _on_zoom_slider(value: float) -> void:
	if _updating_zoom_slider or atlas == null:
		return
	if atlas.has_method("set_zoom_factor"):
		atlas.set_zoom_factor(float(value))


func _on_zoom_fit() -> void:
	if atlas != null and atlas.has_method("fit_camera_to_map"):
		atlas.fit_camera_to_map()
	_sync_zoom_slider_from_atlas()


func _on_atlas_zoom_factor_changed(factor: float) -> void:
	_sync_zoom_slider(factor)


func _sync_zoom_slider_from_atlas() -> void:
	if atlas == null or not atlas.has_method("get_zoom_factor"):
		return
	_sync_zoom_slider(float(atlas.get_zoom_factor()))


func _sync_zoom_slider(factor: float) -> void:
	_updating_zoom_slider = true
	zoom_slider.value = clampf(factor, ZOOM_MIN, ZOOM_MAX)
	_updating_zoom_slider = false


func _on_generate() -> void:
	var world_seed := int(seed_spin.value)
	var profile := _selected_profile()
	var out_dir := ProjectSettings.globalize_path("res://").get_base_dir().path_join(
		"worlds/atlas_run_%d" % world_seed
	)
	world_path_edit.text = out_dir.path_join("world")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var config_path := out_dir.path_join("planet_config.yaml")
	var cfg_err := _write_planet_config(config_path, _generation_knobs(), profile)
	if cfg_err != OK:
		status_label.text = "Failed to write planet_config.yaml (%s)" % error_string(cfg_err)
		return
	status_label.text = "Launching worker (%s)..." % profile
	progress_bar.value = 0
	var err: Error = runner.start_generation(
		world_seed, out_dir, "world", profile, config_path
	)
	if err != OK:
		status_label.text = "Failed to launch worker (%s)" % error_string(err)
		if inspector.has_method("show_message"):
			inspector.show_message("Check python path / worldsim .venv (see godot/README.md).")


func _on_load() -> void:
	_load_world(world_path_edit.text.strip_edges())


func _load_world(world_root: String) -> void:
	var err: Error = atlas.load_world_atlas(world_root)
	if err != OK:
		status_label.text = "Failed to load atlas at %s" % world_root
		return
	var meta: Dictionary = atlas.get_atlas_meta()
	timeline.set_months(int(meta.get("months", 12)))
	month_spin.max_value = timeline.months
	status_label.text = "Loaded atlas %dx%d" % [
		int(meta.get("raster_width", 0)),
		int(meta.get("raster_height", 0)),
	]
	modes.select_mode(str(meta.get("default_mode", "elevation")))
	if inspector.has_method("clear_inspector"):
		inspector.clear_inspector()
	_apply_vector_layers()
	atlas.set_hex_overlay(hex_check.button_pressed)
	if atlas.has_method("set_flow_overlay"):
		atlas.set_flow_overlay(flow_check.button_pressed)
	call_deferred("_fit_after_load")


func _fit_after_load() -> void:
	if atlas != null and atlas.has_method("fit_camera_to_map"):
		atlas.fit_camera_to_map()
	_sync_zoom_slider_from_atlas()


func _on_worker_line(line: String) -> void:
	var ev: Dictionary = SimulationProtocolScr.parse_line(line)
	if not ev.is_empty():
		progress.handle_event(ev)


func _on_worker_exit(code: int) -> void:
	if code != 0:
		status_label.text = "Worker exited with code %d" % code


func _on_progress(stage: String, value: float) -> void:
	progress_bar.value = value * 100.0
	status_label.text = "%s (%.0f%%)" % [stage, value * 100.0]


func _on_run_complete(world_path: String) -> void:
	status_label.text = "Complete"
	progress_bar.value = 100
	if not world_path.is_empty():
		world_path_edit.text = world_path
		_load_world(world_path)


func _on_run_error(code: String, message: String, stage: String) -> void:
	status_label.text = "Error %s @ %s" % [code, stage]
	if inspector.has_method("show_message"):
		inspector.show_message("%s\n%s" % [code, message])


func _on_mode(mode: String) -> void:
	atlas.set_map_mode(mode)
	_refresh_mode_button_styles(mode)


func _refresh_mode_button_styles(active: String) -> void:
	for mode_id in _mode_buttons.keys():
		var btn: Button = _mode_buttons[mode_id]
		var on := str(mode_id) == active
		btn.button_pressed = on
		var style := _active_mode_style if on else _idle_mode_style
		btn.add_theme_stylebox_override("normal", style)
		btn.add_theme_stylebox_override("hover", style)
		btn.add_theme_stylebox_override("pressed", _active_mode_style)


func _on_month(month: int) -> void:
	month_spin.value = month
	atlas.set_month(month)


func _on_inspect_terrain(info: Dictionary) -> void:
	if inspector.has_method("show_terrain"):
		inspector.show_terrain(info)


func _on_inspect_river(info: Dictionary) -> void:
	if inspector.has_method("show_river"):
		inspector.show_river(info)


func _on_inspect_hex(info: Dictionary) -> void:
	if inspector.has_method("show_hex"):
		inspector.show_hex(info)


func _default_world_hint() -> String:
	var repo := ProjectSettings.globalize_path("res://").rstrip("/").get_base_dir()
	return repo.path_join("worlds/demo/world")
