extends Node2D
class_name WorldAtlas
## Multi-layer atlas: raster + vectors + optional hex overlay (not a TileMap DB).

const RasterLayerRendererScr = preload("res://atlas/RasterLayerRenderer.gd")
const LandLayerRendererScr = preload("res://atlas/LandLayerRenderer.gd")
const LandformLayerRendererScr = preload("res://atlas/LandformLayerRenderer.gd")
const VectorLayerRendererScr = preload("res://atlas/VectorLayerRenderer.gd")
const HexOverlayRendererScr = preload("res://atlas/HexOverlayRenderer.gd")
const FlowLayerRendererScr = preload("res://atlas/FlowLayerRenderer.gd")

signal inspect_feature(kind: String, info: Dictionary)
signal inspect_terrain(info: Dictionary)
signal inspect_river(info: Dictionary)
signal inspect_hex(info: Dictionary)
signal inspect_lake(info: Dictionary)
signal inspect_landform(info: Dictionary)
signal zoom_factor_changed(factor: float)

## Plan B2: Fit = 1.0; inspect cap = 16× Fit (empiric starting point).
const ZOOM_FACTOR_MIN := 1.0
const ZOOM_FACTOR_MAX := 16.0

var raster: Node2D
var land: Node2D
var landforms: Node2D
var vectors: Node2D
var hexes: Node2D
var flow: Node2D
var camera: Camera2D

var _atlas_dir: String = ""
var _meta: Dictionary = {}
var _dragging: bool = false
var _drag_from: Vector2 = Vector2.ZERO
var _prefer_hex_pick: bool = false
var _base_zoom: float = 1.0
var _user_zoom_factor: float = 1.0
var _month: int = 1


func _ready() -> void:
	raster = RasterLayerRendererScr.new()
	land = LandLayerRendererScr.new()
	landforms = LandformLayerRendererScr.new()
	vectors = VectorLayerRendererScr.new()
	hexes = HexOverlayRendererScr.new()
	flow = FlowLayerRendererScr.new()
	camera = Camera2D.new()
	camera.enabled = true
	# C9 draw order: raster → land → landform objects → rivers/lakes → flow → hex
	add_child(raster)
	add_child(land)
	add_child(landforms)
	add_child(vectors)
	add_child(flow)
	add_child(hexes)
	add_child(camera)
	if hexes.has_method("set_camera"):
		hexes.set_camera(camera)
	if vectors.has_method("set_camera"):
		vectors.set_camera(camera)
	if flow.has_method("set_camera"):
		flow.set_camera(camera)
	if landforms.has_method("set_camera"):
		landforms.set_camera(camera)
	landforms.visible = false


func load_world_atlas(world_root: String) -> Error:
	var atlas := world_root
	if not world_root.ends_with("atlas_display"):
		atlas = world_root.path_join("atlas_display")
	var meta_path := atlas.path_join("atlas_meta.json")
	if not FileAccess.file_exists(meta_path):
		push_error("atlas_meta.json missing at %s" % atlas)
		return ERR_FILE_NOT_FOUND
	var meta = JSON.parse_string(FileAccess.get_file_as_string(meta_path))
	if typeof(meta) != TYPE_DICTIONARY:
		return ERR_INVALID_DATA
	_atlas_dir = atlas
	_meta = meta
	raster.load_atlas(atlas, meta)
	var sz: Vector2 = raster.get_texture_size()
	if land.has_method("load_atlas"):
		land.load_atlas(atlas, sz)
	vectors.load_atlas(atlas, sz)
	hexes.load_atlas(atlas, sz)
	if landforms.has_method("load_atlas"):
		landforms.load_atlas(atlas, sz)
	if flow.has_method("load_atlas"):
		flow.load_atlas(atlas, sz)
	_sync_land_presentation()
	# Default coast on — route through soft land rim when composite is active.
	set_vector_layers(true, true, true)
	_user_zoom_factor = 1.0
	fit_camera_to_map()
	return OK


func fit_camera_to_map(margin: float = 0.92) -> void:
	## Frame the full map in the SubViewport (also used by Fit button).
	var sz: Vector2 = raster.get_texture_size()
	if sz.x <= 0.0 or sz.y <= 0.0:
		return
	var vp := get_viewport()
	if vp == null:
		return
	var view: Vector2 = Vector2(vp.size)
	if view.x <= 1.0 or view.y <= 1.0:
		return
	var zoom_x := view.x / sz.x
	var zoom_y := view.y / sz.y
	_base_zoom = minf(zoom_x, zoom_y) * margin
	_user_zoom_factor = 1.0
	camera.zoom = Vector2(_base_zoom, _base_zoom)
	camera.position = sz * 0.5
	_notify_overlay_zoom()
	zoom_factor_changed.emit(_user_zoom_factor)


