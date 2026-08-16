# IMPLEMENTATION_PLAN.md

> **Status:** Milestone **19 complete** (2026-08-15). Physical World v1 plan milestones 0–19 are complete.  
> **Follow-up:** Atlas UX A1–A8 done (`docs/ATLAS_UX_PLAN.md`). **Next atlas track:** `docs/ATLAS_PLAN_B.md` (B1–B7).  
> **Date:** 2026-08-15  
> **Authority:** Derived from `docs/WORLDGEN_ARCHITECTURE.md` (v0.2) §62–§65 and local repository inspection  
> **Rule:** Do **not** implement the full project in one pass. Execute **one milestone at a time**.

---

## 0. Purpose of this document

This plan:

1. records the result of the mandatory pre-Milestone-0 inspection (§64);
2. maps conceptual architecture modules to intended repository paths;
3. lists environment readiness, risks, and true architecture conflicts;
4. sequences Milestones 0–19 with deliverables and acceptance criteria;
5. forbids collapsing the project into a single “build everything” agent command.

It does **not** authorize implementation yet.

---

## 1. Inspection summary (2026-08-14)

### 1.1 Repository state

| Item | Status | Notes |
|---|---|---|
| Project folder | Present | Local path: `Desktop/Conworld History` (space in name). Cursor workspace is this folder. |
| `docs/` | Present | Contains architecture + this plan. |
| `docs/WORLDGEN_ARCHITECTURE.md` | Present | Renamed from `WORLDGEN_ARCHITECTURE_v0.2.md` to canonical name. |
| `docs/IMPLEMENTATION_PLAN.md` | Present | This file. |
| `godot/` project | **Missing** | No `project.godot`. Only engine binary present. |
| `worldsim/` | **Missing** | No Python package yet. |
| `vendor/` | **Missing** | No forked PyPlatec yet. |
| CI | **Missing** | No workflows / CI config. |
| Licensing files | **Missing** | No `THIRD_PARTY_NOTICES.md`, no `licenses/`. |
| Git | Initialized | Branch `main`, **no commits yet**. |
| Tracked content risk | High | Untracked: `docs/`, `Godot.app/` (~334 MB), `.DS_Store`. Engine binary must **not** be committed. |

### 1.2 Toolchain verification

| Tool | Required | Observed | Verdict |
|---|---|---|---|
| Git | any recent | Apple Git 2.39.2 | OK |
| Python | 3.12.x | 3.12.14 (`/opt/homebrew/bin/python3.12`) | OK |
| CMake | for PyPlatec native build | 4.4.2 (Homebrew) | OK |
| C/C++ toolchain | MSVC on Windows; Clang/CLT on macOS | Xcode Command Line Tools + Apple clang 14.0.3 | OK **on this Mac** |
| Visual Studio Build Tools | Windows-only | N/A on darwin/arm64 | Deferred to Windows packaging / CI |
| Godot | 4.7.1 stable | `Godot.app` in repo root, `4.7.1.stable.official` | OK (local binary; not on `$PATH`) |
| Cursor | IDE | Workspace already open on this folder | OK |
| Host | — | Apple M2, arm64, **8 GB RAM** | Constraint for 4096×2048 |

### 1.3 Milestone 0 foundation (completed 2026-08-14)

Delivered under `worldsim/`: package skeleton, config, seeds, progress protocol, CLI dry-run worker, tests, dependency pins. Licensing stubs and `.gitignore` added at repo root. Physical stages and `godot/` project remain intentionally unimplemented.

---

## 2. Locked decisions carried into planning

From architecture §4 (non-negotiable without ADR):

- Godot = atlas / UI only; simulation backend = separate Python process.
- Physical SoT = **raster + vector**; hex 256×128 = **analytical cache only**.
- Topology = cylindrical E–W wrap; **no N–S wrap**.
- Tectonics = extended PyPlatec (+ fallback); climate = 12 months; ecology = Holdridge.
- Hydrology = PyFlwDir primary; rivers/lakes/coast = canonical vectors.
- Target grids: tectonics/climate 1024×512; terrain/hydro 4096×2048 if benchmarks allow, else 2048×1024.
- Primary release platform = Windows x86-64; macOS secondary.

---

## 3. Intended path mapping (conceptual → actual)

Exact paths may be adjusted during Milestone 0, but ownership must stay clear.

