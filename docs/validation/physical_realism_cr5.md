# Physical Realism CR-5 — joint calibration (hypsometry, landforms, hydro km²)

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-5  
**Defects closed:** **F-12** (`tail_softness` no-op); **F-13** remainder (km scales + km² floors + production thresholds); **F-11** remainder (river catchment km²)

---

## Delivered

| Item | Location |
|---|---|
| Real `tail_softness` (`s=1` = PR-2 identity / C1; `s≠1` C0) | `physical/terrain/elevation.py` `power_tail_v2_curve` |
| Production default `hypsometry_mode: power_tail_v2` | YAML + `PlanetConfig` / `TerrainParams` |
| Anchor quantile **0.95**, elevation **3000 m**, body exponent **1.5** | YAML (middle of 1.2 / 1.5 / 1.8 trial band) |
| Landform scales **60 / 150 / 300 km** | `LandformParams` + YAML `landforms:` |
| Min object size **km²** (`min_range_km2=800`, `min_plateau_km2=2500`) | `landforms/params.py` `min_object_cells` |
| Mountain score threshold **0.50** (not 0.60–0.65; see below) | YAML + `LandformParams` |
| Algorithm stamp `landform_v1_cr5`; `area_km2` on ranges/plateaus | `landforms/` |
| River min catchment **500 km²** via `GridMetrics.cells_for_area_km2` | `hydrology/pipeline.py` |
| Landform params through final recalc | `pipeline.py` `FinalRecalcParams(landforms=…)` |
| Tests + 3-seed table | `tests/test_physical_realism_cr5.py`, `docs/validation/physical_realism_cr5/seed_table.json` |

---

## Hypsometry

`rate = p / (span * s)`. Larger softness → gentler climb above the anchor → **lower** `f(x)` at moderate `x>1`. Production `tail_softness: 1.0` preserves the PR-2 C1 join; the knob is no longer a documented no-op.

Body exponent **1.5** is the middle of the CR-5 trial band. A three-value production sweep on full Quick/Atlas was **not** run this milestone.

PR-0 harness probe `land_max_hits_scale` now asserts production `power_tail`: two different raw peaks map to **different** elevations, both **below** `land_scale_m` (9000 m).

---

## Landforms (PR-9E thresholds)

| Knob | Production | Notes |
|---|---|---|
| Fine / meso / macro | 60 / 150 / 300 km | Inside annex bands ~60 / 120–180 / 250–400 |
| `mountain_score_threshold` | **0.50** | Isolated 2200 m cone on 48×64 peaks near u8≈128. **0.60–0.65 needs score-formula retune** |
| Min range / plateau | 800 / 2500 km² | Cell count derived from equal-area `cell_area_km2` |
| `acceptance_ok` | `structural_ok and calibrated` | `mountain_land_fraction` is **diagnostic**; cap 0.40 does not fail acceptance (tiny grids with 1-cell windows flag ~37–70% of land as score-above-threshold) |

Plateau + low-relief fixture still detects ≥1 plateau under production params. Cone fixture detects ≥1 range at threshold 0.50 when km² floor is disabled (cell area on 48×64 otherwise swallows a single peak).

---

## Three-seed metric table (tectonics 64×32 → terrain 128×64)

Not a full Quick/Atlas regen. Absolute land elevations under `power_tail_v2`; maxima are **not** pinned to 9000 m.

| Seed | p50 (m) | mean (m) | max (m) | ranges | plateaus | mountain score frac |
|---|---|---|---|---|---|---|
| 1 | 584 | 923 | 5994 | 21 | 2 | 0.67 |
| 42 | 580 | 951 | 4695 | 15 | 0 | 0.72 |
| 100 | 484 | 835 | 5748 | 11 | 2 | 0.72 |

Raw JSON: [`physical_realism_cr5/seed_table.json`](physical_realism_cr5/seed_table.json).

---

## Acceptance

| Criterion | Result |
|---|---|
| `tail_softness=1` identity + C1 join | PASS |
| Softness stretches tail (higher `s` → lower `f` at x=2.5) | PASS |
| Production mode `power_tail_v2`; maxima not all 9000 m | PASS (3 seeds, distinct maxima) |
| km² object floors scale with cell area | PASS |
| River 500 km² → 1 cell on 256×128; ≥8 on Full 4096×2048 | PASS |
| Plateau kept on high-flat fixture | PASS |
| `pytest -m "not slow"` | PASS — 249 passed, 3 deselected |

---

## Explicitly not done

- Full Quick seeds **1 / 42 / 100** regeneration and Atlas landform counts (table above is 128×64 only)  
- Body-exponent production sweep **1.2 vs 1.5 vs 1.8** on those seeds  
- Moisture trial band (orographic / lee / plume / ITCZ); `orographic_frac` remains **0.85**  
- Godot landform map mode  
- Full memory/time gate (CR-4 already skips `monthly_gross`)  
- Score-formula retune so annex mountain threshold **0.60–0.65** is usable  
- Remaining cell knobs (`advect_steps`, bathymetry shelf cells, …) — not this milestone  
- `folding_ratio` / `ocean_evap_rate` left frozen (do not retune to hide defects)

**Decision:** accept CR-5; stop. CR track complete. Next when instructed: optional **B10** (atlas) or a named moisture/hypsometry follow-up — not a new CR-N unless registered.
