# Physical Realism Corrections — post–PR-9 production hardening

> **Status:** **CR-0–CR-5 accepted** (2026-08-17). CR track complete.  
> **Authority:** This document amends production acceptance of PR-0…PR-9 foundation where fixed-seed audit contradicts milestone notes.  
> **Normative design:** [`WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) remains primary for algorithms; where annex acceptance was marked done but production fails, **this corrections track takes precedence** until closed.  
> **Tracker:** [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md).  
> **Rule:** One **CR-N** milestone at a time. Validate → `docs/validation/physical_realism_crN.md` → stop.  
> **Do not** retune hypsometry / climate / landform thresholds as a substitute for the defects below.  
> **Next when instructed:** optional **B10** (atlas) or a named follow-up (moisture trial band / Full gate / score retune).

---

## 0. Purpose

PR-0…PR-9 delivered scaffolding, fixtures, and several correctness gates. A fixed-seed Quick comparison (seeds **1, 42, 100**) against the pre–realism baseline shows that **production generations still fail annex physical intent** in moisture closure, SST–land coupling, monsoon seasonality, endorheism, landform quality, subgrid stats, and resolution-invariant scales.

This document:

1. records the audit snapshot and why visuals understate the change;
2. registers defects with **code/comment anchors** (not only symptoms);
3. freezes **interim safe defaults** (compensate nothing);
4. sequences **CR-0…CR-5** (then calibration), matching the recommended repair order.

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
| `power_tail_v2` still off | `default_planet.yaml`: `hypsometry_mode: legacy_max` — “Enable power_tail_v2 after calibration.” |
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
| **F-03** | P0 | Spin-up fails in production; ~~`acceptance_ok` ignores convergence~~ | **Closed CR-1/CR-3** — gate + `spinup_max_years=20` |
| **F-04** | P0 | ~~Land store not in spin-up / closure gate~~ | **Closed CR-3** — joint q+store closure |
| **F-05** | P0 | ~~SST couples land toward absolute nearest SST~~ | **Closed CR-3** — `anomaly_zonal_v1` |
| **F-06** | P0 | Inland decay ≈ whole continents | **Closed CR-2/CR-3** — km default + anomaly mix 0.28 |
| **F-07** | P0 | ~~Monsoon always offshore / non-seasonal~~ | **Closed CR-3** — local coast contrast v2 |
| **F-08** | P0 | ~~Endorheic / playa / frozen never appear in production~~ | **Closed CR-4** — finite `fill_max_depth_m=25`; typed outlets; closed basins kept |
| **F-09** | P0 | ~~Monthly vs annual Q incoherent (80–91%)~~ | **Closed CR-4** — canonical = sum of monthly effective Q |
| **F-10** | P1 | ~~Subgrid elev/slope percentiles wrong columns~~ | **Closed CR-2** |
| **F-11** | P1 | Physics still resolution-dependent | **Closed CR-2/CR-5** for monsoon/plume km + river catchment km²; leftovers: `advect_steps`, bathymetry shelf cells |
| **F-12** | P1 | ~~`hypsometry_tail_softness` reserved no-op~~ | **Closed CR-5** — `power_tail_v2_curve(..., tail_softness)`; `s=1` is PR-2 identity |
| **F-13** | P1 | Landform mask/DEM mix coasts+bathymetry; plateaus absent; ~~`acceptance_ok` hardcoded~~ | **Closed CR-1/CR-2/CR-5** — land-only downsample; km scales + km² floors; threshold 0.50 (0.60–0.65 needs score retune) |
| **F-14** | P2 | Full memory / dual work | Monthly hydro arrays can exceed ~6 GiB; moisture rebuilt twice in final (by design for lake/river sources) — confirm no accidental double hydrology; Full perf gate never closed |

### Reopened conflict-register items

| Prior claim | Correction |
|---|---|
| C-06 / C-07 “Done (PR-5/PR-6)” endorheic semantics | **Closed CR-4.** Finite numerical fill; typed outlets; closed basins kept as endorheic/playa/frozen. |
| PR-4 / PR-7 moisture “accepted” | **Closed CR-1/CR-3** for wire + joint q/store spin-up; land precip trial-band still leftover (not retuned in CR-5). |
| PR-8 monsoon “accepted” | **Closed CR-3** for local coastal regime + seasonal flip; modest strength 0.35. |
| PR-3 km scales “accepted” | **Closed CR-2/CR-3/CR-5** for km decay + SST anomaly + landform/hydro km². |
| PR-9 foundation accepted | **9A–C prototype; 9D partial; 9E thresholds CR-5.** Godot landform mode leftover. |

---

## 4. Production defaults after CR-5

Do **not** retune `folding_ratio` / `ocean_evap_rate` to hide remaining Full-gate or moisture-band leftovers. CR-5 production defaults:

| Knob | Value | Rationale |
|---|---|---|
| `tectonics.folding_ratio` | `0.01` | Keep frozen (annex D-01) |
| `moisture.monsoon_strength` | **`0.35`** | Local coastal regime (CR-3); still modest |
| `moisture.ocean_evap_rate` | leave `1.4` | Raising 2.1–4.2 mostly wettened ocean/coast |
| `ocean.sst_mix` | `0.28` | After anomaly coupling (CR-3) |
| `climate.base_temp_c` | `25` | Hold |
| `tau_land` / `tau_ocean` | `0.55` / `2.8` | Hold (PR-3) |
| `moisture.spinup_max_years` | **`20`** | Joint q+store closure (CR-3) |
| `hydrology.fill_max_depth_m` | **`25`** | Numerical pits only (CR-4); `-1` = legacy fill-all |
| `hydrology.transmission_rate` | `0.45` | Hold; rate sweep is calibration, not CR-4 exit |
| `terrain.hypsometry_mode` | **`power_tail_v2`** | Quantile 0.95, anchor 3000 m, body 1.5, `tail_softness` 1.0 |
| `landforms.mountain_score_threshold` | **`0.50`** | 0.60–0.65 needs score-formula retune |
| `landforms` scales / km² | 60 / 150 / 300 km; 800 / 2500 km² | PR-9E production floors |
| `hydrology.river_min_catchment_km2` | **`500`** | Cell count via GridMetrics |

River cosmetics (`river_acc_fraction`, discharge quantile) may densify blue lines but **are not** physical fixes.

---

## 5. Correction milestones (normative order)

```text
CR-0  CI + harness honesty + Windows packaging
  → CR-1  Parameter propagation + acceptance honesty
  → CR-2  GridMetrics completion + subgrid transpose + cell→km leftovers
  → CR-3  Moisture conservation/spin-up + SST anomaly coupling + monsoon regime
  → CR-4  Monthly hydrology coherence + typed outlets / real endorheism
  → CR-5  Joint calibration (hypsometry, climate, landforms) on Quick+Atlas (+ Full gate)
```

**Hard gate (historical):** CR-5 (PR-9E thresholds / default `power_tail_v2`) required green CR-3 and CR-4 notes. **Met 2026-08-17.**

**Parallel (optional):** B10 atlas Full land polys — presentation only.

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

**Acceptance:** met on fixtures + suite. **Stop.** Next was **CR-4** only.

### CR-4 — Monthly hydrology + typed outlets / endorheism ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr4.md`](validation/physical_realism_cr4.md) (2026-08-17).

