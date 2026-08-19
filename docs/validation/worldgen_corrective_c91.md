# Worldgen corrective C9.1 — roll-up

**Date:** 2026-08-18  
**Status:** ⚠️ **IMPLEMENTED ON FIXTURES — PRODUCTION CLOSURE REQUIRED** (see [PC0](01_worldgen_pc0.md), [production-closure addendum](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md))  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md)  
**Next:** **PC1** (lake-supernode). **C10 remains blocked.**

---

## Packages

| Package | Closes | Note |
|---|---|---|
| [C9.1.1](worldgen_corrective_c91_1.md) | P-91-01 | Lake-aware routing; through-flow once; spill outside envelope |
| [C9.1.2](worldgen_corrective_c91_2.md) | P-91-02, P-91-03, P-91-04 | Periodic runoff + storage; unpublished non-periodic liquid lakes |
| [C9.1.3](worldgen_corrective_c91_3.md) | P-91-09 (diag P-91-08) | Honest terminals; no `junction`/`out==0` → `mouth` |
| [C9.1.4](worldgen_corrective_c91_4.md) | P-91-05, P-91-06 | NON_GROWING ≠ Growing–Moist; wetland is inundation, not soil store |
| [C9.1.5](worldgen_corrective_c91_5.md) | P-91-10–13 | Range split + `system_id`; plateau interior ≠ escarpment; honest km² floor |
| [C9.1.6](worldgen_corrective_c91_6.md) | P-91-07 | One `acceptance_ok` conjunction; hex is not sufficient |

Frozen during C9.1 (unchanged): `folding_ratio=0.01`, sea level, `power_tail_v2`, `base_temp_c=25`, lapse 6.5, SST mix/decay, `mountain_score_threshold=0.60`, `plateau_score_threshold=0.40`, `precip_scale_mm`, `river_acc_fraction=0.035`, Q quantile `0.50`.

---

## Definition of Done (addendum §10)

| Invariant | Software | Production leftover until Atlas regen |
|---|---|---|
| Lake routing does not double mass | C9.1.1 gates | seed `183716` still has the old Q field until regen |
| Published runoff / lake storage periodic or hydro red | C9.1.2 | leftover rasters |
| BiomeV2 does not paint non-growing land Growing–Moist | C9.1.4 | leftover class raster |
| Wetland is not saturated-soil-as-marsh | C9.1.4 | leftover class raster |
| River terminals distinguish ocean / lake / endorheic / LOD | C9.1.3 | leftover GeoJSON |
| Ranges split at saddles; ridges follow relief | C9.1.5 | leftover objects |
| Plateau interior/rim ≠ painted perimeter | C9.1.5 | leftover local-form + rims |
| One aggregator owns `acceptance_ok` | C9.1.6 | leftover `climate_summary` / manifest on old worlds |

---

## Explicitly not started

- **C10** (precip / river display / mountain–plateau / erosion grid)
- Atlas `183716` regeneration
- YAML / Godot default retune

**Decision:** stop. Do not start C10 until the user says so after reviewing this roll-up.
