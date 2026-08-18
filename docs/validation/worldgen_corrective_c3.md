# Worldgen corrective C3 — metric erosion recalibration and land-only coastal aggregation

**Date:** 2026-08-17  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **no physics default retune**)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C3  
**Depends on:** C0 (may proceed in parallel with C1 after tests are isolated)  
**Audited commit before this package:** post-C2 working tree

---

## Delivered

| Item | Location |
|---|---|
| Metric slope / Laplacian unchanged (CR-9) | `erosion/pass_one.py`, `erosion/fluvial.py` |
| Separate first-pass vs final knobs + units | `ErosionParams`, `FinalRecalcParams`, YAML, `PlanetConfig` |
| `fluvial_k` is first-pass precip×slope only | diagnostics `fluvial_k_role`; Godot prefix/tooltip |
| `stream_power_k` is final river incision | diagnostics `stream_power_k_role`; YAML `stream_power_*` |
| Lower bound so corr-only no-op cannot pass | `erosion_nontrivial_gate`: `max(1.0 m, 0.0005 × range)` |
| Land-only climate-grid elevation | `climate_grid_land_elevation` / `downsample_land_elevation_mean` |
| Climate / ecology / hex / spatial model / DEM lapse | same helper; climate-land cells do not ingest bathymetry |
| Tests | `tests/test_worldgen_corrective_c3.py` |

Production defaults are **unchanged**: `thermal_kappa=0.08`, `fluvial_k=8.0`, `stream_power_k=12.0`. The addendum grid (kappa 20/50/80, stream-power 500/1000/1500) is recorded below as an experiment, not written into YAML as new defaults.

---

## Units

| Parameter | Role | Units |
|---|---|---|
| `thermal_kappa` | first-pass thermal transport | 1 km-cell coefficient; `kappa_m2 = thermal_kappa × 1000²` |
| `fluvial_k` | first-pass precip×slope | not final stream-power |
| `stream_power_k` | final river incision | independent of `fluvial_k` |
| `max_step_m` / `stream_power_max_step_m` | per-step clip | metres |
| `macro_blend` / `stream_power_macro_blend` | pull back toward pre-step DEM | 0–1 |
| `micro_fill_max_depth_m` | post-fluvial pit fill | metres |

Godot `FluvialKSpin` is labelled **pass-1 fluvial k** and states that it does not control final stream-power. No new stream-power spinbox was added (that would imply a default retune).

---

## Lower bound

`required = max(1.0 m, 0.0005 × land elevation range)`.

Atlas seed `183716` first-pass mean `|Δ|` ≈ **0.204 m** and final fluvial ≈ **0.020 m** (addendum §2) **fail** this gate. `acceptance_ok` on first-pass now requires `erosion_nontrivial` and `ocean_unchanged` as well as drainage / macro / roughness. Final `stable_final_geography` remains an **upper** (catastrophe) bound; land-wide fluvial no-op is reported as `fluvial_erosion_nontrivial=false` and is **not** stuffed into `stable`.

---

## Calibration grid (Earth-radius fixtures; not defaults)

Smooth ridge DEM, iterations / max-step / `folding_ratio` / hypsometry frozen. These numbers document scale: on Earth-radius cells the metric Laplacian of a smooth macro-ridge stays well below 1 m mean even at the addendum centre.

### First-pass `thermal_kappa` — 256×512, 5 iterations, `fluvial_k=8`

| `thermal_kappa` | mean `\|Δ\|` m | median | p90 | max | roughness | minima | corr | nontrivial | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 0.08 (production) | 0.0068 | 0.0050 | 0.010 | 0.49 | 156.26 | 0 | 1.000000 | no | 0.020 |
| 20 | 0.0477 | 0.0133 | 0.027 | 12.01 | 155.30 | 0 | 1.000000 | no | 0.015 |
| 50 (centre) | 0.1157 | 0.0325 | 0.062 | 29.18 | 153.87 | 0 | 0.999998 | no | 0.015 |
| 80 | 0.1824 | 0.0519 | 0.098 | 41.48 | 152.53 | 0 | 0.999996 | no | 0.015 |

Minima before pass: 42. Ocean / coastline unchanged on every row. Macro-relief is preserved. Production `0.08` is a metric no-op, as on Atlas.

On a **1 km-cell** equivalent planet (`R = width / 2π`), the same centre `thermal_kappa=50` yields land-mean `|Δ|` ≈ **14.6 m** with corr ≥ 0.97 — the coefficient is physically active at the scale it is defined for. That is not a production default.

### Final `stream_power_k` — 128×256, one river column, 4 iterations

| `stream_power_k` | land mean `\|Δ\|` m | median | p90 | max | river mean `\|Δ\|` m | corr | land-wide nontrivial | runtime s |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|
| 12 (production) | 0.0002 | 0 | 0 | 0.11 | 0.022 | 1.000 | no | 0.006 |
| 500 | 0.0080 | 0 | 0 | 4.62 | 0.909 | 1.000 | no | 0.006 |
| 1000 (centre) | 0.0160 | 0 | 0 | 9.24 | 1.818 | 1.000 | no | 0.006 |
| 1500 | 0.0240 | 0 | 0 | 13.85 | 2.728 | 1.000 | no | 0.006 |

Incision is local to the channel (river-mean grows with `k`); land-wide mean stays below the 1 m gate on this sparse-river fixture, matching Atlas `0.020 m` at `k=12`. Ocean unchanged.

**Decision:** do **not** promote 50 / 1000 into `default_planet.yaml`. Choosing new defaults is a later calibration pass after C3T/C4+ as instructed.

---

## Land-only coastal aggregation

`downsample_land_elevation_mean` now uses a land-only mean whenever a block contains any land. `climate_grid_land_elevation` then writes climate bathymetry on climate-ocean cells. A mixed coastal block treated as climate land cannot receive a negative elevation from averaging bathymetry. Callers: `build_base_climate`, `correct_climate_for_dem`, ecology, hex analysis, `terrain/elevation_climate_m`.

---

## Acceptance

| Criterion | Result |
|---|---|
| Metric slope / Laplacian kept | PASS |
| Separate pass-1 vs stream-power parameters + units | PASS |
| Godot `fluvial_k` not presented as final incision | PASS |
| Production no-op fails the 1 m land-mean gate | PASS (fixtures + Atlas 0.204 m / 0.020 m) |
| Experimental 1 km-cell centre is non-zero without erasing macro-relief | PASS |
| Ocean / coastline unchanged | PASS |
| No climate-land cell gets bathymetry-mix elevation | PASS |
| No precip / folding / SST / sea-level / erosion-default retune | PASS |
| `pytest -m "not slow"` | PASS — 322 passed, 3 deselected |

Atlas seed `183716` was **not** regenerated. Production erosion remains a leftover until a later C-track regen **after** defaults are chosen.

---

## Explicitly not done

- Choosing new `thermal_kappa` / `stream_power_k` defaults (stop gate)
- Temperature-state integrity (**C3T**)
- Conservative moisture transport / Atlas spin-up (**C4**)
- Landform retune (**C7**)
- Atlas `183716` regen

**Decision:** accept C3; stop. Next when instructed: **C3T** only.
