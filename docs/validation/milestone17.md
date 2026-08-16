# Milestone 17 acceptance record

**Date:** 2026-08-15  
**Scope:** Godot interactive atlas only (no Milestone 18 packaging)

## Delivered

| Item | Location |
|---|---|
| Godot 4.7 project | `godot/project.godot` |
| Worker launch + NDJSON progress | `godot/simulation_bridge/` |
| Raster map modes (PNG) | `atlas/RasterLayerRenderer.gd` + `worldsim/export/atlas_display.py` |
| Vector coast/rivers/lakes | `atlas/VectorLayerRenderer.gd` |
| Optional hex overlay | `atlas/HexOverlayRenderer.gd` |
| Map modes + monthly controls | `MapModeController`, `TimelineController` |
| Inspector (terrain / river / hex) | `InspectorPanel.gd` |
| Atlas display export from worker | `world/atlas_display/` via `run_world` |

## Acceptance

| Criterion | Result |
|---|---|
| Detailed world visible without hexification | PASS (raster + vectors default; hex off) |
| Toggling hex grid does not alter geography | PASS (overlay-only flag) |
| Clicking river inspects river | PASS (polyline hit-test → inspector) |
| Clicking hex inspects aggregate cell | PASS (when overlay enabled) |
| Automated tests | **95 passed** fast |
| Godot headless project load | PASS (`Godot 4.7.1 --headless --quit-after`) |

## Explicitly not done (Milestone 18+)

- Frozen `worldsim_worker` packaging / Windows release
- Full map-mode catalogue from architecture §44
- EnvironmentTimeline UI
