shader_type canvas_item;

// Soft land fill; elevation = beige base + mono overlay; AA coast hairline.

uniform sampler2D land_mask : filter_linear, repeat_disable;
uniform sampler2D mode_tex : filter_linear, repeat_disable;
uniform sampler2D ocean_tex : filter_linear, repeat_disable;
uniform vec4 ocean_color : source_color = vec4(0.25, 0.45, 0.85, 1.0);
uniform vec4 land_flat : source_color = vec4(0.90, 0.85, 0.74, 1.0);
uniform vec4 coast_color : source_color = vec4(0.72, 0.64, 0.52, 1.0);
// 0 = full mode tex on land, 1 = flat land (bathymetry), 2 = beige + mono elev overlay
uniform int style = 2;
uniform int has_ocean_tex = 0;
uniform int show_coast = 1;
uniform float edge_soft = 0.16;
uniform float mode_blur_texels = 0.65;
// Screen-space coast half-width (pixels); AA fringe beyond this.
uniform float coast_width_px = 1.25;
uniform float elev_overlay_strength = 0.9;

vec4 sample_blurred(sampler2D tex, vec2 uv, float texels) {
	if (texels <= 0.001) {
		return texture(tex, uv);
	}
	ivec2 sz = textureSize(tex, 0);
	vec2 px = vec2(texels) / vec2(float(max(sz.x, 1)), float(max(sz.y, 1)));
	vec4 c = texture(tex, uv) * 0.4;
	c += texture(tex, uv + vec2(px.x, 0.0)) * 0.15;
	c += texture(tex, uv - vec2(px.x, 0.0)) * 0.15;
	c += texture(tex, uv + vec2(0.0, px.y)) * 0.15;
	c += texture(tex, uv - vec2(0.0, px.y)) * 0.15;
	return c;
}

void fragment() {
	float raw = texture(land_mask, UV).r;
	float m = smoothstep(0.5 - edge_soft, 0.5 + edge_soft, raw);

	vec4 ocean = has_ocean_tex == 1
		? sample_blurred(ocean_tex, UV, mode_blur_texels)
		: ocean_color;

	vec3 land_rgb = land_flat.rgb;
	if (style == 0) {
		land_rgb = sample_blurred(mode_tex, UV, mode_blur_texels).rgb;
	} else if (style == 2) {
		vec4 elev = sample_blurred(mode_tex, UV, mode_blur_texels);
		float g = dot(elev.rgb, vec3(0.299, 0.587, 0.114));
		// Monochrome relief: darken lows, lift highs over beige fill.
		float shade = mix(0.58, 1.12, clamp(g, 0.0, 1.0));
		land_rgb = land_flat.rgb * mix(1.0, shade, elev_overlay_strength);
	}

	vec4 base_color = mix(ocean, vec4(land_rgb, 1.0), m);

	// Continuous screen-space isocontour (no hard step → no vanish / stair blocks).
	float w = max(fwidth(raw), 1e-4);
	float d_px = abs(raw - 0.5) / w;
	float core = coast_width_px * 0.55;
	float rim = 1.0 - smoothstep(core, core + 1.15, d_px);
	if (show_coast == 1) {
		COLOR = mix(base_color, vec4(coast_color.rgb, 1.0), rim);
	} else {
		COLOR = base_color;
	}
}