func refresh_base_zoom_keep_factor(margin: float = 0.92) -> void:
	## On viewport resize: recompute fit baseline but keep the user's relative zoom.
	var sz: Vector2 = raster.get_texture_size()
	if sz.x <= 0.0 or sz.y <= 0.0:
		return
	var vp := get_viewport()
	if vp == null:
		return
	var view: Vector2 = Vector2(vp.size)
	if view.x <= 1.0 or view.y <= 1.0:
		return
	var zoom_x := view.x / sz.x
	var zoom_y := view.y / sz.y
	_base_zoom = minf(zoom_x, zoom_y) * margin
	_apply_zoom_factor(_user_zoom_factor, Vector2.ZERO, false)


func zoom_in(step: float = 1.2) -> void:
	_apply_zoom_factor(_user_zoom_factor * step, _viewport_center(), true)


func zoom_out(step: float = 1.2) -> void:
	_apply_zoom_factor(_user_zoom_factor / step, _viewport_center(), true)


func set_zoom_factor(factor: float) -> void:
	_apply_zoom_factor(factor, _viewport_center(), true)


func handle_map_gui_input(event: InputEvent, viewport_pixel: Vector2) -> void:
	## Called from Main with events from SubViewportContainer (Milestone A1).
	## ``viewport_pixel`` is the cursor position in SubViewport pixel space.
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			_apply_zoom_factor(_user_zoom_factor * 1.12, viewport_pixel, true)
			get_viewport().set_input_as_handled()
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			_apply_zoom_factor(_user_zoom_factor / 1.12, viewport_pixel, true)
			get_viewport().set_input_as_handled()
		elif mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				_dragging = false
				_drag_from = viewport_pixel
			else:
				if not _dragging and _drag_from.distance_to(viewport_pixel) < 4.0:
					_handle_click_at_viewport(viewport_pixel)
				_dragging = false
	elif event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		var mm := event as InputEventMouseMotion
		# Relative is in container space; Main converts — we receive viewport-space delta
		if mm.get_meta("vp_relative_set", false):
			var rel: Vector2 = mm.get_meta("vp_relative")
			if rel.length() > 0.5:
				_dragging = true
			camera.position -= rel / camera.zoom
		elif mm.relative.length() > 0.5:
			_dragging = true
			camera.position -= mm.relative / camera.zoom


func set_map_mode(mode: String) -> void:
	raster.apply_mode(mode)
	_sync_land_presentation()


func set_month(month: int) -> void:
	_month = month
	raster.set_month(month)
	_sync_land_presentation()


func _sync_land_presentation() -> void:
	if land == null or not land.has_method("set_map_mode"):
		return
	var tex: Texture2D = null
	if raster.has_method("get_texture"):
		tex = raster.get_texture()
	var mode := "elevation"
	if raster.has_method("get_mode"):
		mode = str(raster.get_mode())
	land.set_map_mode(mode, tex)
	var use_composite := land.has_method("has_land") and bool(land.has_land())
	if raster.has_method("set_land_composite_active"):
		raster.set_land_composite_active(use_composite)


func set_hex_overlay(overlay_on: bool) -> void:
	_prefer_hex_pick = overlay_on
	hexes.set_overlay_visible(overlay_on)


func set_flow_overlay(overlay_on: bool) -> void:
	if flow != null and flow.has_method("set_show_flow"):
		flow.set_show_flow(overlay_on)


func set_landform_overlay(overlay_on: bool) -> void:
	if landforms == null:
		return
	if landforms.has_method("set_show_objects"):
		landforms.set_show_objects(overlay_on)
	landforms.visible = overlay_on
	if not overlay_on and landforms.has_method("set_selection"):
		landforms.set_selection("", -1)


func get_legends() -> Dictionary:
	if hexes != null and hexes.has_method("get_legends"):
		return hexes.get_legends()
	return {}


func get_atlas_dir() -> String:
	return _atlas_dir


func set_vector_layers(coast: bool = true, rivers: bool = true, lakes: bool = true) -> void:
	## Milestone A3: show/hide overlays without regenerating the world.
	## With land composite, coast follows soft land silhouette in the shader
	## (vector mask-edge coast would misalign after B6b softening).
	var use_composite := land.has_method("has_land") and bool(land.has_land())
	if use_composite and land.has_method("set_show_coast"):
		land.set_show_coast(coast)
		vectors.show_coast = false
	else:
		if land.has_method("set_show_coast"):
			land.set_show_coast(false)
		vectors.show_coast = coast
	vectors.show_rivers = rivers
	vectors.show_lakes = lakes
	vectors.queue_redraw()