| Conceptual module | Intended path |
|---|---|
| Architecture docs | `docs/WORLDGEN_ARCHITECTURE.md` |
| This plan / ADRs / validation | `docs/IMPLEMENTATION_PLAN.md`, `docs/ADR/`, `docs/validation/` |
| Future history architecture | `docs/HISTORY_SIMULATION_ARCHITECTURE.md` (out of scope here) |
| Python package root | `worldsim/` (`pyproject.toml`, `requirements.lock`, `src/worldsim/`, `tests/`) |
| CLI / worker entry | `worldsim/src/worldsim/__main__.py` |
| Config / seeds / pipeline / state | `worldsim/src/worldsim/config.py`, `seeds.py`, `pipeline.py`, `state.py` |
| Coordinates | `worldsim/src/worldsim/spatial/coordinates.py` (+ root shim `coordinates.py`) |
| Spatial extent | `worldsim/src/worldsim/spatial/extent.py` |
| Physical stages A–O | `worldsim/src/worldsim/physical/{tectonics,terrain,ocean,climate,erosion,hydrology,ecology,vectorize}/` |
| Spatial stores / hex / queries | `worldsim/src/worldsim/spatial/{raster_store,vector_store,hex_grid,spatial_index,queries}/` |
| Environment timeline scaffold | `worldsim/src/worldsim/environment_timeline/` |
| Export / diagnostics | `worldsim/src/worldsim/export/`, `diagnostics/` |
| Vendored PyPlatec fork | `vendor/pyplatec/` |
| Godot atlas + bridge | `godot/` (`project.godot`, `atlas/`, `simulation_bridge/`) |
| Licences | `licenses/`, `THIRD_PARTY_NOTICES.md` |
| Local Godot engine binary (dev convenience) | keep **outside git** (e.g. `tools/Godot.app` + `.gitignore`, or system install) |

---

## 4. Feasibility assessments (pre-implementation)

### 4.1 PyPlatec extension

- **Feasible** on this machine: CMake + Clang CLT present; architecture already expects fork under `vendor/pyplatec/`.
- Risk: LGPL compliance and Windows MSVC build for packaging (Milestone 3 / 18).
- Plan: Milestone 2 = upstream baseline; Milestone 3 = extended metadata bindings; document fallback if native extension fails.

### 4.2 PyFlwDir packaging

- Preferred hydrology engine (§5, §28).
- Risk: packaging into frozen Windows worker (Milestone 18); keep WorldEngine hydrology as **documented fallback only** via ADR if required.
- Plan: Milestone 11 integrates PyFlwDir behind a narrow interface so fallback can swap without rewriting vectors.

### 4.3 4096×2048 memory / runtime (critical on this host)

Host has **8 GB RAM**. Rough float32 field cost:

| Resolution | Cells | ≈ bytes / float32 field | Notes |
|---|---|---|---|
| 1024×512 | 524 288 | ~2 MB | Comfortable |
| 2048×1024 | 2 097 152 | ~8 MB | Comfortable |
| 4096×2048 | 8 388 608 | ~32 MB | Per field; many simultaneous fields + intermediates + Python overhead can pressure 8 GB |

**Planning decision (provisional, finalize in Milestone 5 benchmarks):**

- Develop default / debug on **2048×1024** (or fast mode 512×256 / 1024×512).
- Attempt **4096×2048** only with staged allocation, disk-backed intermediates, and explicit memory budgets.
- Do **not** lock production resolution until Milestone 5 acceptance is measured on both Windows (release target) and this Mac.

### 4.4 Godot ↔ Python boundary

- Dev: Godot launches `python3.12 -m worldsim ...`.
- Packaged: frozen `worldsim_worker` / `.exe`; users must not need system Python.
- Protocol and progress reporting belong in Milestone 0; atlas UI in Milestone 17.

---

## 5. True conflicts / gaps found during inspection

These are not philosophy debates; they are concrete repo/environment gaps:

1. **Empty product tree** — architecture assumes `godot/` + `worldsim/`; only docs + engine binary exist.
2. **Godot.app inside project root** — convenient locally, toxic for git/size; must be gitignored or moved before first commit.
3. **Folder name has a space** (`Conworld History`) — fine for Cursor; watch quoting in scripts/CI paths.
4. **Windows Build Tools absent here** — expected on macOS; Windows packaging/CI remains a release gate (§4 primary platform).
5. **No CI yet** — Milestone 18 / earlier regression milestones need GitHub Actions (or equivalent) for Windows builds.
6. **8 GB RAM vs 4096×2048 target** — potential conflict with architecture aspiration; resolve via Milestone 5 benchmarks + optional ADR if production falls back to 2048×1024.
7. **System `python3` is 3.9.6** — agents/scripts must call **`python3.12` explicitly**, not bare `python3`.

No conflict found with the core invariant: hex is analytical cache, not world geometry.

---

## 6. Milestone sequence (execute one at a time)

Source: architecture §62. Each milestone ends with acceptance checks and a stop for human review.

