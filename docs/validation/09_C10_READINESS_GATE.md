# C10 readiness gate (post PC0–PC7 + pre-C10 repairs)

**Date:** 2026-08-20  
**Status:** `NOT_READY_FOR_CALIBRATION` — hydrology lake convergence + landforms acceptance repaired pending regen; erosion starts C10 at `stream_power_k=500`.  
**Authority:** [`00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §12 + §16

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
| **Pkg1** Godot YAML thermal/fluvial order, C10 UI ranges, spin quantization | ✅ (2026-08-20) |
| **Pkg2** Lake inflow = all incoming edges; same-month land-mediated spill | ✅ (2026-08-20) |
| **Pkg2** Acceptance checks real `withheld_count` (not hard-coded published=0) | ✅ |
| **Pkg3** True global mass ledger (runoff/ET/storage/ocean/closed) + capture ≥ 1−ε + unassigned_spill=0 | ✅ (2026-08-20) |
| **Pkg4** Display rivers trace on physical network to terminal; erosion delta ≡ DEM change | ✅ (2026-08-20) |
| **Pkg5** Honest PC7 suite (`suite_ok` ≠ green gates; AND across atlas seeds) | ✅ (2026-08-20) |
| **unassigned_spill** ocean-mouth / late-lake spill declared or absorbed (not lost) | ✅ (2026-08-20) |
| **G0** seasonal snow periodicity = end-of-year store (not monthly cube vs growing firn) | ✅ (2026-08-20) |
| **G0** runoff/snow spin-up default **64y** (Atlas perennial fill ≈57y; Godot legacy-8 migrate) | ✅ (2026-08-20) |
| **Lake withheld** §5.5 materiality (fail on published-nonperiodic / material wet-area share; mean-rel convergence; spinup 24y) | ✅ (2026-08-20) |

---

## Blocking gates (Atlas `183716` reference)

Until these are green on a fresh Atlas regen, **do not start C10 calibration**:

- `hydrology_ok` — re-check after G0 end-of-year snow + material withheld policy (2026-08-20); was seasonal-snow cube + hard `withheld==0`
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
| `snow_firn_ok` | false | Pre-fix: monthly seasonal cube vs firn growth; **fixed structurally 2026-08-20** (needs regen) |
| `hydrology_ok` | false | Pre-fix: hard fail on any withheld; **§5.5 materiality + mean-rel + 16y spinup 2026-08-20** (needs regen) |
| Periodic liquid lakes | **45 / 97** | Per-lake router fix restored publish (was **0 / 97** pre-fix) |
| `lake_liquid_cell_count` | 112 | Raster liquid cells present again (was 0) |
| `lake_reported_wet_area_km2` | ~62 831 | Published lake area restored |
| `q_through_lake_once` | true | Structural improvement vs audit baseline |
| `runoff_periodic` | true | G0 runoff repeats; seasonal snow store does not |
| `erosion_or_fluvial_ok` | false | corridor mean **0.68 m** < required **~1.92 m** (C10 `stream_power_k`) |
| `landforms_ok` | false | escarpment **~87%** > 50%; `plateau_fraction_alarm`; representability |
| Atlas runtime | **~574 s** | `final` ~419 s, `hydrology` ~131 s |

**Remaining work before C10:** regen Atlas to confirm `hydrology_ok`; then landform escarpment semantics; then `stream_power_k` calibration.

---

## User acceptance required

C10 is **calibration**, not more structural closure. Before running §12 grids:

1. Review `worldsim` output of `review_c10_readiness()` / `pc7_report.json`.
2. Regenerate Atlas `183716` locally (`run_pc7_suite` atlas profile) and inspect diagnostics.
3. Explicitly accept that remaining red gates are **calibration targets**, not missing PC milestones.

Programmatic verdict: `worldsim.validation.production_closure.c10_readiness.review_c10_readiness`.

---

## Runtime note (Atlas `183716`, post PC1+PC3)

Pre-audit baseline (**163.9 s** at commit `68d0ce93`) predates condensed lake routing and G0 8-year spin-up. A fresh Atlas run on current code is typically **~600 s** (dominant stages: `final` ~65%, standalone `hydrology` ~31%). See [`08_worldgen_pc7.md`](08_worldgen_pc7.md).
