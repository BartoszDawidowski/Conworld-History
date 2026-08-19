# Worldgen production closure PC0 — baseline and failing regressions

**Date:** 2026-08-19 (updated post PC7 pre-C10 repairs)  
**Status:** ✅ **Delivered** — baseline frozen; synthetic regressions now **hard PASS** (PC1–PC5 resolved on fixtures)  
**Authority:** [`docs/00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §11 PC0  
**Audited commit:** `68d0ce93c24a030e9581a810ceadc228289de19f`  
**Reference world:** Atlas profile, seed `183716`

---

## Delivered

| Item | Location |
|---|---|
| Frozen Atlas `183716` baseline metrics | `worldsim/src/worldsim/validation/production_closure/data/atlas_183716_baseline.json` |
| Baseline loader | `worldsim/src/worldsim/validation/production_closure/baseline.py` |
| Hydrology pipeline-order contract probes | `worldsim/src/worldsim/validation/production_closure/hydrology_contract.py` |
| Synthetic failure fixtures | `worldsim/src/worldsim/validation/production_closure/fixtures.py` |
| PC0 regression tests (`@pytest.mark.pc0`) | `worldsim/tests/test_worldgen_pc0.py` |
| Per-stage wall time + peak RSS on `run_world` | `worldsim/src/worldsim/progress.py`, `worldsim/src/worldsim/pipeline.py` |
| `precip_scale_mm` documentation parity (`200` effective) | packaged YAML + `effective_config.json` |

No physics **defaults** were changed in PC0. Later milestones (PC1–PC7) changed algorithms.

---

## Regression tests (now hard PASS)

| Test | Resolved in | Invariant |
|---|---|---|
| `test_lake_cascade_same_month_inflow` | PC1 | Same-month cascade routing |
| `test_spill_incurs_channel_loss` | PC1 | Spill incurs bed losses |
| `test_stale_river_mask_pipeline_order` | PC2 | Final Q before display masks |
| `test_snow_store_periodic_when_runoff_periodic` | PC3 | G0 periodicity |
| `test_conditioning_excluded_from_erosion_acceptance` | PC4 | Conditioning excluded from gate |
| `test_landform_object_explosion_fails_acceptance` | PC5 | Catastrophe fails landforms |

---

## Local Atlas probe

When `godot/worlds/atlas_run_183716` exists, `test_atlas_baseline_json_on_disk_if_present` checks:

- `overall_acceptance_ok` matches frozen baseline (`false`)
- `channel_physical_cell_count` within tolerance (±12 cells; post-PC runs may read **25266** vs frozen **25260**)

---

## Acceptance

Run: `pytest -m pc0 -q`

---

## Next

Structural closure continues in [PC1](02_worldgen_pc1.md) … [PC7](08_worldgen_pc7.md). C10 calibration: [`09_C10_READINESS_GATE.md`](09_C10_READINESS_GATE.md).
