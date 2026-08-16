# Atlas UX improvement plan

> **Status:** A1–A8 complete (2026-08-15). **Continuation:** `docs/ATLAS_PLAN_B.md` (B1–B7 planned — currents→biomes, land fill, UI chrome).  
> **Date:** 2026-08-15 (extended: post-A4 feedback — rivers/lakes, default Atlas, smoothing deferred)  
> **Authority:** Post–Milestone 19 atlas feedback (Godot on macOS); decisions below.  
> **Rule:** Execute **one atlas milestone at a time**. Physical World M0–19 stay frozen unless a milestone explicitly touches worker/export.

---

## 0. Context

After Physical World v1 (M0–19), the Godot atlas is usable for smoke runs but **not** as a detailing tool. A1–A4 delivered zoom, profiles, layer toggles, and first stroke polish.

**Post-A3/A4 human findings (Atlas profile, seed 124; Full often stalls ~55% on `vectors`):**

1. Flickering bluish ghosts → **Coast** layer; thinner coasts help (A4); seam chords remain (**A5**).
2. Full-width horizontal bright lines on Coast → **dateline / per-cell segment wrap** (**A5**).
3. Rivers still too strong vs lakes; rivers drawn **through** lake polygons; need thinner Strahler taper + **clip through lakes** (**A4b**).
4. Archipelago / shredded coasts → **tuning knobs** (**A6**).
5. Micro-segment coast → merge (**A5**) unlocks Full `vectors`.
6. “Pixel stairs” on land/coast/rivers → outline **smoothing** considered later (§7), not in A4b–A8 critical path.
7. Day-to-day Generate should default to **Atlas**, not Full.

---

## 1. Agreed decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Default generate profile | **Atlas** (mid). Full + Quick remain selectable |
| 2 | Bright land outlines | Coast vectors (A3). Merge + seam in **A5** |
| 3 | Texture filter | **Linear** |
| 4 | Hex overlay | True hex contours — **A7 done** |
| 5 | Layer visibility | Coast / Rivers / Lakes / Hex — **A3 done** |
| 6 | Holdridge labels | **A8 done** |
| 7 | River stroke | Thinner; **mouth ≈ current A4 upper width**; **sources ≈ ⅓ of mouth** via Strahler (order 1 ≈ source); **alpha = lake fill alpha** after lake bump |
| 8 | Lake fill | **Less transparent** than A4 `0.48` (target ~`0.55–0.60`); geometry unchanged |
| 9 | River ∩ lake | **Lake wins** — clip/suppress river stroke on lake interior (**A4b**) |
| 10 | Generation tuning | Small knobs — **A6** |
| 11 | Outline smoothing | **Deferred** — §7 only; do not block A4b–A8 |
| — | Full `vectors` stall | **A5** |

---

## 2. Generation profiles (Godot UI)

| Profile | Tectonics | Climate | Terrain (production) | Use |
|---|---|---|---|---|
| **Quick** | 128×64 | 128×64 | 256×128 | UI/smoke |
| **Atlas** (**default**) | 512×256 | 512×256 | 1024×512 | daily iteration / detailing mid |
| **Full** | 1024×512 | 1024×512 | 4096×2048 | production / high detail (after A5) |

Notes:

- Changing default to Atlas is a **one-line UI default** (+ README); Full still uses packaged YAML resolutions when selected.
- UI SHOULD warn when Full is selected (RAM/time on 8 GB hosts).
- Analysis grid stays **256×128** unless a later milestone changes it.

---

## 3. Milestone sequence

### Milestone A1 — Atlas interaction: zoom & pan

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a1.md`

**Stop after this milestone unless told to continue.**

---

### Milestone A2 — Generation profiles (default was Full)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a2.md`

Note: default profile superseded by decision #1 → **Atlas** (implemented in **A4b**).

**Stop after this milestone unless told to continue.**

---

### Milestone A3 — Layer toggles + coastline artefact verification

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a3.md` + `docs/validation/atlas_coast_artefact.md`

**Stop after this milestone unless told to continue.**

---

### Milestone A4 — Vector stroke polish (presentation)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a4.md`

**Delivered (historical):** coast `0.2`; rivers Strahler clamp `[0.2, 0.85]`; lake alpha `0.48`.

**Stop after this milestone unless told to continue.**

---

