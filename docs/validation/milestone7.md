# Milestone 7 acceptance record

**Date:** 2026-08-14  
**Scope:** Atmospheric circulation only (no Milestone 8 ocean currents / SST)

## Delivered

| Item | Location |
|---|---|
| Pressure proxy (ITCZ trough, subtropical highs, …) | `worldsim/physical/atmosphere/circulation.py` |
| Monthly `wind_u` / `wind_v` + circulation zones | same + `pipeline.py` |
| Coriolis deflection + topographic perturbation | `circulation.py` |
| Atmosphere pipeline + diagnostics | `worldsim/physical/atmosphere/pipeline.py` |
| CLI | `--stage atmosphere` (default) |
| Artefacts | `atmosphere/atmosphere.npz`, `atmosphere_diagnostics.json` |

## Acceptance

| Criterion | Result |
|---|---|
| Coherent fields (no random wind arrows; low zonal std) | PASS |
| Trades easterly (Hadley mean `u` &lt; 0) | PASS |
| Ferrel westerly (mean `u` &gt; 0) | PASS |
| Polar easterly (mean `u` &lt; 0) | PASS |
| ITCZ migrates (June north of December) | PASS |
| Automated tests | **63 passed** fast (includes atmosphere suite) |

## Explicitly not done (Milestone 8+)

- Ocean currents / basin constraints
- SST coupling beyond climate land/ocean bias
- Moisture / precipitation / orographic rain
- Fluid solver / GCM dynamics
