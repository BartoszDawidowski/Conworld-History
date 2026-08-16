# Milestone 15 acceptance record

**Date:** 2026-08-14  
**Scope:** 256×128 analytical hex grid only (no Milestone 16 WorldSpatialModel persistence)

## Delivered

| Item | Location |
|---|---|
| Flat-top odd-q layout, equal-area cylindrical centres | `worldsim/spatial/hex_grid/layout.py` |
| Raster aggregation (mean/min/max/std, monthly, dominant) | `hex_grid/aggregate.py` |
| River/lake/coastline id caches + `river_edge_mask` | `hex_grid/intersections.py` |
| Hex pipeline + artefacts | `hex_grid/pipeline.py` → `hex/` |
| CLI | `--stage hex` (default) |
| Artefacts | `hex_environment.npz`, `hex_object_refs.json`, `hex_diagnostics.json` |

## Acceptance

| Criterion | Result |
|---|---|
| Exactly 32 768 cells (production 256×128) | PASS (`HexGridSpec.n_cells`) |
| Correct E–W wrap | PASS |
| No N–S wrap | PASS |
| Cache vs raster within tolerance (ocean fraction, elev sample) | PASS |
| Hex is derived cache (rasters/vectors remain SoT) | PASS |
| Automated tests | **88 passed** fast (includes hex suite) |

## Explicitly not done (Milestone 16+)

- WorldSpatialModel load/save / query API
- Full environmental cache field set from architecture §33.3 (slope, winds, SST, …) — core subset shipped
- Godot hex overlay
