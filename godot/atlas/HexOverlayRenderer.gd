extends Node2D
class_name HexOverlayRenderer
## Optional analytical hex overlay — flat-top contours (A7). Toggle must not alter geography.

const HEX_LINE := Color(0.86, 0.88, 0.95, 0.3)
## Target on-screen stroke (px). Zoom-invariant via width/camera.zoom.
const HEX_WIDTH_SCREEN := 0.75
## When Fit-zoomed so each hex is tiny, draw every Nth cell (LOD). Full grid when zoomed in.
const LOD_HEX_PX := 4.0

## odd-q flat-top neighbour deltas (NE,E,SE,SW,W,NW) — matches worldsim layout.py
const _NEIGH_EVEN := [
	Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1),
	Vector2i(-1, -1), Vector2i(-1, 0), Vector2i(0, 1),
]
const _NEIGH_ODD := [
	Vector2i(1, 1), Vector2i(1, 0), Vector2i(0, -1),
	Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1),
]

var visible_overlay: bool = false
var _hex_env: Dictionary = {}
var _holdridge_legend: Dictionary = {}
var _biome_legend: Dictionary = {}
var _landform_legend: Dictionary = {}
var _inspect_schema: Dictionary = {}
var _inspect_blob: PackedByteArray = PackedByteArray()
var _hex_w: int = 256
var _hex_h: int = 128
var _tex_size: Vector2 = Vector2.ZERO
var _camera: Camera2D


func _ready() -> void:
	z_index = 20


func set_camera(cam: Camera2D) -> void:
	_camera = cam


func load_atlas(atlas_dir: String, tex_size: Vector2) -> void:
	_tex_size = tex_size
	var grid_path := atlas_dir.path_join("hex_grid.json")
	if FileAccess.file_exists(grid_path):
		var g = JSON.parse_string(FileAccess.get_file_as_string(grid_path))
		if typeof(g) == TYPE_DICTIONARY:
			_hex_w = int(g.get("width", 256))
			_hex_h = int(g.get("height", 128))
	var env_path := atlas_dir.path_join("hex_environment.json")
	if FileAccess.file_exists(env_path):
		var e = JSON.parse_string(FileAccess.get_file_as_string(env_path))
		if typeof(e) == TYPE_DICTIONARY:
			_hex_env = e
	_holdridge_legend.clear()
	var legend_path := atlas_dir.path_join("holdridge_zone_legend.json")
	if FileAccess.file_exists(legend_path):
		var leg = JSON.parse_string(FileAccess.get_file_as_string(legend_path))
		if typeof(leg) == TYPE_DICTIONARY:
			_holdridge_legend = leg
	_biome_legend.clear()
	var biome_path := atlas_dir.path_join("biome_v2_legend.json")
	if FileAccess.file_exists(biome_path):
		var bleg = JSON.parse_string(FileAccess.get_file_as_string(biome_path))
		if typeof(bleg) == TYPE_DICTIONARY:
			_biome_legend = bleg
	_landform_legend.clear()
	var lf_path := atlas_dir.path_join("landform_legend.json")
	if FileAccess.file_exists(lf_path):
		var lleg = JSON.parse_string(FileAccess.get_file_as_string(lf_path))
		if typeof(lleg) == TYPE_DICTIONARY:
			_landform_legend = lleg
	_inspect_schema = {}
	_inspect_blob = PackedByteArray()
	var ig_json := atlas_dir.path_join("inspection_grid.json")
	var ig_bin := atlas_dir.path_join("inspection_grid.bin")
	if FileAccess.file_exists(ig_json) and FileAccess.file_exists(ig_bin):
		var sch = JSON.parse_string(FileAccess.get_file_as_string(ig_json))
		if typeof(sch) == TYPE_DICTIONARY:
			_inspect_schema = sch
		_inspect_blob = FileAccess.get_file_as_bytes(ig_bin)
	queue_redraw()


func set_overlay_visible(v: bool) -> void:
	visible_overlay = v
	queue_redraw()


func notify_zoom_changed() -> void:
	if visible_overlay:
		queue_redraw()


func _draw() -> void:
	if not visible_overlay or _tex_size.x < 1.0 or _hex_w < 1 or _hex_h < 1:
		return
	var step := _lod_step()
	var multiline := PackedVector2Array()
	for r in range(0, _hex_h, step):
		for q in range(0, _hex_w, step):
			var verts := _hex_pixels_qr(q, r)
			for i in range(6):
				var a: Vector2 = verts[i]
				var b: Vector2 = verts[(i + 1) % 6]
				if absf(a.x - b.x) > _tex_size.x * 0.5:
					continue
				multiline.append(a)
				multiline.append(b)
	if multiline.size() >= 2:
		draw_multiline(multiline, HEX_LINE, _stroke_width_world(), false)


