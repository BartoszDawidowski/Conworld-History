# Worldgen corrective C2 — rivers, channel-bed loss, bounded coupling

**Date:** 2026-08-17  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no physics default retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §4, §5.2, §6 C2  
**Depends on:** C1  
**Audited commit before this package:** post-C1 working tree

---

## Delivered

| Item | Location |
|---|---|
| `effective_min_cells = max(ceil(km² / cell), acc_cells)` | `hydrology/channels.py` `effective_channel_min_cells` |
| Diagnostic when catchment < one cell | hydrology diagnostics `catchment_smaller_than_cell` |
| Display LOD after the physical mask | unchanged order; provenance counts in diagnostics |
| Flow-limited channel-bed loss (geometry, not PET×cell) | `transmission.channel_bed_loss_potential_m3s` + `effective_discharge_and_sink` |
| Actual loss ≤ available Q and ≤ potential | routing + `bed_loss_never_exceeds_q` |
| `RiverSegment` / GeoJSON: state, catchment km², monthly Q, bed loss | `vectorize/rivers.py`, atlas export, VectorStore |
| Fractional river-water area for evaporation | `river_water_fraction`; moisture `river_fraction` |
| Channel state independent of display width | Godot stroke still Strahler + discharge only |
| Lakes cover rivers only on actual liquid | `lake_mask` (C1 liquid), not `basin_envelope_id` |
| Bounded M1→H1→M2→H2 (+ one damped pass) | `final/pipeline.py`; Jaccard, ΔQ, checksums |
| Tests | `tests/test_worldgen_corrective_c2.py` |

`transmission_rate` remains in config (0.45) for compatibility and is **not** used by C2 routing. New loss uses `HydrologyParams.bed_loss_m3_per_km_month` (default `2e5`). That is a new contract, not a retune of PET, precip, or folding.

---

## Acceptance

| Criterion | Result |
|---|---|
| Nil-like corridor survives; weak wadi terminates | PASS |
| Annual effective Q matches monthly aggregation | PASS (identity via month-length weights; independent annual rel. < 0.35) |
| Channel loss never exceeds available Q | PASS |
| Physical channel mask is not 100% of land under production defaults | PASS |
| Atlas/Full catchment floors share the same km² request + acc floor | PASS |
| Moisture and hydrology checksums + Jaccard / ΔQ recorded | PASS |
| No precip / folding / SST / sea-level retune | PASS |
| `pytest -m "not slow"` | PASS — 314 passed, 3 deselected |

Atlas seed `183716` was **not** regenerated. Production river visuals remain a regen leftover until a later C-track regen.

---

## Coupling honesty

The loop is M1 (no inland water) → H1 → M2 (fractional lake + river) → H2 (same DEM/drainage). Stop if lake-mask Jaccard ≥ 0.98 and total effective-Q change ≤ 5%. Otherwise at most one damped hydrology pass, then mark `coupling_nonconverged` if still outside the gate.

Published ecology moisture is M2 (H1 water fractions). When H2 has converged against H1, those masks are bounded-consistent. Checksums of lake masks and precipitation are persisted. A third moisture spin-up is not started.

On the small `test_final` fixture, M2 spin-up may still miss the C4 closure gate; that remains a **C4** defect, not a C2 retune.

---

## Explicitly not done

- Erosion coefficient grid and land-only coastal aggregation (**C3**)
- Temperature-state integrity (**C3T**)
- Conservative moisture transport / Atlas spin-up (**C4**)
- Precipitation / monsoon retune (**C5**)
- Atlas `183716` regen

**Decision:** accept C2; stop. Next when instructed: **C3** only.
