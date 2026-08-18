extends Node2D
class_name VectorLayerRenderer
## Draws coastline / rivers / lakes from GeoJSON in normalised map space.

## Opaque water overlays (post-A4c): rivers under lakes; lakes cover through-flow.
## Stroke widths: screen-space px / camera.zoom so Fit does not erase subpixel coasts.
## Coast: prefer edges from land_mask.png (same grid as fill). Lakes/rivers = shallow bathy.
const COAST_WIDTH_SCREEN := 1.0
const RIVER_WIDTH_MIN_SCREEN := 0.7
const RIVER_WIDTH_MAX_SCREEN := 2.2
const WATER_FILL := Color(0.25, 0.45, 0.85, 1.0)
const COAST_COLOR := Color(0.72, 0.64, 0.52, 1.0)  # match shader coast beige
const POINT_EPS := 0.5
const WIDTH_REF_TEX_X := 1024.0

var _atlas_dir: String = ""
var _tex_size: Vector2 = Vector2(1024, 512)
var _rivers: Array = []
var _coast: Array = []
## Pixel-space coast segments derived from land_mask (preferred over GeoJSON).
var _coast_mask_segs: Array = []
var _use_mask_coast: bool = false
var _lakes: Array = []
## Pixel-space rings used for draw + point-in-lake tests.
var _lake_rings_px: Array = []
var _lake_feats: Array = []
## Highest Strahler in loaded GeoJSON (≥2 so order 1 vs 2 still tapers).
var _strahler_max: float = 2.0
## log(1 + max mean_discharge) for B7 stroke scaling.
var _discharge_log_max: float = 1.0
## Shallowest ocean colour from bathymetry (lakes + rivers match coastal shelf).
var _shallow_water: Color = WATER_FILL
var show_rivers: bool = true
var show_coast: bool = true
var show_lakes: bool = true
var lakes_skipped_degenerate: int = 0
var _camera: Camera2D
var _lake_schema_warned: bool = false


func set_camera(cam: Camera2D) -> void:
	_camera = cam


func notify_zoom_changed() -> void:
	queue_redraw()


func load_atlas(atlas_dir: String, tex_size: Vector2) -> void:
	_atlas_dir = atlas_dir
	_tex_size = tex_size
	_rivers = _load_lines(atlas_dir.path_join("rivers.geojson"))
	_coast = _load_lines(atlas_dir.path_join("coastline.geojson"))
	_lakes = _load_polygons(atlas_dir.path_join("lakes.geojson"))
	_strahler_max = 2.0
	_discharge_log_max = 1.0
	for feat in _rivers:
		_strahler_max = maxf(_strahler_max, float(feat.get("strahler_order", 1)))
		var q := maxf(float(feat.get("mean_discharge", 0.0)), 0.0)
		_discharge_log_max = maxf(_discharge_log_max, log(1.0 + q))
	_rebuild_coast_from_land_mask(atlas_dir)
	_rebuild_shallow_water(atlas_dir)
	_rebuild_lake_rings_px()
	queue_redraw()


func set_texture_size(tex_size: Vector2) -> void:
	_tex_size = tex_size
	_rebuild_lake_rings_px()
	queue_redraw()


func _camera_zoom() -> float:
	if _camera != null and _camera.zoom.x > 0.0001:
		return _camera.zoom.x
	return 1.0


func _screen_to_world_width(screen_px: float) -> float:
	## Constant on-screen hairline across Fit / zoom-in.
	return screen_px / _camera_zoom()


func river_width_for_strahler(order: float) -> float:
	## Map observed Strahler [1, _strahler_max] → screen-space river widths.
	var o_max := maxf(_strahler_max, 2.0)
	var o := clampf(maxf(order, 1.0), 1.0, o_max)
	var t := (o - 1.0) / (o_max - 1.0)
	var screen := lerpf(RIVER_WIDTH_MIN_SCREEN, RIVER_WIDTH_MAX_SCREEN, t)
	return _screen_to_world_width(screen)


