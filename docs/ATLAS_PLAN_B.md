# Atlas Plan B — presentation, climate coupling, UI

> **Status:** **B1–B7 complete** (B7: 2026-08-16). Climate/geography defaults **user-retuned** (see §6 / `milestone_b5.md`).  
> **Next Plan B presentation when instructed:** **B10** (Full land polys) may run independently.  
> **Next climate physics:** **CR-0–CR-2 ✅**; next **CR-3** — [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md). Tracker: [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md). Do not retune B8/B9 knobs to hide CR defects.  
> **Hydro UX follow-up:** ✅ flow-direction **layer** + channel transmission losses — §6.3.1 / `docs/validation/hydro_flow_and_transmission.md` (2026-08-16). Annex still requires cylindrical graph + lake/wadi semantics (PR-5/PR-6).  
> **Date:** 2026-08-16  
> **Authority:** Post-A8 discussion + 2026-08-15 climate/hydro/moisture planning; **amended 2026-08-16** by Physical Realism Annex.  
> **Rule:** Execute **one Plan B milestone at a time**. Stop after each unless told to continue.  
> **Physical World:** Prefer shallow hooks for atlas UX. Correctness follow-ups that touch M6/9/11/13 modules are allowed only via the realism PR track — not as an ad-hoc Plan B rewrite.

---

## 0. Relationship to Plan A

| Plan A | Plan B |
|---|---|
| A1–A8 done (zoom, profiles, layers, strokes, coast merge, knobs A6, hex, Holdridge labels) | Continues atlas product work |
| §7 outline smoothing deferred | Land **fill + elevation texture** first; stroke smooth later |
| §8 cold biomes / weak peaks / currents unused for ecology | Currents→temperature→Holdridge with **inland decay**; knobs exposed; defaults user-retuned after B5 |
| Sidebar + dropdown map modes | Top / bottom chrome; inspector left; compact legend |

Plan A remains the historical record. Do not reopen A1–A8 unless a B milestone explicitly patches a regression.

---

## 1. Agreed decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Currents → biomes | **Yes.** After ocean SST coupling, push corrected temperature into the field ecology/Holdridge use. Include **inland penetration with distance decay** (not coast-cell-only). |
| 2 | Land presentation | Filled **vector land silhouette**; **elevation** projected as texture onto that figure. Other map modes draw **above untextured** land fill (not elevation-textured). |
| 3 | Resolution roll-out | **Atlas-first** land polygons; **Full later** (own milestone). |
| 4 | Coast outline | **Keep** for now (toggleable). Can hide via layer control. |
| 5 | Raster ↔ vector | After any smooth/simplify, presentation must stay **visually aligned** with raster masks (stencil / clip; no free-floating halo). |
| 6 | Climate defaults | Expose knobs in Advanced; **packaged defaults follow user retunes** (geography + climate 2026-08-15). No silent retune without instruction. |
| 7 | UI chrome | Top bar = generate/load; bottom bar = map modes (icons) + layer toggles + zoom slider; inspector = **left**; no right panel; mode **legend** = small BR corner when relevant. |
| 8 | Advanced generation | **Popup** (not inline expand). Close on outside click or ✕. Long help text → **(i)** hover tooltips next to fields. |
| 9 | Zoom | Slider: **min = Fit**, **max = empirical** (see §5.3). |
| 10 | Execution | One milestone at a time; validation note per milestone under `docs/validation/`. |
| 11 | Rivers / lakes vs precip | Topology stays DEM-based; **visibility / masks** gated by catchment discharge (dry local OK if upstream wet). Optional stroke weight ∝ discharge. → **B7**. Follow-up: transmission losses (**Nil OK / wadi dies**) + flow **layer** — §6.3.1. Further graph/endorheic hardening → realism **PR-5/PR-6**. |
| 12 | Moisture realism | Soft inland plume + land ET recycling + ITCZ (proxy, not GCM). → **B8 = PR-7**, only **after moisture correctness gate PR-4**. Mechanisms **amended**: no unconstrained post-hoc precip; all terms inside moisture budget. |
| 13 | Monsoon / trades | Trades already in Hadley (M7). **Monsoon proxy A** → **B9 = PR-8** after PR-7. **Amended:** transport-first wind anomaly; direct precip multiplier is not primary. |
| 14 | Physical realism annex | Corrective P0/P1 physics (hypsometry, GridMetrics, moisture budget, cylindrical hydro, landforms) lives in `PHYSICAL_REALISM_PLAN.md`, not as new B-milestones except revised B8/B9. |

