# River ↔ lake junctions — plan (A4c)

**Status:** ✅ Implemented in A4c — see `docs/validation/milestone_a4c.md`

## Symptom

After A4b clip, rivers often stop **a few pixels short** of the lake fill. In clustered ponds it is hard to see which reach belongs to which lake.

## Why

| Factor | Effect |
|---|---|
| Naive clip drops in-lake vertices | Last point = previous **cell centre**, not shoreline |
| Lake draw = angular hull; clip = `lake_mask` | Boundaries disagree → gap or overlap |
| Godot + worker both clip differently | Extra inconsistency on old vs new exports |
| No `lake_id` on junction | Visual ambiguity in multi-lake scenes |

## Approach (before smoothing)

1. **Topology:** `lake_inlet` / `lake_outlet` nodes with explicit **`lake_id`**.  
2. **Snap:** extend/cut polyline to intersection with lake shoreline (same boundary as fill).  
3. **One authority:** clip+snap in worker export; Godot draws exported geometry.  
4. **IDs from raster** at contact cell — not nearest centroid.

Do **not** start outline smoothing (§7) until junctions look correct.

## Done when

- Gap gone at Atlas zoom on representative crops.  
- Through-flow = same `lake_id` inlet then outlet; no stroke across fill.  
- Recorded in `docs/validation/milestone_a4c.md` after implementation.
