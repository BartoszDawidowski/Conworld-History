# Worldgen production closure PC1 — lake-supernode graph and monthly router

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (synthetic cascade/balance fixtures; no lake parameter retune)  
**Authority:** [`docs/WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §11 PC1  
**Depends on:** [PC0](worldgen_pc0.md)

---

## Delivered

| Item | Location |
|---|---|
| Lake supernode condensed graph | `physical/hydrology/condensed_graph.py` |
| Per-lake / global mass ledger | `physical/hydrology/mass_ledger.py` |
| Single monthly router (same-month cascades, spill bed-loss) | `physical/hydrology/monthly_router.py` |
| One-month storage step + ledger | `physical/hydrology/basins_storage.py` `lake_month_storage_step` |
| Pipeline integration (removed post-hoc spill inject) | `physical/hydrology/pipeline.py` |
| PC1 synthetic tests | `tests/test_worldgen_pc1.py` |

---

## Algorithm change

**Before (C9.1):** lake-aware land routing → `apply_basin_storage` (full-year loops) → post-hoc spill inject into `monthly_eff`.

**After (PC1):** for each spin-up year and month:

1. route local land runoff with lake envelope blocking and bed loss;
2. process lakes in spill-DAG topological order (upstream first);
3. same-month upstream lake spill enters downstream lake storage;
4. land-directed spill routed through the same bed-loss network;
5. record per-lake and global mass ledger residuals.

`hydrology_algorithm`: `pc1_condensed_supernode_v1`

---

## Post-delivery repair (2026-08-19): per-lake periodicity

**Bug:** initial PC1 router reused one **global** year-over-year storage signature for every lake's `storage_periodic` flag. When any lake failed to converge within eight years, **all** liquid lakes were withheld (Atlas `183716`: 0/97 periodic vs audit baseline 25/140).

**Fix (`monthly_router.py`):**

- evaluate **per-lake** monthly storage repeatability (same rule as `apply_basin_storage`);
- publish raster fractions only for lakes that are not `storage_unstable` (parity with `apply_basin_storage`);
- retain global signature only as diagnostic `basin_storage_global_signature_periodic` and as an **early-exit** when every lake is periodic;
- set `convergence_state` on each lake record (`periodic` | `failed`).

Tests: `test_per_lake_periodic_independent_in_coupled_router`, `test_nonperiodic_storage_withheld_via_condensed_router`.

---

## Acceptance

| Criterion | Result |
|---|---|
| Post-hoc `accumulate_weights_lake_aware` inject removed from pipeline | PASS |
| One-lake 10 m³/s chain not doubled | PASS |
| Two-lake cascade spill DAG | PASS |
| Spill through lossy reaches | PASS |
| Global lake ledger residual ≤ 1e-3 m³ on fixture | PASS |
| E–W seam one supernode per envelope | PASS |
| Per-lake periodicity independent of global non-convergence | PASS |
| Withheld lakes omitted from published raster fractions | PASS |
| Lake parameters unchanged | PASS |
| `pytest -m pc1` | PASS |

Run: `pytest -m pc1 -q`

---

## Explicitly not done

- PC2 final-Q three-tier channel networks and vector topology repair
- PC3 G0 snow/soil/firn foundation
- Display mask before final Q reorder (PC2)
- Atlas `183716` integration evidence (PC2)
- Lake parameter retuning

**Decision:** accept PC1; stop. Next when instructed: **PC3** (may run parallel) or **PC2**.
