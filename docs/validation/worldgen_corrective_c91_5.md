# Worldgen corrective C9.1.5 — plateau interior/rim and range splitting

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; score thresholds frozen)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.5  
**Closes:** P-91-10, P-91-11, P-91-12, P-91-13  
**Depends on:** C7 objects (scores kept; geometry changed)  
**Audited commit before this package:** post-C9.1.4 working tree

---

## Delivered

| Item | Location |
|---|---|
| Mountain blobs split at thin saddles / width constrictions | `landforms/objects.py` `_split_component_at_saddles` |
| Child ranges share `system_id` | `MountainRange.system_id` |
| Ridge follows elevation + TPI, not mask geodesic diameter | `_ridge_centerline(..., tpi=)` |
| Plateau interior is never local escarpment | `landforms/classify.py` rim vs `plat_interior` |
| Rim GeoJSON is the steep/scarp edge, not the filled outline | `_plateau_steep_rim_line` |
| `min_plateau_km2=2500` is not silently raised by `min_component_cells` | `effective_min_cells_honest`; diagnostics `min_plateau_km2_configured` vs `min_plateau_km2_representable` |
| `mountain_score_threshold=0.60` and `plateau_score_threshold=0.40` frozen | `LandformParams` + `default_planet.yaml` |
| Tests | `tests/test_worldgen_corrective_c91_5.py` |

On Atlas-scale cells (~15.6×10³ km²) the honest floor is **1 cell**, not `min_component_cells=4` (~62×10³ km²). When a cell is larger than the configured km², `min_plateau_km2_representable_ok` is false and both values are published; the run does not pretend the floor is 2500 km².

Interior-escarpment acceptance uses **interior** cells only. One-cell plateau specks that are geometrically all rim may be 100% escarpment without failing the gate (Quick seeds 1/100). A large plateau painted ~88% escarpment through its interior still fails.

---

## Acceptance

| Criterion | Result |
|---|---|
| Dumbbell (two peaks + thin bar) → ≥2 ranges, one `system_id` | PASS |
| Uniform thin ridge does not shatter when children would be too small | PASS |
| Plateau interior local form is not escarpment | PASS |
| Rim line ≠ filled polygon outline | PASS |
| Configured 2500 km² vs representable reported; no silent 4-cell bump | PASS |
| Thresholds 0.60 / 0.40 unchanged | PASS |
| Focused suite | PASS — 47 passed (`c91_5` + C7 + CR-5 + CR-9 + PR-9) |

Atlas seed `183716` was **not** regenerated. Production glued ranges and escarpment-filled plateau interiors are leftover until regen.

---

## Explicitly not done

- Canonical world `acceptance_ok` aggregator (**C9.1.6**)
- C10 threshold grid / score retune
- Atlas `183716` regeneration

**Decision:** accept C9.1.5; stop. Next: **C9.1.6** only. **C10 remains blocked.**