func get_atlas_meta() -> Dictionary:
	return _meta


func get_zoom_factor() -> float:
	return _user_zoom_factor


func _viewport_center() -> Vector2:
	var vp := get_viewport()
	if vp == null:
		return Vector2.ZERO
	return Vector2(vp.size) * 0.5


func _apply_zoom_factor(factor: float, anchor_vp: Vector2, use_anchor: bool) -> void:
	factor = clampf(factor, ZOOM_FACTOR_MIN, ZOOM_FACTOR_MAX)
	var old_zoom := camera.zoom.x
	if old_zoom <= 0.0001:
		old_zoom = _base_zoom
	var world_before := Vector2.ZERO
	if use_anchor:
		world_before = _viewport_to_world(anchor_vp)
	_user_zoom_factor = factor
	var new_zoom := _base_zoom * _user_zoom_factor
	camera.zoom = Vector2(new_zoom, new_zoom)
	if use_anchor:
		var world_after := _viewport_to_world(anchor_vp)
		camera.position += world_before - world_after
	_notify_overlay_zoom()
	zoom_factor_changed.emit(_user_zoom_factor)


func _notify_overlay_zoom() -> void:
	if hexes != null and hexes.has_method("notify_zoom_changed"):
		hexes.notify_zoom_changed()
	if vectors != null and vectors.has_method("notify_zoom_changed"):
		vectors.notify_zoom_changed()
	if flow != null and flow.has_method("notify_zoom_changed"):
		flow.notify_zoom_changed()
	if landforms != null and landforms.has_method("notify_zoom_changed"):
		landforms.notify_zoom_changed()


func _viewport_to_world(vp_pos: Vector2) -> Vector2:
	## SubViewport pixel → world (map texture) coordinates.
	var vp := get_viewport()
	var center := Vector2(vp.size) * 0.5 if vp else Vector2.ZERO
	return camera.position + (vp_pos - center) / camera.zoom


func _handle_click_at_viewport(vp_pos: Vector2) -> void:
	var local := _viewport_to_world(vp_pos)
	var pick_px := 5.0 / maxf(camera.zoom.x, 0.01)
	if vectors.has_method("pick_lake"):
		var lake: Dictionary = vectors.pick_lake(local)
		if not lake.is_empty():
			_emit_feature("lake", lake)
			return
	var river: Dictionary = vectors.pick_river(local, pick_px)
	if not river.is_empty():
		_emit_feature("river", {
			"id": river.get("id", river.get("parent_segment_id", 0)),
			"strahler_order": river.get("strahler_order", 0),
			"mean_discharge": river.get("mean_discharge", 0.0),
			"basin_id": river.get("basin_id", 0),
			"from_lake_id": river.get("from_lake_id", 0),
			"to_lake_id": river.get("to_lake_id", 0),
			"monthly_discharge": river.get("monthly_discharge", []),
			"channel_state": river.get("channel_state", ""),
			"catchment_km2": river.get("catchment_km2", 0.0),
			"bed_loss_mean": river.get("bed_loss_mean", 0.0),
			"parent_segment_id": river.get("parent_segment_id", river.get("id", 0)),
		})
		return
	if landforms != null and landforms.has_method("pick"):
		var lf: Dictionary = landforms.pick(local, pick_px)
		if not lf.is_empty():
			if landforms.has_method("set_selection"):
				landforms.set_selection(str(lf.get("kind", "")), int(lf.get("id", -1)))
			_emit_feature(str(lf.get("kind", "landform")), lf)
			return
	var map_xy: Vector2 = raster.map_to_uv(local)
	var hid: int = hexes.hex_at(map_xy)
	var hex_info: Dictionary = hexes.hex_info(hid, _month) if hexes.has_method("hex_info") else {}
	_emit_feature("hex", hex_info)


func _emit_feature(kind: String, info: Dictionary) -> void:
	inspect_feature.emit(kind, info)
	match kind:
		"river":
			inspect_river.emit(info)
		"lake":
			inspect_lake.emit(info)
		"hex":
			inspect_hex.emit(info)
		"mountain_range", "plateau", "ridge", "plateau_rim":
			inspect_landform.emit(info)
		_:
			inspect_terrain.emit(info)
