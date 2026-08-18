# Worldgen corrective C3T — temperature-state integrity and optional continental seasonality

**Date:** 2026-08-17  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **no global temperature retune**)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C3T  
**Depends on:** C3 (final DEM correction path); otherwise independent  
**Audited commit before this package:** post-C3 working tree

---

## Delivered

| Item | Location |
|---|---|
| Shared `temperature_diagnostics(array, state_name=…)` | `climate/temperature.py` |
| DEM lapse updates `temperature_c`, `temperature_base_c`, `temperature_equilibrium_c` | `correct_climate_for_dem` |
| SST writeback restamps stats from the coupled array | `apply_ocean_temperature_to_climate` + `restamp_temperature_diagnostics` |
| Provenance: equilibrium / pre-SST base / published | diagnostics `temperature_provenance`, `lapse_apply_count`, `sst_apply_count` |
| Optional inland seasonal gain (default **0**) | `apply_continental_seasonality`; YAML `continental_seasonality_gain` |
| Tests | `tests/test_worldgen_corrective_c3t.py` |

Frozen comparison values: `base_temp_c=25`, lapse `6.5 C/km`, `sst_mix=0.28`, SST inland decay `1200 km`. Gain is exposed only because phase/amplitude tests exist; production gain stays **0**.

---

## Named states

| State | Array | After C3T |
|---|---|---|
| equilibrium | `temperature_equilibrium_c` | Lapse from climate; DEM delta applied once in final |
| pre-SST base | `temperature_base_c` | Inertia (+ optional gain); DEM delta applied; **not** SST-coupled |
| SST-coupled / final published | `temperature_c` | SST writeback once; diagnostics recomputed from this array |

Monsoon still reads `temperature_base_c`, so it no longer sees a stale pre-DEM field after final recalculation. Moisture/ecology use published `temperature_c` (stamped `temperature_final_c` after SST).

`lapse_apply_count` is 1 at base climate and 2 after DEM correction. `sst_apply_count` is 1 after ocean writeback. Diagnostics `temperature_min_c` / `annual_mean_c` / seasonal flags always match the named source array.

---

## Optional continental seasonality (not a default retune)

```text
T' = annual_mean + (T - annual_mean) × (1 + continentality × gain)
```

Per-cell annual mean is preserved. Peak month is unchanged. `gain=0` is a no-op.

Sweep on a 24×48 fixture, `base_temp_c=25`, lapse 6.5 (inland = continentality > 0.25):

| `continentality_scale_km` | gain | inland seasonal amp °C | annual mean °C | applied |
|---|---:|---:|---:|:---:|
| 300 | 0 | 9.30 | 15.82 | no |
| 300 | 0.25 | 11.59 | 15.82 | yes |
| 300 | 0.50 | 13.89 | 15.82 | yes |
| 500 | 0 | 9.30 | 15.82 | no |
| 500 | 0.25 | 11.55 | 15.82 | yes |
| 500 | 0.50 | 13.79 | 15.82 | yes |
| 800 | 0 | 9.29 | 15.82 | no |
| 800 | 0.25 | 11.47 | 15.82 | yes |
| 800 | 0.50 | 13.64 | 15.82 | yes |

**Decision:** do **not** raise production `continental_seasonality_gain` above 0.

---

## Acceptance

| Criterion | Result |
|---|---|
| DEM correction updates every DEM-dependent named state once | PASS |
| SST diagnostics recomputed from the coupled array | PASS |
| Shared diagnostics match direct numpy on the named array | PASS |
| Mirrored fixture N–S symmetric in annual mean; seasonal inversion | PASS |
| Gain raises inland amplitude; annual mean unchanged; phase unchanged | PASS |
| No `base_temp_c` / lapse / SST / folding retune | PASS |
| `pytest -m "not slow"` | PASS — 331 passed, 3 deselected |

Atlas seed `183716` was **not** regenerated.

---

## Explicitly not done

- Raising `continental_seasonality_gain` in production YAML
- Conservative moisture transport / Atlas spin-up (**C4**)
- Precipitation / monsoon retune (**C5**)
- Atlas `183716` regen

**Decision:** accept C3T; stop. Next when instructed: **C4** only.
