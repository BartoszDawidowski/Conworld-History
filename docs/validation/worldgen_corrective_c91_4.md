# Worldgen corrective C9.1.4 — BiomeV2 NON_GROWING and true wetland

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no `precip_scale_mm` retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.4  
**Closes:** P-91-05, P-91-06  
**Depends on:** C9.1.2 (flooding / water-fraction products)  
**Audited commit before this package:** post-C9.1.3 working tree

---

## Delivered

| Item | Location |
|---|---|
| Class raster no longer seeded with Growing–Moist | `ecology/biome_v2.py` default `FROST_SEASONAL` |
| `ThermalRegime.NON_GROWING` and `growing_season_months == 0` never Growing–Moist/Deficit | classifier + `biome_v2_acceptance` |
| Saturated soil = **wetland potential** (moisture axis), not map class 6 | `wetland_potential` raster + diagnostics |
| Map **Wetland** requires inundation, low slope, and river/lake neighbourhood | `classify_biome_v2` predicate |
| Arid / frost / ice cannot be overwritten by root-zone saturation | thermal/arid gates on wetland |
| Legend label matches the raster: “Wetland”, not “Wetland potential” | `BIOME_V2_DISPLAY_CLASSES[6]` |
| Holdridge annual classifier untouched | `ecology/holdridge.py` |
| Tests | `tests/test_worldgen_corrective_c91_4.py` |

### Wetland map predicate (this note)

A land cell is class `WETLAND` only if all of:

1. inundation: `water_fraction ≥ 0.10` (or monthly max) **or** liquid lake mask;
2. low slope: `slope ≤ 0.02` (metric rise/run from climate-grid elevation);
3. 8-neighbour (E–W wrap) of a lake or display river cell;
4. `growing_season_months ≥ 3`;
5. not ice, not arid, not frost-seasonal, not NON_GROWING.

Without hydrology inundation/slope/neighbourhood inputs the map class is empty. Saturated store still sets moisture `WET` (`wetland_potential`).

---

## Acceptance

| Criterion | Result |
|---|---|
| Growing–Moist ∩ (zero growing months) = 0 | PASS |
| Saturated soil alone is not ~36% wetland | PASS (potential vs map class split) |
| True wetland needs inundation + flat + water neighbour | PASS |
| Legend “Wetland” matches class 6 | PASS |
| No `precip_scale_mm` retune | PASS |
| Focused suite | PASS — 41 passed (C9.1.4 + C6/C9/CR-9/ecology/C0) |

Atlas seed `183716` was **not** regenerated. Production Growing–Moist-on-ice and 35.7% wetland are leftover until regen.

---

## Explicitly not done

- Plateau interior vs rim / range split (**C9.1.5**)
- Canonical world `acceptance_ok` aggregator (**C9.1.6**)
- Holdridge / precip retune
- Atlas `183716` regeneration

**Decision:** accept C9.1.4; stop. Next: **C9.1.5** only. **C10 remains blocked.**
