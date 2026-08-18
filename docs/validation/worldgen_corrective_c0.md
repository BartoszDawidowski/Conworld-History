# Worldgen corrective C0 — product-contract hotfixes

**Date:** 2026-08-17  
**Status:** ✅ **Delivered** (fixture + schema gates; no Atlas regen; no physics default retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C0  
**Parent:** [`docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](../WORLDGEN_PHYSICAL_REALISM_ANNEX.md)  
**Audited commit before this package:** `6e7fb94`

---

## Delivered

| Item | Location |
|---|---|
| Atlas GeoJSON keeps lake state axes + identity | `export/atlas_display.py` `lake_atlas_properties` |
| Fail-closed lake draw; one schema warning | `godot/atlas/VectorLayerRenderer.gd` `_lake_is_liquid` |
| BiomeV2 monthly precip not divided by 12 a second time | `ecology/biome_v2.py` |
| `lake_vector_v1` + `atlas_display_v2` schema versions | `lakes_meta.LAKE_VECTOR_SCHEMA`, `ATLAS_DISPLAY_SCHEMA` |
| `WorldSpatialModel` schema v3 (`feature_id` vs `water_body_id`) | `spatial/manifest.py` |
| VectorStore river/lake relationship round-trip | `spatial/vector_store/__init__.py` |
| CR-6…CR-9 notes no longer claim production Accepted | `docs/validation/physical_realism_cr{6,7,8,9}.md` |
| Tests | `tests/test_worldgen_corrective_c0.py` |

`water_state` remains a derived compatibility field. Canonical axes are `outlet_type`, `hydroperiod`, and `ice_regime`. Topographic `feature_id` is not the liquid `water_body_id` (dry playa/ice keep `water_body_id = 0`).

Godot draws only records that explicitly qualify as liquid. Missing `water_state` / `hydroperiod` is not water.

---

## Acceptance

| Criterion | Result |
|---|---|
| Open / endorheic exported with state axes; playa / frozen not liquid | PASS (fixture export) |
| Missing lake state is fail-closed | PASS (Python rule + Godot source) |
| Monthly P = monthly PET → annual deficit 0 | PASS |
| Annual precip reconstructed from months equals the sum | PASS |
| Deliberate factor-of-12 formula is absent | PASS |
| `RiverNode.lake_id`, `from_lake_id`, `to_lake_id` survive save/load | PASS |
| Skipped Atlas CR-6…CR-9 notes are not Status Accepted | PASS |
| `pytest -m "not slow"` | PASS — 290 passed, 3 deselected |

Atlas seed `183716` was **not** regenerated in C0. The contract fix is: atlas export no longer drops `water_state`, and Godot no longer treats a missing state as blue water. That is the demonstrated playa/frozen-as-permanent-lake path. Full shoreline/storage geometry is **C1**.

---

## Explicitly not done

- Discrete A–V–h lake storage and rasterized wet fraction (**C1**)
- Channel-bed losses and physical vs display river mask (**C2**)
- Erosion coefficient recalibration (**C3**)
- Conservative face-flux moisture transport (**C4**)
- Structured `atlas_display_v2` mode descriptors / BiomeV2 / landform Godot modes (**C9**)
- Precipitation or `folding_ratio` retune

**Decision:** accept C0; stop. Next when instructed: **C1** only.
