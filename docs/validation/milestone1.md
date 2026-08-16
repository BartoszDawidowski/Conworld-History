# Milestone 1 acceptance record

**Date:** 2026-08-14  
**Scope:** Coordinate system and spatial substrate only (no PyPlatec / Milestone 2)

## Delivered

| Item | Location |
|---|---|
| Cylindrical equal-area helpers | `worldsim/spatial/coordinates.py` |
| E–W wrap / forbidden N–S wrap | `wrap_x`, `clamp_y`, `CoordinateSystem` |
| Latitude ↔ `y = sin(lat)` | `lat_to_y`, `y_to_lat` |
| Spatial extent / grid index | `worldsim/spatial/extent.py` |
| Root shim | `worldsim/coordinates.py` (re-exports) |
| State wiring | `PhysicalWorldState.coordinates` + `.extents` |

## Acceptance

| Criterion | Result |
|---|---|
| Coordinate round-trips (lon/x, lat/y, cell centres) | PASS |
| Pole / equator mapping valid | PASS |
| Wrap behaviour valid (E–W wrap, no N–S wrap) | PASS |
| Automated tests | **29 passed** (includes Milestone 0 + 1) |

## Explicitly not done

- PyPlatec integration (Milestone 2+)
- Physical generation stages
- Godot project
