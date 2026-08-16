# Milestone 4 acceptance record

**Date:** 2026-08-14  
**Scope:** Stage B tectonic interpretation only (no Milestone 5 terrain)

## Delivered

| Item | Location |
|---|---|
| Interpretation engine | `worldsim/physical/tectonics/interpretation.py` |
| Boundary mask / plates / distance | cylindrical BFS distance (E–W wrap) |
| Normals + relative velocity | projected onto normal/tangent |
| Boundary classes | convergent / divergent / transform / oblique / weak |
| Proxies | activity, convergence/divergence/transform, subduction, orogeny, volcanic, earthquake |
| Pipeline wiring | `run_tectonics` runs M3 extended + M4 interpretation |
| Artefacts | `tectonics/tectonics_interpretation.npz` (+ diagnostics JSON) |

## Acceptance

| Criterion | Result |
|---|---|
| Expected spatial correlations | PASS (synthetic convergent/divergent; activity near boundaries) |
| Classification from relative velocity (not random) | PASS |
| Automated tests | **46 passed** fast (+ prior slow suite still available) |

## Explicitly not done (Milestone 5+)

- High-resolution terrain refinement / bathymetry
- Sea-level calibration lock
- Coastline vectorization
- Resolution benchmarks 4096×2048 vs 2048×1024