### Milestone 0 — repository and environment foundation

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone0.md`

**Delivered:** `worldsim/` skeleton; pinned deps (`pyproject.toml` + `requirements.lock`); CLI worker; config loader; deterministic seeds; NDJSON progress protocol; pytest suite; `.gitignore` (includes `Godot.app`); licensing stubs (`THIRD_PARTY_NOTICES.md`, `licenses/`).

**Acceptance:** worker launches; progress protocol valid; seed manifest deterministic — **met** (12 tests passed + smoke dry-run).

**Stop after this milestone unless told to continue.**

### Milestone 1 — coordinate system and spatial substrate

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone1.md`

**Delivered:** `worldsim.spatial` package (`coordinates.py`, `extent.py`); cylindrical equal-area helpers; E–W wrap; no N–S wrap; latitude ↔ `y=sin(lat)`; `SpatialExtent` grid index model; tests. Root `worldsim/coordinates.py` is a compatibility shim.

**Acceptance:** coordinate round-trips; pole/equator mapping; wrap behaviour — **met** (29 tests passed).

**Stop after this milestone unless told to continue.**

### Milestone 2 — PyPlatec baseline

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone2.md`

**Delivered:** upstream `pyplatec==1.4.3` integration; 1024×512 height/plate maps; E–W seam selection + roll; diagnostics; CLI `--stage tectonics`; tests (including slow 1024×512).

**Acceptance:** deterministic; seam consistent; no final N–S model connectivity — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 3 — extended PyPlatec

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone3.md` and `docs/ADR/ADR-0001-vendored-pyplatec-extended-bindings.md`

**Delivered:** `vendor/pyplatec` fork with extended bindings; crust age + plate velocity/speed rasters; stable fallback object; macOS build verified; Windows build script; tests.

**Acceptance:** metadata accessible; observational height/plate maps unchanged vs baseline path — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 4 — tectonic interpretation

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone4.md`

**Delivered:** Stage B fields (boundaries, normals, relative motion, classes, activity/orogeny/volcanic/seismic proxies); cylindrical distance-to-boundary; pipeline integration after extended PyPlatec; tests including synthetic convergent/divergent cases.

**Acceptance:** expected spatial correlations — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 5 — high-resolution terrain and ocean

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone5.md` and `ADR-0002`

**Delivered:** terrain refinement; benchmark 4096×2048 vs 2048×1024; sea-level calibration to ocean fraction; bathymetry; water bodies; coastline vector prototype; production resolution locked to **4096×2048**.

**Acceptance:** benchmark-justified resolution; limited E–W seam artefact; coast retained independently of hex — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 6 — base seasonal climate

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone6.md`

**Delivered:** monthly insolation; latitude from equal-area Y; `temperature_c[12,y,x]`; lapse rate; land/ocean thermal inertia + continentality; climate grid from config (1024×512).

**Acceptance:** seasonal inversion; polar/elevation temperature trends — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 7 — atmosphere

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone7.md`

**Delivered:** pressure proxy; monthly `wind_u`/`wind_v`; Hadley/subtropical/Ferrel/polar zones; Coriolis; topographic perturbation; CLI `--stage atmosphere`.

**Acceptance:** coherent fields; trades easterly, Ferrel westerly, polar easterly; ITCZ migrates — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 8 — ocean circulation

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone8.md`

**Delivered:** monthly `current_u`/`current_v`; basin constraints; western/eastern boundary currents; SST; coastal climate coupling; CLI `--stage ocean`.

**Acceptance:** no land crossing; coherent circulation — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 9 — moisture and precipitation

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone9.md`

**Delivered:** evaporation; downwind advection; orographic precip + rain shadows; convection; monthly precip/humidity; CLI `--stage moisture`.

**Acceptance:** downwind transport; windward/leeward effect; Earth-like wet/dry tendencies — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 10 — erosion pass one

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone10.md`

**Delivered:** climate-informed erosion; high-res DEM v1; before/after diagnostics; CLI `--stage erosion`.

**Acceptance:** drainage quality improves; tectonic macro-relief preserved — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 11 — PyFlwDir hydrology

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone11.md`

**Delivered:** DEM conditioning; flow direction/accumulation; basins; river mask; Strahler; discharge (annual + monthly); lakes; CLI `--stage hydrology`; `pyflwdir==0.5.12` dependency.

**Acceptance:** valid drainage graph; sensible accumulation downstream — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 12 — canonical vector physical geography

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone12.md`

**Delivered:** coastline vectors; river node/segment network + polylines; lake polygons; basin metadata; spatial indexes; CLI `--stage vectors`.

**Acceptance:** raster/vector consistency; river topology valid; hex-independent persistence — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 13 — second erosion and final physical recalculation

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone13.md`

