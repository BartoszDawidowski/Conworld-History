# Worldgen corrective C1 — lake geometry from storage

**Date:** 2026-08-17  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no physics default retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C1  
**Depends on:** C0  
**Audited commit before this package:** post-C0 working tree

---

## Delivered

| Item | Location |
|---|---|
| Discrete A–V–h from sorted depression cells | `hydrology/basins_storage.py` `discrete_avh_v1` |
| Monthly storage for **open and closed** basins | `apply_basin_storage` |
| Spill only after `v_spill`; excess recorded and routed at outlet | storage + `accumulate_weights` |
| Frozen month: liquid evap = 0; perennial ice not a liquid mask | storage + C0 axes reclass |
| Raster = cells below water surface (+ one shoreline cell) | `DiscreteAVH.raster_wet_fraction` |
| `basin_envelope_id` vs product `lake_id` / `water_fraction_mean` | `HydrologyResult`, `RasterStore` |
| Evap / hex use mean liquid fraction, not the fill envelope | `final/pipeline.py`, `hex_grid/pipeline.py` |
| Lake vectors from wet footprint; `envelope_area_km2` separate | `vectorize/lakes.py` |
| Tests | `tests/test_worldgen_corrective_c1.py` |

Linear `A(h)` remains only as `storage_curve=linear_a_of_h`. Default is discrete.

A dry closed depression is a playa (`water_body_id = 0`). An open lake is not filled to its spill envelope.

---

## Acceptance

| Criterion | Result |
|---|---|
| Empty closed basin stays dry | PASS |
| Seasonal basin expands/contracts without staying permanent | PASS |
| Open below spill: no outflow | PASS |
| Open above spill: exact excess | PASS |
| Evap cannot remove more storage than exists | PASS |
| Frozen month suppresses liquid evap | PASS |
| Greater storage never yields smaller wet area | PASS |
| Rasterized wet area vs `wet_area_km2` within one shoreline cell | PASS |
| E–W seam cells belong to one A–V–h object | PASS |
| Repeating climate reaches periodic storage | PASS |
| Synthetic hydro: raster/reported wet-area ratio in 0.95–1.05 | PASS |
| Envelope area reported separately | PASS |
| No physics default retuned | PASS |
| `pytest -m "not slow"` | PASS — 301 passed, 3 deselected |

Atlas seed `183716` was **not** regenerated. The production 52× envelope-as-water failure is the same class as the fixture: product liquid area is the A–V–h wet area, not `basin_envelope_id > 0`. Full Atlas ratio remains a regen leftover.

---

## Explicitly not done

- Channel-bed losses and physical vs display river mask (**C2**)
- Moisture–hydrology iteration to Jaccard 0.98 (**C2**)
- Erosion coefficient grid (**C3**)
- Precipitation retune

**Decision:** accept C1; stop. Next when instructed: **C2** only.
