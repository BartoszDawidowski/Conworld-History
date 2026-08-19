# Worldgen production closure PC2 — final-Q network and channel tiers

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (pipeline reorder + synthetic tier/topology fixtures)  
**Authority:** [`docs/00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §4.2, §6, §11 PC2  
**Depends on:** [PC1](02_worldgen_pc1.md), [PC3](04_worldgen_pc3.md)

---

## Delivered

| Item | Location |
|---|---|
| Physical / geomorphic / display tier builders | `physical/hydrology/network_tiers.py` |
| Pipeline order: routing → final Q → tiers → vectors | `physical/hydrology/pipeline.py` |
| Vector topology gate + terminal repair | `physical/vectorize/rivers.py` |
| Static order contract | `validation/production_closure/hydrology_contract.py` |
| PC2 tests | `tests/test_worldgen_pc2.py` |

---

## Required order (§6.1)

~~~text
candidate basins → lake-condensed routing → final effective Q
    → channel states → physical → geomorphic → display LOD → vector graph
~~~

**Before:** `display_channel_candidates` and discharge gating ran on preliminary Q.  
**After:** `build_display_river_mask()` runs only after `spinup_condensed_lake_routing` publishes final `monthly_eff`.

Published masks:

| Field | Tier |
|---|---|
| `channel_mask` | physical |
| `geomorphic_channel_mask` | geomorphic (persistent Q / state) |
| `display_river_mask` / `river_mask` | display LOD + downstream trace |
| `river_vector_topology_ok` | vector gate |

`hydrology_algorithm`: `pc2_final_q_network_v1`

---

## Acceptance

| Criterion | Result |
|---|---|
| No pipeline order violations | PASS |
| Display ⊂ physical ⊂ land | PASS |
| Geomorphic uses persistence, not display quantile | PASS |
| Vector gate catches invalid endorheic terminal | PASS |
| PC0 order xfail resolved | PASS |
| `pytest -m pc2` | PASS |

Run: `pytest -m pc2 -q`

---

## Explicitly not done

- Atlas `183716` integration rerun (PC7)
- Erosion geomorphic corridor (PC4)
- Retuning `river_acc_fraction` / discharge quantile defaults
- Full `role` / `terminal_type` vector-node schema split

**Decision:** accept PC2; stop. Next when instructed: **PC4** or **PC7** prep.
