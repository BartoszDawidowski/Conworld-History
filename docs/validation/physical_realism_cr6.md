# Physical Realism CR-6 — hydrology hotfix (PET, liquid lakes, Godot km)

**Date:** 2026-08-17  
**Status:** BASELINE IMPLEMENTED — CORRECTION REQUIRED (skipped Atlas 183716 is not production Accepted; see addendum C0–C2)  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-6  
**Defects closed:** **F-09** (PET×12); **F-15** (playa/ice as liquid); **F-16** (closed vs land outlet); **F-19** (Godot continentality km); **F-20** (centroid-star polygons)  
**Partial:** **F-17** (`river_acc_fraction` 0.035; km² still often inert on Atlas); **F-18** (liquid mask + fraction; hydro not rebuilt after ecology moisture — **CR-8**)

---

## Delivered

| Item | Location |
|---|---|
| Monthly PET = annual Holdridge × days_in_month/365 | `hydrology/transmission.py` `pet_year_fraction` |
| Real monthly vs independent-annual Q check (`rel_ind < 0.35`) | `hydrology/pipeline.py` + tests |
| `closed_basin` requires no land outlet | `lakes_meta.classify_lake_body` |
| Product `lake_mask` = open + watered endorheic only | `liquid_lake_mask` |
| Playa/ice kept in records + geojson `water_state`; not in evap/Holdridge/Godot fill | hydrology, ecology via mask, `VectorLayerRenderer.gd` |
| Climate-cell **lake fraction** into second moisture pass | `final/pipeline.py`, `evaporation_components` |
| Godot writes `continentality_scale_km: 500` + hydrology block | `godot/scenes/Main.gd` |
| Lake outline = cell-edge union, not centroid sort | `vectorize/lakes.py` |
| `river_acc_fraction` default **0.035** | YAML, config, Godot |
| Tests | `tests/test_physical_realism_cr6.py` |

---

## Acceptance

| Criterion | Result |
|---|---|
| PET monthly ≪ annual-applied-every-month | PASS |
| Independent annual Q within 35% of canonical monthly sum | PASS (was ~88.8% with PET×12) |
| Land-outlet body is not `closed_basin` | PASS |
| Playa/ice not in product `lake_mask` | PASS |
| Concave lake outline area = cell count; axis-aligned edges | PASS |
| Lake fraction 0.25 → 25% of full-mask evap | PASS |
| Godot YAML contains `continentality_scale_km: 500.0` | PASS |
| `pytest -m "not slow"` | PASS — 259 passed, 3 deselected |

Atlas 183716 full regen was **not** re-run this milestone (fixtures + suite). Expected production effect: liquid water ≪ 10.64% land; river cells up from PET/12 + 0.035 fraction.

---

## Explicitly not done

- Soil bucket / Q in m³/s / basin A–V–h (**CR-7**)  
- Conservative advection, lee as condensation brake, monsoon seasonal gate, hydro↔evap iteration (**CR-8**)  
- Spin-up convergence (**F-03**)  
- `river_min_catchment_km2` still loses to accumulation quantile on Atlas/Quick (**F-17** leftover)  
- Landform score / erosion `cell_scale_m` (**CR-9**)  
- Precipitation / `orographic_frac` / `folding_ratio` / SST / `lake_min_depth_m` frozen  

**Decision:** CR-6 remains a fixture baseline. A skipped Atlas run is not production Accepted. Remainder → addendum **C0–C2**.
