# Milestone B6 — Stroke smoothing (+ presentation polish B6b)

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md` §7 B6 / Plan A §7 B/C  
**Status:** ✅ Complete (+ B6b presentation follow-up)

## Scope

Presentation only. Simulation rasters / hydrology SoT unchanged.

### B6 (strokes)

| Piece | Where |
|---|---|
| DP + Chaikin rivers/coast GeoJSON | `worldsim/export/stroke_smooth.py` + `atlas_display.py` |
| Coast accent from `land_mask` edges | `VectorLayerRenderer` chain + smooth |

### B6b (user follow-up — land / lakes / texture softness)

| Piece | Where | Notes |
|---|---|---|
| Soft land silhouette | `land_composite.gdshader` | Linear mask + smoothstep; light beige fill |
| Coast aligned to soft land | same shader rim (`show_coast`) | Beige AA hairline via `fwidth(raw)` screen distance (stable under zoom; no hard-step vanish) |
| Elevation | style 2 | Beige land + monochrome luminance overlay (not full colour replace) |
| Mode texture softness | mild blur; weaker on Holdridge | |
| Lake outlines | closed Chaikin | |

Land **fill** soft edges; coast is a **single** screen-space rim on that edge (no double band). Lakes: **mild** Laplacian + Chaikin only; reject self-intersecting results (`Geometry2D.triangulate_polygon` guard) so large lakes no longer vanish.

## Acceptance

| Criterion | Result |
|---|---|
| Softer rivers/coasts, no dateline chords | Met |
| Land fill soft under coast strokes | Met (B6b) |
| Lakes not stair-stepped | Met (B6b) |
| Elevation (and continuous modes) softer | Met (presentation blur) |
| Simulation unchanged | Met |

## Stop

B6 (+B6b) complete. Next when instructed: **B7**.
