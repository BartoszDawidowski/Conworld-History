# ADR-0001 — Vendored PyPlatec with extended observational bindings

- **Status:** Accepted
- **Date:** 2026-08-14
- **Milestone:** 3

## Context

Architecture §18 requires:

- `elevation_raw`, `plate_id` (mandatory)
- `crust_age`, `plate_velocity_x/y`, `plate_speed` when feasible
- preferred Python API: `get_agemap`, `get_plate_count`, `get_plate_velocity`, `get_plate_speed`

Upstream PyPI `pyplatec==1.4.3` only exposes heightmap + platesmap, even though the
native C library already implements age maps and plate velocity queries.

## Decision

1. Vendor a minimal fork under `vendor/pyplatec` (C++ `cpp_src/` + Python
   `platec_src/`), not the entire plate-tectonics monorepo extras.
2. Extend bindings to expose existing native observational getters.
3. Fix `platec_api_get_agemap` to accept a lithosphere pointer (consistent with
   other getters; upstream id-based signature was unusable from Python handles).
4. Capture plate velocity/speed during the step loop because plate objects are
   destroyed when `is_finished` becomes true (`getPlateCount() == 0`).
5. Keep a stable fallback result object (`metadata_source=fallback_inferred_zero`)
   if extended getters are unavailable, so downstream Milestone 4+ APIs do not
   branch on missing fields.

## Consequences

- macOS Apple Silicon build verified via editable install of `worldsim-platec`.
- Windows requires MSVC Build Tools; see `vendor/pyplatec/scripts/build_windows.ps1`.
  Full CI packaging remains Milestone 18.
- LGPL-3.0 obligations: license text in `vendor/pyplatec/LICENSE` and
  `licenses/PYPLATEC_LGPL-3.0.txt`; notices in `THIRD_PARTY_NOTICES.md`.
- Simulation stepping code is unchanged; getters are read-only. Height/plate maps
  for a given seed remain the simulation outputs (observational extension).
