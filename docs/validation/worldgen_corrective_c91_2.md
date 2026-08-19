# Worldgen corrective C9.1.2 — periodic runoff and lake storage

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no physics default retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.2  
**Closes:** P-91-02, P-91-03, P-91-04  
**Depends on:** C9.1.1  
**Audited commit before this package:** post-C9.1.1 working tree

---

## Delivered

| Item | Location |
|---|---|
| Snow/soil spin-up to a periodic climatological year (or fail closed) | `hydrology/runoff.py` `build_monthly_runoff` — `soil_bucket_periodic_v1` |
| Lake storage driven by that published hydrograph | `hydrology/pipeline.py` (unchanged call order; runoff is now year-N) |
| Non-periodic liquid lakes withheld from the liquid product | `basins_storage.py` `storage_unstable` → `water_body_id = 0` |
| Monthly liquid and ice fraction rasters | `water_fraction_monthly`, `ice_fraction_monthly` (not a fake annual series) |
| Diagnostics | `runoff_periodic`, `runoff_year2_vs_year1_rel_delta`, `runoff_published_vs_repeat_rel_delta`, `basin_storage_liquid_periodic_count`, withheld counts |
| Hydrology `acceptance_ok` requires periodic runoff + no published non-periodic liquid | `hydrology/pipeline.py` |
| Tests | `tests/test_worldgen_corrective_c91_2.py` |

Published runoff is the last spun year. Repeating that year from ending stores must change it by ≤ `runoff_spinup_tol` (default 0.01). A liquid lake that is not `storage_periodic` remains in `lake_records.json` as a warning (`storage_unstable`) and is not painted as open/endorheic water.

Defaults: `runoff_spinup_years = 8`, `lake_storage_spinup_years = 8`. Not a YAML retune.

---

## Acceptance

| Criterion | Result |
|---|---|
| Repeating the published year changes runoff by ≤ 0.01, not ~12% | PASS (`runoff_published_vs_repeat_rel_delta`) |
| Year-2 vs year-1 cold-start delta is recorded and larger than the published repeat | PASS |
| Non-periodic liquid withheld; `basin_storage_nonperiodic_liquid_published_count = 0` | PASS |
| Monthly liquid/ice fractions published; frozen months are ice, not liquid | PASS |
| No precip / `fill_max_depth_m` retune | PASS |
| Focused suite | PASS — 54 passed (C9.1.1–1.2 + C0/C1 + CR-7/PR-6 + hydrology) |

Atlas seed `183716` was **not** regenerated. Production 27/140 periodic lakes and ~12% year-2 runoff bump are leftover cold-start artefacts until regen.

---

## Explicitly not done

- Honest river terminal vocabulary (**C9.1.3**)
- BiomeV2 NON_GROWING / wetland predicate (**C9.1.4**)
- Plateau interior vs rim / range split (**C9.1.5**)
- Canonical world `acceptance_ok` aggregator (**C9.1.6**)
- Atlas `183716` regeneration
- YAML retune

**Decision:** accept C9.1.2; stop. Next: **C9.1.3** only. **C10 remains blocked.**
