extends PanelContainer
class_name LegendPanel
## Overlay legend in the map's bottom-right corner. Width follows the zoom box.

@onready var _text: RichTextLabel = %LegendText
@onready var _scroll: ScrollContainer = %LegendScroll
@onready var _header: Button = %LegendHeader

var _collapsed: bool = false
var _last_body: String = ""
var _last_title: String = "Legend"
var _dock_width: float = 160.0
var _max_height: float = 200.0
var _size_sync_queued: bool = false


func _ready() -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.09, 0.11, 0.92)
	sb.set_border_width_all(1)
	sb.border_color = Color(0.32, 0.35, 0.40, 1)
	sb.set_corner_radius_all(4)
	sb.content_margin_left = 4
	sb.content_margin_right = 4
	sb.content_margin_top = 2
	sb.content_margin_bottom = 2
	add_theme_stylebox_override("panel", sb)
	if _header:
		_header.pressed.connect(_toggle_collapsed)
	mouse_filter = Control.MOUSE_FILTER_STOP
	call_deferred("_apply_size")


func sync_layout(width: float, max_height: float) -> void:
	_dock_width = maxf(width, 120.0)
	_max_height = maxf(max_height, 72.0)
	_apply_size()


func set_legend(title: String, entries: Array, overlay_lines: Array = []) -> void:
	_last_title = title if title != "" else "Legend"
	var lines: PackedStringArray = []
	for item in entries:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var color := str(item.get("color", "#888888"))
		var label := str(item.get("label", item.get("key", "")))
		lines.append("[color=%s]■[/color]  %s" % [color, label])
	if overlay_lines.size() > 0 and lines.size() > 0:
		lines.append("")
	for item in overlay_lines:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var color := str(item.get("color", "#888888"))
		var label := str(item.get("label", ""))
		lines.append("[color=%s]—[/color]  %s" % [color, label])
	# Always store body so expanding after a no-legend mode still has entries.
	_last_body = "\n".join(lines)
	visible = lines.size() > 0 or title != ""
	_set_header_text()
	if not visible:
		if _scroll:
			_scroll.visible = false
		if _text:
			_text.text = ""
		_apply_size()
		return
	if _collapsed:
		if _scroll:
			_scroll.visible = false
		if _text:
			_text.text = ""
		_apply_size()
		return
	if _scroll:
		_scroll.visible = true
	if _text:
		_text.text = _last_body
	_apply_size()


func clear_legend() -> void:
	visible = false
	_last_body = ""
	if _text:
		_text.text = ""
	if _scroll:
		_scroll.visible = false
	_apply_size()


func _toggle_collapsed() -> void:
	_collapsed = not _collapsed
	if _scroll:
		_scroll.visible = not _collapsed and visible
	if _collapsed:
		if _text:
			_text.text = ""
	elif _text:
		_text.text = _last_body
	_set_header_text()
	_apply_size()


func _set_header_text() -> void:
	if _header == null:
		return
	var mark := "▸" if _collapsed else "▾"
	_header.text = "%s  %s" % [mark, _last_title]


func _apply_size() -> void:
	var margin := 8.0
	offset_right = -margin
	offset_bottom = -margin
	offset_left = -margin - _dock_width
	if _scroll == null:
		return
	if not visible:
		return
	if _collapsed:
		offset_top = -margin - 36.0
		_scroll.custom_minimum_size = Vector2(_dock_width - 12.0, 0.0)
		return
	_scroll.custom_minimum_size.x = maxf(_dock_width - 12.0, 80.0)
	if _text:
		_text.custom_minimum_size.x = maxf(_dock_width - 28.0, 64.0)
	if not _size_sync_queued:
		_size_sync_queued = true
		call_deferred("_apply_height")


func _apply_height() -> void:
	_size_sync_queued = false
	if not is_inside_tree() or _scroll == null or not visible or _collapsed:
		return
	var content_h := 0.0
	if _text:
		content_h = float(_text.get_content_height())
	var header_h := 28.0
	if _header:
		header_h = maxf(_header.size.y, 24.0)
	var inner := minf(content_h + 8.0, maxf(_max_height - header_h - 16.0, 48.0))
	_scroll.custom_minimum_size.y = inner
	_scroll.visible = content_h > 0.0
	var margin := 8.0
	offset_top = -margin - header_h - inner - 16.0
	offset_left = -margin - _dock_width
	offset_right = -margin
	offset_bottom = -margin
