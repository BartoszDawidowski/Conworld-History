# Worldgen corrective C5 — precipitation mechanisms and regional monsoon

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **production precip knobs not retuned**)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C5  
**Depends on:** C4 (conservative transport) and C3 (metric DEM path)  
**Audited commit before this package:** post-C4 working tree

---

## Delivered

| Item | Location |
|---|---|
| Metric, meso-smoothed, speed-normalised orographic ascent | `orographic_lift` (`metric_smooth_ascent_v1`) |
| Humidity stratiform + supersaturation overflow → large-scale precip | `partition_precipitation` / `_month_step` |
| Lee = condensation efficiency + extra capacity on descent; `lee_sink=0` | `partition_precipitation` |
| Monsoon gate per cell/coastal sector, not hemisphere mean | `monsoon_sector_gate_v1` |
| Seasonal onshore **and** precip-ratio tests | `tests/test_worldgen_corrective_c5.py` |
| Component share diagnostics | budget `precip_share_*` |

Budget stamp: `moisture_budget_spinup_v6_c5`. Orography stamp: `metric_smooth_ascent_v1`. Monsoon stamp: `monsoon_sector_gate_v1`.

Frozen YAML (not retuned): `orographic_frac=0.85`, `large_scale_frac=0.15`, `advect_wind_scale=0.2`, `convective_scale=2.0`, `itcz_convective_scale=1.2`, `monsoon_strength=0.35`, `plume_strength=0.18`. Choosing new numbers from the grid below is **C10**.

Hardcoded orographic analysis length: `ORO_SMOOTH_KM=150`, `ORO_SLOPE_SCALE_M_PER_KM=25`.

---

## Operators

### Orographic

Elevation is box-smoothed at 150 km when GridMetrics spacing is available, then `∇h` is taken in m/km. Lift is `(u sx − v sy) / |wind|` with `tanh(slope / 25 m km⁻¹)`, so the field is in `[-1, 1]` and one-cell DEM spikes do not dominate.

### Large-scale / stratiform

Previously `large_scale_frac × max(0, q − capacity)` was ~0 because `q` almost never reached saturation, and leftover humidity was a silent `capacity_sink` at `1.25 × capacity`. Now:

1. stratiform demand `∝ q × RH` (operational below saturation);
2. remaining `q > capacity` after the partition is **additional large-scale precip**, not an unreported sink.

### Lee

Descent raises effective capacity and multiplies every condensation term by `1/(1+lee_w)`. No `q` mass is destroyed.

### Monsoon

A cell is gated on only if its own monthly land–SST anomaly series crosses both `+ε` and `−ε`. Opposite regional monsoons in the same hemisphere no longer cancel. Trades outside the lat band and ungated cells stay on the base field.

---

## Calibration grid (warm tropical ridge fixture; not defaults)

24×48, ocean west, N–S ridge, `T=26°C`, `u=6`, plume off, `advect_max_substeps=8`, 3 spin-up years. Residual ≤ `1e-16` on every row that completed.

| `advect_wind_scale` | `orographic_frac` | `large_scale_frac` | oro share | large-scale | conv+ITCZ | windward/lee |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.25 | 0.15 | 0.020 | 0.177 | 0.802 | 1.89 |
| 0.2 | 0.25 | 0.45 | 0.016 | 0.389 | 0.595 | 1.86 |
| 0.2 | 0.40 | 0.15 | 0.032 | 0.175 | 0.793 | 2.20 |
| 0.2 | 0.40 | 0.45 | 0.026 | 0.385 | 0.589 | 2.14 |
| 0.2 | 0.55 | 0.15 | 0.044 | 0.173 | 0.784 | 2.53 |
| 0.2 | 0.55 | 0.45 | 0.036 | 0.381 | 0.584 | 2.43 |
| **0.2** | **0.85** | **0.15** | **0.066** | **0.168** | **0.766** | **3.24** |
| 0.2 | 0.85 | 0.45 | 0.054 | 0.373 | 0.573 | 3.06 |

`wind_scale=0.4` with cap **8** fails CFL closed (expected). Production cap **32** is the numerical safety limit, not reach.

Convective/ITCZ at production oro/large/wind:

| `convective_scale` | `itcz_convective_scale` | oro | large-scale | conv+ITCZ |
|---:|---:|---:|---:|---:|
| 1.5 | 0.8 | 0.077 | 0.213 | 0.710 |
| 1.5 | 1.2 | 0.073 | 0.195 | 0.732 |
| 2.0 | 0.8 | 0.069 | 0.182 | 0.749 |
| **2.0** | **1.2** | **0.066** | **0.168** | **0.766** |

On this warm fixture convection dominates globally while the ridge still casts a 3:1 rain shadow. Addendum C10 bands (oro 15–55%, conv+ITCZ 20–65%) are **not** fitted here.

**Decision:** keep production YAML. The operators are no longer numerically inactive; knob selection waits for the multi-seed C10 grid.

---

## Acceptance

| Criterion | Result |
|---|---|
| No mechanism is live only because another is a no-op | PASS (production knobs: oro, large-scale, conv+ITCZ all > 2%) |
| Interiors get stratiform/transported moisture; ridge shadow remains | PASS |
| Opposite NH landmasses keep opposite monsoon anomalies; trades coherent | PASS |
| Seasonal onshore **and** coastal precip ratio vs no-monsoon control | PASS |
| Budget closed on every completed sweep candidate (rel residual ≪ 1e-6) | PASS |
| `pytest -m "not slow"` | PASS — 348 passed, 3 deselected |
| Atlas `183716` | **Leftover** — not regenerated |

---

## Explicitly not done

- Writing new `orographic_frac` / `large_scale_frac` / `advect_wind_scale` / `convective_scale` / `monsoon_strength` into YAML (**C10**)
- Default `plume_strength=0` experiment
- Atlas `183716` regen
- BiomeV2 climatological wetness (**C6**)

**Decision:** accept C5 operator correctness; stop. Next when instructed: **C6** only.
