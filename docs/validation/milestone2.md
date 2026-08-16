# Milestone 2 acceptance record

**Date:** 2026-08-14  
**Scope:** Upstream PyPlatec baseline only (no extended metadata / Milestone 3)

## Delivered

| Item | Location |
|---|---|
| Upstream `pyplatec==1.4.3` dependency | `worldsim/pyproject.toml` |
| Baseline runner | `worldsim/physical/tectonics/baseline.py` |
| E–W seam selection + roll | `worldsim/physical/tectonics/seam.py` |
| Diagnostics | `worldsim/physical/tectonics/diagnostics.py` |
| Pipeline stage | `run_tectonics` in `worldsim/pipeline.py` |
| CLI | `--stage tectonics` (default); overrides `--tectonics-width/height` |

## Outputs

Under `<output>/tectonics/`:

- `tectonics_baseline.npz` — `elevation_raw`, `plate_id`, seam/seed metadata
- `tectonics_diagnostics.json`
- `tectonics_meta.json`

## Acceptance

| Criterion | Result |
|---|---|
| Deterministic (same seed → same maps/seam) | PASS |
| Seam consistent (selected column becomes western edge) | PASS |
| No final N–S connectivity in model (`SpatialExtent.neighbour`) | PASS |
| Target 1024×512 path | PASS (`pytest -m slow`, ~18s on M2) |
| Automated tests | **37 passed** (36 fast + 1 slow) |

## Explicitly not done (Milestone 3+)

- Vendoring / forking PyPlatec
- `get_agemap` / plate velocity bindings
- Tectonic interpretation (boundaries, classes)
- Windows/MSVC packaging build matrix
