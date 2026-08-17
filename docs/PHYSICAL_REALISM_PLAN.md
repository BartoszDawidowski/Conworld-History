# Physical Realism Plan — operational tracker

> **Status:** **PR-0–PR-9 foundation delivered**; **CR-0–CR-2 accepted**; next **CR-3** — [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md).  
> **Authority:** [`docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) (design) + corrections doc (production defects / repair order).  
> **Rule:** One milestone at a time. Validate → `docs/validation/physical_realism_{pr|cr}N.md` → stop.  
> **Next when instructed:** **CR-3** (moisture closure + SST anomaly + monsoon). Do not calibrate hypsometry/landforms until CR-3+CR-4. Optional atlas: **B10**.

---

## 0. Purpose

This document is the **execution index** for scientific hardening of the physical world after Physical World v1 (M0–19) and Atlas Plan B (B1–B7 + hydro UX follow-up).

- Full design, algorithms, acceptance, and prohibitions live in the annex.
- **Post–PR-9 production gaps** and the repair sequence live in [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md).
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
| `PHYSICAL_REALISM_CORRECTIONS.md` | Post–PR-9 defect register + **CR-0…CR-5** repair order |
| This file | Living status + conflict register + next milestone |

Where the annex identifies a demonstrated correctness problem, its corrective requirement **takes precedence** over an earlier qualitative “milestone complete” acceptance statement. Where the **corrections** document shows production failure of an accepted PR, the CR track **takes precedence** until the defect is closed. Unrelated architectural decisions remain valid.

---

## 2. Conflict register (explicit)

| ID | Earlier statement | Annex / corrections resolution |
|---|---|---|
| C-01 | Plan B next = **B8** immediately after B7 | **Resolved.** Revised B8 = **PR-7**; revised B9 = **PR-8**. |
| C-02 | B8 soft plume may add distance-to-ocean precip contribution | **Resolved (PR-7).** Plume mixes existing `q` inside budget (D-08). Production wire: see **F-02** / **CR-1**. |
| C-03 | B9 optional light precip boost as peer mechanism | **Resolved (PR-8).** Monsoon is transport-first; regime bug **F-07** / **CR-3**. |
| C-04 | Plan B §8: “fully physically conserved water budget” out of scope | **Superseded** for atmospheric moisture: budget closure is **P0** (annex §10). Production spin-up: **F-03/F-04** / **CR-3**. |
| C-05 | Plan B: “prefer shallow hooks; do not reopen M0–19” | Softened: **scientific-hardening follow-ups** to M6/9/11/13 modules are in scope; **not** a full generator rewrite. |
| C-06 | B7 + §6.3.1 transmission / flow layer = Nil/wadi done | **PR-5/PR-6 scaffolding done; production endorheism reopened (F-08 / CR-4).** |
| C-07 | Every Lake `closed_basin=True`; fill-all depressions | **Types exist; fill-all still prevents real closed basins (F-08 / CR-4).** |
| C-08 | Cell-based climate scales (`*_cells`) as permanent params | Migrate to **km** via GridMetrics (**PR-1** partial); leftovers **F-11** / **CR-2**. |
| C-09 | Single max land normalisation / every seed hits `land_scale_m` | **power_tail_v2** (**PR-2**) implemented but **default off**; `tail_softness` no-op (**F-12**); calibrate in **CR-5**. |
| C-10 | Moisture #2 labeled as if it caused hydrology | Provenance split: `moisture_hydrology_input` vs `moisture_ecology` (D-13); diagnostics must not mislabel. |
| C-11 | PR-0…PR-9 “complete” ⇒ production-ready climate | **Superseded 2026-08-17.** Foundation complete; production hardening = **CR track**. |

---

## 3. Dependency graph (normative)

```text
PR-0 … PR-9   Foundation (delivered; see honest status in corrections §6)
  → CR-0  CI + harness honesty
  → CR-1  Parameter propagation + acceptance honesty
  → CR-2  GridMetrics / subgrid transpose / cell→km leftovers
  → CR-3  Moisture closure + SST anomaly + monsoon regime   ← HARD GATE
  → CR-4  Monthly hydrology + typed outlets / endorheism     ← HARD GATE
  → CR-5  Joint calibration (hypsometry, climate, landforms / 9E)

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
| PR-2 | Hypsometry `power_tail_v2` | ⚠️ Option only | [`docs/validation/physical_realism_pr2.md`](validation/physical_realism_pr2.md) |
| PR-3 | Temperature periodic response + km scales | ⚠️ Partial | [`docs/validation/physical_realism_pr3.md`](validation/physical_realism_pr3.md) |
| PR-4 | Moisture correctness core | ⚠️ Partial in production | [`docs/validation/physical_realism_pr4.md`](validation/physical_realism_pr4.md) |
| PR-5 | Canonical cylindrical hydrology graph | ✅ Strongest | [`docs/validation/physical_realism_pr5.md`](validation/physical_realism_pr5.md) |
| PR-6 | Effective runoff, wadis, endorheic, lakes | ⚠️ Partial in production | [`docs/validation/physical_realism_pr6.md`](validation/physical_realism_pr6.md) |
| PR-7 | Revised B8 (Plan B moisture v2) | ⚠️ Partial | [`docs/validation/physical_realism_pr7.md`](validation/physical_realism_pr7.md) |
| PR-8 | Revised B9 (Plan B monsoon) | ⚠️ Partial | [`docs/validation/physical_realism_pr8.md`](validation/physical_realism_pr8.md) |
| PR-9 | LandformAnalysis foundation | ⚠️ 9A–D partial; 9E deferred | [`docs/validation/physical_realism_pr9.md`](validation/physical_realism_pr9.md) |

Detail: annex §§7–19. Production defects: corrections §3 (F-01…).

### 4.2 Corrections (CR-0…CR-5)

| ID | Title | Status | Validation note |
|---|---|---|---|
| CR-0 | CI + harness honesty | ✅ Complete | [`docs/validation/physical_realism_cr0.md`](validation/physical_realism_cr0.md) |
| CR-1 | Parameter propagation + acceptance honesty | ✅ Complete | [`docs/validation/physical_realism_cr1.md`](validation/physical_realism_cr1.md) |
| CR-2 | GridMetrics / subgrid / km leftovers | ✅ Complete | [`docs/validation/physical_realism_cr2.md`](validation/physical_realism_cr2.md) |
| CR-3 | Moisture + SST anomaly + monsoon | ⬜ Next | — |
| CR-4 | Monthly hydro + endorheism | ⬜ | — |
| CR-5 | Joint calibration (+ PR-9E) | ⬜ blocked on CR-3/4 | — |

---

## 5. Mapping to Plan B labels

| Plan B | Realism track | Notes |
|---|---|---|
| B1–B7 + hydro UX | Baseline delivered | Remains; does not prove annex invariants |
| B8 | **= PR-7** after PR-4 | Production closure → **CR-1/CR-3** |
| B9 | **= PR-8** after PR-7 | Regime fix → **CR-3**; interim `monsoon_strength=0` |
| B10 | Independent | Atlas Full land polys; may run anytime when instructed |

---

## 6. History coupling

Do **not** calibrate history against hex latitude / area aggregates until hex geometry leftovers in **CR-2** are accepted (annex §7.4). See `HISTORY_SIMULATION_ARCHITECTURE.md` §46 amendment.

Landforms (**PR-9** / **CR-5**) feed hex caches and `EnvironmentAdapter` later; history must not treat “mountain” as automatically impassable (annex §19).

---

## 7. Suggested human instructions

```text
Physical realism corrections: execute CR-3 only.
```

Interim (until CR-3): keep `monsoon_strength=0.0`; do not raise `ocean_evap_rate` to “fix” dryness; do not enable default `power_tail_v2`.

Optional atlas:

```text
Atlas Plan B: execute B10 only.
```

---

## 8. Traceability

| Source | Carried here |
|---|---|
| Annex §4 decision register D-01…D-16 | Binding |
| Annex §15 PR-0…PR-9 | Foundation sequence |
| Corrections F-01…F-14 / CR-0…CR-5 | Production repair |
| Annex §20 traceability matrix | Requirement IDs |
| Audit commit `6a96116…` | Baseline for harness |
| Production audit 2026-08-17 (Quick 1/42/100) | Corrections evidence |
