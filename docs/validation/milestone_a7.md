# Milestone A7 acceptance record

**Date:** 2026-08-15  
**Scope:** True flat-top hex contours — no A8 Holdridge labels

## Delivered

| Item | Location |
|---|---|
| Flat-top corner offsets matching analytical lattice | `spatial/hex_grid/layout.py` (`hex_corner_offsets`, `hex_vertices_xy`) |
| Godot draw of hex outlines (`draw_multiline`) | `godot/atlas/HexOverlayRenderer.gd` |
| LOD subsample when Fit makes hexes &lt; ~4 px | `_lod_step` / `notify_zoom_changed` |
| Hairline stroke (0.5 screen px, zoom-invariant) | `HEX_WIDTH_SCREEN` / `_stroke_width_world` |
| PNG export uses outlines (not crosses) | `export/atlas_display._draw_hex_overlay` |
| Click-inspect preserved | `hex_at` / `hex_info` unchanged contract |

## Performance note

Primary display is **Godot vector draw** (not the PNG). Full 32 768 cells when zoomed in; when Fit shrinks hexes below ~4 screen px, every Nth cell is drawn (N≤8). Overlay toggle still does not alter raster/vector SoT.

## Acceptance

| Criterion | Result |
|---|---|
| Overlay on → readable **hexagons** (not crosses / square pixel grid) | PASS (geometry + draw path) |
| Overlay off → geography unchanged | PASS (draw-only / visibility) |
| Click-hex inspect when overlay on | PASS (existing pick path) |
| Automated tests | `test_hex_vertices_flat_top_six`, atlas export, Godot skeleton |

## Explicitly not done

- A8 Holdridge legend strings
- Continentality / hypsometry (planned separately)
- Outline smoothing (§7)
