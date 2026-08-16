# Milestone B7 — Precip-aware rivers & lakes

**Date:** 2026-08-16  
**Plan:** `docs/ATLAS_PLAN_B.md` §6.3 / B7  
**Status:** ✅ Complete

## Scope

DEM topology unchanged (D8 / accumulation / fill). River and lake **visibility** gated by catchment discharge / local precip so Atlas does not draw arid desert stream webs or dry playas.

## Delivered

| Piece | Where |
|---|---|
| River gate | `gate_river_mask_by_discharge` — DEM acc candidates ∩ (Q ≥ **candidate** quantile) + D8 downstream inherit |
| Lake gate | Rain-fed (local precip ≥ land p70) **or** river-touch + not arid (p45); drop mean T < 1°C; no bare catchment-Q playas |
| Params / YAML | `HydrologyParams` + `hydrology.*`; `PlanetConfig.to_hydrology_params()`; climate T into `build_hydrology` |
| Diagnostics | before/after counts; `lake_dropped_cold` / `lake_dropped_arid` / kept rain|river |
| Presentation | Godot `river_width_for_feature` — stroke ∝ `log(1+discharge)` blended with Strahler |

**Default thresholds (2026-08-16 retune #2):** rivers `candidate_quantile=0.50`; lakes `precip=0.70`, `arid=0.45`, `min_mean_temp_c=1.0`. Earlier land-Q inflow let desert terminal basins through; polar fill lakes lacked a freeze gate.

## Acceptance

| Criterion | Result |
|---|---|
| Dry headwaters without wet upstream Q drop | Met (`test_gate_river_drops_arid_headwater_keeps_wet_corridor`) |
| Wet highland → arid corridor remains | Met (catchment Q + downstream walk) |
| Arid closed depressions without precip/inflow not lakes | Met (`test_gate_lakes_drops_arid_closed_basin`) |
| Vectorize / fluvial still consume gated masks | Met (same `river_mask` / `lake_mask` SoT) |
| Optional stroke ∝ discharge | Shipped (Godot blend) |

## Stop

B7 complete. Next when instructed: **B8** (moisture v2).

## Follow-ups

Shipped 2026-08-16 — see **`docs/validation/hydro_flow_and_transmission.md`**:

- Flow directions as a **layer checkbox** (not a map mode).
- Channel **transmission losses** so Nil-like rivers survive arid corridors while wadis die.
- **Distant-fed lakes stay**; atmospheric lake/river evap remains separate (moisture #2 only).
