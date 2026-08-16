# Physical Realism PR-0 — baseline and regression harness

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §15 PR-0  
**Production physics:** unchanged  

---

## Delivered

| Item | Location |
|---|---|
| Seed suites (Quick / Atlas / Full) | `worldsim/.../validation/physical_realism/seed_suites.py` |
| Checksums / metrics / absolute maps | `checksums.py`, `metrics.py`, `absolute_maps.py` |
| Synthetic audit fixtures / probes | `fixtures.py` |
| Baseline capture CLI | `python -m worldsim.validation.physical_realism.capture_baseline` |
| Captured Quick baseline | `docs/validation/physical_realism_pr0/baseline/` |
| Harness tests (must pass) | `worldsim/tests/test_physical_realism_pr0.py` |
| Audit invariants (`xfail` strict) | `worldsim/tests/test_physical_realism_audit_xfails.py` |

Reproduce:

```bash
cd worldsim
.venv/bin/python -m worldsim.validation.physical_realism.capture_baseline \
  --output ../docs/validation/physical_realism_pr0/baseline \
  --profile quick --seeds 1,42,100
.venv/bin/python -m pytest tests/test_physical_realism_pr0.py \
  tests/test_physical_realism_audit_xfails.py -q
```

---

## Acceptance

| Criterion | Result |
|---|---|
| No production behaviour changes | PASS — only new `validation/` package + tests |
| Baseline can be reproduced | PASS — report + per-seed metrics/checksums/config |
| Audit failures fail for the correct reason | PASS — 5 strict `xfail` tests |
| Existing qualitative tests remain available | PASS — moisture / hydrology / hex suites still green |

---

## Captured Quick baseline (host M2 / arm64)

Profile grids match Godot `PROFILE_QUICK` (tectonics 128×64, terrain 256×128, climate 128×64).

| Seed | elapsed_s | peak_rss_mb (after) | land max_m | river_cells |
|---|---:|---:|---:|---:|
| 1 | ~2.4 | ~198 | ~8939 | 96 |
| 42 | ~2.3 | ~199 | ~8939 | 108 |
| 100 | ~2.5 | ~203 | ~8939 | 96 |

Full JSON: `baseline/baseline_report.json`. Absolute-scale maps: `seed_*/absolute_maps/` (elevation `[-6000, land_scale_m]`, precip `[0, 40]` proxy).

Note: final DEM maxima sit slightly below `land_scale_m=9000` after fluvial erosion; the **raw** `raw_to_elevation_m` mapping still forces every seed’s land max to `land_scale_m` (see fixture probe / HYP-01 xfail).

---

## Fixture probes (current buggy behaviour)

| Probe | Observation |
|---|---|
| Northward impulse (`wind_v>0`) | Mass moves **south** (larger j) — MOIST-01 |
| Precip vs available `q` | `max_overshoot ≈ 2.4` — MOIST-02 |
| Constant climate year | Strong Jan→Dec ramp (`jan/jul ≈ 0.014`) — MOIST-03 |
| Two raw peaks → metres | Both maxima = 9000 m — HYP-01 |

---

## Audit xfail register

| Test | Fix milestone |
|---|---|
| `test_audit_northward_wind_moves_moisture_to_smaller_j` | PR-4 |
| `test_audit_precip_never_exceeds_available_moisture` | PR-4 |
| `test_audit_constant_climate_has_no_january_startup_ramp` | PR-4 |
| `test_audit_hex_latitudes_mirror_and_mean_near_zero` | PR-1 |
| `test_audit_land_max_not_mechanically_identical_across_peaks` | PR-2 |

When a later PR fixes an invariant, the unexpected pass under `strict=True` will fail CI until the `xfail` marker is removed.

---

## Explicitly not done

- PR-1+ physics fixes  
- Atlas / Full seed baseline capture (suites defined; run when needed)  
- Hydrology seam / cylindrical-graph audit xfails (deferred to PR-5 fixtures)

**Decision:** accept PR-0; stop.
