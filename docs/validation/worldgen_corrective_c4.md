# Worldgen corrective C4 — conservative atmospheric moisture transport

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; **no precip/transport retune**)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md) §6 C4  
**Depends on:** C0  
**Audited commit before this package:** post-C3T working tree

---

## Delivered

| Item | Location |
|---|---|
| Shared E–W / N–S face-flux donor-cell advection (`m = q × area`) | `moisture/transport.py` `_face_flux_advect` |
| Conservative 4-face diffusion (no N–S wrap / polar leak) | `_diffuse_moisture` |
| 2-D CFL `|Cx|+|Cy| ≤ 0.9`; cap exceeded → fail-closed | `_cfl_substeps` / `MoistureTransportError` |
| Clip of negatives recorded as explicit sink | `advect_clip_mass` in monthly budget |
| `advect_max_substeps` + legacy `advect_steps` | YAML, `PlanetConfig`, `MoistureParams`, Godot dump |
| Topographic wind uses the same (east, north) slope as lift | `apply_topographic_perturbation` |
| Honest precip demand / allocated / available | `partition_precipitation` + month budget |
| Field spin-up gates (L2 `q`, p99 `q`, L1 store, annual precip) | `build_monthly_moisture` |
| Production spin-up cap **48** years with early stop | `default_planet.yaml` / Godot dump |
| M2 warm-start from M1 `q` + land-store | `final/pipeline.py` |
| Tests | `tests/test_worldgen_corrective_c4.py` |

Budget stamp: `moisture_budget_spinup_v5_c4`. Advection stamp: `face_flux_cfl_v1`.

Frozen comparison values (not retuned): `orographic_frac=0.85`, `large_scale_frac=0.15`, `advect_wind_scale=0.2`, `convective_scale=2.0`, `ocean_evap_rate=1.4`, `plume_strength=0.18`, `advect_max_substeps=32`.

---

## Numerical contract

- One flux per shared face; equal-and-opposite updates; E–W wrap; **no** N–S wrap.
- Polar faces: north face of `j=0` and south face of `j=h-1` are zero.
- Courant numbers are **never** clipped. If the 2-D CFL needs more substeps than `advect_max_substeps`, the solver raises `MoistureTransportError` with `advect_cfl_month_2d` / `advect_substeps_required`.
- `advect_max_substeps` is a numerical safety cap, not physical transport reach. Legacy YAML key `advect_steps` is an alias; `advect_max_substeps` wins when both are present.
- Production default **32** is unchanged.

### Topographic sign

`orographic_lift` remains `u·sx − v·sy` with `sy = d_elev/d_south`. Wind perturbation now uses slope `(east, north) = (sx, −sy)`, so blocking/diversion matches lift. Northward wind on an E–W ridge is windward on the **south** face.

---

## Moisture budget (each month)

```text
storage_start
+ ocean evaporation
+ fractional lake evaporation
+ fractional river evaporation
+ water-limited land ET
− convective / large-scale / orographic / ITCZ (partitioned, sum = total precip)
− capacity_sink
− advect_clip_mass
= storage_end + numerical_residual
```

Relative residual gate: `max_month_residual_rel ≤ 1e-6`. Moisture `acceptance_ok` requires spin-up **and** this budget gate.

`max_precip_overshoot` is `max(allocated − q_pre_removal)`, not the previous tautology `max(precip − (q_after + precip))`.

---

## Spin-up

Hard field gates (not YAML precip knobs):

| Gate | Threshold |
|---|---:|
| relative L2 `q` | 0.5% |
| p99 `\|Δq\|` / mean `q` | 2% |
| relative L1 land-store | 1% |
| relative L2 annual precip vs previous year | 0.5% |

Maximum cell change is a **warning** (`spinup_max_cell_warning`). Annual precip must be compared across two years, so a 1-year cap cannot pass.

Production YAML cap is **48** years with early stop. `MoistureParams.spinup_max_years` default remains **4** for fixtures that do not load YAML.

M2 hydrology moisture is warm-started from the last month of M1 `q` and land-store.

---

## Acceptance

| Criterion | Result |
|---|---|
| Transport-only closed fixture, relative mass ≤ 1e-10 float64 | PASS |
| Accounted monthly budget, relative residual ≤ 1e-6 | PASS |
| Four-direction impulse + E–W seam; no N–S wrap | PASS (existing PR-4 + C4 extras) |
| Raising the substep cap (CFL already satisfied) stays within 15% land-mean precip | PASS |
| N/S ridge lift and topographic-wind orientation | PASS |
| CFL over cap fails closed (no Courant clip) | PASS |
| No `orographic_frac` / `large_scale_frac` / `advect_wind_scale` / plume retune | PASS |
| `pytest -m "not slow"` | PASS — 341 passed, 3 deselected |
| Atlas seed `183716` reaches the production spin-up gate | **Leftover** — not regenerated this package |

---

## Explicitly not done

- Atlas `183716` regen (spin-up on the production profile is unmeasured here)
- Transport / precipitation calibration (`advect_wind_scale`, `orographic_frac`, `large_scale_frac`, …) — **C5**
- Default `plume_strength=0` experiment (addendum: after advection is calibrated)
- Monsoon retune — **C5**

**Decision:** accept C4 correctness; stop. Next when instructed: **C5** only. Atlas 183716 spin-up remains an honest leftover until regen.
