# Milestone 8 acceptance record

**Date:** 2026-08-14  
**Scope:** Ocean circulation + SST only (no Milestone 9 moisture / precipitation)

## Delivered

| Item | Location |
|---|---|
| Monthly `current_u` / `current_v` (Ekman, equatorial, WBC/EBC) | `worldsim/physical/ocean/currents.py` |
| Basin labels + western/eastern boundary masks | same |
| Monthly `sst_c` + coastal temperature coupling | `worldsim/physical/ocean/sst.py` |
| Ocean pipeline + diagnostics | `worldsim/physical/ocean/pipeline.py` |
| CLI | `--stage ocean` (default) |
| Artefacts | `ocean/ocean_circulation.npz`, `ocean_diagnostics.json` |

## Acceptance

| Criterion | Result |
|---|---|
| No land crossing (currents zero on land) | PASS |
| Coherent circulation (non-trivial ocean speed) | PASS |
| Equatorial westward tendency | PASS |
| SST NaN on land / finite on ocean | PASS |
| Climate coupling (`temperature_coupled_c`) | PASS |
| Automated tests | **67 passed** fast (includes ocean suite) |

## Explicitly not done (Milestone 9+)

- Evaporation / moisture advection / precipitation
- Orographic rain / rain shadows
- Full GCM / fluid ocean solver
- Snow / albedo iteration loop
