# Worldgen production closure PC4 — geomorphic erosion and process-specific gates

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (synthetic process-delta fixtures; no coefficient retune)  
**Authority:** [`docs/WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §8 + §11 PC4  
**Depends on:** [PC0](worldgen_pc0.md), [PC2](worldgen_pc2.md)

---

## Delivered

| Item | Location |
|---|---|
| `ProcessDeltas` + domain gates | `physical/erosion/gates.py` |
| Conditioning accumulation helper | `physical/erosion/process_deltas.py` |
| First pass returns separate deltas | `physical/erosion/pass_one.py` |
| Metric km geomorphic corridor | `physical/erosion/fluvial.py` |
| Hillslope vs fluvial acceptance | `physical/erosion/pipeline.py`, `physical/final/pipeline.py` |
| PC4 synthetic tests | `tests/test_worldgen_pc4.py` |
| PC0 conditioning xfail resolved | `tests/test_worldgen_pc0.py` |

---

## Algorithm change

**Before (C3 / PC2):** land-wide mean absolute delta fed erosion acceptance; pit-fill/conditioning mixed with incision; final fluvial pass used display river mask and a fixed 2-cell halo.

**After (PC4):**

1. track `thermal_or_hillslope_delta_m`, `first_fluvial_delta_m`, `conditioning_or_pit_fill_delta_m`, and `final_stream_power_delta_m` independently;
2. `total_erosion_delta_m` excludes conditioning; `total_dem_adjustment_m` may include it;
3. first-pass acceptance uses hillslope domain only;
4. final-pass acceptance uses geomorphic corridor mean, not land-wide mean;
5. `apply_fluvial_erosion()` consumes `geomorphic_channel_mask` + metric `step_length_km` corridor (default 5 km influence);
6. report `geomorphic_channel_jaccard_pre_post` in final diagnostics.

`erosion_algorithm`: `pc4_process_deltas_v1`

---

## Acceptance

| Criterion | Result |
|---|---|
| Separate process deltas on first pass | PASS |
| Conditioning excluded from erosion gate | PASS |
| Metric corridor wider than fixed cell halo | PASS |
| Fluvial incision tied to geomorphic mask | PASS |
| Domain-specific fluvial corridor stats | PASS |
| PC0 conditioning xfail resolved | PASS |
| `pytest -m pc4` | PASS |

Run: `pytest -m pc4 -q`

---

## Explicitly not done

- Coefficient grid selection (`thermal_kappa` 20/50/80, `stream_power_k` 500/1000/1500)
- **PC5** landform catastrophe gates and object-count acceptance
- Atlas `183716` erosion diagnostics rerun

**Decision:** accept PC4; stop. Next when instructed: **PC5**.
