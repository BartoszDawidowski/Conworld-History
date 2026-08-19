# Worldgen Corrective C9.1 — production closure

## Lake-aware routing, periodic storage, BiomeV2 semantics, terminals, landform structure, honest acceptance

> **Status:** Accepted planning guidance; **implementation not started by this document**  
> **Date:** 2026-08-18  
> **Repository:** `BartoszDawidowski/Conworld-History`  
> **Audited commits:** `9ebca51` (C0–C9) and `96065a3` (plateau fill / legend)  
> **Reference world:** Atlas profile, seed `183716`  
> **Supporting runs:** Quick seeds `1`, `42`, `100`  
> **Parent design:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`  
> **Predecessor:** `docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md` (C0–C9 delivered; **C10 blocked**)  
> **Primary objective:** Close remaining production invariants that would make C10 calibration fit routing and classification bugs rather than climate or landform physics.

---

# 1. Authority and agent entry protocol

C9.1 is a **production-closure** programme between delivered C9 and blocked C10. It does not replace the annex or the C0–C9 addendum. Where this file and an earlier “✅ Complete” validation note disagree on a production invariant, **this file takes precedence**.

A green unit suite, green macOS/Windows CI, or `acceptance_ok=true` on hex/world manifests is **not** evidence that hydrology, BiomeV2, or landforms are physically closed.

The first agent task after receiving this file is planning-only:

1. read this file completely;
2. read the C0–C9 addendum §§3–6 and annex §§10–17, 19–21;
3. inspect the current repository (do not trust line numbers here);
4. reconcile trackers so **next = C9.1.1**, not C10;
5. stop and wait for an explicit instruction to implement **one** subpackage.

After the plan is accepted, implement **C9.1.1 → C9.1.6 in order**. Every subpackage ends with tests, a fixed-seed note, a performance note, and a stop. Do **not** combine a correctness fix with YAML/Godot default retuning in the same change.

Python/worldsim remains the sole owner of physics and classifications. Godot only displays declared products.

---

# 2. Audit verdict (Atlas `183716` on `9ebca51` / `96065a3`)

Local `pytest` collected 388 tests, all passed. macOS and Windows CI were green; Ubuntu was still installing CMake and had not reached tests. That software result is recorded and is **orthogonal** to the production defects below.

| Observation | Audit result |
|---|---|
| Moisture is better | **Confirmed.** Annual precipitation vs previous version: correlation ≈ **0.63**. Holdridge class changed on ≈ **64%** of land. Final moisture budget is tightly closed. This is not cosmetic. |
| Almost no tropical rain forest | **Confirmed.** 1 rain-forest cell, 119 wet forest, 630 moist forest. Mainly absolute precip scale and dry interiors, **not** tropical temperatures. Calibration belongs in **C10**, after routing is honest. |
| Growing–Moist covers ice | **BiomeV2 bug**, not a seed quirk. 1083/1084 such cells have **zero growing months**; 779 overlap Holdridge Permanent ice. |
| Some ranges are very thick | **Confirmed.** Width P90 ≈ **297 km**, max ≈ **960 km**; largest component ≈ **8.46 million km²**. These are glued mountain systems. |
| Too few plateaus | **Confirmed.** Plateau context = **0.742%** of land (alarm band 1–8%). Configured `min_plateau_km2=2500` is not the real floor: effective minimum ≈ **15.6 thousand km²**. |
| Lakes look more reasonable | **Visually yes:** liquid water ≈ **0.72%** of land (was >7%). Lake **physical balance is still critically wrong**. |
| Few rivers, few reach the sea | **Mostly presentation + terminal labels**, not climate. Physical network **25 260** cells; map shows **444** cells / **44** segments. |

Temperature is the strongest product. Land-temperature correlation vs previous version ≈ **0.99997**; mean change ≈ **0.007 °C**. Hypsometry of this seed is plausible (median 567 m, p95 3000 m, max 6436 m). Atlas elevation colour is still stretched to each world’s p98, so hypsometry can look unchanged even when it is not.

---

# 3. Why C10 must not start

C10 is a **multi-seed parameter grid** (precip, river display, mountain/plateau thresholds, erosion). Fitting those knobs now would absorb:

- doubled discharge below lakes;
- unpublished, non-periodic lake storage;
- a BiomeV2 class that means “default leftover” rather than growing-season moist land;
- a display river filter that deletes ~98% of the physical network;
- `mouth` labels on lakes, depressions, and LOD cutoffs;
- glued ranges and plateaus classified as escarpment.

The moisture improvement and the lake-area reduction are real. They are **not** a licence to calibrate.

---

# 4. Frozen during C9.1

Do **not** change these defaults (Godot Advanced, YAML, or code dataclass defaults):

| Parameter | Frozen value |
|---|---|
| `tectonics_folding_ratio` | `0.01` |
| sea level / ocean fraction | current |
| hypsometry | `power_tail_v2` |
| `base_temp_c` | `25` |
| lapse rate | `6.5` °C/km |
| `sst_mix` | `0.28` |
| SST inland decay | `1200` km |
| `mountain_score_threshold` | `0.60` |
| `precip_scale_mm` | current (300) |
| `river_acc_fraction` | `0.035` |
| `river_discharge_candidate_quantile` | `0.50` |
| `plateau_score_threshold` | `0.40` |
| `fill_max_depth_m` | current — **not** a lake-count knob |
| Holdridge annual classifier | unchanged |

`precip_scale_mm=350` produced 37 tropical rain-forest cells and better precip bands **on this seed**. Do not write it as a default in C9.1: it also rescales runoff, Q, and storage.

River display `.15 / .35` produced ~2475 river cells instead of 444. Allowed only as a **temporary diagnostic override** in a local run, never as a committed default before C9.1.1–C9.1.3.

Mountain `0.65` shrinks the largest component from 8.46 to ~3.04 million km² and **does not** fix gluing. Plateau `0.30` overshoots the escarpment alarm. Do not use either as a C9.1 default.

---

# 5. Recorded C10 grid (not authorised)

These are starting points **after** C9.1 closes. They are not new defaults.

| Area | Start | Test grid |
|---|---|---|
| `precip_scale_mm` | 300 | 250 / 300 / 350 |
| River display fraction | 0.15 | 0.10 / 0.15 / 0.20 |
| River Q quantile | 0.35 | 0.25 / 0.35 / 0.45 |
| Mountain threshold | 0.62 | 0.60 / 0.62 / 0.65 |
| Plateau threshold | 0.35 or 0.40 | 0.35 / 0.40 |
| Thermal erosion | 50 | 20 / 50 / 80 |
| Final stream power | 1000 | 500 / 1000 / 1500 |

---

# 6. Defect register

IDs are binding for C9.1 subpackages.

| ID | Sev | Symptom | Code / comment anchor |
|---|---|---|---|
| **P-91-01** | P0 | Through-lake flow is counted twice. Graph routes all runoff; lake storage then re-reads that Q and **adds spill again** downstream. Synthetic 10 m³/s → ~20 m³/s below the lake. Atlas: 142 cells with `Q_effective > Q_gross`, some by absurd factors. | `physical/hydrology/pipeline.py` — `accumulate_weights` on monthly Q, then `apply_basin_storage`, then `monthly_eff[m] += accumulate_weights(graph, spill_w)` |
| **P-91-02** | P0 | Lake storage does not reach a periodic cycle. 103/216 basins periodic; among 140 liquid lakes only **27** periodic. Published state is year-8 leftover. | `physical/hydrology/basins_storage.py` `apply_basin_storage`; diagnostics `storage_periodic`, `basin_storage_periodic_count` |
| **P-91-03** | P0 | Snow/soil runoff starts from zero stores. Repeating the year raises year-2 runoff by ~**12%**. Lake spin-up therefore sees a biased hydrograph. | `physical/hydrology/runoff.py` `build_monthly_runoff` — `store`/`soil` zeros, single 12-month pass, no published periodic year |
| **P-91-04** | P1 | Monthly water/ice fractions for lakes are not a first-class published product (hydroperiod/ice still largely annual reclass). | `basins_storage.py` `_reclass_storage_axes`; lake records / atlas vectors |
| **P-91-05** | P0 | BiomeV2 class raster is initialised to `GROWING_MOIST`. `ThermalRegime.NON_GROWING` never receives its own class, so ice and zero-growth land stay green. | `physical/ecology/biome_v2.py` — `klass = np.full(..., GROWING_MOIST)` then moisture/thermal overrides that skip NON_GROWING |
| **P-91-06** | P0 | Wetland = 35.7% of land because saturated root-zone store overwrites arid/frost. This is **wet-soil potential**, not wetland. | `biome_v2.py` `wetland = (moisture == WET) & (growing_months >= 3) & …`; display legend already hedges with `wetland_potential` |
| **P-91-07** | P0 | `acceptance_ok` is not a conjunction of known gates. Final computes `landforms_ok` and `fluvial_erosion_nontrivial` but does not require them. World/manifest copies **hex** `acceptance_ok`. Same run: failed erosion gate, non-periodic lakes, plateau alarm, inconsistent climate-summary flags — still green. | `physical/final/pipeline.py` `acceptance_ok: stable and no_catastrophe`; `spatial/model.py` `acceptance_ok=hex_grid.diagnostics["acceptance_ok"]`; `export/atlas_display.py` `overall_acceptance_ok` |
| **P-91-08** | P1 | Display rivers are double-filtered: `river_acc_fraction=0.035` keeps 3.5% of the **already extracted** physical network, then Q quantile **0.50** drops about half of the remainder → 25 260 → 444 cells. | `hydrology/rivers.py` / `channels.py` `display_channel_candidates`; `config.py` `hydrology_river_acc_fraction`, `hydrology_river_discharge_candidate_quantile` |
| **P-91-09** | P0 | Any terminal segment may be typed `mouth`. 18 `mouth` nodes, **8** actually adjacent to ocean. Lake, endorheic, and LOD terminals are mislabelled. | `physical/vectorize/rivers.py` — ocean-neighbour → `mouth`; leftover `junction` with `out==0` forced to `mouth` |
| **P-91-10** | P1 | Mountain components are glued across saddles/straits. Raising the score threshold shrinks area but does not split systems. | `physical/landforms/objects.py` connected components on mountain mask |
| **P-91-11** | P1 | Ridge is essentially a geodesic diameter of the mask, not a height/TPI ridge line. | `physical/landforms/objects.py` ridge extraction |
| **P-91-12** | P1 | Plateau context cells are 87.7% local **escarpment**. Rim is the full object perimeter, not a detected scarp. Interior flats are lost. | `physical/landforms/classify.py` local-form order; `objects.py` `components_to_geojson_rims` |
| **P-91-13** | P1 | `min_plateau_km2=2500` is not enforceable on the analysis grid: `min_object_cells` × `min_component_cells` yields an effective floor ~15.6e3 km². Diagnostics must not claim 2500 km². | `landforms/params.py` `min_object_cells`; `pipeline.py` `min_plateau_km2_representable` |

---

# 7. Corrected hydrology contract (normative)

A lake is a **single storage node**:

```text
catchment runoff / channel inflow
        ↓  (once)
   lake storage (A–V–h)
        ↓
   published spill only  →  downstream graph
   (no through-flow on the same cells)