---

## 2. Target product sketch

### 2.1 Top bar

- Seed  
- Generate profile (Quick / Atlas / Full)  
- **Advanced generation…** → popup with knobs (A6 geography + B climate knobs when ready)  
- Generate world  
- Load world  
- Loaded-atlas status  
- Generation progress  

Hide always-visible blurbs such as “Raster/vector geography…” and “Full uses config…”. Put that copy behind **(i)** info icons beside the relevant control.

### 2.2 Left panel

- **Inspector only** (terrain / river / hex).  
- After chrome move, left side is otherwise empty — inspector owns it.

### 2.3 Bottom bar (EU5-like mode box)

- **Map mode** = row of **icon buttons** (not OptionButton). Hover tooltip = mode name (`Elevation`, `Bathymetry`, `Temperature`, `Precipitation`, `Holdridge`, …).  
- **Active mode** = coloured border / highlight on the button.  
- Same bar: toggles for **Hex**, **Coast**, **Rivers**, **Lakes** (existing layers).  
- **Zoom slider**: left/min = Fit (`user_zoom_factor = 1`); right/max = cap (§5.3). Wheel/buttons may remain as shortcuts if cheap.

### 2.4 Bottom-right legend

- Compact, optionally scrollable card — **not** a full side panel.  
- Shown for modes that need a key (at least **Holdridge** colours ↔ labels).  
- Hidden or minimal for modes without a discrete legend.

### 2.5 Map compositing (presentation)

```text
ocean / void background
→ filled land polygons (flat / untextured base)
→ [elevation mode only] elevation texture clipped to land
→ [other modes] mode visualisation drawn above untextured land
→ coast / rivers / lakes vectors (toggleable)
→ hex overlay (toggleable)
→ BR legend (mode-dependent)
```

**Elevation:** only mode that **projects** the heightmap as a texture onto the land figure.  
**Other modes (temperature, precip, holdridge, bathymetry, …):** land stays an untextured vector base; mode content is drawn **on top** (existing atlas rasters or equivalent), composed so the land silhouette still reads as vector-edged where applicable. Ocean treatment follows the mode (e.g. bathymetry emphasises water; holdridge ocean = override colour).

Raster SoT and hex analysis remain the inspect/query authority.

---

## 3. Simulation: currents → biomes (shallow)

### 3.1 Goal

Ocean currents already build SST + `temperature_coupled_c` (coast mix). That field must **affect Holdridge**, with **warm/cool influence decaying inland**.

### 3.2 Approach (no deep engine rewrite)

1. Keep existing `build_monthly_sst` + `couple_coastal_temperature`.  
2. Add **inland anomaly propagation**: from coastal/ocean SST anomaly (or coupled delta vs base), blend into land cells with decay  
   `w = exp(-dist_to_ocean / scale_cells)` (or equivalent distance-to-ocean already used for continentality).  
3. Write result into the temperature array **ecology reads** (prefer updating `climate.temperature_c` once after ocean, before moisture/ecology — one correction pass, not a full §26 iteration loop).  
4. Hex aggregates + atlas `holdridge.png` / inspector temps follow automatically.  
5. Expose knobs later (B5): mix strength, decay scale, western/eastern SST anomaly — **defaults unchanged**.

### 3.3 Out of scope here

- Multi-iteration coupled climate to convergence  
- Rewriting moisture physics  
- Palaeoclimate / EnvironmentTimeline UI  

---

## 4. Land vector fill + elevation texture

### 4.1 Goal

Reduce pixel-stair silhouettes: land is a **uniform vector figure**; elevation texture sits on it; other modes sit on flat land vector.

### 4.2 Pipeline sketch

| Step | Where | Notes |
|---|---|---|
| Polygonize `ocean_mask` → land rings (islands, holes if needed) | worker | Prefer contours from mask; dateline-safe split |
| Optional simplify (Atlas) | worker | Keep alignment with mask; do not drift shoreline |
| Export GeoJSON / compact rings for atlas | `atlas_display/` | Atlas resolution first |
| Godot: fill polygons | atlas | Triangulation guards (lessons from lakes) |
| Elevation: clip/sample height texture inside land | Godot shader or stencil | Elevation mode only |
| Coast polyline | keep | Toggle; does not replace fill |

