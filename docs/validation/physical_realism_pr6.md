# Physical Realism PR-6 — runoff, wadis, endorheic lakes

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §11.3–11.7 / §15 PR-6  
**Depends on:** PR-0…PR-5  

---

## Delivered

| Item | Location |
|---|---|
| Monthly rain/snow partition + snow store + melt | `physical/hydrology/runoff.py` |
| Monthly gross + **effective** discharge (transmission) | `physical/hydrology/pipeline.py` |
| Annual routing from annual runoff (snow-aware) | same |
| Q-aware river mask **without** downstream inheritance | `gate_river_mask_by_discharge(..., inherit_downstream=False)` |
| Physical Q floor (`min_effective_discharge`) + acc cells | `HydrologyParams` |
| Lake states: open / endorheic / playa / frozen | `physical/hydrology/lakes_meta.py` |
| Spill elevation, inflow, closed_basin on records | `lake_records.json` + `Lake` vector fields |
| Inlet/outlet river ids from network | `build_lakes(..., river_network=)` |
| Tests | `tests/test_physical_realism_pr6.py` |

---

## Acceptance

| Criterion | Result |
|---|---|
| Cold precip → snow store; thaw melt pulse | PASS |
| Wadi fixture `100,80,20,0,0` — zeros not inherited | PASS |
| Nil corridor survives while Q ≥ threshold | PASS |
| Open vs endorheic lake classification | PASS |
| Frozen lake state | PASS |
| Lake metadata JSON round-trip | PASS |
| Existing hydrology / vectors / final tests | PASS |

---

## Explicitly not done

- Full groundwater / baseflow  
- Retuning Atlas river quantiles after physical floors  
- PR-7 revised B8 (plume / recycling / ITCZ)  

**Decision:** accept PR-6; stop. Next when instructed: **PR-7** (revised B8).
