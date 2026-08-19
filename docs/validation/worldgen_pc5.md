# Worldgen production closure PC5 — landform systems and honest acceptance

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (synthetic representability/catastrophe fixtures; thresholds frozen)  
**Authority:** [`docs/WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §9 + §11 PC5  
**Depends on:** [PC0](worldgen_pc0.md), [PC4](worldgen_pc4.md)

---

## Delivered

| Item | Location |
|---|---|
| Catastrophe + representability gates | `physical/landforms/gates.py` |
| Coarse-grid canonical extraction floor | `physical/landforms/objects.py` |
| Binding acceptance conjunction | `physical/landforms/pipeline.py` |
| Plateau rim validity helper | `physical/landforms/objects.py` |
| Canonical acceptance sub-gates | `spatial/canonical_acceptance.py` |
| PC5 synthetic tests | `tests/test_worldgen_pc5.py` |
| PC0 landform xfail resolved | `tests/test_worldgen_pc0.py` |

---

## Algorithm change

**Before (C9.1.5):** `acceptance_ok` ignored escarpment alarms, object-count catastrophe, and several geometry diagnostics; coarse analysis grids could emit hundreds of 1-cell canonical ranges.

**After (PC5):**

1. `canonical_extraction_min_cells` — when configured km² is below one cell area, require `min_component_cells` before minting canonical objects;
2. track `unresolved_mountain_candidate_cells` for sub-threshold score blobs;
3. bind `acceptance_ok` to representability, geometry, escarpment, fraction alarms, and catastrophe guards;
4. expose `landforms_representability_ok`, `landforms_geometry_ok`, `object_count_catastrophe_ok`;
5. validate plateau rims are not full-perimeter fallbacks when interiors exist.

`algorithm`: `pc5_landform_acceptance_v1`

Thresholds remain frozen: mountain `0.60`, plateau `0.40`.

---

## Acceptance

| Criterion | Result |
|---|---|
| Atlas baseline counts trip catastrophe probe | PASS |
| Coarse grid suppresses 1-cell canonical ranges | PASS |
| Synthetic plateau geometry gates | PASS |
| Catastrophe fails closed acceptance | PASS |
| PC0 landform xfail resolved | PASS |
| `pytest -m pc5` | PASS |

Run: `pytest -m pc5 -q`

---

## Explicitly not done

- Atlas `183716` landform regen / object-count recount
- Mountain/plateau threshold calibration (C10)
- **PC6** canonical products + Godot inspector parity

**Decision:** accept PC5; stop. Next when instructed: **PC6**.
