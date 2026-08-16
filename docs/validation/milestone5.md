# Milestone 5 acceptance record

**Date:** 2026-08-14  
**Scope:** High-resolution terrain + ocean/coast prototype (no Milestone 6 climate)

## Delivered

| Item | Location |
|---|---|
| Cylindrical bilinear upsample | `worldsim/spatial/resample.py` |
| Terrain refinement (tectonics-dominated) | `worldsim/physical/terrain/refine.py` |
| Sea-level vs ocean fraction target | `worldsim/physical/terrain/sealevel.py` |
| Bathymetry shaping | `worldsim/physical/terrain/bathymetry.py` |
| Water bodies / basins | `worldsim/physical/terrain/waterbodies.py` |
| Coastline vector prototype | `worldsim/physical/terrain/coastline.py` |
| Pipeline + benchmark | `worldsim/physical/terrain/pipeline.py` |
| CLI | `--stage terrain` (default) |
| Production lock | `configs/default_planet.yaml` → `terrain_production: [4096, 2048]` |
| Benchmark report | `docs/validation/milestone5_benchmark.json` |
| ADR | `docs/ADR/ADR-0002-terrain-production-resolution.md` |

## Acceptance

| Criterion | Result |
|---|---|
| Production resolution justified by benchmark | PASS — locked **4096×2048** |
| No severe E–W seam artefact | PASS (`seam_gap_relative` ~0.007 on sample) |
| Detailed coast independent of hex grid | PASS (`coastline_prototype.geojson`) |
| Automated tests | **51 passed** fast |

## Explicitly not done (Milestone 6+)

- Monthly climate / insolation / temperature
- Atmosphere and ocean circulation
- Erosion / hydrology engines
