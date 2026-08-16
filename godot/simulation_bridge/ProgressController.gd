extends Node
class_name ProgressController
## Translates worker NDJSON events into UI-friendly signals.

signal progress_changed(stage: String, value: float)
signal stage_started(stage: String)
signal stage_complete(stage: String)
signal run_started(seed: int)
signal run_complete(world_path: String)
signal run_error(code: String, message: String, stage: String)

var _current_stage: String = ""
var _value: float = 0.0


func handle_event(ev: Dictionary) -> void:
	var kind := str(ev.get("event", ""))
	match kind:
		"started":
			run_started.emit(int(ev.get("seed", 0)))
		"stage_started":
			_current_stage = str(ev.get("stage", ""))
			_value = 0.0
			stage_started.emit(_current_stage)
			progress_changed.emit(_current_stage, 0.0)
		"progress":
			_current_stage = str(ev.get("stage", _current_stage))
			_value = float(ev.get("value", 0.0))
			progress_changed.emit(_current_stage, _value)
		"stage_complete":
			_current_stage = str(ev.get("stage", _current_stage))
			stage_complete.emit(_current_stage)
			progress_changed.emit(_current_stage, 1.0)
		"complete":
			run_complete.emit(str(ev.get("world_path", "")))
		"error":
			run_error.emit(
				str(ev.get("code", "ERROR")),
				str(ev.get("message", "")),
				str(ev.get("stage", ""))
			)
