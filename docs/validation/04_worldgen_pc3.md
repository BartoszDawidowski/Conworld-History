# Worldgen production closure PC3 — G0 snow/soil/firn foundation

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (synthetic conservation/periodicity fixtures; no lake parameter retune)  
**Authority:** [`docs/00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §7 + §11 PC3  
**Depends on:** [PC0](01_worldgen_pc0.md); parallel with [PC1](02_worldgen_pc1.md)

---

## Delivered

| Item | Location |
|---|---|
| G0 parameters | `physical/cryosphere/params.py` |
| Seasonal snow + firn transfer + soil bucket | `physical/cryosphere/snow_firn.py` |
| Canonical SurfaceWaterForcing entry | `physical/cryosphere/pipeline.py` |
| Hydrology consumes G0 (no duplicate snow model) | `physical/hydrology/pipeline.py` |
| Legacy `build_monthly_runoff` delegates to G0 | `physical/hydrology/runoff.py` |
| Honest ecology ICE labels | `physical/ecology/holdridge.py`, `biome_v2.py` |
| PC3 synthetic tests | `tests/test_worldgen_pc3.py` |

---

## Algorithm change

**Before (C9.1 / CR-7):** seasonal snow clipped at `max_snow_store`; spin-up checked runoff periodicity only; hidden mass loss on overflow.

**After (G0):** for each climatological month:

1. partition rain/snow with smooth temperature band;
2. add snowfall to seasonal snow;
3. melt seasonal snow before firn;
4. route rain + melt exactly once through soil bucket;
5. transfer seasonal surplus to firn (no clip overflow);
6. iterate years until seasonal snow and soil repeat;
7. accumulating cells close ledger via explicit `firn_gain_m_swe_per_year`.

`runoff_algorithm`: `g0_snow_soil_firn_v1`

Published forcing to hydrology:

~~~text
rainfall_monthly + seasonal_snowmelt_monthly + glacier_melt_monthly (=0 in G0)
    → liquid_input_monthly → runoff
~~~

---

## Acceptance

| Criterion | Result |
|---|---|
| Cold/dry: no snow, no firn | PASS |
| Cold/wet: firn transfer, no clip | PASS |
| Warm cycle: melt appears once in runoff | PASS |
| Non-accumulating climate: stores repeat | PASS |
| Accumulating climate: firn transfer closes ledger | PASS |
| Cold start not marked state-periodic | PASS |
| Mass balance within tolerance | PASS |
| Honest ICE / ice_climate_potential labels | PASS |
| PC0 snow-store xfail resolved | PASS |
| `pytest -m pc3` | PASS |

Run: `pytest -m pc3 -q`

---

## Explicitly not done

- **PC2** three-tier channel networks and final-Q ordering
- G1 dynamic land ice / SMB
- Atlas `183716` store diagnostics rerun
- Lake parameter retuning

**Decision:** accept PC3; stop. Next when instructed: **PC2**.
