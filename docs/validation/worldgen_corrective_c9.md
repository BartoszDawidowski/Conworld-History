# Worldgen corrective C9 — Godot BiomeV2, landforms, legends, inspector

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (Python palettes + Godot modes/picking/inspector; no Atlas regen; no YAML/folding/Holdridge/`mountain_score_threshold` retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C9 + §7–§8  
**Depends on:** C8 (hex/query/export contract)  
**Audited commit before this package:** post-C8 working tree

---

## Delivered

| Item | Location |
|---|---|
| Structured `atlas_display_v2` mode descriptors | `export/atlas_display.py` `PRIMARY_MODE_DESCRIPTORS` |
| Python-owned BiomeV2 palette + legend schema v1 | `ecology/biome_v2.py` `biome_v2_legend()` |
| Derived `display_landform_id` (does not replace canonical layers) | `landforms/classify.py` `derive_display_landform_id()` |
| `biome_v2.png` / `landforms.png` + JSON legends | atlas export |
| `inspection_grid.bin/.json`, `climate_summary.json` | `export/inspection_grid.py` |
| Godot modes El/Ba/Te/Pr/Ho/**B2**/**Lf** | `MapModeController.gd` ∩ atlas descriptors |
| Categorical nearest-neighbour, zero blur | `RasterLayerRenderer.gd`, `LandLayerRenderer.gd`, shader `sample_mode` |
| `LegendPanel.gd` on existing `Main.tscn` panel | swatches from Python JSON |
| `LandformLayerRenderer.gd` + **Landform objects** toggle | styles from `landform_legend.json` |
| Picking: lake → river → range/plateau → **always hex** | `WorldAtlas.gd` |
| Sectioned inspector, labels, no false zeros | `InspectorPanel.gd` |
| Tests | `tests/test_worldgen_corrective_c9.py` |

Canonical C8 legends (`categorical_legends` id→name) stay. Display legends are a separate JSON product. Production `mountain_score_threshold = 0.60` unchanged.

---

## Palettes (Python is SoT)

BiomeV2 title: **Seasonal ecological regime (BiomeV2)**. Ocean swatch documents the class; land-composite ocean still uses ordinary bathymetry.

![BiomeV2 palette](worldgen_corrective_c9/biome_v2_palette.png)

Display landform priority: ocean → accepted range → plateau object/context → basin → remaining upland → plain. Range∩plateau overlap is counted, not used to rewrite canonical classification.

![Landform display palette](worldgen_corrective_c9/landform_palette.png)

These strips are generated with `paint_categorical_rgb` (the same function that writes atlas PNGs). They are not live Atlas `183716` Fit/4× screenshots.

---

## Godot behaviour

- Toolbar shows the intersection of app modes and atlas `map_modes`. v1 string lists still parse; missing B2/Lf files hide those buttons.
- `apply_mode` commits `_mode` only after the PNG loads.
- Hex inspection works with the overlay hidden. Month spin stays on the last month when switching to a static mode; it is disabled, not reset.
- Landform overlay may turn on once when entering **Lf**, then the checkbox owns the choice.
- Object stroke widths are zoom-invariant screen pixels from Python `object_styles`.

---

## Acceptance

| Criterion | Result |
|---|---|
| structured `map_modes` + v1 string-list parser | PASS |
| PNG colours = legend hex colours | PASS (export + strips) |
| `display_landform_id` priority + overlap count | PASS |
| inspection grid round-trip including NaN | PASS |
| no Godot classification threshold / class palettes | PASS (neutral fallbacks only) |
| `LandformLayerRenderer` / `LegendPanel` / picking order | PASS (source contract) |
| `pytest -m "not slow"` | PASS — 384 passed, 3 deselected |
| Atlas `183716` Fit + 4× live screenshots | **Leftover** — world not regenerated |

---

## Explicitly not done

- **C10** multi-seed calibration, Full RSS, landform threshold retune
- Atlas `183716` regeneration
- YAML / folding / Holdridge / `mountain_score_threshold` changes
- Live Godot Fit/4× screenshots of a generated world (requires leftover regen)

**Decision:** accept C9 display/inspector integration; stop. Next when instructed: **C10** only.
