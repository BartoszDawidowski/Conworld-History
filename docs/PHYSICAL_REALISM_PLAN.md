# Physical Realism Plan — operational tracker

> **Status:** **PR-0–PR-9 complete** (2026-08-16; PR-9 = foundation 9A–9D, 9E deferred).  
> **Authority:** [`docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`](WORLDGEN_PHYSICAL_REALISM_ANNEX.md) (accepted design).  
> **Rule:** One **PR-N** milestone at a time. Validate → `docs/validation/physical_realism_prN.md` → stop.  
> **Next when instructed:** **B10** (atlas Full land polys) or PR-9E calibration / Godot landform display.

---

## 0. Purpose

This document is the **execution index** for scientific hardening of the physical world after Physical World v1 (M0–19) and Atlas Plan B (B1–B7 + hydro UX follow-up).

- Full design, algorithms, acceptance, and prohibitions live in the annex.
- This tracker records order, status, and **conflicts** with earlier plans.
- Atlas presentation work (**B10**) may proceed independently of PR physics when explicitly requested.

---

## 1. Document authority

| Document | Role after annex |
|---|---|
| `WORLDGEN_ARCHITECTURE.md` | Baseline architecture; annex amends physical correctness where conflicted |
| `IMPLEMENTATION_PLAN.md` | M0–19 historical record (complete); points here for realism follow-up |
| `ATLAS_PLAN_B.md` | Atlas UX B1–B7 done; **B8/B9 mechanisms and order amended** by annex |
| `WORLDGEN_PHYSICAL_REALISM_ANNEX.md` | Normative corrective design + PR-0…PR-9 sequence |
| This file | Living status + conflict register + next milestone |

Where the annex identifies a demonstrated correctness problem, its corrective requirement **takes precedence** over an earlier qualitative “milestone complete” acceptance statement. Unrelated architectural decisions remain valid.

---

## 2. Conflict register (explicit)

| ID | Earlier statement | Annex resolution |
|---|---|---|
| C-01 | Plan B next = **B8** immediately after B7 | **Resolved.** Revised B8 = **PR-7** ✅; revised B9 = **PR-8**. |
| C-02 | B8 soft plume may add distance-to-ocean precip contribution | **Resolved (PR-7).** Plume mixes existing `q` inside budget (D-08). |
| C-03 | B9 optional light precip boost as peer mechanism | **Resolved (PR-8).** Monsoon is transport-first wind anomaly; no precip belt (D-09). |
| C-04 | Plan B §8: “fully physically conserved water budget” out of scope | **Superseded** for atmospheric moisture: budget closure is **P0** (annex §10). Channel water remains a reduced-order proxy. |
| C-05 | Plan B: “prefer shallow hooks; do not reopen M0–19” | Softened: **scientific-hardening follow-ups** to M6/9/11/13 modules are in scope; **not** a full generator rewrite. |
| C-06 | B7 + §6.3.1 transmission / flow layer = Nil/wadi done | **Done (PR-5/PR-6).** Canonical cylindrical graph + Q-aware mask extinction without downstream inheritance + monthly losses. |
| C-07 | Every Lake `closed_basin=True`; fill-all depressions | **Done (PR-6).** Explicit open / endorheic / playa / frozen + inlet/outlet metadata. |
| C-08 | Cell-based climate scales (`*_cells`) as permanent params | Migrate to **km** via GridMetrics (**PR-1**); silent reinterpretation forbidden. |
| C-09 | Single max land normalisation / every seed hits `land_scale_m` | **power_tail_v2** (**PR-2**); folding frozen during that work (D-01). |
| C-10 | Moisture #2 labeled as if it caused hydrology | Provenance split: `moisture_hydrology_input` vs `moisture_ecology` (D-13); diagnostics must not mislabel. |

---

## 3. Dependency graph (normative)

