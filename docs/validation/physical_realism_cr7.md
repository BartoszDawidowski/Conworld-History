# Physical Realism CR-7 — light hydrology v2

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-7  
**Defects closed:** none newly numbered (F-09 remains closed).  
**Partial:** **F-17** — km² floor is applied *before* `river_acc_fraction` LOD; Atlas/Quick cell area still ≫ 500 km² so the floor is 1 cell and the display quantile still dominates visuals.

---

## Delivered

| Item | Location |
|---|---|
| Shared monthly soil bucket (quickflow + capacity + ET from Holdridge PET) | `hydrology/runoff.py` `soil_bucket_v1` |
| Q in m³/s from cell area, `precip_scale_mm`, and month length | `hydrology/discharge.py`; product `river_discharge_proxy` = month-weighted mean |
| Transmission losses × path length / 50 km | `transmission_sink(..., path_length_km=)` + `GridMetrics.d8_step_length_km_field` |
| Residual PET after soil ET (no double-count with channel demand) | runoff `residual_pet` → transmission |
| Physical channel mask (catchment km²) then display quantile | `hydrology/channels.py` |
| Perennial / seasonal / wadi from monthly Q | `channel_state` uint8 on the LOD network |
| Closed-basin A–V–h: 12 scalar months, 2-year spin, no extra cubes | `hydrology/basins_storage.py` |
| Tests | `tests/test_physical_realism_cr7.py` |

Canonical annual Q is **`mean_monthly_m3s`**, not the sum of monthly rates. Independent annual routing is still diagnosed (`rel_ind < 0.35`).

Defaults (not precip/ocean/folding knobs): `soil_capacity=1.0` proxy (~200 mm), `soil_quickflow_frac=0.20`, `transmission_ref_km=50`, `transmission_rate` stays **0.45**.

---

## Acceptance

| Criterion | Result |
|---|---|
| Soil ET reduces runoff below rain+melt when PET > 0 | PASS |
| Cold snow still delayed (not immediate runoff) | PASS |
| Q scales with cell area | PASS |
| Longer D8 path → larger transmission sink | PASS |
| Physical mask ⊇ display mask; quantile after km² | PASS |
| Channel states: 12-wet perennial, 6-wet seasonal, 1-wet wadi | PASS |
| Closed basin records have 12 A–V–h scalars | PASS |
| Canonical monthly mean = annual product; `rel_ind < 0.35` | PASS |
| `pytest -m "not slow"` | PASS — 268 passed, 3 deselected |
| No Full default change (F-14) | PASS — no new monthly cubes; soil store is 2D final; basin storage is scalars |

Atlas 183716 full regen was **not** re-run this milestone (fixtures + suite). Expected production effect: less hillslope rain dumped straight into Q; channel loss scales with km; lake playa/endorheic can follow stored volume, not only an inflow quantile.

---

## Explicitly not done

- Conservative advection, lee as condensation brake, monsoon seasonal gate, hydro↔evap iteration (**CR-8**)  
- Spin-up convergence (**F-03**)  
- Atlas cell still larger than 500 km² so the catchment floor is one cell (**F-17 leftover**)  
- Landform score / erosion `cell_scale_m` (**CR-9**)  
- Groundwater / hydraulic solver / Full memory rewrite (**F-14**)  
- Precipitation / `orographic_frac` / `folding_ratio` / SST / `lake_min_depth_m` frozen  

**Decision:** accept CR-7; stop. Next when instructed: **CR-8** only.
