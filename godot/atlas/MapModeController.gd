extends Node
class_name MapModeController
## Switches atlas raster colourisation modes.

signal mode_selected(mode: String)

const MODES := [
	"elevation",
	"bathymetry",
	"temperature",
	"precipitation",
	"holdridge",
]

var current_mode: String = "elevation"


func select_mode(mode: String) -> void:
	if mode not in MODES:
		return
	current_mode = mode
	mode_selected.emit(mode)


func cycle(delta: int = 1) -> void:
	var i := MODES.find(current_mode)
	if i < 0:
		i = 0
	i = posmod(i + delta, MODES.size())
	select_mode(MODES[i])