func _camera_zoom() -> float:
	if _camera != null and _camera.zoom.x > 0.0001:
		return _camera.zoom.x
	return 1.0


func _stroke_width_world() -> float:
	## Constant hairline on screen for Atlas / Full / Quick (Fit zoom differs with tex size).
	return HEX_WIDTH_SCREEN / _camera_zoom()


func _lod_step() -> int:
	## Subsample when a hex is smaller than ~LOD_HEX_PX on screen.
	var zoom := _camera_zoom()
	var hex_w_px := (_tex_size.x / float(_hex_w)) * zoom
	if hex_w_px >= LOD_HEX_PX:
		return 1
	var step := int(ceil(LOD_HEX_PX / maxf(hex_w_px, 0.01)))
	return clampi(step, 1, 8)


func _center_unclipped(q: int, r: int) -> Vector2:
	## Matches worldsim `_center_xy_unclipped` (no N/S clip).
	var x := (float(q) + 0.5) / float(_hex_w)
	var y := 1.0 - (float(r) + 0.5) * 2.0 / float(_hex_h)
	if (q & 1) == 1:
		y -= (2.0 / float(_hex_h)) * 0.5
	return Vector2(fposmod(x, 1.0), y)


func _unwrap_x_near(x: float, ref: float) -> float:
	x = fposmod(x, 1.0)
	var d := x - ref
	if d > 0.5:
		return x - 1.0
	if d < -0.5:
		return x + 1.0
	return x


func _hex_pixels_qr(q: int, r: int) -> PackedVector2Array:
	## Voronoi corners: mean(self, n_i, n_{i+1}) — shared edges, no gaps.
	var c := _center_unclipped(q, r)
	var deltas: Array = _NEIGH_ODD if (q & 1) == 1 else _NEIGH_EVEN
	var neigh: Array[Vector2] = []
	neigh.resize(6)
	for i in range(6):
		var d: Vector2i = deltas[i]
		var nq := posmod(q + d.x, _hex_w)
		var nr := r + d.y
		neigh[i] = _center_unclipped(nq, nr)
	var out := PackedVector2Array()
	out.resize(6)
	for i in range(6):
		var p1: Vector2 = neigh[i]
		var p2: Vector2 = neigh[(i + 1) % 6]
		var x1 := _unwrap_x_near(p1.x, c.x)
		var x2 := _unwrap_x_near(p2.x, c.x)
		var vx := fposmod((c.x + x1 + x2) / 3.0, 1.0)
		var vy := clampf((c.y + p1.y + p2.y) / 3.0, -1.0, 1.0)
		out[i] = Vector2(vx * _tex_size.x, (1.0 - vy) * 0.5 * _tex_size.y)
	return out


func hex_at(map_xy: Vector2) -> int:
	## Prefer nearest exported centre when available; else odd-q lattice estimate.
	var x := fposmod(map_xy.x, 1.0)
	var y := clampf(map_xy.y, -1.0, 1.0)
	var centers_x: Array = _hex_env.get("center_x", [])
	var centers_y: Array = _hex_env.get("center_y", [])
	if centers_x.size() == _hex_w * _hex_h and centers_y.size() == centers_x.size():
		var q0 := clampi(int(floor(x * _hex_w)), 0, _hex_w - 1)
		var best := 0
		var best_d := 1e9
		for dq in [-1, 0, 1]:
			var q := posmod(q0 + dq, _hex_w)
			var r_est := (1.0 - y) * 0.5 * float(_hex_h) - 0.5
			if (q & 1) == 1:
				r_est += 0.5
			for dr in [-1, 0, 1]:
				var r := clampi(int(round(r_est)) + dr, 0, _hex_h - 1)
				var hid := r * _hex_w + q
				var cx := float(centers_x[hid])
				var cy := float(centers_y[hid])
				var dx := cx - x
				if dx > 0.5:
					dx -= 1.0
				elif dx < -0.5:
					dx += 1.0
				var d := dx * dx + (cy - y) * (cy - y)
				if d < best_d:
					best_d = d
					best = hid
		return best
	var q0b := clampi(int(floor(x * _hex_w)), 0, _hex_w - 1)
	var best_q := q0b
	var best_r := 0
	var best_db := 1e9
	for dq in [-1, 0, 1]:
		var q := posmod(q0b + dq, _hex_w)
		var r_est := (1.0 - y) * 0.5 * float(_hex_h) - 0.5
		if (q & 1) == 1:
			r_est += 0.5
		for dr in [-1, 0, 1]:
			var r := clampi(int(round(r_est)) + dr, 0, _hex_h - 1)
			var c := _center_unclipped(q, r)
			var dx := c.x - x
			if dx > 0.5:
				dx -= 1.0
			elif dx < -0.5:
				dx += 1.0
			var d := dx * dx + (c.y - y) * (c.y - y)
			if d < best_db:
				best_db = d
				best_q = q
				best_r = r
	return best_r * _hex_w + best_q


