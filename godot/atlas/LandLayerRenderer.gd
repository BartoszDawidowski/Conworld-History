extends Node2D
class_name LandLayerRenderer
## Plan B4: land_mask stencil; ocean = bathymetry; land = beige (+ elev overlay).

const OCEAN_BG := Color(0.25, 0.45, 0.85, 1.0)  # fallback = shallow / lake family
const LAND_FLAT := Color(0.90, 0.85, 0.74, 1.0)  # light beige fill
const COAST_BEIGE := Color(0.72, 0.64, 0.52, 1.0)

var _tex_size: Vector2 = Vector2.ZERO
var _mode: String = "elevation"
var _has_mask: bool = false
var _sprite: Sprite2D
var _material: ShaderMaterial
var _mask_tex: Texture2D
var _ocean_tex: Texture2D


func _ready() -> void:
	_sprite = Sprite2D.new()
	_sprite.centered = false
	_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	_sprite.visible = false
	add_child(_sprite)
	var sh: Shader = load("res://atlas/land_composite.gdshader") as Shader
	_material = ShaderMaterial.new()
	_material.shader = sh
	_material.set_shader_parameter("ocean_color", OCEAN_BG)
	_material.set_shader_parameter("land_flat", LAND_FLAT)
	_material.set_shader_parameter("has_ocean_tex", 0)
	_material.set_shader_parameter("edge_soft", 0.16)
	_material.set_shader_parameter("mode_blur_texels", 0.65)
	_material.set_shader_parameter("show_coast", 1)
	_material.set_shader_parameter("coast_color", COAST_BEIGE)
	_material.set_shader_parameter("coast_width_px", 1.25)
	_material.set_shader_parameter("elev_overlay_strength", 0.9)
	_material.set_shader_parameter("style", 2)
	_sprite.material = _material


func load_atlas(atlas_dir: String, tex_size: Vector2) -> void:
	_tex_size = tex_size
	_has_mask = false
	_mask_tex = null
	_ocean_tex = null
	var mask_path := atlas_dir.path_join("land_mask.png")
	if FileAccess.file_exists(mask_path):
		var img := Image.load_from_file(mask_path)
		if img != null:
			_mask_tex = ImageTexture.create_from_image(img)
			_has_mask = true
			_tex_size = Vector2(img.get_width(), img.get_height())
	var bathy_path := atlas_dir.path_join("bathymetry.png")
	if FileAccess.file_exists(bathy_path):
		var bimg := Image.load_from_file(bathy_path)
		if bimg != null:
			_ocean_tex = ImageTexture.create_from_image(bimg)
	if _material:
		if _mask_tex:
			_material.set_shader_parameter("land_mask", _mask_tex)
		if _ocean_tex:
			_material.set_shader_parameter("ocean_tex", _ocean_tex)
			_material.set_shader_parameter("has_ocean_tex", 1)
		else:
			_material.set_shader_parameter("has_ocean_tex", 0)
	_apply_mode_visibility()
	queue_redraw()


func set_texture_size(tex_size: Vector2) -> void:
	_tex_size = tex_size
	queue_redraw()


func set_map_mode(mode: String, texture: Texture2D) -> void:
	_mode = mode
	if not _has_mask or _material == null or _sprite == null:
		_apply_mode_visibility()
		queue_redraw()
		return
	if mode == "bathymetry":
		_material.set_shader_parameter("style", 1)
		_material.set_shader_parameter("mode_blur_texels", 0.65)
		_material.set_shader_parameter("edge_soft", 0.16)
		if _ocean_tex != null:
			_sprite.texture = _ocean_tex
		elif _sprite.texture == null and _tex_size.x > 0.0:
			var img := Image.create(int(_tex_size.x), int(_tex_size.y), false, Image.FORMAT_RGBA8)
			img.fill(Color.WHITE)
			_sprite.texture = ImageTexture.create_from_image(img)
	elif mode == "elevation":
		_material.set_shader_parameter("style", 2)
		_material.set_shader_parameter("mode_blur_texels", 0.85)
		_material.set_shader_parameter("edge_soft", 0.16)
		if texture != null:
			_sprite.texture = texture
			_material.set_shader_parameter("mode_tex", texture)
	else:
		_material.set_shader_parameter("style", 0)
		if texture != null:
			_sprite.texture = texture
			_material.set_shader_parameter("mode_tex", texture)
		# Holdridge is categorical — less blur so swatches stay readable.
		if mode == "holdridge":
			_material.set_shader_parameter("mode_blur_texels", 0.15)
			_material.set_shader_parameter("edge_soft", 0.12)
		else:
			_material.set_shader_parameter("mode_blur_texels", 0.65)
			_material.set_shader_parameter("edge_soft", 0.16)
	_apply_mode_visibility()
	queue_redraw()


func has_land() -> bool:
	return _has_mask


func set_show_coast(show: bool) -> void:
	## Coast rim is drawn in the composite shader from the soft land edge.
	if _material:
		_material.set_shader_parameter("show_coast", 1 if show else 0)


func _apply_mode_visibility() -> void:
	if _sprite == null:
		return
	_sprite.visible = _has_mask
