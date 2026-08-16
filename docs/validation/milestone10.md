# Milestone 10 acceptance record

**Date:** 2026-08-14  
**Scope:** First climate-informed erosion pass / DEM v1 only (no Milestone 11 hydrology)

## Delivered

| Item | Location |
|---|---|
| Climate-informed erosion (precip, slope, rock resistance) | `worldsim/physical/erosion/pass_one.py` |
| DEM v1 + before/after delta | `worldsim/physical/erosion/pipeline.py` |
| Pit fill / drainage tendency + macro-relief anchor | same |
| CLI | `--stage erosion` (default) |
| Artefacts | `erosion/erosion_pass1.npz`, `erosion_diagnostics.json` |

## Acceptance

| Criterion | Result |
|---|---|
| Drainage quality improves (fewer land local minima) | PASS |
| Tectonic macro-relief preserved (high elev correlation) | PASS |
| Roughness / artefacts reduced | PASS |
| Ocean bathymetry unchanged in pass one | PASS |
| Automated tests | **72 passed** fast (includes erosion suite) |

## Explicitly not done (Milestone 11+)

- PyFlwDir DEM conditioning / flow direction / accumulation
- River mask, Strahler, discharge, lakes
- Second fluvial erosion pass
- Coastline / climate full recalculation after DEM v1
