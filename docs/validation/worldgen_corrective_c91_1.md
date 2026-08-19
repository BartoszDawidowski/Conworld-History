# Worldgen corrective C9.1.1 — lake-aware routing without double flow

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no physics default retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.1  
**Closes:** P-91-01  
**Depends on:** C2 graph + C1 A–V–h  
**Audited commit before this package:** post-C9 working tree

---

## Delivered

| Item | Location |
|---|---|
| Lake cells do not transmit through-flow out of the envelope | `hydrology/cylindrical_graph.py` `accumulate_weights_lake_aware`, `effective_discharge_and_sink(..., lake_id=)` |
| Spill injected on the first cell **outside** the envelope | `first_downstream_outside_lake` + `hydrology/pipeline.py` |
| `q_gross` / `q_effective` published as rasters + diagnostic aliases | `river_discharge_gross` / `river_discharge_proxy`; diagnostics `q_gross`, `q_effective` |
| `q_through_lake_once` and `Q_effective > Q_gross` counts | hydrology diagnostics |
| Material double-count fails `acceptance_ok` | `q_eff > q_gross * 1.25 + 1.0 m³/s` |
| Tests | `tests/test_worldgen_corrective_c91_1.py` |

A lake is one storage node: inflow accumulates once; the only mass leaving to downstream land is computed spill. Pre-C9.1.1 injected spill *inside* the lake on a graph that had already passed the same water through the envelope (~2× Q below).

---

## Material threshold

`q_effective_gt_gross_count` counts any land cell with `Q_effective > Q_gross × 1.01 + 0.05 m³/s` (noise).

`q_effective_gt_gross_material_count` counts `Q_effective > Q_gross × 1.25 + 1.0 m³/s`. That floor is **not** fitted to Atlas `183716`’s 142 cells; it is a physical “this is another copy of the same stream” gate. `acceptance_ok` requires the material count to be zero. `q_through_lake_once` is true only when that count is zero.

Documented sources that may still raise **non-material** `Q_effective` above `Q_gross`: precipitation on the lake surface added in storage, then spilled. That is new mass, not double-routed catchment runoff.

---

## Acceptance

| Criterion | Result |
|---|---|
| Synthetic 10 m³/s into a spilling lake ⇒ ≈10 m³/s below, not 20 | PASS |
| Through-flow does not leave the envelope until spill inject | PASS |
| Old inject-inside-lake path still demonstrates 20 m³/s (regression contrast) | PASS |
| Material `Q_effective > Q_gross` fails hydrology `acceptance_ok` | PASS (wired; count==0 required) |
| No `fill_max_depth_m` / precip retune | PASS |
| Focused hydrology suite | PASS — 36 passed (`c91_1` + C1 + C2 + `test_hydrology`) |

Atlas seed `183716` was **not** regenerated. The production 142-cell double-count is the same class as the fixture and is a regen leftover until a later C-track regen.

---

## Explicitly not done

- Periodic snow/soil runoff and lake `storage_periodic` gating (**C9.1.2**)
- Honest river terminal vocabulary (**C9.1.3**)
- BiomeV2 NON_GROWING / wetland predicate (**C9.1.4**)
- Plateau interior vs rim / range split (**C9.1.5**)
- Canonical world `acceptance_ok` aggregator (**C9.1.6**)
- Atlas `183716` regeneration
- YAML / folding / SST / `river_acc_fraction` retune

**Decision:** accept C9.1.1; stop. Next: **C9.1.2** only. **C10 remains blocked.**
