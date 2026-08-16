# Physical Realism PR-2 — hypsometry `power_tail_v2`

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §8 / §15 PR-2  
**Depends on:** PR-0, PR-1  
**Folding / sea-level / erosion:** **not retuned** (`folding_ratio` remains 0.01)

---

## Delivered

| Item | Location |
|---|---|
| Pure `power_tail_v2` + C1 soft tail | `physical/terrain/elevation.py` |
| Modes: `legacy_max` (default) / `power_tail_v2` | config + `TerrainParams` |
| Robust detail scale (p05–p95) in refine | `physical/terrain/refine.py` |
| Pipeline diagnostics (mask, components, rank, hypsogram) | `physical/terrain/pipeline.py` |
| Seed before/after report + absolute maps | `docs/validation/physical_realism_pr2/hypsometry/` |
| Report CLI | `python -m worldsim.validation.physical_realism.hypsometry_report` |
| Tests | `tests/test_physical_realism_pr2.py` |

Packaged default remains **`hypsometry_mode: legacy_max`** (annex: disabled until calibration). Enable with:

```yaml
terrain:
  hypsometry_mode: power_tail_v2
  hypsometry_anchor_quantile: 0.95
  hypsometry_anchor_elevation_m: 3000.0
  hypsometry_body_exponent: 0.70
  # hypsometry_max_elevation_m defaults to land_scale_m
```

---

## Acceptance

| Criterion | Result |
|---|---|
| Mask / coastline / land components unchanged by land transform | PASS |
| 0→0, no positive→negative, rank order | PASS |
| Maxima not mechanically identical across seeds (v2) | PASS — see report |
| Folding not retuned | PASS |
| Runtime negligible vs terrain | PASS — Full raster transform ~tens of ms |
| Seed suite hypsograms + absolute maps | PASS |

---

## Seed suite (Quick grids 256×128 terrain, folding frozen)

| Seed | legacy max_m | legacy p50 | power_tail max_m | power_tail p50 |
|---|---:|---:|---:|---:|
| 1 | 9000 | ~1175 | ~5489 | ~1382 |
| 42 | 9000 | ~1551 | ~4528 | ~1342 |
| 100 | 9000 | ~2030 | ~4282 | ~1526 |

`maxima_mechanically_identical: false` for power_tail. Artefacts: `hypsometry/seed_*/elevation_*.png` + `hypsometry_seed_report.json`.

---

## Performance

| Operation | Time (M2) |
|---|---|
| power_tail_v2 on 4096×2048 | ~316 ms |
| legacy_max on 4096×2048 | ~227 ms |
| Quick seed terrain with v2 | ~0.2 s |

---

## Audit register

| Item | Status |
|---|---|
| HYP-01 (mechanical max) | ✅ Covered by `power_tail_v2` tests; legacy mode still hits `land_scale_m` by design |
| MOIST xfails | ✅ Fixed in PR-4 |

---

## Explicitly not done

- Enabling `power_tail_v2` as packaged default (calibration step)  
- Retuning lapse / climate for the lower median land heights  
- `landmass_surface` / `relief_surface` (deferred §8.7)  
- PR-3+  

**Decision:** accept PR-2; stop. Next calibration may flip the default mode after reviewing the seed report.
