# Physical Realism PR-9 — LandformAnalysis foundation

**Date:** 2026-08-16  
**Status:** ✅ **Accepted** (foundation 9A–9D; 9E calibration deferred)  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §12 / §15 PR-9  
**Depends on:** PR-0…PR-8 (esp. PR-2 hypsometry / final DEM)

---

## Delivered

| Slice | Item | Location |
|---|---|---|
| 9A | Contract, enums, algorithm version, synthetic fixtures | `physical/landforms/` + `tests/test_physical_realism_pr9.py` |
| 9B | Multi-scale metrics (km via GridMetrics) + continuous scores | `metrics.py`, `classify.py` |
| 9C | MountainRange / Plateau objects, E–W seam IDs | `objects.py` |
| 9D | Persist rasters + geojson; final pipeline; hex aggregates | `pipeline.py`, `final/pipeline.py`, `hex_grid/pipeline.py` |
| 9E | Seed-suite threshold calibration | **Deferred** (foundation defaults only) |

**Outputs:** `final/landforms/landform_rasters.npz`, diagnostics/legend JSON, `vectors/mountain_ranges.geojson`, `plateaus.geojson`.

**Input:** unconditioned `elevation_v2_m` on analysis grid (climate resolution by default). Does not feed back into tectonics/climate.

---

## Acceptance (synthetic)

| Fixture | Result |
|---|---|
| Isolated cone → range, not plateau-dominated flanks | PASS |
| Elevated flat block → plateau + escarpment | PASS |
| Mountain on plateau → both semantics | PASS |
| Rolling high plain → no mountain range | PASS |
| Two ridges → ≥2 objects; connected ridge ≥1 | PASS |
| E–W seam range → one component | PASS |
| N–S mirror scores within tolerance | PASS |
| Disabled path identity | PASS |
| Deterministic IDs | PASS |
| Existing final / hex tests | PASS |

---

## Explicitly not done

- PR-9E seed-suite threshold calibration / performance gate on Full  
- Godot landform map mode / inspector (may follow)  
- Hydrology-dependent peaks, passes, canyons  
- Full contour polygons (bbox/point foundation only)  
- History `EnvironmentAdapter` mobility costs  

**Decision:** accept PR-9 foundation; stop. Next when instructed: **B10** (atlas) or 9E calibration / Godot display.