### Milestone A4b — River/lake composite + default Atlas

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a4b.md` + `docs/validation/atlas_lake_triangulation_plan.md`

**Delivered**

- Default Generate profile = **Atlas**.
- Lake/river alpha **0.58**; Strahler taper via **observed** max order → widths **0.07…0.22** (mouth ≈ coast).
- River∩lake clip (worker + Godot); lake triangulation guards (skip degenerate).
- Optional shadowing renames (`overlay_on` / `master_seed` / `vp_scale`).

**Acceptance:** Atlas default; no river-through-lake paint; no triangulation spam — **met**.

**Known follow-up (not a fail of A4b):** naive clip leaves a **few-pixel gap** between river tip and drawn lake edge — see **A4c**.

**Stop after this milestone unless told to continue.**

---

### Milestone A4c — River ↔ lake junctions (topology + snap)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a4c.md`

**Delivered**

- Worker clip + **shoreline midpoint snap**; `from_lake_id` / `to_lake_id` from raster.
- Atlas GeoJSON exports junction ids; Godot draws as-is (single clip authority).
- Inspector exposes lake ids on river pick.

**Presentation note (amendment):** through-lake reaches are **not** clipped; opaque lakes are drawn **above** rivers so the fill covers the centreline. Junction `lake_id` fields remain for inspect.

---

### 3.1 Planned fix — lake `triangulation failed` (A4b)

**Symptom:** Godot error (often repeated)  
`VectorLayerRenderer.gd` → `draw_colored_polygon` → `Invalid polygon data, triangulation failed`.

**Root cause (likely):** lake rings from `worldsim` `vectorize/lakes.py` (`_boundary_ring`) are a **coarse angular sort of edge-cell centres**, not a guaranteed simple polygon. That yields:

- self-intersecting / bow-tie rings,
- duplicate or near-duplicate vertices,
- rings with &lt; 3 unique points after pixel mapping / dateline `fposmod`,
- concave messes Godot’s canvas triangulator rejects.

Display currently only checks `pts.size() >= 3` — insufficient.

**Fix plan (prefer defence in depth; keep A4b modest):**

| Layer | Action | Effort |
|---|---|---|
| **Godot (required in A4b)** | Before `draw_colored_polygon`: dedupe consecutive points; drop rings with &lt; 3 unique verts; optional area/cross-product sanity; on failure skip polygon (no error spam — guard so Godot never gets bad data). Fallback: `draw_polyline` outline only for skipped fills (optional). | Low |
| **Worker (preferred if still cheap)** | When building/exporting lakes: reject empty/degenerate rings; ensure closed ring; simple validity (non-zero area, no tiny dups). Optional later: replace angular-hull with true contour (marching squares / `skimage.measure.find_contours`) — **out of A4b** unless trivial. | Low–medium |
| **Not in A4b** | Full lake topology rewrite; smoothing curves (§7). | — |

**Validation:** regenerate or load Atlas seed 124 (or any world that currently spams errors); open with Lakes on; debugger clean; most lakes still visible (skipped count documented in `docs/validation/milestone_a4b.md` if &gt; 0).

**Shadowing warnings** (`visible` / `seed` / `scale`): optional hygiene in same PR as A4b (rename params) — not required for triangulation, but cheap.

---

### Milestone A5 — Coast merge + dateline seam (worker)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a5.md`

**Delivered**

- Run-length **merged** coast polylines (H/V interfaces).
- Seam-safe endpoints (no full-width chords); Godot `_to_pixels` unwraps polylines.
- Metrics: Atlas-like **~59×** fewer features; Full-like **~124×** in ~2 s on M2.

**Acceptance:** no dateline chords; order-of-magnitude fewer features; vectors not stuck on micro-edge flood — **met**.

**Stop after this milestone unless told to continue.**

---

### Milestone A6 — Generation tuning knobs (modest)

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a6.md`

**Delivered**

- YAML knobs: ocean fraction, plates, cycles, detail amplitude, erosion iterations, fluvial k (defaults unchanged vs pre-A6).
- Loader → tectonics / terrain / erosion builders.
- Godot **Advanced generation…** foldout writes `planet_config.yaml` and passes `--config`.
- README start-here: ocean ↓, plates ↓, detail ↓, then erosion.

**Acceptance:** ocean fraction visible at fixed seed; defaults preserve behaviour — **met**.

**Known follow-up (not A6):** after flicker fix, coasts look slightly more square (SubViewport nearest + no AA) — revisit with §7 smoothing; do not regress flicker.

**Stop unless told to continue.**

---

### Milestone A7 — True hex contours

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a7.md`

**Delivered**

- Flat-top hex outlines from analytical lattice (`hex_corner_offsets` / Godot `_draw`).
- Optional overlay; LOD when Fit makes cells tiny; click-inspect preserved.
- `hex_overlay.png` export updated (outlines, not crosses).

**Acceptance:** hexagons when overlay on; SoT unchanged when off — **met**.

**Stop unless told to continue.**

---

