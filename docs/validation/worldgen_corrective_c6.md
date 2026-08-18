# Worldgen corrective C6 — BiomeV2 correctness and canonical integration

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **Holdridge annual view unchanged**; precip YAML / folding / landform defaults not retuned)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §5.3 + §6 C6  
**Depends on:** C0 (precip units) and C5 (spun-up monthly `land_store`)  
**Audited commit before this package:** post-C5 working tree

---

## Delivered

| Item | Location |
|---|---|
| Growing-season mean soil wetness (`soil_moisture_growing_mean`) | `classify_biome_v2` / `soil_moisture_growing_mean` |
| Independent `thermal_regime_id` / `moisture_regime_id` before display class | `biome_v2.py` |
| Wetland from climatological saturation, not December snapshot | wetland rule uses growing-season mean |
| Ecology ignores 2-D last-month `hydrology.soil_store` | `climatological_soil_monthly` |
| Periodic monthly soil from moisture `land_store` (fallback: hydro `soil_store_monthly`) | ecology + runoff |
| Holdridge/soil lake override from `water_fraction_mean`, not basin envelope | `climate_liquid_lake_mask` |
| Ecology `acceptance_ok` includes BiomeV2 coverage / finite / legend / water-mask | `biome_v2_acceptance` |
| RasterStore layers listed in addendum §6 C6 | `_fill_rasters` |
| Hex aggregates + query + save/load | `HexAnalysisResult`, `queries` |
| Tests | `tests/test_worldgen_corrective_c6.py` |

Algorithm stamp: `biome_v2_climatology_c6`. Statistic name: `soil_moisture_growing_mean`. Holdridge role remains `annual_diagnostic`.

C0 unit contract is unchanged: `precip_mm_m = precip * precip_scale_mm` (no `/ n_m`).

---

## Operators

### Climatological soil

BiomeV2 no longer reads a single December `soil_store` from a one-year zero-initialized hydrology bucket. Preferred input is the spun-up monthly moisture `land_store` (capacity-normalised). Hydrology now also records `soil_store_monthly` (`[months, y, x]`) while keeping 2-D `soil_store` as the last month for CR-7 compatibility. A 2-D last-month field is **not** used as climatology.

Growing-season mean averages monthly wetness where `T > 5 °C`; cells with no growing month use the annual mean. Soil state / wetland use that named statistic.

### Axes then display class

Thermal (`ocean`, `ice`, `frost_seasonal`, `growing`, `non_growing`) and moisture (`ocean`, `arid`, `deficit`, `moist`, `wet`) are persisted first. The seven-class map is derived from them so seasonal frost on arid land remains inspectable (`thermal_regime_id`) even when the display class is `frost_seasonal`.

Wetland requires moisture `wet` (growing-season soil ≥ 0.80), ≥ 3 growing months, and not perennial ice.

### Lakes

Holdridge lake override and soil lake wetting use downsampled `water_fraction_mean ≥ 0.05`, not `basin_envelope_id` and not a mode-downsampled envelope mask.

---

## Canonical products

RasterStore:

```
ecology/biome_v2_class
ecology/frost_months
ecology/growing_season_months
ecology/water_deficit_mm
ecology/soil_state
ecology/thermal_regime_id
ecology/moisture_regime_id
```

Hex:

```
biome_v2_dominant
frost_months_mean
growing_season_months_mean
water_deficit_mm_mean
soil_state_dominant
```

Queries expose the hex fields and, when present, `ecology/biome_v2_class` at a point. Round-trip save/load is covered by `test_world_spatial_model.py`.

---

## Acceptance

| Criterion | Result |
|---|---|
| Balanced monthly P/PET → deficit 0 | PASS |
| Rotating month labels rotates monthly deficit; annual frost / growing / deficit / class unchanged | PASS |
| Wet December only ≠ wetland; wet growing-season climatology = wetland | PASS |
| Lake override = liquid fraction, not basin envelope | PASS |
| Holdridge annual view unchanged under month rotation | PASS |
| RasterStore keys + hex aggregates + query + save/load | PASS |
| `pytest -m "not slow"` | PASS — 356 passed, 3 deselected |
| Atlas `183716` | **Leftover** — not regenerated |

---

## Explicitly not done

- Retuning precip YAML, `folding_ratio`, Holdridge bins, or landform thresholds
- Godot BiomeV2 map mode / legend (**C9**)
- Landform scale/class/object repairs (**C7**)
- WorldSpatialModel landform product expansion (**C8**)
- Atlas `183716` regen

**Decision:** accept C6 BiomeV2 climatology and canonical wiring; stop. Next when instructed: **C7** only.
