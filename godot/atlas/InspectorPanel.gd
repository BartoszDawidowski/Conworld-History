extends PanelContainer
class_name InspectorPanel
## Inspects terrain points, rivers, lakes, landforms, or hex aggregates.

@onready var _label: RichTextLabel = %InspectorText
@onready var _tabs: TabBar = get_node_or_null("%InspectorTabs")

const HEX_TAB_ORDER := [
	["location", "Location"],
	["terrain", "Terrain"],
	["climate", "Climate"],
	["ecology", "Ecology"],
	["hydrology", "Hydrology"],
	["objects", "Landforms"],
]

var _mode: String = "elevation"
var _month: int = 1
var _climate_summary: Dictionary = {}
var _legends: Dictionary = {}
var _hex_sections: Dictionary = {}
var _tab_ids: PackedStringArray = PackedStringArray()
var _updating_tabs: bool = false


func _ready() -> void:
	if _tabs:
		_tabs.tab_changed.connect(_on_hex_tab_changed)
		_tabs.visible = false


func set_context(mode: String, month: int) -> void:
	_mode = mode
	_month = clampi(month, 1, 12)


func set_climate_summary(summary: Dictionary) -> void:
	_climate_summary = summary


func set_legends(legends: Dictionary) -> void:
	_legends = legends


func show_terrain(info: Dictionary) -> void:
	_hide_tabs()
	_set_text(_format_section("Terrain point", info))


func show_river(info: Dictionary) -> void:
	_hide_tabs()
	_set_text(_format_river(info))


func show_lake(info: Dictionary) -> void:
	_hide_tabs()
	_set_text(_format_lake(info))


func show_landform(info: Dictionary) -> void:
	_hide_tabs()
	_set_text(_format_landform_object(info))


func show_hex(info: Dictionary) -> void:
	_hex_sections = {
		"location": _rows_text([
			["Hex ID", info.get("hex_id", null), ""],
			["Latitude", info.get("latitude_deg", null), "°"],
			["Cell count", info.get("cell_count", null), ""],
			["Land", _pct(info.get("land_fraction", null)), ""],
			["Ocean", _pct(info.get("ocean_fraction", null)), ""],
			["Permanent water", _pct(info.get("permanent_water_fraction", null)), ""],
			["Seasonal water", _pct(info.get("seasonal_water_fraction", null)), ""],
		]),
		"terrain": _rows_text([
			["Elevation mean", info.get("elevation_mean_m", info.get("elevation_mean", null)), " m"],
			["Elevation min", info.get("elevation_min_m", null), " m"],
			["Elevation max", info.get("elevation_max_m", null), " m"],
			["Local relief", info.get("local_relief_mean_m", null), " m"],
			["Mean slope", info.get("slope_mean_deg", null), "°"],
			["Landform context", _label_id("landform", "broad_context", info.get("context_dominant", null)), ""],
			["Local form", _label_id("landform", "local_form", info.get("local_form_dominant", null)), ""],
			["Mountain score", _score(info.get("mountain_score_mean", null)), ""],
			["Mountain terrain", _pct(info.get("mountain_terrain_fraction", null)), ""],
			["Mountain range", _pct(info.get("mountain_range_fraction", null)), ""],
			["Plateau score", _score(info.get("plateau_score_mean", null)), ""],
			["Plateau context", _pct(info.get("plateau_context_fraction", null)), ""],
			["Plateau object", _pct(info.get("plateau_object_fraction", null)), ""],
			["Barrier strength", _score(info.get("terrain_barrier_strength", null)), ""],
		]),
		"climate": _rows_text([
			["Month %d temperature" % _month, info.get("temperature_month_c", null), " °C"],
			["Annual mean temperature", info.get("temperature_annual_c", null), " °C"],
			["Month %d precipitation" % _month, info.get("precipitation_month_mm", null), " mm proxy"],
			["Annual precipitation", info.get("precipitation_annual_mm", info.get("precipitation_annual", null)), " mm proxy"],
			["Month %d RH proxy" % _month, info.get("humidity_month_proxy", null), ""],
			["Frost months", info.get("frost_months_mean", null), ""],
			["Growing-season months", info.get("growing_season_months_mean", null), ""],
			["Water deficit", info.get("water_deficit_mm_mean", null), " mm"],
			["Soil state", _soil_label(info.get("soil_state_dominant", null)), ""],
		]),
		"ecology": _rows_text([
			["Biome V2", _biome_label(info.get("biome_v2_dominant", null)), ""],
			["Holdridge", info.get("holdridge", _holdridge_label(info.get("holdridge_dominant", info.get("holdridge_id", null)))), ""],
		]),
		"hydrology": _rows_text([
			["Basin IDs", info.get("basin_ids", null), ""],
			["Permanent water", _pct(info.get("permanent_water_fraction", null)), ""],
			["Seasonal water", _pct(info.get("seasonal_water_fraction", null)), ""],
			["Perennial channel", _pct(info.get("perennial_river_fraction", null)), ""],
			["Seasonal channel", _pct(info.get("seasonal_river_fraction", null)), ""],
			["Wadi", _pct(info.get("wadi_fraction", null)), ""],
			["Mean effective discharge", info.get("mean_effective_discharge", null), ""],
			["River IDs", info.get("river_ids", info.get("river_ids_nonempty", null)), ""],
			["Lake IDs", info.get("lake_ids", null), ""],
		]),
		"objects": _rows_text([
			["Mountain-range IDs", info.get("mountain_range_ids", null), ""],
			["Plateau IDs", info.get("plateau_ids", null), ""],
		]),
	}
	_rebuild_hex_tabs()
	_render_active_hex_tab()


