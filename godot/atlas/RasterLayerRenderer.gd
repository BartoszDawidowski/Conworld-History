extends Node2D
class_name RasterLayerRenderer
## Displays exported atlas PNG map modes as a texture.

signal mode_changed(mode: String)

var _sprite: Sprite2D
var _atlas_dir: String = ""
var _mode: String = "elevation"
var _month: int = 1
var _meta: Dictionary = {}
var _texture_size: Vector2 = Vector2.ZERO
var _land_composite_active: bool = false


func _ready() -> void:
	_sprite = Sprite2D.new()
	_sprite.centered = false
	# Milestone A1: linear filtering for atlas readability when zoomed.
	_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	add_child(_sprite)


func load_atlas(atlas_dir: String, meta: Dictionary) -> void:
	_atlas_dir = atlas_dir
	_meta = meta
	apply_mode(_mode, _month)


func set_month(month: int) -> void:
	_month = clampi(month, 1, int(_meta.get("months", 12)))
	if _mode in ["temperature", "precipitation"]:
		apply_mode(_mode, _month)


func apply_mode(mode: String, month: int = -1) -> void:
	_mode = mode
	if month > 0:
		_month = month
	var path := _path_for_mode(_mode, _month)
	if path.is_empty() or not FileAccess.file_exists(path):
		push_warning("Missing atlas texture: %s" % path)
		return
	var img := Image.load_from_file(path)
	if img == null:
		push_warning("Failed to load image: %s" % path)
		return
	_texture_size = Vector2(img.get_width(), img.get_height())
	var tex := ImageTexture.create_from_image(img)
	_sprite.texture = tex
	_update_sprite_visibility()
	mode_changed.emit(_mode)


func set_land_composite_active(active: bool) -> void:
	## B4 composite (land_mask + ocean bathymetry) owns the map; hide fullscreen raster.
	_land_composite_active = active
	_update_sprite_visibility()


func _update_sprite_visibility() -> void:
	if _sprite == null:
		return
	_sprite.visible = not _land_composite_active


func get_texture() -> Texture2D:
	return _sprite.texture if _sprite else null


func get_mode() -> String:
	return _mode


func get_texture_size() -> Vector2:
	return _texture_size


func map_to_uv(local_pos: Vector2) -> Vector2:
	## Local pixel → normalised cylindrical (x in [0,1), y in [-1,1]).
	if _texture_size.x <= 0.0 or _texture_size.y <= 0.0:
		return Vector2.ZERO
	var u := fposmod(local_pos.x / _texture_size.x, 1.0)
	var v := clampf(local_pos.y / _texture_size.y, 0.0, 1.0)
	var y := 1.0 - v * 2.0
	return Vector2(u, y)


func _path_for_mode(mode: String, month: int) -> String:
	match mode:
		"elevation":
			return _atlas_dir.path_join("elevation.png")
		"bathymetry":
			return _atlas_dir.path_join("bathymetry.png")
		"holdridge":
			return _atlas_dir.path_join("holdridge.png")
		"temperature":
			return _atlas_dir.path_join("temperature_%02d.png" % month)
		"precipitation":
			return _atlas_dir.path_join("precipitation_%02d.png" % month)
		_:
			return _atlas_dir.path_join("elevation.png")
