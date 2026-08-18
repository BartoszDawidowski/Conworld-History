extends Node
class_name MapModeController
## Switches atlas raster colourisation modes. Modes = app ∩ atlas descriptors.

signal mode_selected(mode: String)

const APP_MODES := [
	"elevation",
	"bathymetry",
	"temperature",
	"precipitation",
	"holdridge",
	"biome_v2",
	"landforms",
]

## Legacy alias used by older tests / callers.
const MODES := APP_MODES

const DEFAULT_DESCRIPTORS := {
	"elevation": {"id": "elevation", "label": "Elevation", "icon": "El", "kind": "continuous", "file": "elevation.png", "monthly": false},
	"bathymetry": {"id": "bathymetry", "label": "Bathymetry", "icon": "Ba", "kind": "continuous", "file": "bathymetry.png", "monthly": false},
	"temperature": {"id": "temperature", "label": "Temperature", "icon": "Te", "kind": "continuous", "file": "temperature_{month:02d}.png", "monthly": true},
	"precipitation": {"id": "precipitation", "label": "Precipitation", "icon": "Pr", "kind": "continuous", "file": "precipitation_{month:02d}.png", "monthly": true},
	"holdridge": {"id": "holdridge", "label": "Holdridge", "icon": "Ho", "kind": "categorical", "file": "holdridge.png", "legend": "holdridge_zone_legend.json", "monthly": false},
	"biome_v2": {"id": "biome_v2", "label": "Biome V2", "icon": "B2", "kind": "categorical", "file": "biome_v2.png", "legend": "biome_v2_legend.json", "monthly": false},
	"landforms": {"id": "landforms", "label": "Landforms", "icon": "Lf", "kind": "categorical", "file": "landforms.png", "legend": "landform_legend.json", "monthly": false},
}

var current_mode: String = "elevation"
var available_modes: PackedStringArray = PackedStringArray(APP_MODES)
var descriptors: Dictionary = {}


func configure_from_meta(meta: Dictionary) -> void:
	descriptors = DEFAULT_DESCRIPTORS.duplicate(true)
	var declared: PackedStringArray = _declared_mode_ids(meta)
	available_modes = PackedStringArray()
	for mode_id in APP_MODES:
		if declared.is_empty() or mode_id in declared:
			available_modes.append(mode_id)
	if current_mode not in available_modes and available_modes.size() > 0:
		current_mode = str(available_modes[0])


func descriptor(mode_id: String) -> Dictionary:
	if descriptors.has(mode_id):
		return descriptors[mode_id]
	return DEFAULT_DESCRIPTORS.get(mode_id, {})


func is_monthly(mode_id: String) -> bool:
	return bool(descriptor(mode_id).get("monthly", mode_id in ["temperature", "precipitation"]))


func is_categorical(mode_id: String) -> bool:
	return str(descriptor(mode_id).get("kind", "")) == "categorical"


func select_mode(mode: String) -> void:
	if mode not in available_modes and mode not in APP_MODES:
		return
	if available_modes.size() > 0 and mode not in available_modes:
		return
	current_mode = mode
	mode_selected.emit(mode)


func cycle(delta: int = 1) -> void:
	var list := available_modes if available_modes.size() > 0 else PackedStringArray(APP_MODES)
	var i := 0
	for j in range(list.size()):
		if str(list[j]) == current_mode:
			i = j
			break
	i = posmod(i + delta, list.size())
	select_mode(str(list[i]))


func _declared_mode_ids(meta: Dictionary) -> PackedStringArray:
	var out := PackedStringArray()
	var raw = meta.get("map_modes", [])
	if typeof(raw) == TYPE_ARRAY:
		for item in raw:
			if typeof(item) == TYPE_DICTIONARY:
				var mid := str(item.get("id", ""))
				if mid != "":
					out.append(mid)
					descriptors[mid] = item
			else:
				var sid := str(item)
				if sid != "":
					out.append(sid)
	var ids = meta.get("map_mode_ids", [])
	if out.is_empty() and typeof(ids) == TYPE_ARRAY:
		for item in ids:
			out.append(str(item))
	return out
