extends SceneTree
## PC7 headless smoke: load atlas meta + climate_summary inspector contract, then quit.

const EXIT_OK := 0
const EXIT_FAIL := 1


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("pc7_smoke: pass world root path (…/output_dir with world/atlas_display)")
		quit(EXIT_FAIL)
		return
	var world_root := str(args[0])
	var atlas := world_root
	if not world_root.ends_with("atlas_display"):
		atlas = world_root.path_join("world/atlas_display")
		if not DirAccess.dir_exists_absolute(atlas):
			atlas = world_root.path_join("atlas_display")
	var meta_path := atlas.path_join("atlas_meta.json")
	var summary_path := atlas.path_join("climate_summary.json")
	if not FileAccess.file_exists(meta_path):
		push_error("missing %s" % meta_path)
		quit(EXIT_FAIL)
		return
	var meta = JSON.parse_string(FileAccess.get_file_as_string(meta_path))
	if typeof(meta) != TYPE_DICTIONARY:
		push_error("invalid atlas_meta.json")
		quit(EXIT_FAIL)
		return
	if str(meta.get("schema", "")) == "":
		push_error("atlas_meta missing schema")
		quit(EXIT_FAIL)
		return
	if not FileAccess.file_exists(summary_path):
		push_error("missing %s" % summary_path)
		quit(EXIT_FAIL)
		return
	var summary = JSON.parse_string(FileAccess.get_file_as_string(summary_path))
	if typeof(summary) != TYPE_DICTIONARY:
		push_error("invalid climate_summary.json")
		quit(EXIT_FAIL)
		return
	var status = summary.get("inspector_status", {})
	if typeof(status) != TYPE_DICTIONARY or status.is_empty():
		push_error("climate_summary missing inspector_status (PC6 contract)")
		quit(EXIT_FAIL)
		return
	print("pc7_smoke ok schema=%s inspector=%s" % [
		str(meta.get("schema")),
		str(summary.get("inspector_contract_version", "?")),
	])
	quit(EXIT_OK)