func river_width_for_feature(feat: Dictionary) -> float:
	## Stroke from Strahler + discharge only. Channel state is diagnostic, never width.
	## B7: stroke ∝ log(1+discharge), blended with Strahler so tiny stubs stay readable.
	var order := float(feat.get("strahler_order", 1))
	var by_order := river_width_for_strahler(order)
	var q := maxf(float(feat.get("mean_discharge", 0.0)), 0.0)
	var t_q := 0.0
	if _discharge_log_max > 1e-6:
		t_q = clampf(log(1.0 + q) / _discharge_log_max, 0.0, 1.0)
	var screen_q := lerpf(RIVER_WIDTH_MIN_SCREEN, RIVER_WIDTH_MAX_SCREEN, t_q)
	var by_q := _screen_to_world_width(screen_q)
	return lerpf(by_order, by_q, 0.65)


func _width_scale() -> float:
	## Keep lake area thresholds similar at Atlas vs Full.
	if _tex_size.x <= 1.0:
		return 1.0
	return maxf(_tex_size.x / WIDTH_REF_TEX_X, 1.0)


func _min_draw_length() -> float:
	## Drop micro stubs that become flickering dust when Fit-zoomed on Full.
	return 1.25 * _width_scale()


func _polyline_length(pts: PackedVector2Array) -> float:
	var total := 0.0
	for i in range(pts.size() - 1):
		total += pts[i].distance_to(pts[i + 1])
	return total


func _lake_is_liquid(poly: Dictionary) -> bool:
	## C0 fail-closed: missing state must not mean permanent liquid water.
	var ice := str(poly.get("ice_regime", ""))
	var hydro := str(poly.get("hydroperiod", ""))
	var state := str(poly.get("water_state", ""))
	if ice == "perennially_frozen" or hydro == "ephemeral_or_dry":
		return false
	if state == "open" or state == "endorheic":
		return true
	if hydro == "permanent" or hydro == "seasonal":
		if ice == "" or ice == "normally_liquid" or ice == "seasonally_frozen":
			var outlet := str(poly.get("outlet_type", ""))
			return outlet == "ocean_draining" or outlet == "open_lake" or outlet == "closed_endorheic"
	return false


func _warn_lake_schema_once() -> void:
	if _lake_schema_warned:
		return
	_lake_schema_warned = true
	push_warning(
		"Lake GeoJSON missing water_state/hydroperiod; fail-closed — not drawn as liquid water."
	)


func _rebuild_lake_rings_px() -> void:
	_lake_rings_px.clear()
	_lake_feats.clear()
	lakes_skipped_degenerate = 0
	for poly in _lakes:
		if not _lake_is_liquid(poly):
			var state := str(poly.get("water_state", ""))
			var hydro := str(poly.get("hydroperiod", ""))
			if state == "" and hydro == "":
				_warn_lake_schema_once()
			continue
		var best := PackedVector2Array()
		for piece in _to_pixel_polylines(poly.get("coords", [])):
			var ring := _sanitize_polygon_ring(piece)
			if ring.size() > best.size():
				best = ring
		if best.is_empty():
			lakes_skipped_degenerate += 1
			continue
		var drawn := _smooth_lake_ring_px(best)
		if not _ring_triangulates(drawn):
			drawn = best
			if best.size() >= 3 and best[0].distance_to(best[best.size() - 1]) > 0.01:
				drawn = best.duplicate()
				drawn.append(best[0])
		if not _ring_triangulates(drawn):
			lakes_skipped_degenerate += 1
			continue
		_lake_rings_px.append(drawn)
		_lake_feats.append(poly)


func _ring_triangulates(ring: PackedVector2Array) -> bool:
	if ring.size() < 3:
		return false
	var open := ring
	if open.size() >= 2 and open[0].distance_to(open[open.size() - 1]) < 0.01:
		open = open.duplicate()
		open.remove_at(open.size() - 1)
	if open.size() < 3:
		return false
	var idx := Geometry2D.triangulate_polygon(open)
	return not idx.is_empty()


