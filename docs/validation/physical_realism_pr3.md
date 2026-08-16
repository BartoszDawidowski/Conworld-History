# Physical Realism PR-3 — temperature periodic response + physical scales

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §9 / §15 PR-3  
**Depends on:** PR-0, PR-1, PR-2  
**Defaults:** `base_temp_c` **not retuned** (still Atlas-era 25 °C in packaged config)

---

## Delivered

| Item | Location |
|---|---|
| Periodic first-order thermal reservoir + spin-up closure | `physical/climate/temperature.py` |
| Named states: equilibrium / base / SST-coupled / final | climate + ocean + final diagnostics |
| Continentality in km via `GridMetrics` | `continentality_factor` + climate pipeline |
| SST inland decay in km (Atlas cells → km, applied on live grid) | `physical/ocean/sst.py` + `OceanParams` |
| Boundary-current width in km | `physical/ocean/currents.py` |
| Metric SST advective gradients | `build_monthly_sst(..., metrics=)` |
| Subgrid elev stats contract (p10/p90/ridge/RMS slope) | `downsample_elevation_subgrid_stats` — **not** applied to T |
| Length resolution in `to_ocean_params()` / climate build | `config.py`, `pipeline.py` |
| Tests | `tests/test_physical_realism_pr3.py` |

Compatibility: legacy `inland_decay_cells=60` converts via Atlas climate mid-lat EW (~**4691 km**). That physical length is then used on Atlas **and** Full so reach is profile-independent in km (cell count scales with resolution).

---

## Acceptance

| Criterion | Result |
|---|---|
| Ocean amplitude &lt; land; ocean seasonal max lags forcing | PASS |
| N–S annual symmetry on symmetric all-ocean world | PASS |
| NH/SH seasonal phases opposite | PASS |
| Lapse cools high land (lat/continentality controlled fixtures) | PASS |
| SST inland influence falls with physical km | PASS |
| Same km → cell-count ratio matches climate resolution ratio (Atlas vs Full) | PASS |
| Provenance: one climate equilibrium lapse; DEM delta counted; SST apply once in final | PASS (diagnostics `lapse_apply_count`, `sst_apply_count`) |
| `base_temp_c` untouched | PASS |

---

## Provenance (temperature owners)

1. **`temperature_equilibrium_c`** — insolation + lat + lapse + ocean bias (`climate_equilibrium`)  
2. **`temperature_base_c`** — after periodic inertia (`periodic_first_order_v1`)  
3. **DEM Δ lapse** (final only) — `lapse_from_dem_v2` / `final_dem_delta`  
4. **`temperature_sst_coupled_c`** — ocean SST + inland km decay (`ocean_coupling`)  
5. **`temperature_final_c`** — climate after single SST writeback (moisture / ecology)

Subgrid relief fields are persisted on `ClimateResult` but `subgrid_applied_to_temperature: false`.

---

## Explicitly not done

- Retuning `base_temp_c` / seasonal taus after hypsometry v2  
- Using subgrid ridge/RMS slope inside temperature or moisture  
- PR-4 moisture correctness (v-sign, budget, spin-up)  

**Decision:** accept PR-3; stop. Next when instructed: **PR-4**.