func _format_hex(info: Dictionary) -> String:
	show_hex(info)
	return _label.text if _label else ""


func show_feature(kind: String, info: Dictionary) -> void:
	match kind:
		"river":
			show_river(info)
		"lake":
			show_lake(info)
		"hex":
			show_hex(info)
		"mountain_range", "plateau", "ridge", "plateau_rim":
			show_landform(info)
		_:
			show_terrain(info)


func show_message(text: String) -> void:
	_hide_tabs()
	_set_text(text)


func clear_inspector() -> void:
	_hide_tabs()
	_set_text(_status_line() + "Click the map to inspect a lake, river, landform, or hex.")


func _hide_tabs() -> void:
	if _tabs:
		_tabs.visible = false


func _rebuild_hex_tabs() -> void:
	if _tabs == null:
		return
	var keep := ""
	if _tabs.tab_count > 0 and _tab_ids.size() > _tabs.current_tab and _tabs.current_tab >= 0:
		keep = str(_tab_ids[_tabs.current_tab])
	_updating_tabs = true
	while _tabs.tab_count > 0:
		_tabs.remove_tab(0)
	_tab_ids = PackedStringArray()
	for pair in HEX_TAB_ORDER:
		var sid := str(pair[0])
		if str(_hex_sections.get(sid, "")) == "":
			continue
		_tabs.add_tab(str(pair[1]))
		_tab_ids.append(sid)
	_tabs.visible = _tab_ids.size() > 0
	var prefer := keep if keep in _tab_ids else _preferred_hex_tab()
	var idx := 0
	for i in range(_tab_ids.size()):
		if str(_tab_ids[i]) == prefer:
			idx = i
			break
	if _tabs.tab_count > 0:
		_tabs.current_tab = idx
	_updating_tabs = false


func _preferred_hex_tab() -> String:
	match _mode:
		"elevation", "bathymetry":
			return "terrain"
		"landforms":
			return "objects" if str(_hex_sections.get("objects", "")) != "" else "terrain"
		"temperature", "precipitation":
			return "climate"
		"holdridge", "biome_v2":
			return "ecology"
		_:
			return "location"


func _on_hex_tab_changed(_tab: int) -> void:
	if _updating_tabs:
		return
	_render_active_hex_tab()


func _render_active_hex_tab() -> void:
	var sid := "location"
	if _tabs and _tab_ids.size() > _tabs.current_tab and _tabs.current_tab >= 0:
		sid = str(_tab_ids[_tabs.current_tab])
	var title := sid.capitalize()
	for pair in HEX_TAB_ORDER:
		if str(pair[0]) == sid:
			title = str(pair[1])
			break
	var body := str(_hex_sections.get(sid, ""))
	if body == "":
		body = "No data"
	_set_text("%s[b]%s[/b]\n%s" % [_status_line(), title, body])


