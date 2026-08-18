extends Node2D
class_name LandformLayerRenderer
## C9 landform object overlay. Styles come from Python landform_legend.json.

## Neutral fallbacks only. Class colours come from landform_legend.json.
const FALLBACK_RANGE := Color(0.22, 0.22, 0.22, 1.0)
const FALLBACK_RIDGE := Color(0.28, 0.28, 0.28, 1.0)
const FALLBACK_RIM := Color(0.35, 0.35, 0.35, 1.0)
const FALLBACK_FILL := Color(0.5, 0.5, 0.5, 0.12)
const FALLBACK_SELECT := Color(1.0, 1.0, 1.0, 1.0)

var show_objects: bool = false
var show_ranges: bool = true
var show_ridges: bool = true
var show_plateaus: bool = true
var show_rims: bool = true
var selected_kind: String = ""
var selected_id: int = -1

var _tex_size: Vector2 = Vector2.ZERO
var _camera: Camera2D
var _ranges: Array = []
var _ridges: Array = []
var _plateaus: Array = []
var _rims: Array = []
var _styles: Dictionary = {}


func set_camera(cam: Camera2D) -> void:
	_camera = cam


func notify_zoom_changed() -> void:
	if show_objects:
		queue_redraw()


func load_atlas(atlas_dir: String, tex_size: Vector2) -> void:
	_tex_size = tex_size
	_ranges = _load_features(atlas_dir.path_join("mountain_ranges.geojson"))
	_ridges = _load_features(atlas_dir.path_join("mountain_ridges.geojson"))
	_plateaus = _load_features(atlas_dir.path_join("plateaus.geojson"))
	_rims = _load_features(atlas_dir.path_join("plateau_rims.geojson"))
	_styles = {}
	var legend_path := atlas_dir.path_join("landform_legend.json")
	if FileAccess.file_exists(legend_path):
		var leg = JSON.parse_string(FileAccess.get_file_as_string(legend_path))
		if typeof(leg) == TYPE_DICTIONARY:
			var styles_raw = leg.get("object_styles", {})
			if typeof(styles_raw) == TYPE_DICTIONARY:
				_styles = styles_raw
	queue_redraw()


func set_show_objects(v: bool) -> void:
	show_objects = v
	queue_redraw()


func set_selection(kind: String, object_id: int) -> void:
	selected_kind = kind
	selected_id = object_id
	queue_redraw()


func _draw() -> void:
	if not show_objects or _tex_size.x < 1.0:
		return
	var z := _camera_zoom()
	if show_plateaus:
		var fill := _style_color("plateau_fill", FALLBACK_FILL)
		for feat in _plateaus:
			_draw_polygon_feat(feat, fill)
	if show_ranges:
		var col := _style_color("mountain_range", FALLBACK_RANGE)
		var w := _style_width("mountain_range", 1.25) / z
		for feat in _ranges:
			_draw_outline_feat(feat, col, w)
	if show_rims:
		var col := _style_color("plateau_rim", FALLBACK_RIM)
		var w := _style_width("plateau_rim", 1.25) / z
		for feat in _rims:
			_draw_line_feat(feat, col, w)
	if show_ridges:
		var col := _style_color("ridge", FALLBACK_RIDGE)
		var w := _style_width("ridge", 0.95) / z
		for feat in _ridges:
			_draw_line_feat(feat, col, w)
	if selected_id > 0:
		var gold := _style_color("selection", FALLBACK_SELECT)
		var w := 2.0 / z
		match selected_kind:
			"mountain_range":
				for feat in _ranges:
					if int(feat.get("id", -1)) == selected_id:
						_draw_outline_feat(feat, gold, w)
			"plateau":
				for feat in _plateaus:
					if int(feat.get("id", -1)) == selected_id:
						_draw_outline_feat(feat, gold, w)
			"ridge":
				for feat in _ridges:
					if int(feat.get("id", -1)) == selected_id:
						_draw_line_feat(feat, gold, w)


