# Milestone B1 — Currents → temperature → Holdridge (inland decay)

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md`  
**Status:** ✅ Complete

## Scope

Shallow ocean→climate coupling so Holdridge / hex / atlas temperatures reflect SST and boundary currents, with **inland penetration that decays with distance from ocean**.

## Delivered

| Item | Location |
|---|---|
| Inland SST blend `mix * exp(-(dist−1)/scale)` | `worldsim/.../ocean/sst.py` — `couple_temperature_with_sst_inland` |
| Default `mix=0.35`, `inland_decay_cells=16` | `OceanParams` |
| Writeback into climate after final ocean pass | `apply_ocean_temperature_to_climate` in `final/pipeline.py` |
| Diagnostics (coast vs deep ΔT, optional W/E land) | `ocean_diagnostics` / final diagnostics |
| Tests | `tests/test_ocean.py` (writeback + synthetic decay) |

## Design notes

- `build_ocean_circulation` **does not** mutate `climate_v1` (avoids double-coupling before DEM lapse).
- One correction pass after the **final** ocean rebuild: ecology and atlas read `final.climate.temperature_c`.
- Moisture already consumed `temperature_coupled_c`; behaviour aligned with written-back climate.
- Knobs remain at current defaults (Plan B5 will expose them without silent retune).

## Acceptance

| Criterion | Result |
|---|---|
| Ecology path uses coupled temperatures | Met — `apply_ocean_temperature_to_climate` before moisture/ecology in final |
| Inland decay weaker than coast | Met — unit test + diagnostics `coast_*` ≥ `deep_inland_*` |
| No full §26 iteration loop | Met |
| Unrelated climate defaults unchanged | Met (`base_temp_c` etc. untouched) |

## Human check (optional)

Regenerate Atlas at a fixed seed and compare coastal hex `temperature_annual_c` / Holdridge near western vs eastern boundary currents; inland cells should move less than the shore.

## Stop

B1 complete. Next when instructed: **B2** (Atlas UI chrome).
