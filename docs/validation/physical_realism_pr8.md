# Physical Realism PR-8 — revised B9 (monsoon transport-first)

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §10.8 / §15 PR-8  
**Plan B:** Milestone B9 = this PR  
**Depends on:** PR-0…PR-7  

---

## Delivered

| Item | Location |
|---|---|
| Seasonal land–SST contrast → bounded onshore/offshore wind anomaly | `physical/atmosphere/monsoon.py` |
| Anomaly fed into moisture transport (not a precip belt) | `build_moisture` before `build_monthly_moisture` |
| Trades / base winds unchanged outside tropical coastal band | envelope × latitude band |
| Diagnostics (`b9_terms_active`, monthly onshore, ΔT) | moisture diagnostics |
| YAML + `MoistureParams` + Godot Advanced knobs | `default_planet.yaml`, `config.py`, `Main.gd` / `Main.tscn` |
| Tests | `tests/test_physical_realism_pr8.py` |

No standalone monsoon precip multiplier. Optional residual precip left at 0 (transport-only).

---

## Acceptance

| Criterion | Result |
|---|---|
| Seasonal onshore (summer) vs offshore (winter) contrast | PASS |
| Coastal moisture rises under onshore transport vs base trades | PASS |
| Trades / high-latitude winds coherent outside active band | PASS |
| Precip components still sum; budget residual bounded | PASS |
| `strength=0` identity | PASS |
| Existing moisture / atmosphere / config tests | PASS |

---

## Explicitly not done

- Full pressure-solver monsoon (approach C)  
- Standalone wet-belt without wind  
- PR-9 LandformAnalysis  

**Decision:** accept PR-8; stop. Next when instructed: **PR-9** (LandformAnalysis) or **B10** (atlas).
