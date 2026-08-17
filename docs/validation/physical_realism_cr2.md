# Physical Realism CR-2 — GridMetrics / subgrid / km leftovers

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-2  
**Defects closed:** **F-10** (subgrid transpose); **F-11** partial (monsoon/plume reaches in km); **F-06** partial (explicit SST decay km, not 4691 cell accident); NS gradient span bug; landform land-only downsample (F-13 mask hygiene)

---

## Delivered

| Item | Location |
|---|---|
| Subgrid block `transpose(0,2,1,3)` before flatten | `physical/climate/pipeline.py` `downsample_elevation_subgrid_stats` |
| Land-only DEM downsample for landforms | `downsample_land_elevation_mean` → landforms pipeline |
| NS central difference uses full `ns[j-1]+ns[j]` span | `spatial/metrics.py` `metric_gradients` |
| Default `sst_inland_decay_km: 1200` (explicit) | `configs/default_planet.yaml` |
| `continentality_scale_km: 500`, `western_boundary_width_km: 250` | same |
| `monsoon_coast_reach_km` / `plume_mix_reach_km` → cells via GridMetrics | `moisture/pipeline.py` |
| Godot inland decay spin in **km** (default 1200) | `Main.tscn` / `Main.gd` |
| Tests | `tests/test_physical_realism_cr2.py` |

---

## Acceptance

| Criterion | Result |
|---|---|
| Synthetic fine spike → ridge argmax in correct coarse cell | PASS |
| Fixed km plume steps scale Atlas→Full (~2×) | PASS |
| Explicit SST km source=`km`, value 1200 | PASS |
| Metric NS unit slope ≈ 1 | PASS |
| Land-only downsample avoids bathymetry mix | PASS |
| `pytest -m "not slow"` | PASS — 231 passed |

---

## Leftovers (not CR-2)

| Item | Next |
|---|---|
| `advect_steps` still a numerical substep count (not length) | Documented; physical transport length scaling → later if needed |
| Hydro thresholds still partly cell/quantile based | **CR-4** |
| SST still blends toward **absolute** nearest SST | **CR-3** (F-05); 1200 km is interim only |
| Monsoon regime still wrong | **CR-3** (F-07); keep strength modest / off until then |
| Landform threshold calibration | **CR-5** / 9E — accepted (`physical_realism_cr5.md`) |

**Decision:** accept CR-2; stop. Next when instructed: **CR-3** only.