func _set_text(text: String) -> void:
	if _label:
		_label.text = text


func _status_line() -> String:
	if _climate_summary.is_empty():
		return ""
	var status = _climate_summary.get("inspector_status", {})
	if typeof(status) == TYPE_DICTIONARY and not status.is_empty():
		var bits: PackedStringArray = []
		bits.append("Moisture %s" % _mark_status(status.get("moisture_ok", false)))
		bits.append("Snow/Firn %s" % _mark_status(status.get("snow_firn_ok", false)))
		bits.append("Hydro %s" % _mark_status(status.get("hydrology_ok", false)))
		bits.append("Erosion %s" % _mark_status(status.get("erosion_ok", false)))
		bits.append("Landforms %s" % _mark_landforms(status))
		var warn = _climate_summary.get("warnings", [])
		var amber := ""
		if typeof(warn) == TYPE_ARRAY and warn.size() > 0:
			amber = "\n[color=#E6B35A]⚠ %s[/color]" % str(warn[0])
		return "[b]%s[/b]%s\n\n" % ["   ".join(bits), amber]
	var bits: PackedStringArray = []
	bits.append("Temperature %s" % _mark("temperature_integrity_ok"))
	bits.append("Spin-up %s" % _mark("moisture_spinup_ok"))
	bits.append("Water budget %s" % _mark("moisture_budget_ok"))
	bits.append("Hydro feedback %s" % _mark("hydrology_coupling_ok"))
	var warn = _climate_summary.get("warnings", [])
	var amber := ""
	if typeof(warn) == TYPE_ARRAY and warn.size() > 0:
		amber = "\n[color=#E6B35A]⚠ %s[/color]" % str(warn[0])
	return "[b]%s[/b]%s\n\n" % ["   ".join(bits), amber]


func _mark_status(ok: bool) -> String:
	return "✓" if ok else "✕"


func _mark_landforms(status: Dictionary) -> String:
	if bool(status.get("landforms_ok", false)):
		return "✓"
	if bool(status.get("landforms_warning", false)):
		return "⚠"
	return "✕"


func _mark(key: String) -> String:
	if bool(_climate_summary.get(key, false)):
		return "✓"
	return "✕"


func _rows_text(rows: Array) -> String:
	var lines: PackedStringArray = []
	for row in rows:
		var value = row[1]
		if _is_missing(value):
			continue
		var unit := str(row[2]) if row.size() > 2 else ""
		lines.append("%s: %s%s" % [str(row[0]), _fmt(value), unit])
	return "\n".join(lines)


func _format_river(info: Dictionary) -> String:
	var body := _rows_text([
		["ID", info.get("id", info.get("parent_segment_id", null)), ""],
		["State", info.get("channel_state", null), ""],
		["Strahler", info.get("strahler_order", null), ""],
		["Catchment", info.get("catchment_km2", null), " km²"],
		["Mean discharge", info.get("mean_discharge", null), ""],
		["Bed-loss mean", info.get("bed_loss_mean", null), ""],
		["Basin ID", info.get("basin_id", null), ""],
		["From lake", info.get("from_lake_id", null), ""],
		["To lake", info.get("to_lake_id", null), ""],
	])
	return "%s[b]River[/b]\n%s" % [_status_line(), body]


func _format_lake(info: Dictionary) -> String:
	var body := _rows_text([
		["ID", info.get("id", info.get("lake_id", info.get("water_body_id", null))), ""],
		["Basin ID", info.get("basin_id", null), ""],
		["Outlet type", info.get("outlet_type", null), ""],
		["Hydroperiod", info.get("hydroperiod", null), ""],
		["Ice regime", info.get("ice_regime", null), ""],
		["Mean wet area", info.get("mean_wet_area_km2", null), " km²"],
		["Envelope area", info.get("envelope_area_km2", null), " km²"],
		["Surface elevation", info.get("surface_elevation", null), " m"],
		["Spill elevation", info.get("spill_elevation", null), " m"],
		["Mean inflow", info.get("mean_effective_inflow", null), ""],
		["Inlet rivers", info.get("inlet_river_ids", null), ""],
		["Outlet river", info.get("outlet_river_id", null), ""],
	])
	return "%s[b]Lake[/b]\n%s" % [_status_line(), body]