func _smooth_lake_ring_px(ring: PackedVector2Array) -> PackedVector2Array:
	## Mild presentation smooth only. Aggressive DP/Laplacian made self-intersections
	## → triangulation failed and large lakes vanished.
	if ring.size() < 4:
		return ring
	var open := PackedVector2Array()
	for i in range(ring.size()):
		if i + 1 == ring.size() and ring[0].distance_to(ring[i]) < 0.01:
			break
		open.append(ring[i])
	if open.size() < 3:
		return ring
	var area0 := _ring_area_abs(open)
	# Light tooth damping, then one Chaikin pass.
	open = _laplacian_smooth_closed_px(open, 2, 0.28)
	open = _chaikin_closed_px(open, 1)
	var area1 := _ring_area_abs(open)
	# Reject collapse / blow-up (bad geometry).
	if area0 > 1.0 and (area1 < 0.55 * area0 or area1 > 1.6 * area0):
		return ring
	if open.size() >= 3 and open[0].distance_to(open[open.size() - 1]) > 0.01:
		open.append(open[0])
	return open


func _ring_area_abs(pts: PackedVector2Array) -> float:
	var n := pts.size()
	if n < 3:
		return 0.0
	var a := 0.0
	for i in range(n):
		var p: Vector2 = pts[i]
		var q: Vector2 = pts[(i + 1) % n]
		a += p.x * q.y - q.x * p.y
	return absf(a) * 0.5


func _ring_bbox_size(pts: PackedVector2Array) -> Vector2:
	var mn := pts[0]
	var mx := pts[0]
	for p in pts:
		mn = Vector2(minf(mn.x, p.x), minf(mn.y, p.y))
		mx = Vector2(maxf(mx.x, p.x), maxf(mx.y, p.y))
	return mx - mn


func _laplacian_smooth_closed_px(pts: PackedVector2Array, iterations: int, weight: float) -> PackedVector2Array:
	var cur := pts.duplicate()
	var w := clampf(weight, 0.0, 1.0)
	for _k in range(maxi(iterations, 0)):
		var n := cur.size()
		if n < 3:
			break
		var nxt := PackedVector2Array()
		nxt.resize(n)
		for i in range(n):
			var prev: Vector2 = cur[(i - 1 + n) % n]
			var mid: Vector2 = cur[i]
			var nxtp: Vector2 = cur[(i + 1) % n]
			nxt[i] = mid * (1.0 - w) + (prev + nxtp) * (0.5 * w)
		cur = nxt
	return cur


func _chaikin_closed_px(pts: PackedVector2Array, iterations: int) -> PackedVector2Array:
	var cur := pts
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


func _draw() -> void:
	## Draw order: rivers under lakes so through-lake reaches are covered by opaque fill.
	## Antialiasing off: AA + Camera2D zoom caused bluish “ghost” flashes (not geography).
	## min_len only on Full (scale>1): Atlas coasts are often ~1 px runs — must still draw.
	var cull_dust := _width_scale() > 1.01
	var min_len := _min_draw_length() if cull_dust else 0.0
	if show_coast:
		var coast_w := _screen_to_world_width(COAST_WIDTH_SCREEN)
		if _use_mask_coast:
			for pts in _coast_mask_segs:
				if typeof(pts) == TYPE_PACKED_VECTOR2_ARRAY and pts.size() >= 2:
					draw_polyline(pts, COAST_COLOR, coast_w, false)
		else:
			for feat in _coast:
				for pts in _to_pixel_polylines(feat.get("coords", [])):
					if pts.size() >= 2:
						draw_polyline(pts, COAST_COLOR, coast_w, false)
	if show_rivers:
		for feat in _rivers:
			var w := river_width_for_feature(feat)
			for pts in _to_pixel_polylines(feat.get("coords", [])):
				if pts.size() >= 2 and (not cull_dust or _polyline_length(pts) >= min_len):
					draw_polyline(pts, _shallow_water, w, false)
	if show_lakes:
		for ring in _lake_rings_px:
			# Guard: never call draw_colored_polygon on non-triangulable rings.
			if _ring_triangulates(ring):
				draw_colored_polygon(ring, _shallow_water)


