# Milestone B3 — Land polygons export (Atlas)

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md`  
**Status:** ✅ Complete

## Scope

Export closed **land** rings from `climate/ocean_mask` for atlas presentation (fill/texture in B4). Coast polylines remain unchanged.

## Delivered

| Item | Location |
|---|---|
| `extract_land_polygons` (8-connect + E–W merge, stitch, dateline split) | `worldsim/.../vectorize/land.py` |
| `atlas_display/land.geojson` | `export/atlas_display.py` |
| Diagnostics `land_polygons_diagnostics.json` | polygon count, recall, coverage |
| Tests | `tests/test_land_polygons.py`, atlas export asserts |

## Validation (seed 183716 Atlas climate mask)

| Metric | Value |
|---|---|
| `polygon_count` | 238 |
| `land_cell_recall` | ~0.95 |
| No dateline chords | enforced (`|Δx| ≤ 0.5`) |

Godot **fill / elevation texture** is **B4** (not drawn yet). Existing atlas runs were re-exported with `land.geojson`.

## Acceptance

| Criterion | Result |
|---|---|
| Land rings exported for Atlas-sized climate mask | Met |
| Dateline-safe; islands supported; degenerate filtered | Met |
| Coast still exported | Met |
| Offline recall vs `ocean_mask` | Met (~95% land-cell recall) |
| Full 4096 | Deferred to B7 |

## Stop

B3 complete. Next when instructed: **B4** (land fill + elevation texture in Godot).
