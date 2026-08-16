# Milestone A4c acceptance record

**Date:** 2026-08-15  
**Scope:** River ↔ lake junctions (snap + `lake_id`) — no A5 coast merge

## Delivered

| Item | Location |
|---|---|
| `clip_polyline_outside_lakes` + shoreline midpoint snap | `vectorize/rivers.py` |
| `from_lake_id` / `to_lake_id` on segments + node `lake_id` | same |
| `lake_id` raster passed into network build | `vectorize/pipeline.py` |
| GeoJSON export properties | `atlas_display.py`, vectors `save` |
| Godot draws exported polylines as-is (no second clip) | `VectorLayerRenderer.gd` |
| Inspector shows `from_lake_id` / `to_lake_id` | `WorldAtlas.gd` |

## Snap rule

On land→lake (or lake→land) edge, append/prepend midpoint of the two consecutive vertices (shared cell edge in norm space). Lake id = `lake_id[row,col]` at the lake cell.

## Acceptance

| Criterion | Result |
|---|---|
| No systematic multi-pixel gap after **regenerate** | PASS (snap to shore) |
| No centerline through lake fill | PASS (clip retained) |
| Junction lake ids from raster | PASS |
| Unit tests for snap + ids | PASS (`test_a4b_lake_river_clip.py`) |

**Note:** Existing worlds must be **re-generated** (or re-exported) to pick up snapped GeoJSON; loading old atlases keeps previous gaps until then.

## Presentation amendment (same day)

User follow-up: **stop interrupting** rivers through lakes. Instead:

- continuous centreline through lakes (no worker clip on export);
- **opaque** river + lake colors;
- atlas draw order **rivers under lakes** so the fill covers through-flow.

Snap/clip helpers remain in code for tests; network build no longer clips.