func pick(local_pos: Vector2, max_dist: float = 6.0) -> Dictionary:
	if not show_objects:
		return {}
	var best := {}
	var best_d := max_dist
	if show_rims:
		for feat in _rims:
			var d := _min_line_dist(feat, local_pos)
			if d < best_d:
				best_d = d
				best = feat.duplicate()
				best["kind"] = "plateau_rim"
	if show_ridges:
		for feat in _ridges:
			var d := _min_line_dist(feat, local_pos)
			if d < best_d:
				best_d = d
				best = feat.duplicate()
				best["kind"] = "ridge"
	if show_ranges:
		for feat in _ranges:
			if _point_in_feat(feat, local_pos):
				best = feat.duplicate()
				best["kind"] = "mountain_range"
				return best
			var d := _min_line_dist(feat, local_pos)
			if d < best_d:
				best_d = d
				best = feat.duplicate()
				best["kind"] = "mountain_range"
	if show_plateaus:
		for feat in _plateaus:
			if _point_in_feat(feat, local_pos):
				best = feat.duplicate()
				best["kind"] = "plateau"
				return best
	return best


func _camera_zoom() -> float:
	if _camera != null and _camera.zoom.x > 0.0001:
		return _camera.zoom.x
	return 1.0


func _style_color(key: String, fallback: Color) -> Color:
	var spec = _styles.get(key, {})
	if typeof(spec) != TYPE_DICTIONARY:
		return fallback
	var hex := str(spec.get("color", ""))
	if hex == "":
		return fallback
	var c := Color.html(hex)
	if spec.has("alpha"):
		c.a = clampf(float(spec["alpha"]), 0.0, 1.0)
	return c


func _style_width(key: String, fallback: float) -> float:
	var spec = _styles.get(key, {})
	if typeof(spec) == TYPE_DICTIONARY and spec.has("width_px"):
		return float(spec["width_px"])
	return fallback


func _load_features(path: String) -> Array:
	var out: Array = []
	if not FileAccess.file_exists(path):
		return out
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		return out
	for feat in data.get("features", []):
		if typeof(feat) != TYPE_DICTIONARY:
			continue
		var props_raw = feat.get("properties", {})
		var geom_raw = feat.get("geometry", {})
		if typeof(props_raw) != TYPE_DICTIONARY or typeof(geom_raw) != TYPE_DICTIONARY:
			continue
		var props: Dictionary = props_raw
		var geom: Dictionary = geom_raw
		var gtype := str(geom.get("type", ""))
		if gtype == "Point":
			continue
		out.append({
			"id": int(props.get("id", -1)),
			"kind": str(props.get("kind", "")),
			"properties": props,
			"type": gtype,
			"rings": _coords_to_rings(gtype, geom.get("coordinates", [])),
		})
	return out


func _coords_to_rings(gtype: String, coords) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	if typeof(coords) != TYPE_ARRAY:
		return out
	match gtype:
		"LineString":
			out.append_array(_to_pixel_polylines(coords as Array, false))
		"MultiLineString":
			for part in coords:
				if typeof(part) == TYPE_ARRAY:
					out.append_array(_to_pixel_polylines(part as Array, false))
		"Polygon":
			if coords.size() > 0 and typeof(coords[0]) == TYPE_ARRAY:
				out.append_array(_to_pixel_polylines(coords[0] as Array, true))
		"MultiPolygon":
			for poly in coords:
				if typeof(poly) == TYPE_ARRAY and poly.size() > 0 and typeof(poly[0]) == TYPE_ARRAY:
					out.append_array(_to_pixel_polylines(poly[0] as Array, true))
	return out


func _to_pixel_polylines(coords: Array, closed: bool = false) -> Array[PackedVector2Array]:
	## Split on the dateline so a wrap does not become a screen-wide chord.
	var pieces: Array[PackedVector2Array] = []
	var pts := PackedVector2Array()
	var prev_x := INF
	for c in coords:
		if typeof(c) != TYPE_ARRAY or c.size() < 2:
			continue
		var x := fposmod(float(c[0]), 1.0)
		var y := float(c[1])
		if prev_x != INF and absf(x - prev_x) > 0.5:
			if pts.size() >= 2:
				pieces.append(pts)
			pts = PackedVector2Array()
		prev_x = x
		pts.append(Vector2(x * _tex_size.x, (1.0 - clampf(y, -1.0, 1.0)) * 0.5 * _tex_size.y))
	if pts.size() >= 2:
		pieces.append(pts)
	var out: Array[PackedVector2Array] = []
	var use_closed := closed and pieces.size() == 1
	for piece in pieces:
		out.append(_smooth_line(piece, use_closed))
	return out