### 4.3 Alignment rule

Smoothing/simplify is allowed only if the filled edge stays consistent with raster land/ocean for presentation (stencil from same rings; no textured land spilling over ocean).

### 4.4 Full resolution

Separate milestone after Atlas path is accepted. Do not block Atlas UX on 4096 polygonization.

---

## 5. UI details

### 5.1 Advanced popup

- Opens from top-bar control.  
- Modal-ish popup: **✕** or click-outside closes.  
- Contains generation knobs (existing A6 + climate knobs when B5 lands).  
- No long paragraphs in the bar itself.

### 5.2 Map mode icons (initial set)

| Mode | Icon direction (simple) | Tooltip |
|---|---|---|
| elevation | mountain / relief | Elevation |
| bathymetry | waves / depth | Bathymetry |
| temperature | thermometer | Temperature |
| precipitation | rain | Precipitation |
| holdridge | leaf / biome | Holdridge |

Exact art can be placeholder geometry until final icons exist.

### 5.3 Zoom slider — initial proposal

Today `WorldAtlas` clamps `_user_zoom_factor` roughly to `[0.25, 48]` with Fit ≈ factor recomputed as baseline.

**Plan B target:**

| End | Meaning | Initial value |
|---|---|---|
| Min | Fit (whole map in view) | `user_zoom_factor = 1.0` |
| Max | Strong inspect zoom | **`user_zoom_factor = 16.0`** |

Rationale: 16× Fit is enough to read hexes / coasts on Atlas (1024) without the old 48× dust/overshoot; easy to raise to 24 or lower to 12 after human try. Document the chosen cap in the UI milestone validation note after one empiric pass on macOS.

Slider updates the same `_user_zoom_factor` path (preserve pan anchor behaviour if already correct).

### 5.4 Legend

- Holdridge: colour swatches + wiki-style labels (reuse `holdridge_zone_legend.json`).  
- Optional later: continuous scales for temp/precip.  
- Position: **bottom-right**, compact, scroll if long; does not displace inspector.

### 5.5 Right panel

**Removed** from the layout target. Nothing essential lives there after the move.

---

## 6. Generation knobs (expose + user-retuned defaults)

Expose via Advanced + YAML. **Packaged defaults** match Atlas experiments (2026-08-15) unless a later retune is requested.

Candidates (building on A6 / B5):

| Group | Examples |
|---|---|
| Geography (A6) | ocean fraction, plates, cycles, detail amplitude, erosion |
| Climate mean / gradient | **`base_temp_c`** (exposed), `insolation_scale_c` (still deferred), latitude `sin²`, `lapse_rate_c_per_km` |
| Currents / coupling | **`sst_mix`**, **`inland_decay_cells`**, western/eastern SST anomaly (°C) |
| **Moisture / precip inland** | §6.2 knobs; further physics in **B8** |
| Hypsometry / tectonics | folding, tect sea/erosion, land/ocean scale, orogeny/activity/boundary relief |
| Ecology scaling | **`precip_scale_mm`** (Holdridge PET/P) |

**B5 shipped** knobs + wiring. **User climate retune (defaults now):**  
`base_temp_c=25`, `sst_mix=0.4`, `inland_decay_cells=60`, west/east SST `2.2`/`1.8`,  
`advect_steps=32`, `advect_wind_scale=0.2`, `large_scale_frac=0.15` (rainout), `orographic=0.85`,  
`convective=2.0`, `ocean_evap=1.4`, `land_et=0.4`, `continentality_dry=0.4`, `lee_dry=0.12`,  
`precip_scale_mm=200` (unchanged). Geography tectonics retune unchanged (plates 7, cycles 3, …).

### 6.1 Precipitation vs currents (design note)

Moisture **already** consumes SST + `temperature_coupled_c`. Prefer transport/rainout / realism **PR-4 → B8–B9 (PR-7/8)** over a separate “precip from currents” field (double-count risk).

### 6.2 Moisture inland reach (post-B4 / B5)

**Symptom (pre-retune):** narrow coastal wet fringe; knobs change absolute precip but interior/coast **ratio** stayed similar; precip PNG min–max hid changes (fixed to absolute scale).