func _rebuild_coast_from_land_mask(atlas_dir: String) -> void:
	## Land/ocean edges from the same raster as fill → no geojson drift.
	## Includes 1-cell islands (every land pixel with an ocean neighbour gets edges).
	_coast_mask_segs.clear()
	_use_mask_coast = false
	var path := atlas_dir.path_join("land_mask.png")
	if not FileAccess.file_exists(path):
		return
	var img := Image.load_from_file(path)
	if img == null:
		return
	var w: int = img.get_width()
	var h: int = img.get_height()
	if w < 1 or h < 1:
		return
	_tex_size = Vector2(w, h)

	# Horizontal interfaces between row y and y+1 (edge at py = y+1).
	for y in range(h - 1):
		var x: int = 0
		while x < w:
			var above: bool = _mask_land_at(img, x, y)
			var below: bool = _mask_land_at(img, x, y + 1)
			if above == below:
				x += 1
				continue
			var x0: int = x
			var orient: bool = above
			x += 1
			while x < w:
				var a2: bool = _mask_land_at(img, x, y)
				var b2: bool = _mask_land_at(img, x, y + 1)
				if a2 == b2 or a2 != orient:
					break
				x += 1
			_coast_mask_segs.append(PackedVector2Array([Vector2(x0, y + 1), Vector2(x, y + 1)]))

	# Vertical interfaces between col x and x+1 (edge at px = x+1).
	for x in range(w - 1):
		var y: int = 0
		while y < h:
			var left: bool = _mask_land_at(img, x, y)
			var right: bool = _mask_land_at(img, x + 1, y)
			if left == right:
				y += 1
				continue
			var y0: int = y
			var orient: bool = left
			y += 1
			while y < h:
				var a2: bool = _mask_land_at(img, x, y)
				var b2: bool = _mask_land_at(img, x + 1, y)
				if a2 == b2 or a2 != orient:
					break
				y += 1
			_coast_mask_segs.append(PackedVector2Array([Vector2(x + 1, y0), Vector2(x + 1, y)]))

	# Dateline: col 0 vs col w-1 → edges at x=0 and x=w (two stubs, no chord).
	for y in range(h):
		var west: bool = _mask_land_at(img, 0, y)
		var east: bool = _mask_land_at(img, w - 1, y)
		if west == east:
			continue
		if west and not east:
			_coast_mask_segs.append(PackedVector2Array([Vector2(0, y), Vector2(0, y + 1)]))
		elif east and not west:
			_coast_mask_segs.append(PackedVector2Array([Vector2(w, y), Vector2(w, y + 1)]))

	_coast_mask_segs = _chain_and_smooth_coast(_coast_mask_segs, w)
	_use_mask_coast = not _coast_mask_segs.is_empty()


func _mask_land_at(img: Image, x: int, y: int) -> bool:
	return img.get_pixel(x, y).r >= 0.5


func _point_key(p: Vector2) -> int:
	## Integer pixel endpoint key for chaining axis-aligned coast edges.
	return int(round(p.x)) * 100000 + int(round(p.y))


