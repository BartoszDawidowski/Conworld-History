extends Node
class_name SimulationRunner
## Launches packaged worldsim_worker or `python -m worldsim` (architecture §8).
## Progress is captured via an NDJSON log file (reliable across platforms).

signal line_received(line: String)
signal process_exited(code: int)

## Generation profiles (Milestone A2). Full = packaged config defaults.
const PROFILE_QUICK := "quick"
const PROFILE_ATLAS := "atlas"
const PROFILE_FULL := "full"

@export var python_executable: String = ""
@export var worldsim_root: String = ""
@export var worker_executable: String = ""
@export var default_stage: String = "world"
## Default Generate profile: Atlas (mid). Full remains selectable.
@export var generation_profile: String = PROFILE_ATLAS

var _pid: int = -1
var _running: bool = false
var _progress_path: String = ""
var _progress_offset: int = 0


func _ready() -> void:
	if worker_executable.is_empty():
		worker_executable = _detect_packaged_worker()
	if python_executable.is_empty():
		python_executable = _detect_python()
	if worldsim_root.is_empty():
		worldsim_root = _detect_worldsim_root()


func is_running() -> bool:
	return _running


func uses_packaged_worker() -> bool:
	## Prefer repo venv / source worldsim when available so atlas export tracks
	## checked-in Python (packaged worker can lag behind).
	if not python_executable.is_empty() and FileAccess.file_exists(python_executable):
		var src := worldsim_root.path_join("src/worldsim/__main__.py")
		if worldsim_root.is_empty():
			src = _detect_worldsim_root().path_join("src/worldsim/__main__.py")
		if FileAccess.file_exists(src):
			return false
	return not worker_executable.is_empty() and FileAccess.file_exists(worker_executable)


func start_generation(
	master_seed: int,
	output_dir: String,
	stage: String = "",
	profile: String = "",
	config_path: String = "",
) -> Error:
	if _running:
		return ERR_BUSY
	if stage.is_empty():
		stage = default_stage
	if profile.is_empty():
		profile = generation_profile

	DirAccess.make_dir_recursive_absolute(output_dir)
	_progress_path = output_dir.path_join("progress.ndjson")
	var err_path := output_dir.path_join("worker.stderr.log")
	var f := FileAccess.open(_progress_path, FileAccess.WRITE)
	if f:
		f.close()
	f = FileAccess.open(err_path, FileAccess.WRITE)
	if f:
		f.close()

	var args := _build_args(master_seed, output_dir, stage, profile, config_path)
	var is_win := OS.get_name() == "Windows"
	var quoted_args := _quote_arg_list(args, is_win)
	var shell: String
	var shell_args: PackedStringArray

	if uses_packaged_worker():
		if is_win:
			shell = "cmd.exe"
			shell_args = PackedStringArray([
				"/C",
				"%s %s > %s 2> %s" % [
					_win_quote(worker_executable),
					quoted_args,
					_win_quote(_progress_path),
					_win_quote(err_path),
				],
			])
		else:
			shell = "/bin/zsh"
			shell_args = PackedStringArray([
				"-lc",
				"%s %s > %s 2> %s" % [
					_shell_quote(worker_executable),
					quoted_args,
					_shell_quote(_progress_path),
					_shell_quote(err_path),
				],
			])
	else:
		var py := python_executable
		if py.is_empty():
			push_error("Neither packaged worker nor Python executable found")
			return ERR_FILE_NOT_FOUND
		if is_win:
			shell = "cmd.exe"
			shell_args = PackedStringArray([
				"/C",
				"cd /d %s && %s -m worldsim %s > %s 2> %s" % [
					_win_quote(worldsim_root),
					_win_quote(py),
					quoted_args,
					_win_quote(_progress_path),
					_win_quote(err_path),
				],
			])
		else:
			shell = "/bin/zsh"
			shell_args = PackedStringArray([
				"-lc",
				"cd %s && %s -m worldsim %s > %s 2> %s" % [
					_shell_quote(worldsim_root),
					_shell_quote(py),
					quoted_args,
					_shell_quote(_progress_path),
					_shell_quote(err_path),
				],
			])

	_pid = OS.create_process(shell, shell_args)
	if _pid <= 0:
		push_error("Failed to launch worldsim worker")
		return FAILED
	_running = true
	_progress_offset = 0
	set_process(true)
	return OK


