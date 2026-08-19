# Worldgen production closure PC7 — production suite + C10 readiness

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (suite harness, performance ledger, readiness review)  
**Authority:** [`docs/00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §11 PC7 + §16  
**Depends on:** [PC0](01_worldgen_pc0.md) … [PC6](07_worldgen_pc6.md)

---

## Delivered

| Item | Location |
|---|---|
| PC7 seed matrix | `validation/production_closure/seeds.py` |
| Suite runner + fixed-scale maps | `validation/production_closure/suite.py` |
| Runtime regression analysis | `validation/production_closure/performance.py` |
| C10 readiness review | `validation/production_closure/c10_readiness.py` |
| G0 repeat-year skip (hydrology) | `physical/cryosphere/snow_firn.py` |
| Lake record index lookup | `physical/hydrology/monthly_router.py` |
| Godot headless smoke | `godot/tools/pc7_smoke.gd` |
| PC7 tests | `tests/test_worldgen_pc7.py` |

---

## Required suite (addendum §11 PC7)

| Profile | Seeds | CI default |
|---|---|---|
| Quick | `1`, `42`, `100` | `@pytest.mark.slow` smoke (`seed 42`) |
| Atlas | `42`, `183716` | manual / release `run_pc7_suite` |
| Full smoke | `42` + peak RSS | `run_pc7_suite(include_full=True)` |

Run full suite locally:

```bash
cd worldsim
python -c "
from pathlib import Path
from worldsim.validation.production_closure.suite import run_pc7_suite
run_pc7_suite(output_dir=Path('_pc7_out'), include_full=True, include_cross_profile=True)
"
```

Fast CI:

```bash
pytest -m pc7 -q
pytest -m 'pc7 and slow' -q   # quick seed + optional Godot headless
```

---

## Performance regression (Atlas)

| Metric | Value | Notes |
|---|---|---|
| Pre-closure audit total | 134.3 s | Commit before production-closure package |
| Mid-audit total (`68d0ce93`) | 163.9 s | `apply_basin_storage`; no G0 8-year spin-up |
| Post PC1+PC3 (Atlas `183716`, local) | **~610 s** | Condensed router + G0 spin-up; hydrology ~3× per run |
| Dominant stage (post PC1+PC3) | **`final`** (~65%) | Includes H1/H2 rebuild + stream-power loop |

The **+22%** figure (134 → 164 s) documents the mid-audit step only. Current Atlas runtime is dominated by PC1 lake spin-up and PC3 G0 state iteration; expect several minutes, not ~3 minutes.

**Documented optimizations (PC7):**

1. Skip redundant G0 validation year when spin-up converges early (`g0_repeat_year_skipped` diagnostic).
2. O(1) lake-record lookup in condensed monthly router (was O(n) per lake-month).

**Post-PC7 repair (2026-08-19):** per-lake storage periodicity in condensed router (see [PC1](02_worldgen_pc1.md)).

---

## C10 readiness

**Verdict:** `NOT_READY_FOR_CALIBRATION` (expected — baseline gates still red on hydrology + erosion).

Blocking gates on reference Atlas `183716`:

- `hydrology_ok`
- `erosion_or_fluvial_ok`

User review is required before C10 even when suite passes.

---

## Acceptance

| Criterion | Result |
|---|---|
| Seed matrix defined | PASS |
| Runtime regression attributed | PASS |
| Optimization attempt documented + coded | PASS |
| Fixed-scale absolute maps in suite | PASS |
| C10 readiness fail-closed | PASS |
| Godot headless smoke script | PASS |
| `pytest -m pc7` | PASS |

---

## Pre-C10 structural repairs (2026-08-19)

| Repair | Status |
|---|---|
| Three lake-surface fractions | ✅ |
| G0 cryosphere rasters in WorldSpatialModel | ✅ |
| Godot `effective_config.json` on load | ✅ minimal |
| Godot Advanced §10.1 UI groups | ✅ |
| PC1 per-lake lake-storage periodicity | ✅ |
| PC0 docs / baseline tolerance | ✅ |
| C10 readiness gate doc | [`09_C10_READINESS_GATE.md`](09_C10_READINESS_GATE.md) |

**C10 calibration:** not started — requires user acceptance of readiness gate.