func _chain_and_smooth_coast(raw: Array, tex_w: int) -> Array:
	## Merge abutting mask edges into longer polylines, then DP + Chaikin (B6).
	## Keeps land_mask alignment (fill SoT); stroke only is softened.
	if raw.is_empty():
		return []
	var segs: Array = []
	for item in raw:
		if typeof(item) != TYPE_PACKED_VECTOR2_ARRAY:
			continue
		var pts: PackedVector2Array = item
		if pts.size() < 2:
			continue
		segs.append(pts)
	if segs.is_empty():
		return []

	var used := PackedByteArray()
	used.resize(segs.size())
	used.fill(0)

	# endpoint key → list of [seg_index, end_flag 0=start 1=end]
	var adj: Dictionary = {}
	for i in range(segs.size()):
		var s: PackedVector2Array = segs[i]
		var k0 := _point_key(s[0])
		var k1 := _point_key(s[s.size() - 1])
		if not adj.has(k0):
			adj[k0] = []
		if not adj.has(k1):
			adj[k1] = []
		adj[k0].append([i, 0])
		adj[k1].append([i, 1])

	var chains: Array = []
	for start_i in range(segs.size()):
		if used[start_i] != 0:
			continue
		used[start_i] = 1
		var chain: PackedVector2Array = segs[start_i].duplicate()
		# Extend forward from end
		while true:
			var end_key := _point_key(chain[chain.size() - 1])
			var nxt_i := -1
			var nxt_rev := false
			if adj.has(end_key):
				for entry in adj[end_key]:
					var si: int = entry[0]
					var end_flag: int = entry[1]
					if used[si] != 0:
						continue
					nxt_i = si
					nxt_rev = end_flag == 1
					break
			if nxt_i < 0:
				break
			used[nxt_i] = 1
			var add: PackedVector2Array = segs[nxt_i]
			if nxt_rev:
				add = add.duplicate()
				add.reverse()
			for j in range(1, add.size()):
				chain.append(add[j])
		# Extend backward from start
		while true:
			var start_key := _point_key(chain[0])
			var prv_i := -1
			var prv_rev := false
			if adj.has(start_key):
				for entry in adj[start_key]:
					var si2: int = entry[0]
					var end_flag2: int = entry[1]
					if used[si2] != 0:
						continue
					prv_i = si2
					prv_rev = end_flag2 == 0
					break
			if prv_i < 0:
				break
			used[prv_i] = 1
			var add2: PackedVector2Array = segs[prv_i]
			if prv_rev:
				add2 = add2.duplicate()
				add2.reverse()
			var prefix := PackedVector2Array()
			for j in range(add2.size() - 1):
				prefix.append(add2[j])
			prefix.append_array(chain)
			chain = prefix
		chains.append(_smooth_coast_polyline_px(chain, tex_w))

	var out: Array = []
	for c in chains:
		if typeof(c) == TYPE_ARRAY:
			for piece in c:
				if typeof(piece) == TYPE_PACKED_VECTOR2_ARRAY and piece.size() >= 2:
					out.append(piece)
		elif typeof(c) == TYPE_PACKED_VECTOR2_ARRAY and c.size() >= 2:
			out.append(c)
	return out


func _smooth_coast_polyline_px(pts: PackedVector2Array, tex_w: int) -> Array:
	## Pixel-space DP (eps≈0.85) + Chaikin×2; split wrap chords into separate strokes.
	var result: Array = []
	if pts.size() < 3:
		result.append(pts)
		return result
	var simplified := _douglas_peucker_px(pts, 0.85)
	var smoothed := _chaikin_open_px(simplified, 2)
	return _split_wrap_pieces_px(smoothed, tex_w)


func _douglas_peucker_px(pts: PackedVector2Array, eps: float) -> PackedVector2Array:
	if pts.size() <= 2 or eps <= 0.0:
		return pts
	var keep := _dp_rec(pts, 0, pts.size() - 1, eps * eps)
	var out := PackedVector2Array()
	for i in keep:
		out.append(pts[i])
	return out


func _dp_rec(pts: PackedVector2Array, start: int, end: int, eps2: float) -> Array:
	if end <= start + 1:
		return [start, end]
	var a := pts[start]
	var b := pts[end]
	var max_d := -1.0
	var idx := start
	for i in range(start + 1, end):
		var d := _dist2_point_seg(pts[i], a, b)
		if d > max_d:
			max_d = d
			idx = i
	if max_d <= eps2:
		return [start, end]
	var left: Array = _dp_rec(pts, start, idx, eps2)
	var right: Array = _dp_rec(pts, idx, end, eps2)
	left.pop_back()
	return left + right


