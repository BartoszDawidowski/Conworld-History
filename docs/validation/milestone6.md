# Milestone 6 acceptance record

**Date:** 2026-08-14  
**Scope:** Base seasonal climate only (no Milestone 7 atmosphere / winds)

## Delivered

| Item | Location |
|---|---|
| Monthly insolation (lat + axial tilt) | `worldsim/physical/climate/insolation.py` |
| Temperature + lapse + land/ocean inertia | `worldsim/physical/climate/temperature.py` |
| Climate pipeline (downsample terrain → 1024×512) | `worldsim/physical/climate/pipeline.py` |
| CLI | `--stage climate` (default) |
| Artefacts | `climate/climate_base.npz` (`temperature_c[12,y,x]`, `insolation`, …) |

## Acceptance

| Criterion | Result |
|---|---|
| Correct seasonal inversion (NH warm in June / SH warm in December) | PASS |
| Polar colder than tropics (annual) | PASS |
| Elevation cools land (negative elev–temp correlation) | PASS |
| Automated tests | **58 passed** fast (includes new climate suite) |

## Explicitly not done (Milestone 7+)

- Pressure proxy / wind fields / circulation zones
- Coriolis / topographic wind perturbation
- Ocean currents / SST coupling beyond simple ocean bias
- Moisture / precipitation
