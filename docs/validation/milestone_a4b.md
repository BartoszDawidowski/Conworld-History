# Milestone A4b acceptance record

**Date:** 2026-08-15  
**Scope:** Default Atlas; river/lake composite; clip rivers through lakes; lake triangulation guards — no A5 coast merge

## Strokes

| Item | Value |
|---|---|
| Lake / river alpha | **0.58** (`WATER_ALPHA`) |
| River source width | **0.07** (`RIVER_WIDTH_MIN`) |
| River mouth width | **0.22** (`RIVER_WIDTH_MAX`, ≈ coast) |
| Formula | `lerpf(MIN, MAX, t)` with `t` from order **1…observed max** in loaded GeoJSON (not fixed 1…8) |

Fix vs first A4b ship: fixed max=8 made orders 1–3 look identical; absolute mouth 0.85 was too thick.

## Delivered

| Item | Location |
|---|---|
| Default profile **Atlas** | `SimulationRunner.gd`, `Main.gd` |
| Godot lake ring sanitize / skip | `VectorLayerRenderer._sanitize_polygon_ring` |
| Godot river∩lake clip (draw + pick) | `_clip_polyline_outside_lakes` |
| Worker lake ring sanitize | `vectorize/lakes.py` |
| Worker river clip vs `lake_mask` | `clip_polyline_outside_lakes` in `rivers.py` |
| Shadowing renames | `overlay_on`, `master_seed`/`world_seed`, `vp_scale` |

## Acceptance

| Criterion | Result |
|---|---|
| Default Generate profile = Atlas | PASS |
| Rivers thinner at sources; mouth ≈ A4 max | PASS |
| Same alpha rivers/lakes | PASS |
| No river stroke through lake fill (Godot + new exports) | PASS |
| No triangulation spam for degenerate lakes | PASS (skip invalid rings) |
| Coast merge | not in scope (A5) |

## Tests

- `tests/test_a4b_lake_river_clip.py`
- `tests/test_godot_atlas_skeleton.py` (A4b markers)
