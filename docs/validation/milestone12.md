# Milestone 12 acceptance record

**Date:** 2026-08-14  
**Scope:** Canonical vector physical geography only (no Milestone 13 fluvial feedback)

## Delivered

| Item | Location |
|---|---|
| Final coastline vectors | `worldsim/physical/vectorize/coast.py` → `vectors/coastline.geojson` |
| River node/segment network + polylines | `vectorize/rivers.py` → `river_network.json`, `rivers.geojson` |
| Lake polygons | `vectorize/lakes.py` → `lakes.geojson` |
| Basin metadata | `vectorize/basins.py` → `basins.json` |
| Spatial index (grid buckets, hex-independent) | `vectorize/indexes.py` → `spatial_index.json` |
| CLI | `--stage vectors` (default) |

## Acceptance

| Criterion | Result |
|---|---|
| Raster/vector consistency (coast, rivers, lakes) | PASS |
| River topology valid | PASS |
| Vectors persist independently of hex grid | PASS |
| Automated tests | **77 passed** fast (includes vectors suite) |

## Explicitly not done (Milestone 13+)

- Second fluvial erosion / terrain v2
- Climate correction feedback loop
- Final hydrology + vector refresh after erosion v2
- Shapely-based geometry engine (not required for M12)
