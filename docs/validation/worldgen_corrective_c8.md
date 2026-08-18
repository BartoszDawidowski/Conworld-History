# Worldgen corrective C8 — canonical model, hex contract, queries, export

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no Godot BiomeV2/landform modes)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C8  
**Depends on:** C6 (BiomeV2), C7 (landform objects)  
**Audited commit before this package:** post-C7 working tree

---

## Delivered

| Item | Location |
|---|---|
| Landform rasters in RasterStore | `landforms/context_id`, `local_form_id`, scores, object IDs |
| Hydrology `lake_id` in RasterStore | `_fill_rasters` |
| VectorStore landform collections | `mountain_ranges`, `mountain_ridges`, `plateaus`, `plateau_rims` |
| `build_world_spatial_model(..., landforms=)` | `spatial/model.py`; pipeline passes `final.landforms` |
| `rebuild_hex_analysis_cache` keeps landforms | live object or raster fallback |
| Hex contract field names | `spatial/hex_grid/contract.py` |
| Score mean ≠ terrain/object fraction | `mountain_score_mean` vs `mountain_terrain_fraction` / `mountain_range_fraction` |
| Ocean-only / uncovered → `null` | land elevation, landform scores/fractions |
| Shared query/export record | `hex_environment_record` / `hex_environment_columns` |
| Lookup by object ID | range, plateau, river, lake, basin |
| Canonical + atlas legends | `metadata["categorical_legends"]`; atlas JSON legends |
| Tests | `tests/test_worldgen_corrective_c8.py` |

Schema stays **v3**. Atlas `map_modes` unchanged (BiomeV2 / landform display is **C9**). Godot still receives `elevation_mean` / `precipitation_annual` aliases.

---

## Hex contract

Query and `hex_environment.json` share the C8 names. `*_fraction` is never a score mean. Legacy hex caches that stored `mountain_fraction` load it as `mountain_score_mean`.

Land statistics on ocean-only hexes are JSON `null`, not `0`. `land_fraction == 0` stays a real zero. Annual precipitation is `sum(monthly proxy) × precip_scale_mm` with unit `mm_declared_proxy`.

---

## Acceptance

| Criterion | Result |
|---|---|
| save/load rasters, vectors, hex fields, IDs | PASS |
| rebuild without live landforms still aggregates | PASS |
| query field names = atlas export names | PASS |
| no fraction field is a score mean | PASS |
| legends cover emitted Holdridge / BiomeV2 / landform IDs | PASS |
| lookup by mountain-range, plateau, river, lake, basin ID | PASS |
| `pytest -m "not slow"` | PASS — 378 passed, 3 deselected |
| Atlas `183716` | **Leftover** — not regenerated |

---

## Explicitly not done

- Godot `biome_v2` / `landforms` map modes, legend panel, LandformLayerRenderer (**C9**)
- Retuning YAML, folding, Holdridge, `mountain_score_threshold` (stays **0.60**)
- Atlas `183716` regen
- Schema bump (still v3)

**Decision:** accept C8 data-contract integration; stop. Next when instructed: **C9** only.