func _dist2_point_seg(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var len2 := ab.length_squared()
	if len2 < 1e-12:
		return p.distance_squared_to(a)
	var t := clampf((p - a).dot(ab) / len2, 0.0, 1.0)
	var proj := a + ab * t
	return p.distance_squared_to(proj)


func _chaikin_open_px(pts: PackedVector2Array, iterations: int) -> PackedVector2Array:
	var cur := pts
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


func _split_wrap_pieces_px(pts: PackedVector2Array, tex_w: int) -> Array:
	var pieces: Array = []
	if pts.size() < 2 or tex_w < 2:
		if pts.size() >= 2:
			pieces.append(pts)
		return pieces
	var max_dx := float(tex_w) * 0.5
	var cur := PackedVector2Array()
	cur.append(pts[0])
	for i in range(1, pts.size()):
		if absf(pts[i].x - cur[cur.size() - 1].x) > max_dx:
			if cur.size() >= 2:
				pieces.append(cur)
			cur = PackedVector2Array()
			cur.append(pts[i])
		else:
			cur.append(pts[i])
	if cur.size() >= 2:
		pieces.append(cur)
	return pieces


func _rebuild_shallow_water(atlas_dir: String) -> void:
	## Brightest ocean pixel in bathymetry ≈ shelf / littoral; lakes & rivers match it.
	_shallow_water = WATER_FILL
	var mask_path := atlas_dir.path_join("land_mask.png")
	var bathy_path := atlas_dir.path_join("bathymetry.png")
	if not FileAccess.file_exists(mask_path) or not FileAccess.file_exists(bathy_path):
		return
	var mask := Image.load_from_file(mask_path)
	var bathy := Image.load_from_file(bathy_path)
	if mask == null or bathy == null:
		return
	if mask.get_width() != bathy.get_width() or mask.get_height() != bathy.get_height():
		return
	var best_lum := -1.0
	var best := WATER_FILL
	var w := mask.get_width()
	var h := mask.get_height()
	# Subsample for speed on Full; Atlas is fine dense.
	var step := 1 if w * h <= 512 * 256 else 2
	for y in range(0, h, step):
		for x in range(0, w, step):
			if mask.get_pixel(x, y).r >= 0.5:
				continue
			var c := bathy.get_pixel(x, y)
			var lum := c.r + c.g + c.b
			if lum > best_lum:
				best_lum = lum
				best = c
	if best_lum >= 0.0:
		_shallow_water = best


func pick_river(local_pos: Vector2, max_dist: float = 4.0) -> Dictionary:
	if not show_rivers:
		return {}
	var best := {}
	var best_d := max_dist
	for feat in _rivers:
		for pts in _to_pixel_polylines(feat.get("coords", [])):
			for i in range(pts.size() - 1):
				var d := _dist_point_segment(local_pos, pts[i], pts[i + 1])
				if d < best_d:
					best_d = d
					best = feat
	return best


func pick_lake(local_pos: Vector2) -> Dictionary:
	if not show_lakes:
		return {}
	for i in range(_lake_rings_px.size()):
		var ring: PackedVector2Array = _lake_rings_px[i]
		var open := ring
		if open.size() >= 2 and open[0].distance_to(open[open.size() - 1]) < 0.5:
			open = open.duplicate()
			open.remove_at(open.size() - 1)
		if open.size() >= 3 and Geometry2D.is_point_in_polygon(local_pos, open):
			return _lake_feats[i] if i < _lake_feats.size() else {"kind": "lake"}
	return {}


func _sanitize_polygon_ring(pts: PackedVector2Array) -> PackedVector2Array:
	## Dedupe consecutive verts; require ≥3 unique; non-zero area. Empty → skip draw.
	if pts.size() < 3:
		return PackedVector2Array()
	var cleaned := PackedVector2Array()
	for p in pts:
		if cleaned.is_empty() or cleaned[cleaned.size() - 1].distance_to(p) > POINT_EPS:
			cleaned.append(p)
	if cleaned.size() >= 2 and cleaned[0].distance_to(cleaned[cleaned.size() - 1]) <= POINT_EPS:
		cleaned.remove_at(cleaned.size() - 1)
	if cleaned.size() < 3:
		return PackedVector2Array()
	# Unique count (coarse).
	var uniq := 0
	for i in range(cleaned.size()):
		var distinct := true
		for j in range(i):
			if cleaned[i].distance_to(cleaned[j]) <= POINT_EPS:
				distinct = false
				break
		if distinct:
			uniq += 1
	if uniq < 3:
		return PackedVector2Array()
	var area2 := 0.0
	for i in range(cleaned.size()):
		var a: Vector2 = cleaned[i]
		var b: Vector2 = cleaned[(i + 1) % cleaned.size()]
		area2 += a.x * b.y - b.x * a.y
	if absf(area2) < maxf(1.0, _width_scale() * _width_scale()):
		return PackedVector2Array()
	return cleaned


func _load_lines(path: String) -> Array:
	var out: Array = []
	if not FileAccess.file_exists(path):
		return out
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		return out
	for feat in data.get("features", []):
		var geom: Dictionary = feat.get("geometry", {})
		var props: Dictionary = feat.get("properties", {})
		if str(geom.get("type", "")) != "LineString":
			continue
		out.append({
			"id": int(props.get("id", 0)),
			"strahler_order": int(props.get("strahler_order", 1)),
			"mean_discharge": float(props.get("mean_discharge", 0.0)),
			"basin_id": int(props.get("basin_id", 0)),
			"monthly_discharge": props.get("monthly_discharge", []),
			"from_lake_id": int(props.get("from_lake_id", 0)),
			"to_lake_id": int(props.get("to_lake_id", 0)),
			"channel_state": str(props.get("channel_state", "")),
			"catchment_km2": float(props.get("catchment_km2", 0.0)),
			"coords": geom.get("coordinates", []),
		})
	return out


func _load_polygons(path: String) -> Array:
	var out: Array = []
	if not FileAccess.file_exists(path):
		return out
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		return out
	for feat in data.get("features", []):
		var geom: Dictionary = feat.get("geometry", {})
		var props: Dictionary = feat.get("properties", {})
		if str(geom.get("type", "")) != "Polygon":
			continue
		var rings: Array = geom.get("coordinates", [])
		if rings.is_empty():
			continue
		var rec := {
			"id": int(props.get("id", 0)),
			"kind": "lake",
			"closed_basin": bool(props.get("closed_basin", true)),
			"water_state": str(props.get("water_state", "")),
			"outlet_type": str(props.get("outlet_type", "")),
			"hydroperiod": str(props.get("hydroperiod", "")),
			"ice_regime": str(props.get("ice_regime", "")),
			"coords": rings[0],
		}
		for k in props.keys():
			if k == "polygon" or rec.has(k):
				continue
			rec[k] = props[k]
		out.append(rec)
	return out


func _to_pixel_polylines(coords: Array) -> Array:
	## Norm coords → texture pixels. Split (do not unwrap) when |Δx|>0.5 so we
	## never draw a dateline chord or flash off-map stubs (A5 + flicker fix).
	var pieces: Array = []
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
		var px := x * _tex_size.x
		var py := (1.0 - clampf(y, -1.0, 1.0)) * 0.5 * _tex_size.y
		pts.append(Vector2(px, py))
	if pts.size() >= 2:
		pieces.append(pts)
	elif pts.size() == 1 and pieces.is_empty():
		pass
	return pieces


func _to_pixels(coords: Array) -> PackedVector2Array:
	## Flatten first polyline piece (legacy helpers / sanitize).
	var pieces := _to_pixel_polylines(coords)
	if pieces.is_empty():
		return PackedVector2Array()
	return pieces[0]


func _dist_point_segment(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var t := 0.0
	var denom := ab.length_squared()
	if denom > 1e-8:
		t = clampf((p - a).dot(ab) / denom, 0.0, 1.0)
	return p.distance_to(a + ab * t)