```

Invariants:

1. Cells inside a wet lake envelope are **not** ordinary river-graph transmitters of the same volume that storage already absorbed.
2. Downstream of an outlet, `Q_effective` is storage spill (minus declared channel loss), not `Q_gross + spill`.
3. `Q_effective ≤ Q_gross` except where a documented local source exists (on-lake precipitation counted once, never as both graph flow and storage inflow).
4. Synthetic fixture: 10 m³/s into a spilling lake ⇒ ≈ 10 m³/s (not 20) immediately below the outlet, within numerical tolerance.
5. Published monthly Q, lake spill, and wet fraction come from a **periodic** year after snow/soil and storage spin-up, or the run must fail the hydrology gate.

---

# 8. Work packages

Execute in order. Do not start C9.1.(n+1) until C9.1.n has a validation note and an explicit stop.

## C9.1.1 — Lake-aware routing without double flow

**Priority:** P0  
**Closes:** P-91-01  
**Depends on:** C2 graph + C1 A–V–h (keep; change how Q enters them)

Required:

- treat each lake (or each spilling waterbody) as a graph **sink + source**: inflow accumulates to the storage node once; the only mass leaving to downstream cells is computed spill;
- stop adding `accumulate_weights(spill)` on top of a graph that already passed that water through the lake cells;
- publish `q_gross`, `q_effective`, `q_through_lake_once`, and a count of cells with `q_effective > q_gross`;
- hydrology `acceptance_ok` fails if that count is material (threshold in the validation note, not tuned to hide Atlas 142);
- Godot unchanged except consuming honest Q if already displayed.

### Acceptance

- synthetic 10 m³/s lake fixture does not double;
- Atlas 183716: no systematic `Q_effective > Q_gross` below lakes;
- `docs/validation/worldgen_corrective_c91_1.md`;
- tests Quick 1/42/100 (hydrology subset) + Atlas 42/183716 diagnostics;
- **stop**. Do not retune `fill_max_depth_m` or precip.

## C9.1.2 — Periodic runoff and lake storage; monthly water/ice fractions

**Priority:** P0  
**Closes:** P-91-02, P-91-03, P-91-04  
**Depends on:** C9.1.1

Required:

- spin snow store and soil bucket to a periodic climatological year (or fail closed) **before** publishing runoff used by routing/storage;
- lake storage spin-up uses that periodic runoff, not a cold-start year-1 hydrograph;
- a liquid lake that does not meet `storage_periodic` may not be published as a stable open/endorheic waterbody; it is a warning object or withheld from liquid rendering according to the note;
- publish monthly wet-area fraction and ice/liquid fraction (or an honest “annual-only” flag — not a fake monthly series);
- diagnostics: periodic basin count, periodic liquid-lake count, year-2 vs year-1 runoff relative delta.

### Acceptance

- repeating the forced year changes published runoff by a documented small epsilon, not ~12%;
- liquid-lake periodic fraction is reported and gated;
- `docs/validation/worldgen_corrective_c91_2.md`;
- **stop**.

## C9.1.3 — Honest river terminals (display filter unchanged)

**Priority:** P0  
**Closes:** P-91-09; **diagnoses** P-91-08  
**Depends on:** C9.1.1 (lake nodes must be real)

Required terminal vocabulary (canonical; Godot may show labels but must not invent types):

| Type | Meaning |
|---|---|
| `ocean_mouth` | last channel cell adjacent to ocean |
| `lake_inlet` | channel ends in a wet lake envelope |
| `lake_outlet` | channel leaves a wet lake at the spill node |
| `endorheic_sink` | depression / closed basin with no ocean or lake outlet |
| `lod_cutoff` | physical channel continues but display LOD dropped it |

Rules:

- **never** coerce leftover `junction`/`out==0` to `mouth`;
- `mouth` as a legacy alias is allowed only as `ocean_mouth`;
- diagnostics: counts per terminal type; fraction of `ocean_mouth` that actually neighbour ocean (must be 1);
- keep `river_acc_fraction=0.035` and Q quantile `0.50` as **committed defaults**;
- record physical vs display cell counts (`channel_physical_cell_count` vs display) in hydrology diagnostics so C10 can choose a LOD without confusing it with climate;
- optional local override for screenshots is not a YAML change.

### Acceptance

- Atlas 183716: nodes labelled ocean-mouth are ocean-adjacent;
- lake inlet/outlet survive round-trip on GeoJSON;
- `docs/validation/worldgen_corrective_c91_3.md`;
- **stop**. No river-fraction retune.

## C9.1.4 — BiomeV2 NON_GROWING and wetland vs wetland potential

**Priority:** P0  
**Closes:** P-91-05, P-91-06  
**Depends on:** C9.1.2 for flooding/water-level products used by true wetland; NON_GROWING may be coded first but the package is not accepted until wetland is not a soil-saturation paint

Required:

- do **not** initialise the class raster to `GROWING_MOIST`;
- every `ThermalRegime.NON_GROWING` land cell maps to frost/ice/non-growing display class, never Growing–Moist;
- cells with `growing_season_months == 0` cannot be Growing–Moist or Growing–deficit;
- **Wetland potential** may remain a diagnostic axis (saturated store);
- **Wetland** as a map class requires at least: inundation or high water fraction, low slope, and neighbourhood of river/lake (exact predicate in the validation note). Arid/frost cannot be overwritten by root-zone saturation alone;
- legend strings must match the raster meaning (no “Growing — moist” on ice);
- Holdridge annual classifier stays untouched.

### Acceptance

- Atlas 183716: Growing–Moist ∩ (zero growing months) = 0;
- wetland land fraction is not ~36% from soil store alone;
- `docs/validation/worldgen_corrective_c91_4.md`;
- **stop**. No `precip_scale_mm` change to “create” rain forest.

## C9.1.5 — Plateau interior/rim and range splitting

**Priority:** P1  
**Closes:** P-91-10, P-91-11, P-91-12, P-91-13  
**Depends on:** C7 objects (keep scores; change geometry)

Required:

- split mountain components at saddles and width constrictions; do not rely on raising `mountain_score_threshold`;
- ridge line prefers elevation / TPI along the component, not the mask geodesic diameter;
- plateau **interior** vs **escarpment**: local escarpment must not consume the plateau interior; alarm if plateau-context ∩ escarpment remains ~88%;
- rim = detected scarp / steep edge, not the entire polygon perimeter;
- report `min_plateau_km2_configured` vs `min_plateau_km2_representable`; if 2500 km² is not representable, either analyse at a grid where it is, or fail the honesty gate — do not silently enforce ~15.6e3 km²;
- leave `mountain_score_threshold=0.60` and `plateau_score_threshold=0.40` frozen.

### Acceptance

- largest range component is split or explicitly marked as a mountain *system* with child ridges (schema in the note);
- plateau context land fraction is not still 0.74% solely because of a hidden area floor;
- rim GeoJSON is not a duplicate of the filled outline;
- `docs/validation/worldgen_corrective_c91_5.md`;
- **stop**. No C10 threshold grid.

## C9.1.6 — Canonical `acceptance_ok` aggregator

**Priority:** P0  
**Closes:** P-91-07  
**Depends on:** C9.1.1–C9.1.5 so the conjunction is meaningful

One owner, one formula, copied to final diagnostics, world manifest, and `climate_summary.json`.

Conjunction **must** include at least:

- moisture `acceptance_ok` (spin-up **and** budget);
- hydrology `acceptance_ok` including P-91-01/02 gates;
- vector `acceptance_ok`;
- ecology `acceptance_ok` including BiomeV2 class coverage;
- landforms `acceptance_ok` including plateau/range honesty diagnostics;
- erosion / `fluvial_erosion_nontrivial` when the profile claims metric erosion;
- hex schema/layout `acceptance_ok` (layout is **not** a substitute for physics).

A failed component may emit warnings, but **may not** be omitted from the conjunction to keep the run green. Climate-summary flags must match the same aggregator (no amber-vs-green split between inspector and manifest).

### Acceptance

- a fixture with doubled lake Q, non-periodic lakes, or Growing–Moist-on-ice cannot publish `overall_acceptance_ok=true`;
- hex-only success cannot paint the world green;
- `docs/validation/worldgen_corrective_c91_6.md` plus a roll-up `docs/validation/worldgen_corrective_c91.md`;
- **stop**. C10 remains blocked until the user reviews the roll-up.

---

# 9. Required evidence per subpackage

Minimum:

- `pytest -m "not slow"` plus new focused tests;
- Quick seeds **1 / 42 / 100**;
- Atlas seeds **42 / 183716** (diagnostics JSON; regen only when the subpackage changes published rasters/vectors);
- no YAML/Godot default retune unless the user explicitly asks after the note;
- performance: Atlas runtime/RSS warning if >15% slower or +128 MiB vs `9ebca51` Atlas 183716.

Do not regenerate leftover worlds “for screenshots” in a package that did not change those products.

---

# 10. Global Definition of Done for C9.1

C9.1 is complete only when:

- lake routing does not double mass;
- published runoff and lake storage are periodic or the hydrology gate is red;
- BiomeV2 does not paint non-growing land as Growing–Moist;
- wetland is not saturated-soil-as-marsh;
- river terminals distinguish ocean, lake, endorheic, and LOD cutoff;
- ranges are split at saddles/constrictions and ridges follow relief;
- plateau interior/rim are distinct from a painted perimeter;
- one aggregator owns `acceptance_ok`;
- Quick 1/42/100 and Atlas 42/183716 notes exist;
- **C10 is still not started**.

At that point calibration of precip, river LOD, and landform thresholds can be an honest C10 grid instead of compensation for routing and class bugs.
