# C10 readiness gate (post PC0–PC7 + pre-C10 repairs)

**Date:** 2026-08-19  
**Status:** `NOT_READY_FOR_CALIBRATION` — structural repairs delivered; physics gates still red on Atlas `183716`  
**Authority:** [`WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §12 + §16

---

## Structural checklist (pre-C10 repairs)

| Item | Status |
|---|---|
| Three lake-surface fractions (`water_present`, `open_water`, `lake_ice`) | ✅ |
| G0 state rasters in `WorldSpatialModel` (`seasonal_snow_swe`, `firn_swe`, `soil_water`) | ✅ |
| Godot reads `effective_config.json` on load | ✅ (minimal — status suffix) |
| PC0–PC7 pytest markers | ✅ |
| Atlas baseline tolerance for post-PC channel drift | ✅ |
| Full Godot Advanced §10.1 UI groups | ✅ (`Main.gd` — hydrology, lake storage, snow/firn, erosion, landforms, display LOD, solver/expert) |
| PC1 per-lake lake-storage periodicity in condensed router | ✅ (2026-08-19 — fixes global-signature regression) |

---

## Blocking gates (Atlas `183716` reference)

Until these are green on a fresh Atlas regen, **do not start C10 calibration**:

- `hydrology_ok` — G0 seasonal-snow periodicity + lake storage convergence (partial publish after PC1 fix)
- `erosion_or_fluvial_ok` — final stream-power corridor magnitude (`stream_power_k` calibration target)

**Also red on fresh PC5-enforced runs (not C10 blockers, but honest acceptance):**

- `landforms_ok` — plateau-context escarpment dominance (~87% > 50% alarm); baseline JSON previously marked this green incorrectly

Other gates expected green: moisture, ecology, hex, vector.

---

## Observed Atlas `183716` status (post per-lake router fix, 2026-08-19)

Fresh local regen (`godot/worlds/atlas_run_183716`, not in git):

| Gate / metric | Value | Notes |
|---|---|---|
| `failed_gates` | `hydrology_ok`, `landforms_ok`, `erosion_or_fluvial_ok` | Same three as pre-fix |
| `snow_firn_ok` | false | `seasonal_snow_periodic=false`; δ ≈ 10.2% > tol 1.1% |
| `hydrology_ok` | false | `acceptance_ok=false`; 52/97 liquid lakes still nonperiodic → withheld |
| Periodic liquid lakes | **45 / 97** | Per-lake router fix restored publish (was **0 / 97** pre-fix) |
| `lake_liquid_cell_count` | 112 | Raster liquid cells present again (was 0) |
| `lake_reported_wet_area_km2` | ~62 831 | Published lake area restored |
| `q_through_lake_once` | true | Structural improvement vs audit baseline |
| `runoff_periodic` | true | G0 runoff repeats; seasonal snow store does not |
| `erosion_or_fluvial_ok` | false | corridor mean **0.68 m** < required **~1.92 m** (C10 `stream_power_k`) |
| `landforms_ok` | false | escarpment **~87%** > 50%; `plateau_fraction_alarm`; representability |
| Atlas runtime | **~574 s** | `final` ~419 s, `hydrology` ~131 s |

**Remaining work before C10:** calibrate G0 spin-up / seasonal-snow closure, lake-storage convergence for slow lakes, `stream_power_k`, and landform escarpment semantics (classification or acceptance band review — not a Godot/YAML bug).

---

## User acceptance required

C10 is **calibration**, not more structural closure. Before running §12 grids:

1. Review `worldsim` output of `review_c10_readiness()` / `pc7_report.json`.
2. Regenerate Atlas `183716` locally (`run_pc7_suite` atlas profile) and inspect diagnostics.
3. Explicitly accept that remaining red gates are **calibration targets**, not missing PC milestones.

Programmatic verdict: `worldsim.validation.production_closure.c10_readiness.review_c10_readiness`.

---

## Runtime note (Atlas `183716`, post PC1+PC3)

Pre-audit baseline (**163.9 s** at commit `68d0ce93`) predates condensed lake routing and G0 8-year spin-up. A fresh Atlas run on current code is typically **~600 s** (dominant stages: `final` ~65%, standalone `hydrology` ~31%). See [`worldgen_pc7.md`](worldgen_pc7.md).