func _smooth_line(pts: PackedVector2Array, closed: bool) -> PackedVector2Array:
	if pts.size() < 3:
		return pts
	if closed:
		return _chaikin_closed_px(pts, 2)
	return _chaikin_open_px(pts, 2)


func _chaikin_open_px(pts: PackedVector2Array, iterations: int) -> PackedVector2Array:
	var cur: PackedVector2Array = pts
	for _i in range(maxi(iterations, 0)):
		if cur.size() < 2:
			break
		var nxt := PackedVector2Array()
		nxt.append(cur[0])
		for i in range(cur.size() - 1):
			var p0 := cur[i]
			var p1 := cur[i + 1]
			nxt.append(p0 * 0.75 + p1 * 0.25)
			nxt.append(p0 * 0.25 + p1 * 0.75)
		nxt.append(cur[cur.size() - 1])
		cur = nxt
	return cur


func _chaikin_closed_px(pts: PackedVector2Array, iterations: int) -> PackedVector2Array:
	var cur: PackedVector2Array = pts
	for _i in range(maxi(iterations, 0)):
		var n := cur.size()
		if n < 3:
			break
		var nxt := PackedVector2Array()
		for i in range(n):
			var p0 := cur[i]
			var p1 := cur[(i + 1) % n]
			nxt.append(p0 * 0.75 + p1 * 0.25)
			nxt.append(p0 * 0.25 + p1 * 0.75)
		cur = nxt
	return cur


func _rings(feat: Dictionary) -> Array[PackedVector2Array]:
	var raw = feat.get("rings", [])
	var out: Array[PackedVector2Array] = []
	if typeof(raw) != TYPE_ARRAY:
		return out
	for pts in raw:
		if typeof(pts) == TYPE_PACKED_VECTOR2_ARRAY:
			out.append(pts)
	return out


func _draw_line_feat(feat: Dictionary, color: Color, width: float) -> void:
	for pts: PackedVector2Array in _rings(feat):
		if pts.size() >= 2:
			draw_polyline(pts, color, maxf(width, 0.25), false)


func _draw_outline_feat(feat: Dictionary, color: Color, width: float) -> void:
	for pts: PackedVector2Array in _rings(feat):
		if pts.size() < 2:
			continue
		var line: PackedVector2Array = pts
		if line[0].distance_to(line[line.size() - 1]) > 0.5:
			line = line.duplicate()
			line.append(line[0])
		draw_polyline(line, color, maxf(width, 0.25), false)


func _draw_polygon_feat(feat: Dictionary, color: Color) -> void:
	for pts: PackedVector2Array in _rings(feat):
		var open: PackedVector2Array = _open_ring(pts)
		if open.size() < 3:
			continue
		var idx := Geometry2D.triangulate_polygon(open)
		if idx.is_empty():
			continue
		var tri := PackedVector2Array()
		for i in idx:
			if int(i) >= 0 and int(i) < open.size():
				tri.append(open[i])
		if tri.size() >= 3:
			draw_colored_polygon(tri, color)


func _min_line_dist(feat: Dictionary, pos: Vector2) -> float:
	var best := 1e9
	for pts: PackedVector2Array in _rings(feat):
		for i in range(pts.size() - 1):
			var d := Geometry2D.get_closest_point_to_segment(pos, pts[i], pts[i + 1]).distance_to(pos)
			if d < best:
				best = d
	return best


func _point_in_feat(feat: Dictionary, pos: Vector2) -> bool:
	for pts: PackedVector2Array in _rings(feat):
		var open: PackedVector2Array = _open_ring(pts)
		if open.size() >= 3 and Geometry2D.is_point_in_polygon(pos, open):
			return true
	return false


func _open_ring(pts: PackedVector2Array) -> PackedVector2Array:
	var open: PackedVector2Array = pts
	if open.size() >= 2 and open[0].distance_to(open[open.size() - 1]) < 0.5:
		open = open.duplicate()
		open.remove_at(open.size() - 1)
	return open