func hex_info(hex_id: int, month: int = 1) -> Dictionary:
	if hex_id < 0:
		return {}
	var cx: Array = _as_array(_hex_env.get("center_x", []))
	if hex_id >= cx.size():
		return {"hex_id": hex_id}
	var counts: Array = _as_array(_hex_env.get("cell_count", []))
	## Legacy atlas JSON had no cell_count — do not treat as empty coverage.
	var has_counts := counts.size() > hex_id
	var cell_count := int(counts[hex_id]) if has_counts else -1
	var zone_id := int(_arr_num(_as_array(_hex_env.get("holdridge_dominant", [])), hex_id, -1))
	var info := {
		"hex_id": hex_id,
		"holdridge_id": zone_id,
	}
	if has_counts:
		info["cell_count"] = cell_count
	var no_coverage := (has_counts and cell_count <= 0) or zone_id < 0
	if no_coverage:
		info["holdridge"] = "No data (hex outside climate coverage)"
	else:
		info["holdridge"] = holdridge_label(zone_id)
	_copy_num(info, "latitude_deg", hex_id)
	_copy_num(info, "land_fraction", hex_id)
	_copy_num(info, "ocean_fraction", hex_id)
	_copy_num(info, "lake_fraction", hex_id)
	_copy_num(info, "elevation_mean_m", hex_id)
	if not info.has("elevation_mean_m"):
		_copy_num(info, "elevation_mean", hex_id)
		if info.has("elevation_mean"):
			info["elevation_mean_m"] = info["elevation_mean"]
	_copy_num(info, "elevation_min_m", hex_id)
	_copy_num(info, "elevation_max_m", hex_id)
	_copy_num(info, "elevation_std_m", hex_id)
	_copy_num(info, "local_relief_mean_m", hex_id)
	_copy_num(info, "slope_mean_deg", hex_id)
	_copy_num(info, "temperature_annual_c", hex_id)
	_copy_num(info, "precipitation_annual_mm", hex_id)
	if not info.has("precipitation_annual_mm"):
		_copy_num(info, "precipitation_annual", hex_id)
	_copy_num(info, "frost_months_mean", hex_id)
	_copy_num(info, "growing_season_months_mean", hex_id)
	_copy_num(info, "water_deficit_mm_mean", hex_id)
	_copy_int(info, "biome_v2_dominant", hex_id)
	_copy_int(info, "soil_state_dominant", hex_id)
	_copy_int(info, "context_dominant", hex_id)
	_copy_int(info, "local_form_dominant", hex_id)
	_copy_num(info, "mountain_score_mean", hex_id)
	_copy_num(info, "plateau_score_mean", hex_id)
	_copy_num(info, "mountain_terrain_fraction", hex_id)
	_copy_num(info, "mountain_range_fraction", hex_id)
	_copy_num(info, "plateau_context_fraction", hex_id)
	_copy_num(info, "plateau_object_fraction", hex_id)
	_copy_num(info, "terrain_barrier_strength", hex_id)
	_copy_num(info, "permanent_water_fraction", hex_id)
	_copy_num(info, "seasonal_water_fraction", hex_id)
	_copy_num(info, "perennial_river_fraction", hex_id)
	_copy_num(info, "seasonal_river_fraction", hex_id)
	_copy_num(info, "wadi_fraction", hex_id)
	_copy_num(info, "mean_effective_discharge", hex_id)
	_copy_num(info, "permeability_mean", hex_id)
	var rivers: Array = _id_list("river_ids", hex_id)
	if rivers.is_empty():
		rivers = _hex_env.get("river_ids_nonempty", {}).get(str(hex_id), [])
	info["river_ids"] = rivers
	info["lake_ids"] = _id_list("lake_ids", hex_id)
	info["basin_ids"] = _id_list("basin_ids", hex_id)
	info["mountain_range_ids"] = _id_list("mountain_range_ids", hex_id)
	info["plateau_ids"] = _id_list("plateau_ids", hex_id)
	var month_i := clampi(month, 1, 12) - 1
	info["temperature_month_c"] = _inspect_value("temperature_c", month_i, hex_id)
	info["precipitation_month_mm"] = _inspect_value("precipitation_mm_or_proxy", month_i, hex_id)
	info["humidity_month_proxy"] = _inspect_value("humidity_rh_proxy", month_i, hex_id)
	return info


