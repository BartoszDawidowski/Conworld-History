# Physical Realism PR-1 — GridMetrics + balanced hex geometry

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §7 / §15 PR-1  
**Depends on:** PR-0  

---

## Delivered

| Item | Location |
|---|---|
| `GridMetrics` (area, EW/NS spacing, gradients, slope, D8 length, distance-to-mask km, neighbourhood) | `worldsim/src/worldsim/spatial/metrics.py` |
| Length-units migration (`*_cells` → `*_km`, Atlas source profile) | `worldsim/src/worldsim/spatial/units_migration.py` |
| Balanced odd-q hex layout v2 (no pole clip, N–S mirror) | `worldsim/src/worldsim/spatial/hex_grid/layout.py` (`HEX_LAYOUT_ALGORITHM_VERSION = 2`) |
| Hex diagnostics + acceptance include layout invariants | `hex_grid/pipeline.py` |
| World manifest v2 + `length_units` / layout version | `spatial/manifest.py` (`WORLD_MODEL_SCHEMA_VERSION = 2`), `spatial/model.py` |
| Optional `planet.radius_km` + YAML km overrides | `config.py`, `configs/default_planet.yaml` |
| Tests | `tests/test_physical_realism_pr1.py`; audit hex xfail **removed** (now passes) |

---

## Acceptance

| Criterion | Result |
|---|---|
| Metric + hex synthetic tests | PASS |
| No pole clipping | PASS (`|y|_max = 1 - 0.5/H`) |
| Atlas/Full distance convergence | PASS (60 Atlas cells ≈ 120 Full cells mid-lat EW) |
| Caches versioned | PASS — world model schema **2**; hex layout algorithm **2** |
| Performance | PASS — see below |

**Not in this milestone:** wiring `*_km` into live SST / continentality / currents (still use cell knobs). Migration records effective km for PR-3.

---

## Performance (M2 arm64)

| Operation | Time |
|---|---|
| GridMetrics Full climate (1024×512) spacing + slope | ~10 ms |
| Cached `grid_metrics` factory | ≪1 µs |
| Hex centres + neighbour matrix 256×128 | ~70 ms (unchanged order; one-time per world) |

---

## Length migration note

Legacy `inland_decay_cells=60` on the **Atlas climate** grid (512×256) converts to ≈ **4691 km** mid-latitude EW. That documents the Atlas-tuned cell reach; it is **not** a new physical retune. PR-3 should adopt explicit `sst_inland_decay_km` (and peers) and recalibrate.

Compatibility warnings are emitted once per distinct conversion message when a world model is built.

---

## Audit register update

| Test | Status |
|---|---|
| `test_audit_hex_latitudes_mirror_and_mean_near_zero` | ✅ **PASS** (PR-1) |
| MOIST-01/02/03, HYP-01 xfails | still xfail → PR-4 / PR-2 |

---

## Explicitly not done

- PR-2 hypsometry  
- Applying km scales inside temperature / SST / boundary currents (PR-3)  
- Moisture / hydrology P0 fixes  

**Decision:** accept PR-1; stop.
