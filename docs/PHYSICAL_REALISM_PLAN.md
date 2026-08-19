# Physical Realism Plan — operational tracker

> **Status:** **PR-0–PR-9 foundation delivered**; **CR-0–CR-9** baseline implemented — **correction required** ([`WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md)).  
> **Authority:** [`docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) (design) + corrections doc + addendum (production defects / repair order).  
> **Rule:** One milestone at a time. Validate → stop.  
> **Next when instructed:** **C10 calibration** (structural PC0–PC7 + pre-C10 repairs delivered; user acceptance required). Do not retune defaults without C10 grid.

---

## 0. Purpose

This document is the **execution index** for scientific hardening of the physical world after Physical World v1 (M0–19) and Atlas Plan B (B1–B7 + hydro UX follow-up).

- Full design, algorithms, acceptance, and prohibitions live in the annex.
- **Post–PR-9 production gaps** and the repair sequence live in [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md).
- **C9.1 production closure** (blocks C10) lives in [`WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) — **implemented on fixtures**; successor: [`WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) (**PC0–PC7**).
- This tracker records order, status, and **conflicts** with earlier plans.
- Atlas presentation work (**B10**) may proceed independently of PR/CR physics when explicitly requested.

---

## 1. Document authority

| Document | Role after annex |
|---|---|
| `WORLDGEN_ARCHITECTURE.md` | Baseline architecture; annex amends physical correctness where conflicted |
| `IMPLEMENTATION_PLAN.md` | M0–19 historical record (complete); points here for realism follow-up |
| `ATLAS_PLAN_B.md` | Atlas UX B1–B7 done; **B8/B9 mechanisms and order amended** by annex |
| `WORLDGEN_PHYSICAL_REALISM_ANNEX.md` | Normative corrective design + PR-0…PR-9 sequence |
| `PHYSICAL_REALISM_CORRECTIONS.md` | Post–PR-9 defect register + **CR-0…CR-9** repair order |
| `WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md` | Post–CR-9 production repairs **C0…C9**; C10 blocked |
| `WORLDGEN_CORRECTIVE_C91_ADDENDUM.md` | **C9.1** production closure (routing, storage, BiomeV2, terminals, landforms, `acceptance_ok`); precedence until closed |
| This file | Living status + conflict register + next milestone |

Where the annex identifies a demonstrated correctness problem, its corrective requirement **takes precedence** over an earlier qualitative “milestone complete” acceptance statement. Where the **corrections** document shows production failure of an accepted PR, the CR track **takes precedence** until the defect is closed. Unrelated architectural decisions remain valid.

---

## 2. Conflict register (explicit)

| ID | Earlier statement | Annex / corrections resolution |
|---|---|---|
| C-01 | Plan B next = **B8** immediately after B7 | **Resolved.** Revised B8 = **PR-7**; revised B9 = **PR-8**. |
| C-02 | B8 soft plume may add distance-to-ocean precip contribution | **Resolved (PR-7).** Plume mixes existing `q` inside budget (D-08). Production wire: see **F-02** / **CR-1**. |
| C-03 | B9 optional light precip boost as peer mechanism | **Resolved (PR-8) scaffolding.** Production monsoon **partial CR-8 / F-07** (Atlas leftover). |
| C-04 | Plan B §8: “fully physically conserved water budget” out of scope | **Superseded** P0 (annex §10). Production spin-up **partial CR-8 / F-03** (Atlas leftover). |
| C-05 | Plan B: “prefer shallow hooks; do not reopen M0–19” | Softened: **scientific-hardening follow-ups** to M6/9/11/13 modules are in scope; **not** a full generator rewrite. |
| C-06 | B7 + §6.3.1 transmission / flow layer = Nil/wadi done | PET×12 + liquid mask ✅ **CR-6**; soil/Q m³/s/km ✅ **CR-7**. |
| C-07 | Every Lake `closed_basin=True`; fill-all depressions | Finite fill CR-4; land-outlet vs closed ✅ **CR-6**. |
| C-08 | Cell-based climate scales (`*_cells`) as permanent params | Godot omits `continentality_scale_km` (**F-19**, closed CR-6); `advect_steps` is CFL cap (**CR-8**); erosion metric slope (**CR-9**). |
| C-09 | Single max land normalisation / every seed hits `land_scale_m` | **power_tail_v2** production default (**CR-5**); `tail_softness` real (**F-12**). |
| C-10 | Moisture #2 labeled as if it caused hydrology | Provenance split: `moisture_hydrology_input` vs `moisture_ecology` (D-13); diagnostics must not mislabel. |
| C-11 | PR-0…PR-9 “complete” ⇒ production-ready climate | **Superseded.** CR-0…CR-9 baseline + C0…C9 delivered; **C9.1** required before C10. |

---

## 3. Dependency graph (normative)

```text
PR-0 … PR-9   Foundation (delivered; see honest status in corrections §6)
  → CR-0  CI + harness honesty
  → CR-1  Parameter propagation + acceptance honesty
  → CR-2  GridMetrics / subgrid transpose / cell→km leftovers
  → CR-3  Moisture closure + SST anomaly + monsoon regime   ← HARD GATE
  → CR-4  Monthly hydrology + typed outlets / endorheism     ← HARD GATE
  → CR-5  Joint calibration — hypsometry accepted; landforms reopened
  → CR-6  Hydrology hotfix (PET, outlets, liquid mask, Godot km)  BASELINE — CORRECTION REQUIRED
  → CR-7  Light hydrology v2  BASELINE — CORRECTION REQUIRED
  → CR-8  Atmosphere (conservative advect, monsoon, one hydro↔evap pass)  BASELINE — CORRECTION REQUIRED
  → CR-9  Erosion / landforms / BiomeV2  BASELINE — CORRECTION REQUIRED
  → C0  Product-contract hotfixes  ✅
  → C1  Lake geometry from storage  ✅
  → C2  Rivers, channel losses, bounded coupling  ✅
  → C3  Metric erosion recalibration  ✅
  → C3T Temperature-state integrity  ✅
  → C4  Conservative moisture transport  ✅
  → C5  Precipitation mechanisms / monsoon  ✅
  → C6  BiomeV2 correctness  ✅
  → C7  Landform scales / classes / objects  ✅
  → C8  Canonical WorldSpatialModel / hex / query  ✅
  → C9  Godot BiomeV2 / landform modes  ✅
  → C9.1 Production closure (lake routing, periodic storage, BiomeV2, terminals, landforms, acceptance)  ← NEXT
       C9.1.1 lake-aware routing
       C9.1.2 periodic runoff / storage
       C9.1.3 river terminals
       C9.1.4 BiomeV2 NON_GROWING / wetland
       C9.1.5 plateau interior/rim + range split
       C9.1.6 canonical acceptance_ok
  → C10 Multi-seed calibration / Full RSS / release decision  **BLOCKED** until C9.1

Parallel (atlas presentation only, when requested):
  B10  Full-resolution land polygons  — no PR/CR dependency
```

Corrected physical derivation order (annex §6) remains authoritative for pipeline work.

---

## 4. Milestone status

### 4.1 Foundation (PR-0…PR-9)

| ID | Title | Status | Validation note |
|---|---|---|---|
| PR-0 | Baseline and regression harness | ✅ Foundation | [`docs/validation/physical_realism_pr0.md`](validation/physical_realism_pr0.md) |
| PR-1 | GridMetrics + analytical hex geometry | ⚠️ Partial | [`docs/validation/physical_realism_pr1.md`](validation/physical_realism_pr1.md) |
| PR-2 | Hypsometry `power_tail_v2` | ✅ Production default (CR-5) | [`docs/validation/physical_realism_pr2.md`](validation/physical_realism_pr2.md) |
| PR-3 | Temperature periodic response + km scales | ⚠️ Partial | [`docs/validation/physical_realism_pr3.md`](validation/physical_realism_pr3.md) |
| PR-4 | Moisture correctness core | ⚠️ Partial in production | [`docs/validation/physical_realism_pr4.md`](validation/physical_realism_pr4.md) |
| PR-5 | Canonical cylindrical hydrology graph | ✅ Strongest | [`docs/validation/physical_realism_pr5.md`](validation/physical_realism_pr5.md) |
| PR-6 | Effective runoff, wadis, endorheic, lakes | ⚠️ Partial in production | [`docs/validation/physical_realism_pr6.md`](validation/physical_realism_pr6.md) |
| PR-7 | Revised B8 (Plan B moisture v2) | ⚠️ Partial | [`docs/validation/physical_realism_pr7.md`](validation/physical_realism_pr7.md) |
| PR-8 | Revised B9 (Plan B monsoon) | ⚠️ Partial | [`docs/validation/physical_realism_pr8.md`](validation/physical_realism_pr8.md) |
| PR-9 | LandformAnalysis foundation | ⚠️ 9A–D + 9E thresholds (CR-5); Godot leftover | [`docs/validation/physical_realism_pr9.md`](validation/physical_realism_pr9.md) |

Detail: annex §§7–19. Production defects: corrections §3 (F-01…).

### 4.2 Corrections (CR-0…CR-9)

| ID | Title | Status | Validation note |
|---|---|---|---|
| CR-0 | CI + harness honesty | ✅ Complete | [`docs/validation/physical_realism_cr0.md`](validation/physical_realism_cr0.md) |
| CR-1 | Parameter propagation + acceptance honesty | ✅ Complete | [`docs/validation/physical_realism_cr1.md`](validation/physical_realism_cr1.md) |
| CR-2 | GridMetrics / subgrid / km leftovers | ✅ Complete | [`docs/validation/physical_realism_cr2.md`](validation/physical_realism_cr2.md) |
| CR-3 | Moisture + SST anomaly + monsoon | ⚠️ Fixtures OK; production reopened | [`docs/validation/physical_realism_cr3.md`](validation/physical_realism_cr3.md) |
| CR-4 | Monthly hydro + endorheism | ⚠️ Fixtures OK; PET×12 / lakes reopened | [`docs/validation/physical_realism_cr4.md`](validation/physical_realism_cr4.md) |
| CR-5 | Joint calibration (+ PR-9E) | ⚠️ Hypsometry OK; landforms reopened | [`docs/validation/physical_realism_cr5.md`](validation/physical_realism_cr5.md) |
| CR-6 | Hydrology hotfix | BASELINE — CORRECTION REQUIRED | [`docs/validation/physical_realism_cr6.md`](validation/physical_realism_cr6.md) |
| CR-7 | Light hydrology v2 | BASELINE — CORRECTION REQUIRED | [`docs/validation/physical_realism_cr7.md`](validation/physical_realism_cr7.md) |
| CR-8 | Atmosphere (advect / lee / monsoon) | BASELINE — CORRECTION REQUIRED | [`docs/validation/physical_realism_cr8.md`](validation/physical_realism_cr8.md) |
| CR-9 | Erosion, landforms, BiomeV2 | BASELINE — CORRECTION REQUIRED | [`docs/validation/physical_realism_cr9.md`](validation/physical_realism_cr9.md) |
| C0 | Product-contract hotfixes | ✅ Complete | [`docs/validation/worldgen_corrective_c0.md`](validation/worldgen_corrective_c0.md) |
| C1 | Lake geometry from storage | ✅ Complete | [`docs/validation/worldgen_corrective_c1.md`](validation/worldgen_corrective_c1.md) |
| C2 | Rivers, channel losses, bounded coupling | ✅ Complete | [`docs/validation/worldgen_corrective_c2.md`](validation/worldgen_corrective_c2.md) |
| C3 | Metric erosion recalibration | ✅ Complete (defaults not retuned) | [`docs/validation/worldgen_corrective_c3.md`](validation/worldgen_corrective_c3.md) |
| C3T | Temperature-state integrity | ✅ Complete (gain default 0) | [`docs/validation/worldgen_corrective_c3t.md`](validation/worldgen_corrective_c3t.md) |
| C4 | Conservative moisture transport | ✅ Complete (Atlas spin-up leftover) | [`docs/validation/worldgen_corrective_c4.md`](validation/worldgen_corrective_c4.md) |
| C5 | Precipitation mechanisms / monsoon | ✅ Complete (YAML knobs not retuned) | [`docs/validation/worldgen_corrective_c5.md`](validation/worldgen_corrective_c5.md) |
| C6 | BiomeV2 correctness / canonical integration | ✅ Complete (Holdridge annual unchanged) | [`docs/validation/worldgen_corrective_c6.md`](validation/worldgen_corrective_c6.md) |
| C7 | Landform scales / classes / objects | ✅ Complete (threshold 0.60 not retuned) | [`docs/validation/worldgen_corrective_c7.md`](validation/worldgen_corrective_c7.md) |
| C8 | Canonical WorldSpatialModel / hex / query / export | ✅ Complete (Godot display leftover → C9) | [`docs/validation/worldgen_corrective_c8.md`](validation/worldgen_corrective_c8.md) |
| C9 | Godot BiomeV2 / landform modes / legends / inspector | ✅ Complete (Fit/4× leftover until regen) | [`docs/validation/worldgen_corrective_c9.md`](validation/worldgen_corrective_c9.md) |
| C9.1 | Production closure (fixtures) | ⚠️ Implemented on fixtures — PC required | [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) |
| PC0 | Baseline + failing regressions | ✅ Complete | [`docs/validation/worldgen_pc0.md`](validation/worldgen_pc0.md) |
| PC1 | Lake-supernode + monthly router | ✅ Complete | [`docs/validation/worldgen_pc1.md`](validation/worldgen_pc1.md) |
| PC2 | Periodic storage + 3-tier networks | ✅ Complete | [`docs/validation/worldgen_pc2.md`](validation/worldgen_pc2.md) |
| PC3 | G0 snow/soil/firn | ✅ Complete | [`docs/validation/worldgen_pc3.md`](validation/worldgen_pc3.md) |
| PC4 | Geomorphic erosion + gates | ✅ Complete | [`docs/validation/worldgen_pc4.md`](validation/worldgen_pc4.md) |
| PC5 | Landform systems + acceptance | ✅ Complete | [`docs/validation/worldgen_pc5.md`](validation/worldgen_pc5.md) |
| PC6 | Products + Godot + inspector | ✅ Complete | [`docs/validation/worldgen_pc6.md`](validation/worldgen_pc6.md) |
| PC7 | Production suite + C10 readiness | ✅ Complete | [`docs/validation/worldgen_pc7.md`](validation/worldgen_pc7.md) |
| C10 | Multi-seed calibration / Full RSS | **Blocked** — user review of PC7 readiness | addendum §12 |
| C11 | Cryosphere G1–G3 glaciation | **Deferred** after PC7/C10 | addendum §13 |

---

## 5. Mapping to Plan B labels

| Plan B | Realism track | Notes |
|---|---|---|
| B1–B7 + hydro UX | Baseline delivered | Remains; does not prove annex invariants |
| B8 | **= PR-7** after PR-4 | Production closure → **CR-1/CR-3** |
| B9 | **= PR-8** after PR-7 | Scaffolding CR-3; production monsoon **CR-8** (Atlas leftover) |
| B10 | Independent | Atlas Full land polys; may run anytime when instructed |

---

## 6. History coupling

Do **not** calibrate history against hex latitude / area aggregates until hex geometry leftovers in **CR-2** are accepted (annex §7.4). See `HISTORY_SIMULATION_ARCHITECTURE.md` §46 amendment.

Landforms (**PR-9** / **CR-5**) feed hex caches and `EnvironmentAdapter` later; history must not treat “mountain” as automatically impassable (annex §19).

---

## 7. Suggested human instructions

```text
Worldgen production closure PC0–PC7 complete. C10 only after user accepts readiness review.
```

PC2 delivered. C9.1 = implemented on fixtures. **C10 is blocked** until PC7 ([`WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md)). Do not retune precip, river LOD, mountain/plateau thresholds, or folding. Optional atlas **B10** remains independent presentation.

---

## 8. Traceability

| Source | Carried here |
|---|---|
| Annex §4 decision register D-01…D-16 | Binding |
| Annex §15 PR-0…PR-9 | Foundation sequence |
| Corrections F-01…F-21 / CR-0…CR-9 | Production repair |
| Production audit Atlas 183716 / 85ea366 | Reopened hydro + moisture |
| Annex §20 traceability matrix | Requirement IDs |
| Audit commit `6a96116…` | Baseline for harness |
| Production audit 2026-08-17 (Quick 1/42/100) | Corrections evidence |
