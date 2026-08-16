# Milestone 9 acceptance record

**Date:** 2026-08-14  
**Scope:** Moisture transport + precipitation only (no Milestone 10 erosion)

## Delivered

| Item | Location |
|---|---|
| Evaporation (ocean SST + land ET) | `worldsim/physical/moisture/transport.py` |
| Downwind advection + continentality drying | same |
| Orographic lift / rain + emergent rain shadows | same |
| Convection proxy | same |
| Monthly moisture / precip / humidity | `worldsim/physical/moisture/pipeline.py` |
| CLI | `--stage moisture` (default) |
| Artefacts | `moisture/moisture.npz`, `moisture_diagnostics.json` |

## Acceptance

| Criterion | Result |
|---|---|
| Downwind moisture transport | PASS |
| Detectable windward / leeward effect | PASS |
| Broad Earth-like wet/dry (tropics > subtropics) | PASS |
| Automated tests | **70 passed** fast (includes moisture suite) |

## Explicitly not done (Milestone 10+)

- Climate-informed erosion / DEM v1
- Hydrology (PyFlwDir)
- Full coupled climate iteration / snow-albedo loop
- Noise-based precipitation (intentionally not used)
