# Milestone 16 acceptance record

**Date:** 2026-08-14  
**Scope:** WorldSpatialModel persistence + spatial queries only (no Milestone 17 Godot atlas)

## Delivered

| Item | Location |
|---|---|
| Canonical raster store (npz + layers catalog) | `worldsim/spatial/raster_store/` |
| Canonical vector store (JSON + spatial index) | `worldsim/spatial/vector_store/` |
| Hex cache under analysis_grid | `physical/analysis_grid/` via `HexAnalysisResult` |
| Manifest + world model schema versioning | `spatial/manifest.py` (`WORLD_MODEL_SCHEMA_VERSION=1`) |
| `WorldSpatialModel` load/save | `spatial/model.py` → `world/` |
| Spatial query API (Godot-free) | `spatial/queries/` + façade on model |
| Cache rebuild (`river_edge_mask`, spatial index) | `WorldSpatialModel.rebuild_*` |
| CLI | `--stage world` (default) |

## Layout

```text
world/
  manifest.json
  config.json
  metadata.json
  physical/
    rasters/
    vectors/
    analysis_grid/
```

## Acceptance

| Criterion | Result |
|---|---|
| Round-trip preserves world | PASS |
| Query API works without Godot | PASS |
| Caches can be rebuilt | PASS |
| Automated tests | **91 passed** fast |

## Explicitly not done (Milestone 17+)

- Godot atlas / worker UI
- Full §33.3 hex cache field set
- EnvironmentTimeline (Milestone 19)
