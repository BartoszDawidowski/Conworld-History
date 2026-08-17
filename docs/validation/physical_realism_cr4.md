# Physical Realism CR-4 — monthly Q coherence + typed outlets / endorheism

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-4  
**Defects closed:** **F-08** (endorheism); **F-09** (monthly vs annual Q)

---

## Delivered

| Item | Location |
|---|---|
| Finite numerical fill (`fill_max_depth_m=25`; `-1` = legacy fill-all) | `physical/hydrology/flow.py`, YAML |
| Fill-all depression depth for lake geometry only | `depression_depth_m` |
| Typed outlets: ocean / closed_basin / local_pit / broken_cycle / ns_edge | `cylindrical_graph.classify_outlets` |
| Closed lakes kept (endorheic / playa / frozen), not dropped as arid | `rivers.gate_lakes_by_water_supply` + `lakes_meta` |
| Canonical monthly effective Q; annual = sum | `physical/hydrology/pipeline.py` |
| Transmission sink on **runoff**, not raw precip | `transmission_sink` callers |
| Skip `monthly_gross` storage by default | `HydrologyParams.store_monthly_gross=False` |
| Tests | `tests/test_physical_realism_cr4.py` |

---

## Acceptance

| Criterion | Result |
|---|---|
| Finite fill retains inland pit; fill-all drains it | PASS |
| Endorheic and/or playa records on closed-basin fixture | PASS |
| Frozen closed basin kept | PASS |
| `sum(monthly_eff) == annual Q` (canonical) | PASS (`rel_diff = 0`) |
| Independent annual routing diagnosed, not used as product Q | PASS (`rel_ind < 0.80`) |
| Hydro `acceptance_ok` requires typed outlets | PASS |
| `pytest -m "not slow"` | PASS — 241 passed |

---

## Explicitly not done

- Quick seeds 1/42/100 regeneration (recommended follow-up, not blocking)  
- `transmission_rate` 0.30 / 0.35 / 0.45 / 0.60 sweep — calibration, keep 0.45  
- River min catchment in km² — **closed CR-5** (`river_min_catchment_km2=500`)  
- Hypsometry / landform calibration — **closed CR-5** (see `physical_realism_cr5.md`)  
- Full memory gate beyond omitting monthly gross (**F-14**)

**Decision:** accept CR-4; stop. Next was **CR-5** (accepted 2026-08-17).