func _format_landform_object(info: Dictionary) -> String:
	var kind := str(info.get("kind", "landform")).replace("_", " ")
	var props: Dictionary = info.get("properties", info)
	var body := _rows_text([
		["ID", props.get("id", info.get("id", null)), ""],
		["Area", props.get("area_km2", null), " km²"],
		["Mean elevation", props.get("mean_elev_m", null), " m"],
		["Max elevation", props.get("max_elev_m", null), " m"],
		["Base elevation", props.get("base_elev_m", null), " m"],
		["Local relief", props.get("local_relief_m", props.get("internal_relief_m", null)), " m"],
		["Orientation", props.get("orientation_deg", null), "°"],
		["Elongation", props.get("elongation", null), ""],
		["Mean slope", props.get("mean_slope", null), ""],
		["Provenance", _label_id("landform", "provenance", props.get("provenance_mode", null)), ""],
		["Confidence", _score(props.get("confidence", null)), ""],
		["Crosses E–W seam", props.get("crosses_ew_seam", null), ""],
	])
	return "%s[b]%s[/b]\n%s" % [_status_line(), kind.capitalize(), body]


func _format_section(title: String, info: Dictionary) -> String:
	var lines: PackedStringArray = []
	var keys := info.keys()
	keys.sort()
	for k in keys:
		var v = info[k]
		if _is_missing(v):
			continue
		lines.append("%s: %s" % [str(k).replace("_", " "), str(v)])
	return "%s[b]%s[/b]\n%s" % [_status_line(), title, "\n".join(lines)]


func _is_missing(value) -> bool:
	if value == null:
		return true
	if typeof(value) == TYPE_FLOAT and not is_finite(float(value)):
		return true
	if typeof(value) == TYPE_STRING and str(value) == "":
		return true
	if typeof(value) == TYPE_ARRAY and value.size() == 0:
		return true
	return false


func _fmt(value) -> String:
	if typeof(value) == TYPE_FLOAT:
		return "%.2f" % float(value)
	return str(value)


func _pct(value) -> Variant:
	if _is_missing(value):
		return null
	if typeof(value) in [TYPE_FLOAT, TYPE_INT]:
		return "%.0f%%" % (float(value) * 100.0)
	return value


func _score(value) -> Variant:
	if _is_missing(value):
		return null
	if typeof(value) in [TYPE_FLOAT, TYPE_INT]:
		return "%.2f" % float(value)
	return value


func _biome_label(zid) -> Variant:
	if _is_missing(zid):
		return null
	var classes = _legends.get("biome_v2", {}).get("classes", {})
	var rec = classes.get(str(int(zid)), {})
	if typeof(rec) == TYPE_DICTIONARY and rec.has("label"):
		return rec["label"]
	return str(zid)


func _holdridge_label(zid) -> Variant:
	if _is_missing(zid):
		return null
	var legend = _legends.get("holdridge", {})
	var classes = legend.get("classes", {})
	if typeof(classes) == TYPE_DICTIONARY:
		var rec = classes.get(str(int(zid)), {})
		if typeof(rec) == TYPE_DICTIONARY and rec.has("label"):
			return rec["label"]
	if legend.has(str(int(zid))):
		var raw = legend[str(int(zid))]
		if typeof(raw) == TYPE_STRING:
			return raw
	return str(zid)


func _label_id(group: String, section: String, zid) -> Variant:
	if _is_missing(zid):
		return null
	var block = _legends.get(group, {}).get(section, {})
	var rec = block.get(str(int(zid)), {})
	if typeof(rec) == TYPE_DICTIONARY:
		return rec.get("label", rec.get("key", str(zid)))
	if typeof(rec) == TYPE_STRING and rec != "":
		return rec
	return str(zid)


func _soil_label(zid) -> Variant:
	if _is_missing(zid):
		return null
	match int(zid):
		0:
			return "ocean / dry"
		1:
			return "moist"
		2:
			return "wet"
		3:
			return "saturated"
		_:
			return str(zid)
