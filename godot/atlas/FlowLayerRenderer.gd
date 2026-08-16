extends Node2D
class_name FlowLayerRenderer
## Diagnostic D8 flow arrows (Plan B §6.3.1). Layer toggle — not a map mode.

const FLOW_COLOR := Color(0.45, 0.58, 0.72, 0.40)
const FLOW_COLOR_RIVER := Color(0.15, 0.55, 0.95, 0.95)
## Shaft length as fraction of cell size.
const SHAFT_FRAC := 0.42
## Arrowhead size relative to shaft length.
const HEAD_FRAC := 0.45
const HEAD_ANGLE := 0.55  # radians from shaft axis (~31°)
## Target on-screen cell size before densifying.
const LOD_CELL_PX := 8.0
## World-space stroke ≈ this many screen px / zoom.
const STROKE_SCREEN_PX := 1.15
const STROKE_RIVER_SCREEN_PX := 1.6

## ArcGIS D8 → (dc, dr) → image (x right, y down).
const _D8 := {
	1: Vector2(1, 0),  # E
	2: Vector2(1, 1),  # SE
	4: Vector2(0, 1),  # S
	8: Vector2(-1, 1),  # SW
	16: Vector2(-1, 0),  # W
	32: Vector2(-1, -1),  # NW
	64: Vector2(0, -1),  # N
	128: Vector2(1, -1),  # NE
}

var show_flow: bool = false
var _tex_size: Vector2 = Vector2.ZERO
var _flow_w: int = 0
var _flow_h: int = 0
var _codes: PackedByteArray = PackedByteArray()
var _river: PackedByteArray = PackedByteArray()
var _camera: Camera2D


func _ready() -> void:
	z_index = 15


func set_camera(cam: Camera2D) -> void:
	_camera = cam


func load_atlas(atlas_dir: String, tex_size: Vector2) -> void:
	_tex_size = tex_size
	_codes = PackedByteArray()
	_river = PackedByteArray()
	_flow_w = 0
	_flow_h = 0
	var path := atlas_dir.path_join("flow_direction.png")
	if not FileAccess.file_exists(path):
		queue_redraw()
		return
	var img := Image.load_from_file(path)
	if img == null:
		queue_redraw()
		return
	_flow_w = img.get_width()
	_flow_h = img.get_height()
	if _flow_w < 1 or _flow_h < 1:
		queue_redraw()
		return
	_tex_size = Vector2(_flow_w, _flow_h)
	var n := _flow_w * _flow_h
	_codes.resize(n)
	_river.resize(n)
	for y in range(_flow_h):
		for x in range(_flow_w):
			var c: Color = img.get_pixel(x, y)
			var i := y * _flow_w + x
			# R holds D8 code 1..128 as 8-bit; tolerate float decode.
			var code := int(round(c.r * 255.0))
			if code == 0 and c.r > 0.0:
				code = 1
			_codes[i] = code
			_river[i] = 1 if c.g > 0.5 else 0
	queue_redraw()


func set_show_flow(show: bool) -> void:
	show_flow = show
	queue_redraw()


func notify_zoom_changed() -> void:
	if show_flow:
		queue_redraw()


func _camera_zoom() -> float:
	if _camera != null and _camera.zoom.x > 0.0001:
		return _camera.zoom.x
	return 1.0


func _screen_to_world_width(screen_px: float) -> float:
	return screen_px / _camera_zoom()


func _lod_step() -> int:
	if _flow_w < 1 or _tex_size.x < 1.0:
		return 4
	var cell_screen := (_tex_size.x / float(_flow_w)) * _camera_zoom()
	if cell_screen >= LOD_CELL_PX:
		return 1
	var step := int(ceil(LOD_CELL_PX / maxf(cell_screen, 0.01)))
	return clampi(step, 1, 16)


func _draw_arrow(origin: Vector2, dir: Vector2, length: float, col: Color, width: float) -> void:
	## dir = unit vector pointing downstream; arrowhead at tip.
	if length < 0.15 or dir.length_squared() < 0.01:
		return
	var tip := origin + dir * length
	var tail := origin - dir * length * 0.15
	draw_line(tail, tip, col, width, false)
	var head_len := length * HEAD_FRAC
	var left := dir.rotated(PI - HEAD_ANGLE) * head_len
	var right := dir.rotated(-(PI - HEAD_ANGLE)) * head_len
	draw_line(tip, tip + left, col, width, false)
	draw_line(tip, tip + right, col, width, false)


func _draw() -> void:
	if not show_flow or _flow_w < 1 or _codes.is_empty():
		return
	var step := _lod_step()
	var sx := _tex_size.x / float(_flow_w)
	var sy := _tex_size.y / float(_flow_h)
	var cell := minf(sx, sy)
	var shaft := cell * SHAFT_FRAC
	## Fit / sparse: rivers only (readable). Zoomed: land + rivers.
	var land_too := step <= 2
	var w_land := _screen_to_world_width(STROKE_SCREEN_PX)
	var w_riv := _screen_to_world_width(STROKE_RIVER_SCREEN_PX)
	for y in range(0, _flow_h, step):
		for x in range(0, _flow_w, step):
			var i := y * _flow_w + x
			var code := int(_codes[i])
			if not _D8.has(code):
				continue
			var is_riv := int(_river[i]) == 1
			if not is_riv and not land_too:
				continue
			var delta: Vector2 = _D8[code]
			var dir := delta.normalized()
			var center := Vector2((x + 0.5) * sx, (y + 0.5) * sy)
			if is_riv:
				_draw_arrow(center, dir, shaft * 1.15, FLOW_COLOR_RIVER, w_riv)
			else:
				_draw_arrow(center, dir, shaft * 0.85, FLOW_COLOR, w_land)