func get_legends() -> Dictionary:
	return {
		"holdridge": _holdridge_legend,
		"biome_v2": _biome_legend,
		"landform": _landform_legend,
	}


func _as_array(value) -> Array:
	return value if typeof(value) == TYPE_ARRAY else []


func _arr_num(arr, hex_id: int, fallback = null) -> Variant:
	if typeof(arr) != TYPE_ARRAY or hex_id >= arr.size() or hex_id < 0:
		return fallback
	var v = arr[hex_id]
	if v == null:
		return fallback
	return v


func _copy_num(info: Dictionary, key: String, hex_id: int) -> void:
	var v = _arr_num(_hex_env.get(key, []), hex_id, null)
	if v == null:
		return
	if typeof(v) == TYPE_FLOAT and not is_finite(float(v)):
		return
	info[key] = float(v)


func _copy_int(info: Dictionary, key: String, hex_id: int) -> void:
	var v = _arr_num(_hex_env.get(key, []), hex_id, null)
	if v == null:
		return
	var iv := int(v)
	if iv < 0:
		return
	info[key] = iv


func _id_list(key: String, hex_id: int) -> Array:
	var payload = _hex_env.get(key, {})
	var found = null
	if typeof(payload) == TYPE_DICTIONARY:
		found = payload.get(str(hex_id), [])
	elif typeof(payload) == TYPE_ARRAY and hex_id < payload.size():
		found = payload[hex_id]
	if typeof(found) == TYPE_ARRAY:
		return found
	return []


func _inspect_value(field_id: String, month: int, hex_id: int) -> Variant:
	if _inspect_blob.is_empty() or _inspect_schema.is_empty():
		return null
	var fields = _inspect_schema.get("fields", [])
	for spec in fields:
		if typeof(spec) != TYPE_DICTIONARY or str(spec.get("id", "")) != field_id:
			continue
		var n_hex := int(_inspect_schema.get("n_hex", 0))
		var months := int(_inspect_schema.get("months", 12))
		if month < 0 or month >= months or hex_id < 0 or hex_id >= n_hex:
			return null
		var off := int(spec.get("offset_bytes", 0)) + month * n_hex * 4 + hex_id * 4
		if off < 0 or off + 4 > _inspect_blob.size():
			return null
		var v := _inspect_blob.decode_float(off)
		if not is_finite(v):
			return null
		return v
	return null


func holdridge_label(zone_id: int) -> String:
	## Wikipedia-style name from legend file, else decode id / overrides.
	var key := str(zone_id)
	if _holdridge_legend.has(key):
		return str(_holdridge_legend[key])
	match zone_id:
		0:
			return "Ocean"
		1:
			return "Lake"
		2:
			return "Permanent ice"
		3:
			return "Alpine bare"
	if zone_id >= 10:
		var code := zone_id - 10
		var bio := int(code / 10.0)
		var hum := code % 10
		return _life_zone_name(bio, hum)
	return "Zone %d" % zone_id


func _life_zone_name(bio: int, hum: int) -> String:
	## Mirrors worldsim `_LIFE_ZONE_DISPLAY` (wet→dry columns).
	const NAMES := [
		["Polar rain tundra", "Polar wet tundra", "Polar moist tundra", "Polar dry tundra", "Polar desert", "Polar desert", "Polar desert"],
		["Subpolar rain tundra", "Subpolar wet tundra", "Subpolar moist tundra", "Subpolar dry tundra", "Subpolar desert", "Subpolar desert", "Subpolar desert"],
		["Boreal rain forest", "Boreal wet forest", "Boreal moist forest", "Boreal dry scrub", "Boreal desert", "Boreal desert", "Boreal desert"],
		["Cool temperate rain forest", "Cool temperate wet forest", "Cool temperate moist forest", "Cool temperate steppe", "Cool temperate desert scrub", "Cool temperate desert", "Cool temperate desert"],
		["Warm temperate rain forest", "Warm temperate wet forest", "Warm temperate moist forest", "Warm temperate dry forest", "Warm temperate thorn scrub", "Warm temperate desert scrub", "Warm temperate desert"],
		["Tropical rain forest", "Tropical wet forest", "Tropical moist forest", "Tropical dry forest", "Tropical thorn woodland", "Tropical desert scrub", "Tropical desert"],
	]
	var bi := clampi(bio, 0, NAMES.size() - 1)
	var hi := clampi(hum, 0, NAMES[bi].size() - 1)
	return str(NAMES[bi][hi])
