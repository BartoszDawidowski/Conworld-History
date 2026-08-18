# Worldgen corrective C7 — landform scales, classes, masks, and objects

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **`mountain_score_threshold` stays 0.60**; no precip/folding retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C7  
**Depends on:** C3 (metric DEM path)  
**Audited commit before this package:** post-C6 working tree

---

## Delivered

| Item | Location |
|---|---|
| Minimum analysis radius **1 cell** (was 2) | `scale_window` |
| Requested + effective E–W/N–S km per scale | `diagnostics["scale_windows"]` |
| Quick collapse flag when windows coincide | `quick_scales_indistinguishable` |
| Coastal roughness / mean slope ÷ land fraction | `compute_metric_fields` |
| Full-resolution ocean mask reapplied after upsample | `build_landform_analysis` |
| Min object area km² + representable floor | `min_*_km2_representable` |
| Shoulder, footslope, valley, depression, summit, ridge | `classify_layers` |
| Escarpment = plateau-adjacent / convex step, not broad relief | `classify_layers` |
| Configured mountain threshold only (no hidden `0.55`) | `mtn_thr = params.mountain_score_threshold` |
| Geodesic ridge on unwrapped mask; PCA for orientation only | `_ridge_centerline` |
| Duplicate prune; ridge-in-mask; presentation split at seam | `ridge_geometry_ok`, `_split_polyline_at_seam` |
| Plateau interior polygon + separate rim line | `Plateau.rim_line`, `plateau_rims.geojson` |
| Honest acceptance + alarms (not seed targets) | diagnostics |
| Tests | `tests/test_worldgen_corrective_c7.py` |

Algorithm stamp: `landform_v3_c7`. Production `mountain_score_threshold = 0.60` unchanged. Choosing new score weights is **after** C7, not this package.

---

## Scales

`round(km → cells)` is floored at **one** cell and capped at ¼ of the grid. Each of fine / meso / macro records `requested_km`, `effective_rx/ry_cells`, and `effective_ew/ns_km`. When two scales share the same `(rx, ry)` the result sets `scales_collapsed`; Quick-sized analysis grids (`max(w,h) ≤ 128`) also set `quick_scales_indistinguishable`.

On Earth-radius 32×64 / 128×64, 60 / 150 / 300 km all collapse to one cell. Synthetic cone/ridge fixtures that still need a neighbourhood use `planet_radius_km=250` so those kilometre values are actually representable. That is fixture honesty, not a production retune.

Coastal `roughness_*` and `mean_slope_*` divide the box accumulator by window land fraction, matching the elevation mean.

After nearest upsample to the full DEM, ocean cells are forced to context/local `ocean` and zero object IDs; land that was painted ocean becomes `plain` / `slope`.

---

## Local form

Declared classes are all assigned. Order: default slope → flat → footslope → shoulder → valley → depression → ridge → summit → escarpment.

Escarpment is **not** `relief ≥ 280 m` over a continent. It is:

- a convex high-to-low step (`drop ≥ 80 m`, neighbour below ~220 m), and/or
- a cell near plateau interior with that drop, and
- a thin extra tail (p98 drop × p90 |Laplacian|) that is not mountain core.

Upland uses elevation above sea (`> 150 m`) so a uniformly high rolling surface is upland, not a range.

---

## Objects

Range ridges are the geodesic diameter of the component graph after E–W unwrap. Consecutive duplicate vertices are dropped. Every sample is tested against the range mask. GeoJSON LineStrings split where `|Δx| > 0.5`. PCA remains orientation/elongation only.

Plateau records keep the interior polygon and a separate `rim_line`. Save writes `plateau_rims.geojson` beside `mountain_ridges.geojson`.

IDs stay the sorted-component scheme (deterministic for the same DEM / config / algorithm version).

---

## Acceptance

Hard gates (`acceptance_ok`): structural grid, calibrated knobs when production params are used, mask consistency, local-form IDs ⊆ legend, ridge-in-mask, no consecutive duplicate ridge vertices.

Alarms (recorded, **not** fitted to one seed): mountain terrain 10–30%, plateau context 1–8%, escarpment `< 20%` of land.

| Criterion | Result |
|---|---|
| Cone, plateau+escarpment, mountain-on-plateau | PASS |
| Rolling upland; two ranges vs one ridge | PASS |
| Canyon keeps plateau context | PASS |
| Seam range; N–S mirror | PASS |
| Ridges inside mask, no duplicate vertices | PASS |
| Local classes present on fixtures that require them | PASS |
| Save/load raster round-trip | PASS |
| `pytest -m "not slow"` | PASS — 371 passed, 3 deselected |
| Atlas `183716` | **Leftover** — not regenerated |

---

## Explicitly not done

- Retuning `mountain_score_threshold` / score weights (**after C7**, still 0.60)
- WorldSpatialModel / hex landform contract (**C8**)
- Godot landform mode (**C9**)
- Atlas `183716` regen

**Decision:** accept C7 operator correctness; stop. Next when instructed: **C8** only.
