# Worldgen corrective C9.1.6 — canonical `acceptance_ok`

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no YAML retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.6  
**Closes:** P-91-07  
**Depends on:** C9.1.1–C9.1.5 (conjunction is only meaningful after those gates exist)  
**Audited commit before this package:** post-C9.1.5 working tree

---

## Delivered

| Item | Location |
|---|---|
| One aggregator, fail-closed on missing keys | `spatial/canonical_acceptance.py` `aggregate_canonical_acceptance` |
| World manifest `acceptance_ok` is the overall conjunction | `spatial/model.py` `build_world_spatial_model` |
| Hex rebuild does not restore hex-only green | `rebuild_hex_analysis_cache` |
| `climate_summary.json` copies the same flags (not raster presence) | `export/atlas_display.py` `_climate_summary` |
| Final diagnostics stamped with the same overall after world assembly | `pipeline.run_world` + `stamp_into_diagnostics` |
| Final *stage* gate includes landforms + nontrivial fluvial | `final/pipeline.py` `final_stage_acceptance_ok` |
| Tests | `tests/test_worldgen_corrective_c91_6.py` |

### Conjunction (this note)

All of the following must be true. A failed component may warn, but **may not** be dropped to keep the run green.

1. moisture spin-up **and** moisture budget (via moisture `acceptance_ok` plus those flags);
2. hydrology `acceptance_ok` **and** `q_through_lake_once` **and** `runoff_periodic` (P-91-01/02);
3. vector `acceptance_ok`;
4. ecology `acceptance_ok` **and** `biome_v2_ok` (coverage / Growing–Moist-on-ice);
5. landforms `acceptance_ok` including plateau honesty / interior-not-escarpment when those keys exist;
6. erosion / `fluvial_erosion_nontrivial` when the profile claims metric erosion;
7. hex schema/layout `acceptance_ok` (layout is **not** sufficient on its own).

Missing diagnostics are `false`. Hex-only success therefore cannot paint the world green.

---

## Acceptance

| Criterion | Result |
|---|---|
| Doubled lake Q (`q_through_lake_once=false`) ⇒ overall false | PASS |
| Non-periodic lakes (`runoff_periodic=false`) ⇒ overall false | PASS |
| Growing–Moist-on-ice (`biome_v2_ok=false`) ⇒ overall false | PASS |
| Hex-only success ⇒ overall false | PASS |
| All required gates true ⇒ overall true | PASS |
| climate_summary matches aggregator, not “raster file exists” | PASS |
| Final JSON `acceptance_ok` stamped to overall on world runs | PASS (wired in `run_world`) |

Atlas seed `183716` was **not** regenerated. Production inspector/manifest colour is leftover until regen; leftover worlds still carry the old hex-only meaning until rewritten.

---

## Explicitly not done

- C10 parameter grid
- Atlas `183716` regeneration
- YAML / Godot default retune

**Decision:** accept C9.1.6; **C9.1 complete**. **C10 remains blocked** until the user reviews the roll-up.
