# Physical Realism Corrections — post–PR-9 production hardening

> **Status:** **CR-0 accepted** (2026-08-17). Open: **CR-1…CR-5**.  
> **Authority:** This document amends production acceptance of PR-0…PR-9 foundation where fixed-seed audit contradicts milestone notes.  
> **Normative design:** [`WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) remains primary for algorithms; where annex acceptance was marked done but production fails, **this corrections track takes precedence** until closed.  
> **Tracker:** [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md).  
> **Rule:** One **CR-N** milestone at a time. Validate → `docs/validation/physical_realism_crN.md` → stop.  
> **Do not** retune hypsometry / climate / landform thresholds as a substitute for the defects below.  
> **Next when instructed:** **CR-1** (parameter propagation + acceptance honesty).

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
| PR-7/PR-8 knobs dropped in final moisture rebuild | `physical/final/pipeline.py` rebuilds `MoistureParams` **without** plume / land_store / ITCZ / monsoon fields (dataclass defaults may apply inconsistently vs YAML). |
| Landforms unused in Godot / history | PR-9E + Godot display deferred (`physical_realism_pr9.md`). |
| Precip palette / stretch | Annex §16.4: min–max images hide absolute scale collapse. |

**Implication:** visual review alone is invalid acceptance (annex §16.1). Prefer absolute maps + diagnostics JSON.

---

## 3. Defect register

IDs are binding for CR milestones. Severity: **P0** blocks physical acceptance; **P1** blocks calibration; **P2** product/perf.

| ID | Sev | Symptom | Code / comment anchor |
|---|---|---|---|
| **F-01** | P0 | ~~CI / harness expectations drift; stale PR-0 probes; Windows `vendor\vendor` path~~ | **Closed CR-0** — see `docs/validation/physical_realism_cr0.md` |
| **F-02** | P0 | Final pass ignores YAML PR-7/PR-8 moisture knobs | `physical/final/pipeline.py` constructs partial `MoistureParams(...)` — omits `plume_*`, `land_store_*`, `itcz_*`, `monsoon_*` while first-class fields exist on `MoistureParams` |
| **F-03** | P0 | Spin-up fails in production; `acceptance_ok` ignores convergence | `moisture.spinup_max_years: 4` in YAML; `transport.py` `spinup_converged`; `moisture/pipeline.py` `acceptance_ok` = wet/dry heuristics only — **no** `spinup_converged` |
| **F-04** | P0 | Land store not in spin-up / closure gate | PR-7 land store vs PR-4 budget identity; annex MOIST-03 |
| **F-05** | P0 | SST couples land toward **absolute** nearest SST | `couple_temperature_with_sst_inland`: `(1-w)*temp + w*nearest_sst` (`ocean/sst.py`); docstring “blended toward nearest SST” |
| **F-06** | P0 | Inland decay ≈ whole continents | YAML comment + PR-1 validation: cells→km ≈ **4691 km**; not a physical retune |
| **F-07** | P0 | Monsoon always offshore / non-seasonal | `atmosphere/monsoon.py`: hemispheric `land_mean - ocean_mean` on **post-SST** land T; `coast_reach_cells` still cell-based |
| **F-08** | P0 | Endorheic / playa / frozen never appear in production | `flow.py`: `max_depth=-1` fill-all + `outlets="edge"`; lake classes in `lakes_meta.py` exist but graph never leaves closed basins |
| **F-09** | P0 | Monthly vs annual Q incoherent (80–91%) | PR-6 monthly effective Q vs annual routing path — production divergence |
| **F-10** | P1 | Subgrid elev/slope percentiles wrong columns | `downsample_elevation_subgrid_stats`: `reshape(out_h, by, out_w, bx)` then flatten **without** `transpose(0,2,1,3)` |
| **F-11** | P1 | Physics still resolution-dependent | Advect steps, plume steps, monsoon `coast_reach_cells`, several hydro thresholds remain **cells**; annex C-08 / PR-1 incomplete |
| **F-12** | P1 | `hypsometry_tail_softness` reserved no-op | `terrain/pipeline.py`: “reserved / documented; asymptote uses max/anchor” |
| **F-13** | P1 | Landform mask/DEM mix coasts+bathymetry; plateaus absent; `acceptance_ok` hardcoded | `landforms/pipeline.py` `"acceptance_ok": True`; min sizes in **cells** (`landforms/params.py`) |
| **F-14** | P2 | Full memory / dual work | Monthly hydro arrays can exceed ~6 GiB; moisture rebuilt twice in final (by design for lake/river sources) — confirm no accidental double hydrology; Full perf gate never closed |

### Reopened conflict-register items

| Prior claim | Correction |
|---|---|
| C-06 / C-07 “Done (PR-5/PR-6)” endorheic semantics | **Reopened as F-08.** Types exist; production fill-all prevents them. |
| PR-4 / PR-7 moisture “accepted” | **Partial.** Direction/caps exist; production spin-up + param wire + store closure fail (F-02…F-04). |
| PR-8 monsoon “accepted” | **Partial.** Wired; regime wrong (F-07). |
| PR-3 km scales “accepted” | **Partial.** Migration helpers exist; defaults still huge decay + cell monsoon reach (F-06, F-11); subgrid bug (F-10). |
| PR-9 foundation accepted | **9A–C useful prototype; 9D partial; 9E deferred.** F-13 blocks calibration. |

---

## 4. Interim safe defaults (until CR-3 closes)

Tuning must **not** compensate F-02…F-09. Until moisture/SST/monsoon conservation gates pass:

| Knob | Value | Rationale |
|---|---|---|
| `tectonics.folding_ratio` | `0.01` | Keep frozen (annex D-01) |
| `moisture.monsoon_strength` | **`0.0`** | Disable broken offshore-only regime |
| `moisture.ocean_evap_rate` | leave `1.4` | Raising 2.1–4.2 mostly wettened ocean/coast |
| `climate.base_temp_c` | `25` | Hold |
| `tau_land` / `tau_ocean` | `0.55` / `2.8` | Hold (PR-3) |
| `moisture.spinup_max_years` | **16–20 for validation only** | Not a final Full default until closure proven |
| `terrain.hypsometry_mode` | `legacy_max` | Do not enable `power_tail_v2` for product defaults yet |

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

**Hard gate:** do not start **CR-5** (or PR-9E threshold retune, or enabling `power_tail_v2` as default) until CR-3 and CR-4 acceptance notes are green.

**Parallel (optional):** B10 atlas Full land polys — presentation only.

### CR-0 — CI and harness honesty ✅

**Status:** Accepted — [`docs/validation/physical_realism_cr0.md`](validation/physical_realism_cr0.md) (2026-08-17).

**Intent:** green CI; tests assert corrected physics, not historical bugs.

- Keep PR-0 fixture probes aligned with PR-4+ (northward mass, capped precip, flat January).
- Fix packaging path resolution (`PkgRoot = parent of scripts`, not `vendor/vendor/pyplatec`).
- Document any remaining platform-only packaging failures separately from pytest.

**Acceptance:** all required CI jobs green on `main`; `pytest -m "not slow"` green locally. **Met.**

**Stop.** Next: **CR-1** only.

### CR-1 — Parameter propagation + acceptance honesty

**Intent:** YAML / Godot knobs that exist must reach the final moisture build; diagnostics must not lie.

- Final pipeline: copy **full** `MoistureParams` (or pass `params.moisture` through) including PR-7/PR-8 fields on **both** moisture builds.
- Audit Godot → YAML → `PlanetConfig` → `MoistureParams` for dropped keys (`monsoon_lat_band_min`, coast reach, spin-up, diffusion, etc.).
- Gate `acceptance_ok` (moisture at minimum) on `spinup_converged` (and later land-store closure).
- Landforms: replace hardcoded `acceptance_ok: True` with real checks (or `False` / omitted until calibrated).

**Acceptance:** changing plume / ITCZ / monsoon / land_store in config changes final ecology moisture diagnostics; failed spin-up ⇒ not `acceptance_ok`.

**Stop.**

### CR-2 — GridMetrics / subgrid / resolution invariance

**Intent:** same planet parameters ⇒ comparable physics across Quick / Atlas / Full (annex §16.3).

- Fix subgrid block layout: after `reshape(out_h, by, out_w, bx)` apply **`transpose(0, 2, 1, 3)`** before flattening to `(out_h, out_w, by*bx)`.
- Review `metric_gradients` / slope consumers if audit still flags gradient defects.
- Migrate remaining cell knobs that change physical reach with resolution, at least: monsoon coast reach, any fixed advect/plume **step counts** that encode distance, hydro thresholds documented as length/area.
- Prefer explicit `sst_inland_decay_km` in defaults over giant cell migration accidents; **do not** silently reinterpret old cell values as “correct km”.

**Acceptance:** synthetic subgrid fixture (known ridge in one fine cell) places p90/ridge/RMS in the correct coarse cell; length knobs documented in km; Quick vs Atlas large-scale precip/T patterns closer under identical km params.

**Stop.**

### CR-3 — Moisture closure, SST anomaly, monsoon regime

**Intent:** annex §10 P0 moisture + honest coastal coupling + seasonal transport-first monsoon.

1. **Spin-up / conservation**
   - Converge `q` and land store (or document store as diagnosed state with joint tolerance).
   - Raise validation `spinup_max_years` as needed; choose production default only after seed-suite proof.
   - Budget residual gates; precip remains ≤ available moisture.
2. **SST**
   - Couple **SST anomaly** (relative to a clear baseline), not absolute SST temperature onto land.
   - Retune only after the formula change: trial band `sst_mix≈0.25–0.30`, `sst_inland_decay_km≈800–1500` (≤2000).
3. **Monsoon**
   - Contrast from local coastal land vs nearby SST (not whole-hemisphere means on SST-softened T).
   - Expect seasonal onshore/offshore flip; trades outside band stay coherent.
   - Keep `monsoon_strength=0` until this passes; then re-enable modestly.
4. **Post-fix moisture trial band** (calibration prep, not CR-3 exit):  
   `orographic_frac 0.05–0.10`, `lee_dry 0.02–0.05`, `plume 0.10–0.20`, `land_store 2–4`, `ITCZ 1.0–1.4`, `ocean_evap 1.4–1.6`.

**Acceptance:** Quick seeds 1/42/100 `spinup_converged=True` (or honest fail); monsoon monthly onshore diagnostic changes sign seasonally on at least one tropical coast fixture; land ΔT from SST coupling deep inland ≪ coastal; budget residuals within annex tolerances.

**Stop.**

### CR-4 — Monthly hydrology + typed outlets / endorheism

**Intent:** annex §11 depression semantics and PR-6 production behaviour.

- Stop treating fill-all (`max_depth=-1`, edge outlets) as the only production mode; distinguish ocean outlet, closed basin, local pit, and broken cycle in the graph.
- Materialize open / endorheic / playa / frozen with non-zero counts on suitable fixtures **and** at least one Quick seed.
- Reconcile monthly effective Q with annual products (or define a single canonical discharge field and derive the other).
- After PET/transmission correctness: trial `transmission_rate` 0.30 / 0.35 / 0.45 / 0.60.
- Full: profile memory for monthly arrays; avoid redundant heavy passes.

**Acceptance:** fixture + seed evidence of endorheic/playa; monthly vs annual Q divergence no longer at 80–91% mystery levels; hydro `acceptance_ok` reflects graph rules.

**Stop.**

### CR-5 — Joint calibration (hypsometry, climate, landforms)

**Intent:** only after CR-0…CR-4.

- Enable/evaluate `power_tail_v2`: quantile 0.95, anchor 2800–3000 m; body exponent trials **1.2 / 1.5 / 1.8** (audit band 1.4–1.8 gave median ~0.5–0.9 km, mean ~0.8–1.1 km, max ~4.3–5.7 km on three seeds). Implement real `tail_softness` before trusting the far tail.
- Landforms after slope/mask fix: mountain score ~0.60–0.65; scales ~60 / 120–180 / 250–400 km; **min object size in km²**, not cells; then PR-9E.
- Seed suites: Quick + Atlas mandatory; Full performance/memory gate before changing Full defaults.
- Optional Godot landform mode after thresholds stabilize.

**Acceptance:** multi-seed metric tables (not one hero seed); absolute maps; annex distribution checks; Full within agreed memory/time budget.

**Stop.**

---

## 6. Mapping prior PR track → corrections

| Foundation PR | Honest status after audit | Primary CR |
|---|---|---|
| PR-0 | Harness exists; must stay honest | CR-0 |
| PR-1 | Metrics base OK; cell leftovers + gradient/subgrid issues | CR-2 |
| PR-2 | Option present, default off; `tail_softness` no-op | CR-5 (+ F-12 in CR-2/5) |
| PR-3 | Seasonal filter good; SST form + subgrid bug | CR-2, CR-3 |
| PR-4 | Wind direction fixed; production closure/spin-up incomplete | CR-1, CR-3 |
| PR-5 | Strongest (~70–80%) | CR-4 (outlet typing) |
| PR-6 | ~35–45% in production | CR-4 |
| PR-7 | Skeleton; knobs dropped + budget unfinished | CR-1, CR-3 |
| PR-8 | Wired; wrong monsoon regime | CR-3 |
| PR-9 | Prototype A–C; D partial; E deferred | CR-2 mask, CR-5 / 9E |

---

## 7. Suggested human instructions

```text
Physical realism corrections: execute CR-0 only.
```

```text
Physical realism corrections: execute CR-1 only.
```

After CR-3+CR-4:

```text
Physical realism corrections: execute CR-5 only.
```

Do **not** combine CR milestones. Do **not** start parameter sweeps that assume F-02…F-09 are fixed.

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
