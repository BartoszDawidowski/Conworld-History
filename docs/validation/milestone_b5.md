# Milestone B5 — Climate / coupling / moisture knobs (expose only)

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md` §6 / §6.2 / B5  
**Status:** ✅ Complete (+ user default retune + inland-water moisture)

## Scope

Expose existing engine constants via YAML + Advanced UI. Defaults later retuned from Atlas experiments.

## Delivered

| Knob group | Config keys | UI |
|---|---|---|
| Coupling (B1) | `ocean.sst_mix`, `inland_decay_cells`, `western_warm_c`, `eastern_cool_c` | Advanced spins + tooltips |
| Hypsometry / tectonics | `tectonics.folding_ratio`, `sea_level`, `erosion_period`; `terrain.land_scale_m`, `ocean_scale_m`, `orogeny_boost`, `activity_relief`, `boundary_relief` | Advanced (B5 patch) |
| Ecology / Holdridge | `ecology.precip_scale_mm` | Advanced |
| Climate mean | `climate.base_temp_c` | Advanced |
| Moisture inland (§6.2) | `moisture.advect_steps`, … | Advanced spins + tooltips |
| Inland water moisture | `moisture.lake_evap_rate`, `river_evap_rate` | YAML (post-hydrology rebuild in final) |
| Wiring | `to_ocean_params` / `to_moisture_params` / `to_pyplatec_params` / `to_ecology_params` + `base_temp_c` → climate | |

**Atlas climate defaults (2026-08-15 retune):** `base_temp_c=25`, `sst_mix=0.4`, `inland_decay=60`, west/east SST `2.2`/`1.8`, moisture `advect_steps=32`, `advect_wind=0.2`, `rainout=0.15`, `orographic=0.85`, `convective=2.0`, `ocean_evap=1.4`, `land_et=0.4`, `cont_dry=0.4`, `lee_dry=0.12`, `precip_scale_mm=200` (unchanged). Geography defaults unchanged from prior Atlas tectonics retune.

**Inland water:** After hydrology, final recalculation rebuilds moisture with downsampled `lake_mask` / `river_mask` so large lakes and rivers contribute evaporation (weaker than ocean). Ecology / Holdridge use this second pass.

## Acceptance

| Criterion | Result |
|---|---|
| Config overrides reach moisture/ocean | Met (`to_*_params`, final recalc) |
| Advect/rainout knobs change inland precip directionally | Met (`test_moisture_advect_knob_moves_precip_inland`) |
| Lakes/rivers raise local humidity/precip | Met (`test_inland_lake_increases_humidity_and_precip`) |
| Packaged defaults match Atlas retune | Met (YAML + Godot SpinBox) |

## Stop

B5 complete. Next when instructed: **B6+** (see Plan B); B6 stroke smoothing is done — see `milestone_b6.md`.
