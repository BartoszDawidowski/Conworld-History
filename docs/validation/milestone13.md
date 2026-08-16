# Milestone 13 acceptance record

**Date:** 2026-08-14  
**Scope:** Fluvial erosion + one final physical recalculation only (no Milestone 14 ecology)

## Delivered

| Item | Location |
|---|---|
| Fluvial / stream-power incision along rivers | `worldsim/physical/erosion/fluvial.py` |
| Terrain DEM v2 + delta | `worldsim/physical/final/pipeline.py` → `final/terrain_v2.npz` |
| Climate correction (lapse from DEM change) | same |
| Refreshed atmosphere / ocean / moisture | `final/atmosphere`, `ocean`, `moisture` |
| Final hydrology + vectors | `final/hydrology`, `final/vectors` |
| CLI | `--stage final` (default) |

## Acceptance

| Criterion | Result |
|---|---|
| Stable final geography (high v1↔v2 correlation, bounded deltas) | PASS |
| No catastrophic feedback (hydro/vectors OK; no elev collapse) | PASS |
| Automated tests | **79 passed** fast (includes final suite) |

## Explicitly not done (Milestone 14+)

- Soils / permeability / Holdridge ecology
- Indefinite geological feedback loops
- Hex analysis grid
