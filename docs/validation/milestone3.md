# Milestone 3 acceptance record

**Date:** 2026-08-14  
**Scope:** Extended PyPlatec (vendor + crust age + velocity). No Milestone 4 interpretation.

## Delivered

| Item | Location |
|---|---|
| Vendored fork | `vendor/pyplatec/` |
| Extended Python API | `get_agemap`, `get_plate_count`, `get_plate_velocity`, `get_plate_speed` |
| Engine + result types | `worldsim/physical/tectonics/{engine,baseline,capabilities,params}.py` |
| ADR | `docs/ADR/ADR-0001-vendored-pyplatec-extended-bindings.md` |
| LGPL text | `licenses/PYPLATEC_LGPL-3.0.txt` |
| macOS build | editable install of `worldsim-platec` (verified) |
| Windows build script | `vendor/pyplatec/scripts/build_windows.ps1` (MSVC required; not run on this Mac) |

## Acceptance

| Criterion | Result |
|---|---|
| Metadata accessible (age + velocity + speed) | PASS (`metadata_source=native_extended`) |
| Simulation maps observationally unchanged vs baseline getters | PASS (height/plate/seam equal for same seed) |
| macOS Apple Silicon build attempt | PASS |
| Windows build | Script provided; needs MSVC host (deferred execution) |
| Automated tests | **42 passed** (40 fast + 2 slow) |

## Explicitly not done (Milestone 4+)

- Boundary classification / tectonic interpretation
- Relative velocity projection onto boundary normals
- Activity / orogeny / volcanic proxies
