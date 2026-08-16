# Milestone 11 acceptance record

**Date:** 2026-08-14  
**Scope:** PyFlwDir raster hydrology only (no Milestone 12 vector geography)

## Delivered

| Item | Location |
|---|---|
| DEM conditioning (fill depressions, ocean outlets) | `worldsim/physical/hydrology/conditioning.py` + `flow.py` |
| E–W wrap via DEM padding | `conditioning.py` |
| Flow direction, accumulation, basins, stream order | `flow.py` |
| River mask + annual/monthly discharge proxy | `rivers.py` + `pipeline.py` |
| Lake mask from fill depth | `rivers.py` |
| CLI | `--stage hydrology` (default) |
| Artefacts | `hydrology/hydrology.npz`, `hydrology_diagnostics.json` |
| Dependency | `pyflwdir==0.5.12` in `pyproject.toml` / `requirements.lock` |

## Acceptance

| Criterion | Result |
|---|---|
| Valid drainage graph (`FlwdirRaster.isvalid`) | PASS |
| Sensible accumulation (rivers > mean land; downstream check) | PASS |
| Automated tests | **75 passed** fast (includes hydrology suite) |

## Explicitly not done (Milestone 12+)

- Canonical river node/segment vectors / polylines
- Lake polygons + spatial indexes
- Coastline finalization / raster–vector consistency suite
- Second fluvial erosion pass