### Milestone A8 — Holdridge (and related) inspector labels

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone_a8.md`

**Delivered**

- `holdridge_zone_legend.json` in `atlas_display/`.
- Hex inspector: human-readable **holdridge** label; **holdridge_id** secondary.
- Overrides ocean / lake / ice / alpine labeled; life zones as `Belt / humidity`.

**Acceptance:** no bare `holdridge_dominant: 0` without meaning — **met**.

**Stop unless told to continue.**

---

## 8. Simulation tuning notes (post-A8 atlas feedback)

Not an authorized milestone until named — capture for continentality / climate work:

| Observation (seed 183716, Atlas) | Likely layer | Notes |
|---|---|---|
| Holdridge reads very cold (tundra, boreal, cold deserts) | Climate / biotemp / PET, or genuine hypsometry | Need hex `temperature_annual_c` + precip in inspector (now exported) to separate SoT vs aggregation |
| Land elevation rarely &gt; ~3000 m | Terrain `land_scale_m` (default 6000) + weak orogeny / raw relief | Mountains should often exceed this; couple with **A9**-style hypsometry / `folding_ratio` / land scale |
| Quick/Smoke hex = Ocean/ice on land | **Fixed:** analysis hex denser than climate left empty hexes (dominant 0). Quick now writes analysis 128×64; worker clamps hex ≤ climate | Regenerate Quick |

Outline smoothing remains §7; continentality/hypsometry remains the next named generator track when instructed.

---

## 4. Explicitly out of scope (this plan)

- Lake polygon beautification / meshing beyond A4b (fill alpha, river clip, **degenerate-ring guards**). True contour lakes = later if needed.
- Full palaeoclimate / EnvironmentTimeline UI.
- HISTORY_SIMULATION_ARCHITECTURE features.
- Changing ADR-0002 production resolution lock except via profiles / knobs.
- Automatic hyperparameter search.
- **Production-quality smooth coast curves** as a hard requirement here (see §7 — deferred design).

---

## 5. Suggested human instructions

```text
(Atlas UX A1–A8 complete. Continuation: docs/ATLAS_PLAN_B.md — start with B1 when instructed.)
```

---

## 6. Definition of done for this plan

Atlas on macOS Godot 4.7:

- defaults to **Atlas** generation; **Full** can finish through vectors/world after A5;
- Coast/Rivers/Lakes strokes readable; **river tips snap to lake shores** (A4c); no centerline through lakes;
- coast polylines **merged** and **seam-safe**;
- small generation knobs;
- true hex contours + Holdridge labels when enabled;
- validation docs for coast artefact + A5 metrics;
- smoothing (§7) may remain open without blocking Done for A1–A8.

---

## 7. Deferred: outline smoothing (“curves instead of pixels”)

**Problem:** Terrain/coast/rivers are derived from **raster grids**. At Atlas (and even Full) zoom, marching edges and stream paths look like **stair-steps / small squares**.

**Can we smooth?** Yes, at several levels — cost and fidelity differ:

| Approach | Difficulty | Effect | Performance |
|---|---|---|---|
| **A. Higher res only** (Full after A5) | Low | Smaller stairs | Already expensive; does not remove topology |
| **B. Display Chaikin / spline on polylines** (coast, rivers) in Godot or at export | **Low–medium** | Softer vector strokes | Cheap if post-merge (A5); avoid per-cell edges |
| **C. Contour simplify + smooth** (Douglas–Peucker then spline) in worker | Medium | Cleaner coasts/lakes | One-time CPU at export; fewer points can **speed** draw |
| **D. Smooth shaded-relief / land mask** (Gaussian then re-extract) | Medium–high | Softer land silhouette in PNG | Extra raster passes; risk of shifting shoreline vs SoT |
| **E. True vector land polygons + LOD** | High | Map-like curves | Big redesign; atlas + queries |

**Recommendation for later (after A5):** start with **B/C on merged coasts + rivers** (presentation/export), keep raster SoT authoritative. Do **not** smooth before merge (smoothing millions of 1-cell edges is wasted work).

**Related display note (post-flicker fix, not a milestone):** SubViewport container **nearest** + non-AA polylines stopped ghosting but can make coasts look more square. Prefer addressing via §7 smoothing rather than re-enabling AA/stretch ghosts. Full (4096) Fit made fixed world-space stroke widths subpixel → dust speckles; mitigated by scaling stroke width with texture (Atlas ref 1024). **Do not cull coast segments by min-length** (Atlas runs are often ~1 px — culling hid shorelines); length cull only for rivers on Full.

**Impact:** Properly done, smoothing **reduces** vertex count and can improve Godot FPS; naive per-frame spline on huge feature sets would hurt — hence A5 first.

**Not scheduled** as A4b–A8 unless explicitly promoted to a new milestone (e.g. A9).