**Delivered:** fluvial erosion; terrain DEM v2; climate correction; final hydrology + vectors; CLI `--stage final`.

**Acceptance:** stable final geography; no catastrophic feedback — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 14 — soils and Holdridge ecology

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone14.md`

**Delivered:** permeability; soil depth/moisture/fertility/erosion-risk proxies; biotemperature; PET ratio; Holdridge zones + overrides; CLI `--stage ecology`.

**Acceptance:** every land/classifiable cell has valid ecological state or explicit override — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 15 — 256×128 analytical hex grid

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone15.md`

**Delivered:** flat-top equal-area placement; aggregation caches; neighbourhood; river/lake/coast refs; optional `river_edge_mask`; CLI `--stage hex`.

**Acceptance:** exactly 32 768 cells; E–W wrap; no N–S wrap; cache vs raster within tolerance — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 16 — WorldSpatialModel persistence and queries

**Status:** ✅ **COMPLETE** (2026-08-14) — see `docs/validation/milestone16.md`

**Delivered:** raster/vector/hex stores; `manifest.json`; load/save; query API; `WORLD_MODEL_SCHEMA_VERSION`; CLI `--stage world`.

**Acceptance:** round-trip preserves world; queries without Godot; caches rebuildable — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 17 — Godot atlas

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone17.md`

**Delivered:** `godot/` project (4.7); worker launch + progress UI; raster/vector display; optional hex overlay; map modes; inspector; monthly controls; `atlas_display` export.

**Acceptance:** detailed world without hexification; hex toggle does not alter geography; river/hex click inspection — **met**.

**Stop after this milestone unless told to continue.**

### Milestone 18 — packaging

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone18.md`

**Delivered:** PyInstaller onedir `worldsim_worker` (Windows script + macOS attempt); Godot packaged-worker launch; GitHub Actions CI; licence notices; ADR-0003.

**Acceptance:** Windows path requires no user Python (packaged EXE); generation works from packaged CLI; macOS arm64 smoke OK — **met** (Windows artefact via CI/local VS build scripts).

**Stop after this milestone unless told to continue.**

### Milestone 19 — environmental timeline scaffold

**Status:** ✅ **COMPLETE** (2026-08-15) — see `docs/validation/milestone19.md`

**Delivered:** `EnvironmentTimeline` interface; baseline snapshot; anomaly schema; time-indexed queries via `year=` on the same spatial API; persisted under `world/timeline/environment/`.

**Acceptance:** baseline vs time-indexed modifiers through one query surface; WorldSpatialModel not redesigned for yearly raster dumps — **met**.

**Stop after this milestone unless told to continue.**

---

## 7. Out of scope (do not implement under this plan)

From architecture §63:

population, culture, language, technology, religion, settlement hierarchy, trade, states, war, collapse, political borders, historical narrative.

These wait for `HISTORY_SIMULATION_ARCHITECTURE.md`.

---

## 8. Agent operating rules for subsequent sessions

### MUST

- Read this plan + `WORLDGEN_ARCHITECTURE.md` before coding.
- Implement **only the requested milestone**.
- Preserve raster/vector canonical data; treat hex as derived cache.
- Keep physical simulation runnable without Godot.
- Pin dependency versions; add tests/diagnostics per stage.
- Prefer ADRs for major deviations (§61).

### MUST NOT

- Implement Milestones 0–19 in one command/session unless explicitly ordered milestone-by-milestone.
- Discard high-res terrain after hex aggregation.
- Make TileMap / Godot the world database.
- Use bare `python3` on this Mac (use `python3.12`).
- Commit `Godot.app`, `.DS_Store`, secrets, or large binary dumps.

### Recommended next human instruction

Physical World plan milestones **0–19** are complete.

**Atlas UX follow-up** is specified in [`docs/ATLAS_UX_PLAN.md`](ATLAS_UX_PLAN.md) (**A1–A5** complete).  
Do not start an A-milestone unless the human explicitly names it.

Example:

> Atlas UX A1–A8 complete. Further atlas work only when explicitly named.

---

## 9. Definition of “ready to start coding”

Milestone 19 is complete. The IMPLEMENTATION_PLAN sequence for Physical World v1 is finished.

- Do not continue into `HISTORY_SIMULATION_ARCHITECTURE.md` unless explicitly requested.
- Atlas polish work uses **`docs/ATLAS_UX_PLAN.md`**, one A-milestone at a time (currently through **A8**).

**Physical World v1 Done** remains as defined in architecture §68; this plan is the path to that Done state, not the Done state itself.
