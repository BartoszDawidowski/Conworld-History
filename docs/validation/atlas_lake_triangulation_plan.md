# Lake triangulation failure — fix plan (A4b)

**Status:** ✅ Fixed in A4b (Godot guards + worker sanitize) — see `docs/validation/milestone_a4b.md`

## Symptom

Godot debugger (repeated):

```text
VectorLayerRenderer.gd @ _draw(): Invalid polygon data, triangulation failed.
```

Triggered by `draw_colored_polygon` on lake rings from `lakes.geojson`.

## Cause

Worker `physical/vectorize/lakes.py` builds rings via `_boundary_ring` (edge cells ordered by angle around centroid). That is **not** a guaranteed simple polygon → self-intersections, duplicates, zero-area rings. Godot’s canvas triangulator then fails. Atlas UI only checks `pts.size() >= 3`.

## Fix (A4b)

1. **Godot (must):** sanitize / skip invalid rings before draw; eliminate error spam.
2. **Worker (should, if cheap):** reject/fix degenerate rings at export.
3. **Later (not A4b):** real contour extraction if angular rings remain ugly.

Shadowing warnings (`visible` / `seed` / `scale`) = optional rename in same milestone.

## Done when

- Lakes-on Atlas load: no triangulation errors.
- Skipped lakes counted in `docs/validation/milestone_a4b.md` if any.