func stop_generation() -> void:
	if _pid > 0 and OS.is_process_running(_pid):
		OS.kill(_pid)
	_cleanup()


func _process(_delta: float) -> void:
	if not _running:
		return
	_read_new_lines()
	if _pid > 0 and not OS.is_process_running(_pid):
		_read_new_lines()
		var code := OS.get_process_exit_code(_pid)
		process_exited.emit(code)
		_cleanup()


func _build_args(
	master_seed: int,
	output_dir: String,
	stage: String,
	profile: String = PROFILE_ATLAS,
	config_path: String = "",
) -> PackedStringArray:
	var args := PackedStringArray([
		"--seed", str(master_seed),
		"--output", output_dir,
		"--stage", stage,
	])
	if not config_path.is_empty():
		args.append_array(PackedStringArray(["--config", config_path]))
	# Full: no size overrides → worldsim uses default_planet.yaml resolutions.
	match profile:
		PROFILE_QUICK:
			args.append_array(PackedStringArray([
				"--tectonics-width", "128",
				"--tectonics-height", "64",
				"--terrain-width", "256",
				"--terrain-height", "128",
				"--climate-width", "128",
				"--climate-height", "64",
			]))
		PROFILE_ATLAS:
			args.append_array(PackedStringArray([
				"--tectonics-width", "512",
				"--tectonics-height", "256",
				"--terrain-width", "1024",
				"--terrain-height", "512",
				"--climate-width", "512",
				"--climate-height", "256",
			]))
		_:
			pass
	return args


func _quote_arg_list(args: PackedStringArray, windows: bool) -> String:
	var parts: PackedStringArray = []
	for a in args:
		parts.append(_win_quote(a) if windows else _shell_quote(a))
	return " ".join(parts)


func _read_new_lines() -> void:
	if _progress_path.is_empty() or not FileAccess.file_exists(_progress_path):
		return
	var file := FileAccess.open(_progress_path, FileAccess.READ)
	if file == null:
		return
	file.seek(_progress_offset)
	while not file.eof_reached():
		var line := file.get_line()
		_progress_offset = file.get_position()
		if line.strip_edges().is_empty():
			continue
		line_received.emit(line)
	file.close()


func _cleanup() -> void:
	_running = false
	_pid = -1
	set_process(false)


func _detect_packaged_worker() -> String:
	var repo := _repo_root()
	var exe_name := "worldsim_worker.exe" if OS.get_name() == "Windows" else "worldsim_worker"
	var candidates := [
		OS.get_executable_path().get_base_dir().path_join(exe_name),
		repo.path_join("packaging/dist/worldsim_worker").path_join(exe_name),
		repo.path_join("dist/worldsim_worker").path_join(exe_name),
		ProjectSettings.globalize_path("res://").rstrip("/").path_join(exe_name),
	]
	for c in candidates:
		if FileAccess.file_exists(c):
			return c
	return ""


func _detect_python() -> String:
	var repo := _repo_root()
	if OS.get_name() == "Windows":
		var win_path := repo.path_join("worldsim/.venv/Scripts/python.exe")
		if FileAccess.file_exists(win_path):
			return win_path
		return "py"
	var candidates := [
		repo.path_join("worldsim/.venv/bin/python"),
		repo.path_join("worldsim/.venv/bin/python3.12"),
		"/opt/homebrew/bin/python3.12",
		"/usr/local/bin/python3.12",
	]
	for c in candidates:
		if FileAccess.file_exists(c):
			return c
	return "python3.12"


func _detect_worldsim_root() -> String:
	return _repo_root().path_join("worldsim")


func _repo_root() -> String:
	var godot_dir := ProjectSettings.globalize_path("res://").rstrip("/")
	return godot_dir.get_base_dir()


func _shell_quote(path: String) -> String:
	return "'%s'" % path.replace("'", "'\\''")


func _win_quote(path: String) -> String:
	return "\"%s\"" % path.replace("\"", "\\\"")
