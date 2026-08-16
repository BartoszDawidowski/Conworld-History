# Milestone B4 — Land fill + elevation texture

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md`  
**Status:** ✅ Complete

## Scope

Godot presentation: filled land vectors; elevation (and climate modes) textured **inside** land rings; bathymetry = full ocean raster + flat land fill; coast/rivers/lakes/hex unchanged.

## Delivered

| Item | Notes |
|---|---|
| `LandLayerRenderer.gd` | Ocean BG + land clip host |
| `LandClipMask.gd` | Opaque land rings + `CLIP_CHILDREN_AND_DRAW` |
| Elevation / temp / precip / holdridge | Mode PNG clipped to land rings |
| Bathymetry | Full raster under flat vector land |
| Fallback | No `land.geojson` → previous full-raster behaviour |
| Holdridge BR legend | **Deferred** (removed in B2 chrome; still deferred) |

## Draw order

```text
raster (bathymetry only when that mode)
→ land (ocean BG + clipped texture or flat land)
→ coast / rivers / lakes
→ hex
```

## Acceptance

| Criterion | Result |
|---|---|
| Land edge from vectors; elevation interior textured | Met (clip) |
| Non-elevation modes do not keep elev texturing | Met (texture swaps with mode) |
| Coast toggle still works | Met |
| Atlas `land.geojson` (B3) | Required for composite |

## Notes

- Fill uses `land_mask.png` + shader (ocean = `bathymetry.png`, land = mode tex).
- Coast strokes are derived from **the same** `land_mask` edges (not legacy
  `coastline.geojson`) so outline and fill share one grid — including 1-cell islands.
- Orphan geojson coast loops without mask land were misalignment ghosts; they are dropped.
- Lakes/rivers use the brightest ocean (shallow) colour sampled from bathymetry.
- Holdridge BR legend remains deferred.

## Stop

B4 complete (fill fix applied). Next when instructed: **B5** (climate/coupling knobs).
