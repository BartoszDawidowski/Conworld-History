# Physical Realism PR-7 — revised B8 (plume + recycling + ITCZ)

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §10.6–10.7 / §15 PR-7  
**Plan B:** Milestone B8 = this PR  
**Depends on:** PR-0…PR-6 (moisture gate PR-4)

---

## Delivered

| Item | Location |
|---|---|
| Soft inland plume (wind-aligned mix of existing `q`, mass-conserving) | `physical/moisture/transport.py` `soft_plume_mix` |
| Water-limited land ET via bounded land store | `evaporation_components` + store refill from precip |
| Non-duplicative ITCZ precip term (budget-capped) | `partition_precipitation` `itcz_precip` |
| Diagnostics: base convective vs ITCZ; interior/coast; B8 flag | moisture `budget` / diagnostics |
| YAML + `MoistureParams` + Godot Advanced knobs | `default_planet.yaml`, `config.py`, `Main.gd` / `Main.tscn` |
| Tests | `tests/test_physical_realism_pr7.py` |

Packaged advect/rainout/evap rates were **not** retuned — only new B8 knobs with modest defaults.

---

## Acceptance

| Criterion | Result |
|---|---|
| Interior reach improves with plume vs off | PASS |
| Strong rain shadow not erased by plume | PASS |
| Moisture budget closed (components sum; residual OK) | PASS |
| Wet-land ET ≫ desert ET at matched T | PASS |
| ITCZ seasonal peak moves (June north of December) | PASS |
| No independent post-hoc rain field | PASS |
| Existing moisture / PR-4 / ecology / final tests | PASS |

---

## Explicitly not done

- B9 / PR-8 monsoon transport-first wind anomaly  
- Retuning Atlas moisture strengths beyond new B8 defaults  
- Separate vapour/cloud reservoirs  

**Decision:** accept PR-7; stop. Next when instructed: **PR-8** (revised B9).