**B5:** expose M9 constants + later default retune (above). **Do not** treat further knob-only tuning as sufficient for continental interiors — see realism **PR-4** then revised **B8 (PR-7)**. Do not retune advect/rainout knobs to “fix” annex P0 bugs.

| Knob | Packaged default (post-retune) | Role |
|---|---|---|
| `moisture_advect_steps` | `32` | Inland travel substeps |
| `moisture_advect_wind_scale` | `0.2` | Cell transport per step |
| `moisture_large_scale_frac` | `0.15` | Rainout (UI: `rainout`) |
| `moisture_orographic_frac` | `0.85` | Orography / rain shadow |
| `moisture_convective_scale` | `2.0` | Tropical convection scale |
| `moisture_ocean_evap_rate` | `1.4` | Ocean source |
| `moisture_land_et_rate` | `0.4` | Land ET (static; **PR-7/B8** makes water-limited) |
| `moisture_continentality_dry` | `0.4` | Interior capacity penalty |
| `moisture_lee_dry` | `0.12` | Lee drying |

### 6.3 Precip-aware rivers & lakes (**B7**)

**Shipped (B7):** DEM topology unchanged; river/lake **visibility** gated (candidate discharge quantile, lake precip/river-touch/freeze). Stroke ∝ `log(1+discharge)`. Details: `docs/validation/milestone_b7.md`.

**Limitation vs intent:** raw `discharge_proxy` has **no** channel loss; hard gates can leave mid-desert “starts” and unclear lake inlets. Atmospheric `lake_evap_rate` / `river_evap_rate` humidify moisture #2 only — they do **not** shrink discharge.

**Acceptance sketch (shipped):** arid interior loses spurious streams; a wet highland draining across dry lowland can still show a continuous river.

### 6.3.1 Follow-up — flow layer + transmission losses (agreed 2026-08-16)

**Status:** ✅ Implemented — `docs/validation/hydro_flow_and_transmission.md`  
**Shipped with B7 follow-up (2026-08-16).**

