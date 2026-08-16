# Physical Realism PR-4 — moisture correctness core

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §10 / §15 PR-4  
**Depends on:** PR-0…PR-3  
**Gate:** B8/B9 (**PR-7/PR-8**) remain blocked until this acceptance

---

## Delivered

| Item | Location |
|---|---|
| Corrected N–S upwind (`wind_v>0` → smaller `j`) | `physical/moisture/transport.py` `_upwind_advect` |
| Δt-scaled neighbour diffusion | `_diffuse_moisture` (`diffusion_mix_per_month`) |
| Precip partition capped by available `q` | `partition_precipitation` |
| Lee drying as explicit sink | `lee_sink` field + budget |
| Periodic annual spin-up (warm start) | `build_monthly_moisture` + `spinup_*` params |
| Budget / provenance diagnostics | `budget` dict → moisture diagnostics |
| Config knobs | `default_planet.yaml` + `PlanetConfig` / `MoistureParams` |
| Tests | `tests/test_physical_realism_pr4.py`; audit MOIST-01…03 now required |

Packaged moisture knobs (advect_steps, rainout fractions, evap rates) were **not** retuned — only correctness.

---

## Acceptance

| Criterion | Result |
|---|---|
| Four-direction impulse + E–W seam; no N–S wrap | PASS |
| Precip ≤ available `q`; components sum to total | PASS |
| Constant-climate January startup ramp removed | PASS |
| `advect_steps` 8 vs 32 within ~15% land-mean precip | PASS |
| Existing windward/leeward + wet/dry moisture tests | PASS |
| Audit MOIST-01…03 (was strict xfail) | PASS |

---

## Budget identity (monthly)

```text
storage_start + Σ sources − precipitation − lee_sink − capacity_sink
  = storage_end + numerical_residual
```

Sources: ocean / lake / river evaporation + land ET (mutually exclusive masks).

---

## Explicitly not done

- B8 plume / water-limited land store / ITCZ (**PR-7**)  
- B9 monsoon transport (**PR-8**)  
- Retuning Atlas moisture strengths after the correctness gate  

**Decision:** accept PR-4; stop. Next when instructed: **PR-5** (canonical cylindrical hydrology graph) — or **PR-7** only after explicit request (still after PR-5/6 in normative order).
