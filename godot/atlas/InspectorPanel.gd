extends PanelContainer
class_name InspectorPanel
## Inspects terrain points, rivers, or hex aggregates (architecture §43).

@onready var _label: RichTextLabel = %InspectorText

const _HEX_FIELD_ORDER := [
	"hex_id",
	"holdridge",
	"holdridge_id",
	"cell_count",
	"temperature_annual_c",
	"precipitation_annual",
	"elevation_mean_m",
	"land_fraction",
	"ocean_fraction",
	"lake_fraction",
	"permeability_mean",
	"river_ids",
]


func show_terrain(info: Dictionary) -> void:
	_set_text(_format_section("Terrain point", info))


func show_river(info: Dictionary) -> void:
	_set_text(_format_section("River", info))


func show_hex(info: Dictionary) -> void:
	_set_text(_format_hex(info))


func show_message(text: String) -> void:
	_set_text(text)


func clear_inspector() -> void:
	_set_text("Click the map to inspect terrain, a river, or a hex.")


func _set_text(text: String) -> void:
	if _label:
		_label.text = text


func _format_hex(info: Dictionary) -> String:
	## Holdridge label primary; climate aggregates when exported (A8+).
	var lines: PackedStringArray = ["[b]Hex (analytical cache)[/b]"]
	var seen: Dictionary = {}
	for key in _HEX_FIELD_ORDER:
		if not info.has(key):
			continue
		seen[key] = true
		var val = info[key]
		if key == "holdridge":
			lines.append("holdridge: [b]%s[/b]" % str(val))
		elif typeof(val) == TYPE_FLOAT:
			lines.append("%s: %.3f" % [key, float(val)])
		else:
			lines.append("%s: %s" % [key, str(val)])
	var keys := info.keys()
	keys.sort()
	for k in keys:
		var key := str(k)
		if seen.has(key) or key == "holdridge_dominant" or key == "elevation_mean":
			continue
		lines.append("%s: %s" % [key, str(info[k])])
	return "\n".join(lines)


func _format_section(title: String, info: Dictionary) -> String:
	var lines: PackedStringArray = ["[b]%s[/b]" % title]
	var keys := info.keys()
	keys.sort()
	for k in keys:
		lines.append("%s: %s" % [str(k), str(info[k])])
	return "\n".join(lines)
