# Physical Realism CR-8 — atmosphere (advection, lee, monsoon, hydro↔evap)

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-8  
**Defects closed:** **F-18** remainder (one damped hydrology rebuild after inland-water moisture).  
**Partial:** **F-03** (lee no longer a mass sink; CFL advection; joint closure unchanged — Atlas 183716 `spinup_converged` not re-measured); **F-07** (anomaly monsoon + sign gate + sea-level / `temperature_base_c` — Atlas year-round offshore leftover until regen); **F-11** (`advect_steps` is a CFL cap; km Courant vs Atlas width 1024).

---

## Delivered

| Item | Location |
|---|---|
| Donor-cell finite-volume advection; GridMetrics spacing; adaptive CFL (`advect_steps` cap) | `moisture/transport.py` `finite_volume_cfl_v1` |
| Production km scale vs Atlas width 1024; fixture default = this-grid equator cell | `ADVECT_SCALE_REF_WIDTH`; `advect_scale_ref_width=` |
| `lee_dry` inhibits condensation; `lee_sink` is zero; diagnostic `lee_inhibited` | `partition_precipitation`; `lee_mode=condensation_brake` |
| Monsoon = land/SST anomalies vs own annual means; sea-level T; 500 km regional mean; hemisphere sign gate | `atmosphere/monsoon.py` `monsoon_anomaly_gate_v1` |
| Monsoon T source = `temperature_base_c` (pre-SST), not coupled surface T | `moisture/pipeline.py` |
| One damped hydro rebuild: blend precip then `build_hydrology` once more | `final/pipeline.py` `hydro_evap_iteration=1`, `hydro_evap_blend=0.5` |
| Tests | `tests/test_physical_realism_cr8.py` |

Budget stamp: `moisture_budget_spinup_v4_cr8`. Sinks are precipitation + capacity ceiling only.

Frozen numbers (not retuned): `orographic_frac=0.85`, `ocean_evap_rate=1.4`, `lee_dry=0.12` (new meaning), `monsoon_strength=0.35`, `advect_steps=32` (CFL max).

---

## Acceptance

| Criterion | Result |
|---|---|
| Lee precip lower with `lee_dry`; remaining `q` not destroyed; `lee_sink=0` | PASS |
| Annual `lee_sink` sum is 0; residual not a lee mass term | PASS |
| Seasonal anomalies flip when absolute land−SST stays negative | PASS |
| Sign gate zeros the anomaly when contrast never crosses ±0.05 | PASS |
| Frozen moisture knobs unchanged | PASS |
| Hydro↔evap: exactly one rebuild, blend 0.5 | PASS (`test_final`) |
| `pytest -m "not slow"` | PASS — 273 passed, 3 deselected |
| Atlas 183716 `spinup_converged` | **Leftover** — world not regenerated this milestone |

Atlas 183716 full regen was **not** re-run (same as CR-6/CR-7). Expected production effect: no ~24.6% precip-as-`lee_sink`; monsoon can gate off or flip with seasonal anomalies vs own means; hydrology sees a damped second precip field after real liquid masks.

---

## Explicitly not done

- Atlas / Quick seed regen and production `spinup_converged` evidence (**F-03 leftover**)  
- `orographic_frac` / precip / SST / `folding_ratio` / `lake_min_depth_m` calibration  
- Orography as slope (not raw Δz); erosion `cell_scale_m=1000` (**F-21 / CR-9**)  
- Landform score / BiomeV2 (**CR-9**)  
- Full memory rewrite (**F-14**)  
- Atlas cell still larger than 500 km² (**F-17 leftover**)

**Decision:** accept CR-8; stop. Next when instructed: **CR-9** only.