**Intent:** annex §11 depression semantics and PR-6 production behaviour.

- Finite numerical fill (`fill_max_depth_m=25`); fill-all only for lake geometry.
- Outlet types: ocean / closed_basin / local_pit / broken_cycle / ns_edge.
- Closed basins kept as endorheic / playa / frozen (not dropped as arid).
- Canonical monthly effective Q; annual = sum. Sink on runoff, not raw precip.
- `monthly_gross` not stored by default (Full memory).

**Acceptance:** fixture endorheic/playa/frozen; monthly vs annual rel_diff = 0 by construction; hydro `acceptance_ok` requires typed outlets. **Met.**

**Stop.** Next: **CR-5** only.

### CR-5 — Joint calibration (hypsometry, climate, landforms) ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr5.md`](validation/physical_realism_cr5.md) (2026-08-17).

**Intent:** only after CR-0…CR-4.

- Enable `power_tail_v2`: quantile 0.95, anchor 3000 m; body exponent **1.5** (middle of 1.2 / 1.5 / 1.8). Real `tail_softness` (`s=1` = PR-2 identity).
- Landforms: scales 60 / 150 / 300 km; min object size in **km²**; mountain score **0.50** (0.60–0.65 blocked until score-formula retune).
- Hydro river min catchment **500 km²** via GridMetrics.
- Moisture trial band **not** retuned (no full Quick/Atlas seed evidence this milestone).
- Godot landform mode skipped.

**Acceptance:** 3-seed hypsometry table (128×64); fixtures for softness / plateau / km²; `pytest -m "not slow"` green. Full Quick+Atlas regen and Full memory gate leftover. **Met** for code/config defaults.

**Stop.** CR track complete.

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
| PR-6 | ~35–45% in production | CR-4 |
| PR-7 | Skeleton; knobs dropped + budget unfinished | CR-1, CR-3 |
| PR-8 | Wired; wrong monsoon regime | CR-3 |
| PR-9 | Prototype A–C; D partial; **9E thresholds CR-5** | CR-2 mask, CR-5 |

---

## 7. Suggested human instructions

```text
Physical realism corrections: execute CR-0 only.
```

```text
Physical realism corrections: execute CR-1 only.
```

After CR-5 (track complete):

```text
Atlas Plan B: execute B10 only.
```

Do **not** combine CR milestones. Moisture / score-formula follow-ups need a named instruction; do not retune `folding_ratio` or `ocean_evap_rate` to hide leftovers.

---

## 8. Validation note contract

Each CR creates:

```text
docs/validation/physical_realism_crN.md
```

Required contents: code/config version; seeds/profiles; tests; defect IDs closed; absolute-metric deltas vs pre-CR baseline; explicit leftovers.

Fixed seeds for regression: Quick **1, 42, 100** (extend with Atlas when touching SST/landforms).

---

## 9. Traceability

| Source | Role |
|---|---|
| User production audit 2026-08-17 (Quick 1/42/100 + Atlas notes) | Defect evidence |
| Annex §10 / §11 / §16 | Correctness bar |
| `PHYSICAL_REALISM_PLAN.md` | Living status |
| Code comments cited in §3 | Implementation anchors |
