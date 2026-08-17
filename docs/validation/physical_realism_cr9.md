# Physical Realism CR-9 — erosion, landforms, BiomeV2

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-9  
**Defects closed:** **F-21** (metric slope + diffusion; micro-depression fill after fluvial).  
**Partial:** **F-13** (score formula + threshold 0.60 + `calibrated` is a real knob check; Atlas 53.7% leftover until regen); **F-11** remainder (`cell_scale_m=1000` gone; orography still raw Δz).

---

## Delivered

| Item | Location |
|---|---|
| Metric slope (`GridMetrics.metric_slope`); 1 km-referenced metric Laplacian | `erosion/pass_one.py` |
| Fill land pits shallower than 25 m after fluvial | `condition_micro_depressions`; `fluvial.py` |
| Mountain score retune; production threshold **0.60** | `landforms/classify.py`, YAML |
| `calibrated` ⇔ threshold in [0.58, 0.65] and km² floors set | `params_are_calibrated` |
| Drop 1–3 cell specks (`min_component_cells=4`) | `landforms/objects.py` |
| Cell-edge contours + ridge centerlines | `mountain_ranges.geojson`, `mountain_ridges.geojson` |
| Seasonal BiomeV2 (frost / growing season / water deficit / soil state) | `ecology/biome_v2.py`; Holdridge stays annual |
| Tests | `tests/test_physical_realism_cr9.py` |

Algorithm stamps: `landform_v2_cr9`, `metric_gridmetrics_v1`, `biome_v2_seasonal_cr9`.

Not retuned: `orographic_frac`, `ocean_evap_rate`, `folding_ratio`, SST, `lake_min_depth_m`.

---

## Acceptance

| Criterion | Result |
|---|---|
| Slope is metric rise/run (not Δz/1000 m) | PASS |
| Shallow pit fills; 40 m pit kept | PASS |
| `LandformParams()` calibrated; threshold 0.42 / disabled / no km² not calibrated | PASS |
| Hilly noise: mountain land fraction < 0.25 at 0.60 | PASS |
| Plateau + escarpment; isolated cone still a range | PASS |
| BiomeV2 frost months / deficit / ocean class; Holdridge annual | PASS |
| `pytest -m "not slow"` | PASS — 280 passed, 3 deselected |
| Atlas 183716 mountain fraction / pit count | **Leftover** — not regenerated |

Expected production effect after regen: fewer cells scoring as mountain at 0.60; fluvial no longer restoring hundreds of shallow pits; ecology writes `biome_v2.npz` beside Holdridge.

---

## Explicitly not done

- Atlas / Quick seed regen (F-13 fraction, F-21 pit count, F-03 spin-up)  
- Orography as metric slope in moisture (`orographic_lift` still cell Δz)  
- Godot landform map mode  
- Atlas cell ≈ 970 km² so 800 km² floor is still a few cells  
- Precipitation / folding / SST calibration  
- Full memory rewrite (**F-14**)

**Decision:** accept CR-9; stop. CR track **CR-0…CR-9** is complete. Next when instructed: optional atlas **B10** only.