```text
PR-0  Baseline harness
  → PR-1  GridMetrics + balanced hex geometry
  → PR-2  Hypsometry power_tail_v2 (+ robust detail scale)
  → PR-3  Temperature periodic response + physical scales
  → PR-4  Moisture correctness gate   ← HARD GATE before B8/B9
  → PR-5  Canonical cylindrical hydrology graph
  → PR-6  Runoff / wadis / endorheic / lake metadata
  → PR-7  Revised B8 (plume + recycling + ITCZ in budget)
  → PR-8  Revised B9 (monsoon transport-first)
  → PR-9  LandformAnalysis (9A–9E as needed)

Parallel (atlas presentation only, when requested):
  B10  Full-resolution land polygons  — no PR dependency
```

Corrected physical derivation order (annex §6) remains authoritative for pipeline work.

---

## 4. Milestone status

| ID | Title | Status | Validation note |
|---|---|---|---|
| PR-0 | Baseline and regression harness | ✅ Complete | [`docs/validation/physical_realism_pr0.md`](validation/physical_realism_pr0.md) |
| PR-1 | GridMetrics + analytical hex geometry | ✅ Complete | [`docs/validation/physical_realism_pr1.md`](validation/physical_realism_pr1.md) |
| PR-2 | Hypsometry `power_tail_v2` | ✅ Complete | [`docs/validation/physical_realism_pr2.md`](validation/physical_realism_pr2.md) |
| PR-3 | Temperature periodic response + km scales | ✅ Complete | [`docs/validation/physical_realism_pr3.md`](validation/physical_realism_pr3.md) |
| PR-4 | Moisture correctness core | ✅ Complete | [`docs/validation/physical_realism_pr4.md`](validation/physical_realism_pr4.md) |
| PR-5 | Canonical cylindrical hydrology graph | ✅ Complete | [`docs/validation/physical_realism_pr5.md`](validation/physical_realism_pr5.md) |
| PR-6 | Effective runoff, wadis, endorheic, lakes | ✅ Complete | [`docs/validation/physical_realism_pr6.md`](validation/physical_realism_pr6.md) |
| PR-7 | Revised B8 (Plan B moisture v2) | ✅ Complete | [`docs/validation/physical_realism_pr7.md`](validation/physical_realism_pr7.md) |
| PR-8 | Revised B9 (Plan B monsoon) | ✅ Complete | [`docs/validation/physical_realism_pr8.md`](validation/physical_realism_pr8.md) |
| PR-9 | LandformAnalysis foundation | ✅ Complete (9A–9D; 9E deferred) | [`docs/validation/physical_realism_pr9.md`](validation/physical_realism_pr9.md) |

Detail, acceptance, and prohibitions: annex §§7–19 and §15.

---

## 5. Mapping to Plan B labels

| Plan B | Realism track | Notes |
|---|---|---|
| B1–B7 + hydro UX | Baseline delivered | Remains; does not prove annex invariants |
| B8 | **= PR-7** after PR-4 | Mechanisms amended (annex §10.7) |
| B9 | **= PR-8** after PR-7 | Mechanisms amended (annex §10.8) |
| B10 | Independent | Atlas Full land polys; may run anytime when instructed |

---

## 6. History coupling

Do **not** calibrate history against hex latitude / area aggregates until **PR-1** hex geometry is accepted (annex §7.4). See `HISTORY_SIMULATION_ARCHITECTURE.md` §46 amendment.

Landforms (**PR-9**) feed hex caches and `EnvironmentAdapter` later; history must not treat “mountain” as automatically impassable (annex §19).

---

## 7. Suggested human instructions

```text
Physical realism PR track complete through foundation PR-9.
Optional follow-ups when instructed: PR-9E calibration, Godot landform mode, or B10 (atlas Full land polys).
```

After PR-4:

```text
Physical realism: execute PR-7 (revised B8) only.
```

---

## 8. Traceability

| Source | Carried here |
|---|---|
| Annex §4 decision register D-01…D-16 | Binding |
| Annex §15 PR-0…PR-9 | Milestone sequence |
| Annex §20 traceability matrix | Requirement IDs |
| Audit commit `6a96116…` | Baseline for harness |
