# Physical Realism Corrections — post–PR-9 production hardening

> **Status:** **CR-0–CR-9** baseline implemented — **correction required** ([`WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md)). Hypsometry stays accepted.  
> **Authority:** This document amends production acceptance of PR-0…PR-9 foundation where fixed-seed audit contradicts milestone notes. The addendum takes precedence where CR-6…CR-9 production gates still fail.  
> **Normative design:** [`WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) remains primary for algorithms; where annex acceptance was marked done but production fails, **this corrections track + addendum** take precedence until closed.  
> **Tracker:** [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md).  
> **Rule:** One **CR-N** / **C-N** milestone at a time. Validate → stop.  
> **Do not** retune precipitation, `folding_ratio`, SST, or `lake_min_depth_m` to hide the defects below.  
> **Next when instructed:** **PC1** (PC0 delivered; **C10 blocked**). Plan: [`00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md).

---

## 0. Purpose

PR-0…PR-9 delivered scaffolding, fixtures, and several correctness gates. A fixed-seed Quick comparison (seeds **1, 42, 100**) against the pre–realism baseline shows that **production generations still fail annex physical intent** in moisture closure, SST–land coupling, monsoon seasonality, endorheism, landform quality, subgrid stats, and resolution-invariant scales.

This document:

1. records the audit snapshot and why visuals understate the change;
2. registers defects with **code/comment anchors** (not only symptoms);
3. freezes **interim safe defaults** (compensate nothing);
4. sequences **CR-0…CR-5** (foundation repair) then **CR-6…CR-9** (production Atlas 183716).

Atlas presentation (**B10**) remains independent and must not block CR work.

---

## 1. Audit snapshot (Quick, seeds 1 / 42 / 100)

Relative to the earlier baseline commit (pre–PR-0…PR-9 production physics):

| Indicator | Observed change |
|---|---|
| Land/ocean cells flipped | 1.6–2.2% |
| Mean land temperature | −0.82 to −1.54 °C |
| Land seasonal temperature amplitude | +0.85 to +0.93 °C |
| Land precip feeding hydrology | **29–31%** of baseline |
| Monthly Q vs annual Q divergence | **80–91%** |
| Holdridge class agreement on land | 49–65% |
| River location Jaccard | 0.16–0.33 |
| Endorheic lakes | **0** on all three seeds |
| Detected plateaus (Quick) | **0** on all three seeds |

Seed **42** ecology precip proxy: **5.48 → 1.82** (−67%). Spatial correlation of precip maps ≈ **0.47**.

All three seeds: `spinup_converged=False` with default `spinup_max_years=4`; seed 42 needed ~**16–20** years. Spin-up watches **`q` only**, not the land water store. Moisture / stage `acceptance_ok` can still be **True**.

Monsoon anomaly was **offshore in every month** (Quick and Atlas): contrast uses hemispheric means of land T already softened by SST.

Atlas seed 42: SST coupling step warmed land by ≈ **+4.25 °C** mean; legacy `inland_decay_cells=60` → ≈ **4691 km** mid-lat EW (see PR-1 note) — continent-scale.

LandformAnalysis Atlas seed 42: ~**45–52%** of land scored as mountain ranges; plateaus nearly absent; DEM averaging mixed coasts with bathymetry (~**4682** mis-masked cells in one Atlas run). `acceptance_ok=True` is hard-coded.

---

## 2. Why the map “doesn’t look that different”

Repo comments and defaults explain the camouflage:

| Mechanism | Evidence |
|---|---|
| Hypsometry stretched per seed | `power_tail_v2` is on (CR-5); atlas climate DEM + p98 colour stretch still hide the numeric change |
| River mask is quantile/fraction gated | Plan B7 UX keeps a similar blue-line density even when physical Q falls to ~20–30%. |
| PR-7/PR-8 knobs dropped in final moisture rebuild | **Fixed CR-1** — was `physical/final/pipeline.py` partial `MoistureParams` |
| Landforms unused in Godot / history | PR-9E + Godot display deferred (`physical_realism_pr9.md`). |
| Precip palette / stretch | Annex §16.4: min–max images hide absolute scale collapse. |

**Implication:** visual review alone is invalid acceptance (annex §16.1). Prefer absolute maps + diagnostics JSON.

---

## 3. Defect register

IDs are binding for CR milestones. Severity: **P0** blocks physical acceptance; **P1** blocks calibration; **P2** product/perf.

| ID | Sev | Symptom | Code / comment anchor |
|---|---|---|---|
| **F-01** | P0 | ~~CI / harness expectations drift; stale PR-0 probes; Windows `vendor\vendor` path~~ | **Closed CR-0** — see `docs/validation/physical_realism_cr0.md` |
| **F-02** | P0 | ~~Final pass ignores YAML PR-7/PR-8 moisture knobs~~ | **Closed CR-1** — full `MoistureParams` through final |
| **F-03** | P0 | Spin-up fails in production; ~~`acceptance_ok` ignores convergence~~ | **Partial CR-8** — lee not a mass sink; CFL advection; hydro↔evap loop. Atlas 183716 `spinup_converged` not re-measured (regen leftover) |
| **F-04** | P0 | ~~Land store not in spin-up / closure gate~~ | **Closed CR-3** — joint q+store closure |
| **F-05** | P0 | ~~SST couples land toward absolute nearest SST~~ | **Closed CR-3** — `anomaly_zonal_v1` |
| **F-06** | P0 | Inland decay ≈ whole continents | **Closed CR-2/CR-3** — km default + anomaly mix 0.28 |
| **F-07** | P0 | Monsoon always offshore / non-seasonal | **Partial CR-8** — `monsoon_anomaly_gate_v1` (anomalies vs own means, sea-level T, 500 km mean, sign gate). Atlas year-round offshore leftover until regen |
| **F-08** | P0 | Endorheic / playa / frozen never appear → over-kept as liquid | **Closed CR-6** for liquid mask (playa/ice not product water); states still recorded |
| **F-09** | P0 | ~~Monthly vs annual Q incoherent~~ | **Closed CR-6** — monthly PET × days/365; independent-annual rel_ind gated `< 0.35` |
| **F-10** | P1 | ~~Subgrid elev/slope percentiles wrong columns~~ | **Closed CR-2** |
| **F-11** | P1 | Physics still resolution-dependent | Leftovers: orography raw Δz not slope; Atlas `river_min_catchment_km2` still 1 cell (**F-17**). **`advect_steps` = CFL cap (CR-8)**; **erosion metric slope (CR-9)** |
| **F-12** | P1 | ~~`hypsometry_tail_softness` reserved no-op~~ | **Closed CR-5** — `power_tail_v2_curve(..., tail_softness)`; `s=1` is PR-2 identity |
| **F-13** | P1 | Landforms uncalibrated | **Partial CR-9** — `landform_v2_cr9`, threshold 0.60, `calibrated` is a knob check, min 4-cell objects. Atlas 183716 53.7% leftover until regen |
| **F-14** | P2 | Full memory / dual work | Atlas ~94 s OK; Full monthly cubes ≥6 GiB, likely 7.5–9 GiB with graph. Stream months, float32, cache topology, one final hydro pass |
| **F-15** | P0 | ~~Fill-envelope treated as water surface~~ | **Closed CR-6** — product `lake_mask` = open + watered endorheic |
| **F-16** | P0 | ~~`closed_basin` ignores land outlet~~ | **Closed CR-6** — closed requires `not has_land_outlet` |
| **F-17** | P1 | `river_acc_fraction` vs 500 km² floor | **Partial CR-7** — quantile after km²; Atlas/Quick cell ≫ 500 km² so floor is 1 cell and 0.035 still dominates visuals |
| **F-18** | P0 | Fake lakes humidify ecology; hydro not rebuilt | **Closed CR-8** — playa/ice out of evap (CR-6); one damped hydro rebuild from inland-water moisture. Atlas regen leftover |
| **F-19** | P1 | ~~Godot YAML omits `continentality_scale_km`~~ | **Closed CR-6** — `Main.gd` writes 500 km + hydrology block |
| **F-20** | P2 | ~~Star-shaped lake polygons~~ | **Closed CR-6** — cell-edge union outline |
| **F-21** | P1 | Fluvial pass recreates pits; slope uses 1000 m cells | **Closed CR-9** — `GridMetrics.metric_slope` + metric Laplacian; `condition_micro_depressions` after fluvial. Atlas pit count leftover until regen |

### Reopened conflict-register items

| Prior claim | Correction |
|---|---|
| C-06 / C-07 “Done (PR-5/PR-6)” endorheic semantics | **Partial CR-4.** States exist; over-kept dry playas as liquid (**F-15/F-16 / CR-6**). |
| PR-4 / PR-7 moisture “accepted” | **Partial CR-8.** Lee is a condensation brake; CFL advection. Atlas spin-up leftover (**F-03**). Do not calibrate precip until Atlas regen. |
| PR-8 monsoon “accepted” | **Partial CR-8 / F-07.** Anomaly + sign gate + `temperature_base_c`. Atlas year-round offshore leftover until regen. |
| PR-3 km scales “accepted” | Godot omits `continentality_scale_km` (**F-19 / CR-6**). |
| PR-9 / CR-5 landforms accepted | Hypsometry stays; landform score **CR-9** (Atlas fraction leftover). |
| CR-4 F-09 “monthly Q coherent” | Identity by construction hid PET×12 (**F-09 / CR-6**). |

---

## 4. Frozen knobs until CR-6+ (do not compensate)

Do **not** retune precipitation, `folding_ratio`, SST, lapse, `base_temp_c`, ocean evaporation, sea level, or `lake_min_depth_m` to hide lakes. `lake_min_depth_m=25` still left ~7.9% land as water on 183716.

| Knob | Until CR-6 code | After CR-6 (calibration, not this milestone) |
|---|---|---|
| `tectonics.folding_ratio` | **`0.01` freeze** | freeze |
| `climate.base_temp_c` / lapse / SST | freeze | freeze |
| `moisture.ocean_evap_rate` | freeze `1.4` | freeze (not retuned in CR-8) |
| `moisture.orographic_frac` | freeze `0.85` — **do not calibrate precip** | still freeze; CR-8 did **not** trial 0.35 / 0.50 / 0.65 |
| `moisture.lee_dry` | production **0.12** as condensation brake (CR-8) | keep 0.12 |
| `moisture.monsoon_strength` | **0.35** with sign-change gate (CR-8) | keep 0.35 |
| `moisture.lake_evap_rate` | **`0.0` until playa/ice split** | restore after CR-6 liquid mask |
| `hydrology.transmission_rate` | diagnostic `0.04` ≈ missing /12; `0.0` control | after PET fix: 0.15 / 0.30 / 0.45 |
| `hydrology.river_acc_fraction` | diagnostic **0.035** (sweep 0.02 / 0.035 / 0.05) | CR-6/7 candidate policy |
| `hydrology.river_discharge_candidate_quantile` | keep **0.50** | keep |
| `climate.continentality_scale_km` | **500** (Godot must write it) | keep |
| `terrain.hypsometry_mode` | keep `power_tail_v2` / anchor 3000 / exp 1.5 | keep |
| `landforms.mountain_score_threshold` | **0.60** (CR-9 score retune) | keep 0.60 |

River cosmetics densify blue lines but **are not** a PET or lake-geometry fix.

---

## 5. Correction milestones (normative order)

```text
CR-0 … CR-5   Foundation repair (notes stand; several defects reopened)
  → CR-6  Hydrology hotfix  BASELINE — CORRECTION REQUIRED (C0–C2)
  → CR-7  Light hydrology v2  BASELINE — CORRECTION REQUIRED (C1–C2)
  → CR-8  Atmosphere  BASELINE — CORRECTION REQUIRED (C4)
  → CR-9  Erosion / landforms / BiomeV2  BASELINE — CORRECTION REQUIRED (C3/C6/C7)
  → C0    Product-contract hotfixes  ✅
  → C1    Lake geometry from storage  ✅
  → C2    Rivers, channel losses, bounded coupling ✅
  → C3    Metric erosion recalibration ✅ (defaults not retuned)
  → C3T   Temperature-state integrity ✅ (gain default 0)
  → C4    Conservative moisture transport ✅ (Atlas spin-up leftover)
  → C5    Precipitation / monsoon ✅ (YAML knobs not retuned)
  → C6    BiomeV2 ✅ (climatology + canonical rasters/hex)
  → C7    Landforms ✅ (scales / classes / objects; threshold 0.60)
  → C8    WorldSpatialModel / hex / query ✅
  → C9    Godot BiomeV2 / landform modes ✅
  → C9.1  Production closure (next: C9.1.1 lake routing)
  → C10   Multi-seed calibration / Full RSS **BLOCKED** until C9.1
```

**Hard gate:** do not calibrate precipitation until conservative transport (C4) is in place. Atlas seed `183716` spin-up is an honest leftover until regen.

**Parallel (optional):** B10 atlas Full land polys — presentation only. Does not fix F-15…F-21.

### CR-0 — CI and harness honesty ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr0.md`](validation/physical_realism_cr0.md) (2026-08-17).

**Intent:** green CI; tests assert corrected physics, not historical bugs.

- Keep PR-0 fixture probes aligned with PR-4+ (northward mass, capped precip, flat January).
- Fix packaging path resolution (`PkgRoot = parent of scripts`, not `vendor/vendor/pyplatec`).
- Document any remaining platform-only packaging failures separately from pytest.

**Acceptance:** all required CI jobs green on `main`; `pytest -m "not slow"` green locally. **Met.**

**Stop.** Next: **CR-1** only.

### CR-1 — Parameter propagation + acceptance honesty ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr1.md`](validation/physical_realism_cr1.md) (2026-08-17).

**Intent:** YAML / Godot knobs that exist must reach the final moisture build; diagnostics must not lie.

- Final pipeline: copy **full** `MoistureParams` (or pass `params.moisture` through) including PR-7/PR-8 fields on **both** moisture builds.
- Audit Godot → YAML → `PlanetConfig` → `MoistureParams` for dropped keys (`monsoon_lat_band_min`, coast reach, spin-up, diffusion, etc.).
- Gate `acceptance_ok` (moisture at minimum) on `spinup_converged` (and later land-store closure).
- Landforms: replace hardcoded `acceptance_ok: True` with real checks (or `False` / omitted until calibrated).

**Acceptance:** changing plume / ITCZ / monsoon / land_store in config changes final ecology moisture diagnostics; failed spin-up ⇒ not `acceptance_ok`. **Met.**

**Stop.** Next: **CR-2** only.

### CR-2 — GridMetrics / subgrid / resolution invariance ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr2.md`](validation/physical_realism_cr2.md) (2026-08-17).

**Intent:** same planet parameters ⇒ comparable physics across Quick / Atlas / Full (annex §16.3).

- Fix subgrid block layout: after `reshape(out_h, by, out_w, bx)` apply **`transpose(0, 2, 1, 3)`** before flattening to `(out_h, out_w, by*bx)`.
- Review `metric_gradients` / slope consumers if audit still flags gradient defects.
- Migrate remaining cell knobs that change physical reach with resolution, at least: monsoon coast reach, any fixed advect/plume **step counts** that encode distance, hydro thresholds documented as length/area.
- Prefer explicit `sst_inland_decay_km` in defaults over giant cell migration accidents; **do not** silently reinterpret old cell values as “correct km”.

**Acceptance:** synthetic subgrid fixture (known ridge in one fine cell) places p90/ridge/RMS in the correct coarse cell; length knobs documented in km; Quick vs Atlas large-scale precip/T patterns closer under identical km params. **Met** (advect_steps leftover noted).

**Stop.** Next: **CR-3** only.

### CR-3 — Moisture closure, SST anomaly, monsoon regime ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr3.md`](validation/physical_realism_cr3.md) (2026-08-17).

**Intent:** annex §10 P0 moisture + honest coastal coupling + seasonal transport-first monsoon.

1. **Spin-up / conservation** — joint `q` + land store; production `spinup_max_years=20`.
2. **SST** — anomaly vs zonal ocean mean; `sst_mix=0.28`, decay 1200 km.
3. **Monsoon** — local coastal land–SST contrast; pre-SST land T; strength 0.35.
4. Moisture trial band left as **post–CR-5 leftover** (not retuned without seed evidence).

**Acceptance:** met on fixtures + suite. **Reopened in production** by Atlas 183716 (F-03, F-07). Remainder → **CR-8** (accepted on fixtures; Atlas leftover).

### CR-4 — Monthly hydrology + typed outlets / endorheism ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr4.md`](validation/physical_realism_cr4.md) (2026-08-17).

**Intent:** annex §11 depression semantics and PR-6 production behaviour.

- Finite numerical fill (`fill_max_depth_m=25`); fill-all only for lake geometry.
- Outlet types: ocean / closed_basin / local_pit / broken_cycle / ns_edge.
- Closed basins kept as endorheic / playa / frozen (not dropped as arid).
- Canonical monthly effective Q; annual = sum. Sink on runoff, not raw precip.
- `monthly_gross` not stored by default (Full memory).

**Acceptance:** fixtures passed; **production identity hid PET×12 (F-09)** and over-kept dry closed basins (F-15/F-16). Remainder → **CR-6**.

### CR-5 — Joint calibration (hypsometry, climate, landforms) ⚠️ split

**Status:** Hypsometry **accepted** — [`docs/validation/physical_realism_cr5.md`](validation/physical_realism_cr5.md) (2026-08-17). Landforms + hydro-km² **reopened** (F-13, F-17) after Atlas 183716.

**Keep:** `power_tail_v2`, quantile 0.95, anchor 3000 m, body 1.5, `tail_softness=1.0`, `folding_ratio=0.01`.

**Reopened:** mountain score 53.7% of land ≥0.5; `river_min_catchment_km2` inert under `river_acc_fraction=0.02`. → **CR-9** / **CR-6**.

**Stop.** Next was **CR-6** only.

### CR-6 — Hydrology hotfix ✅

**Status:** BASELINE IMPLEMENTED — CORRECTION REQUIRED — [`docs/validation/physical_realism_cr6.md`](validation/physical_realism_cr6.md). Skipped Atlas 183716 is not production Accepted.

**Intent:** stop treating fill envelopes and dry playas as liquid water; stop applying annual PET twelve times; make Godot write packaged climate km.

- PET as `PET_annual × days_in_month / year_days` in `transmission_sink`; **real** monthly vs independent-annual Q check (not identity-by-construction).
- `closed_basin` requires no land outlet (`has_land_outlet` must fail closed); export `water_state`; render by state.
- Liquid water = open + watered endorheic only. Playa and ice **out of** liquid mask, lake evaporation, and Holdridge Lake override.
- Pass **water-area fraction** into the second moisture pass, not a binary mask of all depressions.
- Godot YAML: write `continentality_scale_km: 500` (and do not omit other packaged climate lengths).
- Lake polygons: raster contour / marching squares, not angular sort around centroid (F-20).
- Candidate rivers: `river_acc_fraction` must not nullify 500 km² (raise diagnostic 0.035 or derive from km²).

**Not in CR-6:** soil bucket, Q in m³/s, monsoon retune, orographic_frac sweep, landform score formula, BiomeV2, Full memory rewrite.

**Acceptance:** fixtures + suite. Atlas 183716 regen leftover. **Not production Accepted.** Remainder → addendum C0–C2.

**Stop.** Next was **CR-7** only. Reopened by addendum.

### CR-7 — Light hydrology v2 ✅

**Status:** BASELINE IMPLEMENTED — CORRECTION REQUIRED — [`docs/validation/physical_realism_cr7.md`](validation/physical_realism_cr7.md). Skipped Atlas 183716 is not production Accepted.

**Intent:** after CR-6, replace rain+melt-as-Q with a cheap basin/cell water cycle. No hydraulic solver, no groundwater.

- Shared monthly soil bucket for ET and runoff (`soil_bucket_v1`).
- Q in m³/s from cell area and month length (`mean_monthly_m3s`).
- Transmission losses per km of path (`path_length / transmission_ref_km`).
- Physical channel network (km² floor) then display quantile; perennial / seasonal / wadi states.
- Area–volume–level curve and 12 scalar balance steps per closed basin.

**Not in CR-7:** conservative advection / lee / monsoon / hydro↔evap iteration (**CR-8**, accepted). Landforms/erosion/BiomeV2 (CR-9); Full memory rewrite (F-14).

**Acceptance:** fixtures + suite. Atlas 183716 regen leftover. **Not production Accepted.** Remainder → addendum C1–C2.

**Stop.** Next was **CR-8** only. Reopened by addendum.

### CR-8 — Atmosphere (reopen CR-3 production) ✅

**Status:** BASELINE IMPLEMENTED — CORRECTION REQUIRED — [`docs/validation/physical_realism_cr8.md`](validation/physical_realism_cr8.md). Skipped Atlas 183716 is not production Accepted.

**Intent:** only after real liquid masks (CR-6). Do not calibrate precip before this.

- Conservative finite-volume advection with GridMetrics and adaptive CFL (`advect_steps` is the CFL cap).
- `lee_dry` inhibits condensation; must not destroy water (~24.6% of precip as sink on 183716).
- Monsoon from seasonal land/ocean anomalies vs their own annual means; sea-level or smoothed lowland T; 300–800 km regional mean; **gate off** when the sign does not flip.
- One damped hydrology↔evaporation iteration after real water masks.

**Acceptance:** fixtures + suite. Atlas 183716 `spinup_converged` leftover. **Not production Accepted.** Remainder → addendum C4.

**Stop.** Next was **CR-9** only. Reopened by addendum.

### CR-9 — Erosion, landforms, BiomeV2 ✅

**Status:** BASELINE IMPLEMENTED — CORRECTION REQUIRED — [`docs/validation/physical_realism_cr9.md`](validation/physical_realism_cr9.md). Skipped Atlas 183716 is not production Accepted.

**Intent:** after water is honest.

- Metric slopes and diffusion; micro-depression conditioning after fluvial (F-21).
- Recalibrate mountain / escarpment; contours and ridge centerlines; `calibrated` not a constant True.
- Holdridge remains an **annual diagnostic**. Add seasonal BiomeV2 (frost months, growing season, water deficit, soil state) on the climate grid.

**Acceptance:** fixtures + suite. Atlas 183716 mountain fraction / pit count leftover. **Not production Accepted.** Remainder → addendum C3 / C6 / C7.

**Stop.** CR baseline complete. Corrective track starts at **C0**.

### C0 — Product-contract hotfixes ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c0.md`](validation/worldgen_corrective_c0.md) (2026-08-17).

**Intent:** stop visibly false atlas water and BiomeV2 units; tests must fail for the demonstrated reasons; skipped Atlas cannot read as Accepted.

**Stop.** Next was **C1** only.

### C1 — Lake geometry from storage ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c1.md`](validation/worldgen_corrective_c1.md) (2026-08-17).

**Intent:** liquid area comes from monthly storage on a discrete A–V–h curve, not from the fill envelope. Open lakes are not auto-filled to spill.

**Stop.** Next was **C2** only.

### C2 — Rivers, channel losses, bounded coupling ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c2.md`](validation/worldgen_corrective_c2.md) (2026-08-17).

**Intent:** physical channel network from catchment + effective Q; display LOD after; PET-over-cell transmission replaced by flow-limited channel-bed loss; river state/catchment/Q/loss exported; fractional river evap; bounded moisture–hydrology coupling with Jaccard / ΔQ.

**Stop.** Next was **C3** only.

### C3 — Metric erosion recalibration and land-only coastal aggregation ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c3.md`](validation/worldgen_corrective_c3.md) (2026-08-17). Defaults **not** retuned.

**Intent:** keep metric slope/Laplacian; expose pass-1 `thermal_kappa` / `fluvial_k` separately from final `stream_power_k`; fail a corr-only no-op via a 1 m land-mean lower bound; never average bathymetry into climate-land elevation.

**Stop.** Next was **C3T** only.

### C3T — Temperature-state integrity and optional continental seasonality ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c3t.md`](validation/worldgen_corrective_c3t.md) (2026-08-17). `continental_seasonality_gain` default **0**.

**Intent:** DEM and SST corrections update the declared temperature states once; diagnostics are recomputed from the named array; monsoon reads DEM-corrected pre-SST base. Optional inland amplitude gain is tested, not retuned.

**Stop.** Next when instructed: **C4** only.

### C4 — Conservative atmospheric moisture transport ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c4.md`](validation/worldgen_corrective_c4.md) (2026-08-18). Face-flux CFL advection; production `spinup_max_years=48`; precip knobs **not** retuned. Atlas `183716` spin-up **leftover**.

**Intent:** Shared face-flux transport with fail-closed CFL, an accounted monthly budget, and field spin-up gates. Do not treat `advect_max_substeps` as physical reach.

**Stop.** Next when instructed: **C5** only.

### C5 — Precipitation mechanisms and regional monsoon ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c5.md`](validation/worldgen_corrective_c5.md) (2026-08-18). Metric smoothed orography, humidity stratiform, sector monsoon. Production precip YAML **not** retuned. Atlas `183716` leftover.

**Intent:** large-scale and orographic precipitation are both operational; lee is efficiency not a sink; monsoon gates by local seasonal contrast.

**Stop.** Next when instructed: **C6** only.

### C6 — BiomeV2 correctness and canonical integration ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c6.md`](validation/worldgen_corrective_c6.md) (2026-08-18). Growing-season soil climatology, inspectable thermal/moisture axes, liquid-fraction lake override, RasterStore/hex/query round-trip. Holdridge remains a separate annual view. Atlas `183716` leftover.

**Intent:** wetland and soil state are climatological, not a wet December from a one-year zero soil bucket; display class does not erase seasonal frost on the axes.

**Stop.** Next when instructed: **C7** only.

### C7 — Landform scales, classes, masks, and objects ✅

**Status:** Delivered — [`docs/validation/worldgen_corrective_c7.md`](validation/worldgen_corrective_c7.md) (2026-08-18). One-cell minimum radius, land-fraction coastal stats, mask reapply, geodesic ridges, plateau rims, local-form coverage. `mountain_score_threshold` **0.60** not retuned. Atlas `183716` leftover.

**Intent:** scales are honest about collapsing windows; escarpment is a rim/step not a continent paint; object geometry stays inside the mask.

**Stop.** Next when instructed: **C8** only.

---

## 6. Mapping prior PR track → corrections

| Foundation PR | Honest status after audit | Primary CR |
|---|---|---|
| PR-0 | Harness exists; must stay honest | CR-0 |
| PR-1 | Metrics base OK; cell leftovers + gradient/subgrid issues | CR-2 |
| PR-2 | Option present; **production default CR-5**; `tail_softness` real | CR-5 (F-12) |
| PR-3 | Seasonal filter good; SST form + subgrid bug | CR-2, CR-3 |
| PR-4 | Wind direction fixed; production closure/spin-up incomplete | CR-1, CR-3 |
| PR-5 | Strongest (~70–80%) | CR-4 (outlet typing) |
| PR-6 | Over-kept dry closed basins as liquid | CR-4, **CR-6** |
| PR-7 | Skeleton; ecology precip contaminated by fake lakes | CR-1, CR-3, **CR-6/CR-8** (F-18 closed) |
| PR-8 | Wired; monsoon still year-round offshore in production | CR-3, **CR-8** (F-07 partial; Atlas leftover) |
| PR-9 | Prototype; 9E thresholds uncalibrated on Atlas | CR-5 split, **CR-9** (Atlas leftover) |

---

## 7. Suggested human instructions

```text
Physical realism corrections: execute CR-0 only.
```

```text
Physical realism corrections: execute CR-1 only.
```

After C9:

```text
Worldgen corrective C9.1: execute C9.1.1 only.
```

Do **not** execute C10 until C9.1 roll-up is accepted.

---

## 8. Validation note contract

Each CR creates:

```text
docs/validation/physical_realism_crN.md
```

Required contents: code/config version; seeds/profiles; tests; defect IDs closed; absolute-metric deltas vs pre-CR baseline; explicit leftovers.

Fixed seeds: Quick **1, 42, 100**; Atlas **42, 183716**; one Full only after F-14 streaming. Check: moisture convergence + budget; permanent water vs playa vs ice fractions; river continuity/seasonality; Atlas–Full agreement; Godot/CLI config identity; time/memory.

---

## 9. Traceability

| Source | Role |
|---|---|
| User production audit 2026-08-17 (Quick 1/42/100 + Atlas notes) | Defect evidence (F-01…F-14) |
| Production Atlas 183716 on commit **85ea366** | Defect evidence (F-03/F-07/F-09 reopen; F-15…F-21) |
| Annex §10 / §11 / §16 | Correctness bar |
| `PHYSICAL_REALISM_PLAN.md` | Living status |
| Code comments cited in §3 | Implementation anchors |

---

## 10. Atlas 183716 / commit 85ea366 (production)

Repo GitHub: no PRs, issues, or commit-review comments. CI pytest + packaging green. `world/manifest.json` `acceptance_ok=false`. Synthetic tests do not cover production Atlas.

| Layer | Result | Verdict |
|---|---|---|
| Hypsometry | p50 567 m, p95 2986 m, max 6375 m | Keep CR-5 defaults |
| Temperature | −37.4–27.7 °C, global mean 16.0 °C | Strongest layer; Godot missed 500 km continentality |
| Moisture | spin-up false after 20 and 40 y | Do not calibrate precip |
| Lakes | 16 184 cells, 10.64% land; 183 bodies; 76.9% playa/ice | F-15/F-16 |
| Rivers | 782 cells, 0.514% land | F-09 PET×12 + F-17 |
| Biomes | 11.72% land Holdridge Lake | F-18 |
| Landforms | 53.7% land mountain score ≥0.5 | F-13 → CR-9 |

Rendering only open + watered endorheic would drop visible water from 10.64% to ~2.46% land. Star-shaped lake = F-20. `lee_sink` ≈ 24.6% of precip. Fluvial erosion restored 938 pits (F-21). Atlas runtime ~94 s; Full memory still F-14.