| Piece | Decision |
|---|---|
| Flow directions | Atlas **layer checkbox** (like Rivers/Hex), **not** a map mode. Source: D8 `flow_direction`. LOD at Fit. |
| Channel water | Build **effective discharge** with transmission sink along D8 (PET/aridity proxy). **Nil OK** (strong upstream Q survives arid corridor); **wadi dies** (weak Q evaporates away). |
| Distant-fed lakes | **Keep** if effective inflow from far wet sources remains sufficient; dry playas without it stay omitted. |
| Atmospheric lake/river evap | Unchanged role (moisture #2 → ecology). Not a substitute for channel losses. |
| Self-feed | Still: moisture #1 → hydro/gates → moisture #2. No re-gate on lake self-humidity. |
| Remaining (annex) | Canonical E–W periodic graph; monthly effective Q; no unconditional downstream river-mask inheritance; explicit open/endorheic/playa; inlet/outlet metadata — **PR-5/PR-6**, not another Plan B UX patch. |

### 6.4 Moisture v2 — plume, recycling, ITCZ (**B8 = PR-7**)

**Gate:** Do not implement or tune B8 until realism **PR-4** (moisture direction, budget, spin-up, diagnostics) is accepted. See annex §10.1 / `PHYSICAL_REALISM_PLAN.md`.

Three proxies remain in scope; **implementation constraints amended** (annex §10.7):

| Piece | Intent | Amended sketch |
|---|---|---|
| **Soft inland plume** | Widen wet influence beyond advection+rainout collapse | Transports/mixes **existing** `q`; preferably wind-/flow-aligned; subject to orographic rainout and **q budget**. Isotropic distance-to-ocean may be low-weight fallback/diagnostic — **not** an unconstrained final rain layer. |
| **Land ET recycling** | Wet land sustains local humidity | Bounded land-water store; ET water-limited (not temperature-only). |
| **ITCZ / tropical source** | Stronger rain under monthly ITCZ | Strengthens convergence/convection **limited by available moisture**; must not double-count base convection. |

Expose new scales as Advanced knobs. Defaults chosen after PR-4 validation — do not retune in the same milestone that ships the gate.

### 6.5 Monsoon proxy A + trades note (**B9 = PR-8**)

**Trades:** already present in M7 Hadley (`wind_u` easterly + meridional toward ITCZ). Not true 3D trades, but directionally correct — **no rewrite required** for B9 beyond using them.

**Monsoon (approach A — amended):** seasonal land↔ocean **wind anomaly** from land–SST contrast → feed corrected wind into moisture transport. Preserve trades outside the active region. A **small optional** precip residual is allowed only inside the moisture budget after transport — not as the primary mechanism.  
**Not in B9:** full pressure-solver monsoon (approach C) or standalone wet-belt without wind (B alone).

---

## 7. Milestone sequence

Execute in order unless a later note says otherwise. **Stop after each.**

### Milestone B1 — Currents → temperature → Holdridge (inland decay)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b1.md`

**Delivered when**

- Post-ocean correction updates the temperature field used by ecology (and thus Holdridge / hex temps).  
- Inland cells receive a **decaying** fraction of coastal/ocean anomaly (distance-based).  
- Diagnostics: mean |ΔT| land, sample warm-vs-cold western/eastern contrast if applicable.  
- Defaults numerically unchanged vs pre-B1 for disabled/zero-new-knob path… **Correction:** behaviour **will** change once coupling is applied (that is the point). Do not change *unrelated* defaults (base_temp, etc.). Coupling parameters use current SST constants + a documented default decay scale.

**Acceptance**

- Fixed seed: Holdridge / coastal hex `temperature_annual_c` differ in a coherent way near western vs eastern boundary currents vs pre-B1 baseline (document before/after in validation).  
- Inland decay: effect weaker far from ocean than at coast.  
- No full climate iteration loop required.

**Stop unless told to continue.**

---

### Milestone B2 — Atlas UI chrome (layout)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b2.md`

**Delivered when**

- Top bar: seed, profile, Advanced popup, Generate, Load, loaded status, progress.  
- Help blurbs removed from chrome; **(i)** tooltips instead.  
- Bottom bar: icon map modes + vector/hex toggles + zoom slider (Fit…16× initial).  
- Inspector on **left**; right panel gone.  
- BR legend hook for Holdridge (**deferred** — removed from chrome; was covering the map).

**Acceptance**

- Generate/Load/inspect still work on an existing Atlas world.  
- Mode buttons switch modes; active border visible.  
- Advanced opens/closes per §5.1.  
- Zoom slider min = Fit; max = initial cap.

**Stop unless told to continue.**

---

### Milestone B3 — Land polygons export (Atlas resolution)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b3.md`

**Delivered when**

- Worker exports land ring GeoJSON (or equivalent) for Atlas-sized display.  
- Dateline-safe; islands supported; triangulation-hostile rings filtered/guarded.  
- Coast polylines still exported (outline remains available).

**Acceptance**

- Atlas seed load shows valid land polygons in a debug or interim draw path (or validated offline count/area vs `ocean_mask`).  
- Full 4096 polygonization **not** required.

**Stop unless told to continue.**

---

### Milestone B4 — Land fill + elevation texture; other modes over flat land

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b4.md`

**Delivered when**

- Godot fills land vectors.  
- **Elevation** mode: height texture projected/clipped onto land.  
- **Other modes:** untextured land base + mode layer above (existing PNGs / holdridge).  
- Coast/rivers/lakes/hex remain toggles.  
- Holdridge BR legend **deferred** (not in chrome).

**Acceptance**

- Elevation: land edge reads as vector fill; interior shows elevation texture without ocean halo.  
- Switching to temperature/holdridge does **not** keep elevation texturing on land.  
- Coast can still be toggled.  
- Atlas-only; Full land polys later (**B10**).

**Stop unless told to continue.**

---

### Milestone B5 — Climate / coupling / moisture knobs (expose only)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b5.md`  
(+ geography/climate default retunes; `base_temp_c` / `precip_scale_mm`; inland-water moisture rebuild)

**Delivered when**

- Advanced popup exposes climate/coupling/hypsometry/moisture knobs (§6, including §6.2) via config.  
- **Coupling (B1):** `sst_mix`, `inland_decay_cells` (plus western/eastern SST anomaly).  
- **Moisture inland (§6.2):** advect / rainout / orographic / convective / evap / continentality / lee.  
- First landing: defaults matched then-engine constants; **later:** user-supplied defaults applied explicitly.  
- README / (i) tooltips describe effect briefly.

**Acceptance**

- Knobs reach pipeline / final / ecology as documented in validation.  
- No silent retune without user values.

**Stop unless told to continue.**

---

### Milestone B6 — Stroke smoothing (rivers / coast accent)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_b6.md`  
(+ **B6b:** soft land_mask edge, lake Chaikin, mild mode-texture blur — presentation only)

**Delivered when**

- Post-merge simplify + smooth on coast/river polylines (Plan A §7 B/C), presentation/export.  
- Alignment with rasters preserved (no freestyle drift).  
- Land fill remains the primary anti-alias silhouette.

**Acceptance**

- Softer rivers/coasts at Atlas zoom without dateline chords regressing.  
- Vertex count does not explode; draw stays interactive.

**Stop unless told to continue.**

---

### Milestone B7 — Precip-aware rivers & lakes

**Status:** ✅ Complete (`docs/validation/milestone_b7.md`)  
**Design:** §6.3

**Delivered when**

- River **mask / vectors** gated by catchment `discharge_proxy` (threshold) with **downstream inheritance** (wet source → arid corridor still drawn).  
- Lake mask gated by fill-depth **and** (local precip **or** river inflow).  
- Hydrology diagnostics: counts before/after gate; sample arid vs wet basins.  
- Atlas export / Godot use gated masks (no orphan desert stream webs).  
- **Optional (same milestone if cheap):** stroke width or opacity ∝ `log(1 + discharge)`; otherwise document deferral in validation.

**Acceptance**

- Fixed seed: cells with near-zero local precip and no upstream wet discharge lose river drawing; a path from wet highlands across dry land remains.  
- Large arid closed depressions without precip/inflow are not lakes.  
- Discharge proxy / fluvial erosion still have a coherent river set (do not break M13 catastrophically — prefer gating presentation + vectorize input consistently).

**Stop unless told to continue.**

**Follow-up (shipped 2026-08-16):** flow-direction **layer** + channel transmission losses — §6.3.1. Further hydro correctness → realism **PR-5/PR-6**.

---

### Milestone B8 — Moisture v2 (plume + recycling + ITCZ)

**Status:** ✅ **COMPLETE** (2026-08-16) — realism **PR-7**; see `docs/validation/physical_realism_pr7.md` (+ `milestone_b8.md` pointer)  
**Design:** §6.4 + annex §10.7  
**Tracker:** [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md)

**Delivered when** (annex acceptance wins on conflict)

- Soft inland plume / mixing **inside** the moisture budget (no independent post-hoc rain field).  
- Water-limited land ET recycling via bounded land store.  
- Non-duplicative ITCZ convergence term limited by available `q`.  
- New knobs in YAML + Advanced; budget/provenance diagnostics.  
- Validation note: `docs/validation/physical_realism_pr7.md` (and optional `milestone_b8.md` pointer).

**Acceptance**

- Interior reach improves without erasing strong rain shadows.  
- Moisture budget remains closed within tolerance.  
- Wet-land ET exceeds desert ET at matched temperature.  
- ITCZ seasonal movement visible; Holdridge/precip coherent; no NaN/Inf.

**Stop unless told to continue.**

---

### Milestone B9 — Monsoon proxy A

**Status:** ✅ **COMPLETE** (2026-08-16) — realism **PR-8**; see `docs/validation/physical_realism_pr8.md` (+ `milestone_b9.md` pointer)  
**Design:** §6.5 + annex §10.8  
**Tracker:** [`PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md)

**Delivered when**

- Bounded seasonal land–SST **wind** anomaly into moisture transport.  
- Precipitation seasonality follows transport; optional residual precip only inside budget.  
- Uses existing Hadley/trades as base (no full circulation rewrite).  
- Knobs: monsoon strength, latitude band; default modest or off-until-tuned.  
- Validation note: `docs/validation/physical_realism_pr8.md`.

**Acceptance**

- Fixed seed with large tropical continent: opposite onshore tendency and wetter onshore season.  
- Trades elsewhere remain coherent.  
- Moisture budget remains closed.

**Stop unless told to continue.**

---

### Milestone B10 — Full-resolution land polygons

**Status:** ⬜ Pending (was B7)

**Delivered when**

- Same land-fill path works for Full display resolution (or agreed downsampled display mesh derived from Full mask).  
- Performance acceptable on target Mac; guards for huge rings.

**Acceptance**

- Full world load: land fill + elevation texture path works; no multi-minute UI freeze on open.

**Stop unless told to continue.**

---

## 8. Explicitly out of scope (Plan B)

- Full §26 multi-pass coupled climate GCM / pressure-solver monsoon (approach C).  
- Standalone monsoon wet-belt **without** wind (approach B alone) — superseded by A + B8 ITCZ.  
- History simulation / CultureMap UI.  
- Replacing analytical hex SoT with display meshes.  
- Automatic hyperparameter search.  
- Requiring production-perfect coast curves before B4 land fill ships.  
- Full groundwater / baseflow / dynamic lake volume (annex deferred).  
- ~~Fully conserved atmospheric moisture budget~~ — **superseded:** budget closure is required under realism **PR-4** (annex §10). Channel hydrology remains a reduced-order discharge proxy, not metre-scale hydraulics.

---

## 9. Definition of done (Plan B)

When B1–B10 are complete (or a subset explicitly accepted as “B done”):

- Currents influence biomes with inland decay; knobs + user climate defaults in place.  
- Atlas land reads as filled vector + elevation texture in elevation mode.  
- Other modes sit on untextured land vector.  
- UI matches §2 / §5.  
- Rivers/lakes respect precip/discharge gating (B7 + §6.3.1); revised moisture v2 (B8/PR-7); revised monsoon (B9/PR-8).  
- Full land polys available (B10) or explicitly deferred.  
- Each shipped B milestone has `docs/validation/milestone_bN.md` (B8/B9 may point at `physical_realism_pr7/8.md`).  
- Physical P0/P1 invariants from the annex are tracked under `PHYSICAL_REALISM_PLAN.md`, not claimed done by B1–B7 alone.

---

## 10. Suggested human instructions

```text
Plan B presentation: B10 Full land polys when requested (independent of PR/CR track).

Climate physics: foundation PR-0…PR-9 is not production-complete.
Use PHYSICAL_REALISM_PLAN.md + PHYSICAL_REALISM_CORRECTIONS.md: CR-0 → … → CR-5.
Do not retune B8/B9 knobs to hide F-02…F-09.
```

Recommended climate order: **B7 ✅ → PR-0…PR-9 foundation → CR-0…CR-5 → B10 anytime**.

Interim until CR-3: `monsoon_strength=0.0`; keep `folding_ratio=0.01`; do not raise `ocean_evap_rate` to “fix” inland dryness.

---

## 11. Open empirics (non-blocking)

| Item | Initial choice | Tune when |
|---|---|---|
| Zoom max factor | **16× Fit** | During/after B2 on real Atlas/Full fits |
| Inland decay / moisture knobs | User retune 2026-08-15 (§6) | Further only on request |
| B7 discharge / lake precip thresholds | Rivers: candidate Q q=0.50. Lakes: rain p70 / river+not-arid p45 / T≥1°C (retune #2 vs desert+ice playas) | Further on request |
| B7 follow-up: flow layer + transmission | ✅ Layer checkbox + effective Q (`transmission_rate=0.45`) — `hydro_flow_and_transmission.md` | Tune rate on request |
| B8 plume / ITCZ / recycling scales | After PR-4; budgeted terms | PR-7 / B8 experiments |
| B9 monsoon strength | Modest / expose | PR-8 after PR-7 |
| Land simplify tolerance | Atlas-only in B3 | If halo or over-smooth appears |
| Realism PR defaults (hypsometry, spin-up, …) | Annex starting families | Per PR validation; never with correctness fix |

---

## 12. Traceability

| Source | Carried into Plan B |
|---|---|
| `ATLAS_UX_PLAN.md` §7 | Land fill supersedes “smooth strokes only”; strokes = B6 |
| `ATLAS_UX_PLAN.md` §8 | Currents unused for ecology → B1; knobs → B5; peaks via knobs not silent retune |
| `WORLDGEN_ARCHITECTURE.md` §26 | One correction pass, not full loop |
| User 2026-08-15 decisions | §§1–2, 5 of this document |
| User 2026-08-15 climate plan | §1 #11–13, §6.3–6.5, milestones **B7–B9**; Full land renumbered **B10** |
| User 2026-08-16 hydro UX | §6.3.1; `docs/validation/hydro_flow_and_transmission.md` (flow layer; transmission losses) |
| `WORLDGEN_PHYSICAL_REALISM_ANNEX.md` | §1 #12–14; §6.4–6.5 amended; B8/B9 = PR-7/PR-8 after PR-4; conflict C-01…C-10 in `PHYSICAL_REALISM_PLAN.md` |
