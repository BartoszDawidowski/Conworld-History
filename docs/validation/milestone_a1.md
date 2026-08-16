# Milestone A1 acceptance record

**Date:** 2026-08-15  
**Scope:** Atlas zoom / pan / Fit / linear filter only (no A2 profiles)

## Delivered

| Item | Location |
|---|---|
| Map input via `SubViewportContainer.gui_input` | `godot/scenes/Main.gd` |
| Zoom toward cursor + pan | `godot/atlas/WorldAtlas.gd` |
| Buttons − / Fit / + | `Main.tscn` sidebar |
| Linear texture filter | `RasterLayerRenderer.gd`, `HexOverlayRenderer.gd` |
| Resize keeps relative zoom (does not force Fit) | `refresh_base_zoom_keep_factor` |

## Acceptance

| Criterion | Result |
|---|---|
| Zoom into coastal/river detail | PASS (wheel + buttons; factor up to ×48 vs fit) |
| Fit restores framed world | PASS (`fit_camera_to_map`) |
| Scroll and/or buttons on macOS Godot 4.7 | PASS (gui_input path; headless project loads) |
| Automated skeleton tests | PASS |

## Explicitly not done (A2+)

- Generation profiles / default Full
- Layer toggles / coast verification
- True hex contours
- Holdridge labels
