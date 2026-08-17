# Physical Realism CR-1 — parameter propagation + acceptance honesty

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-1  
**Defects closed:** **F-02** (final moisture knob drop); partial **F-03** (acceptance ignores spin-up); partial **F-13** (hardcoded landform `acceptance_ok`)

---

## Delivered

| Item | Location |
|---|---|
| Final pass uses full `MoistureParams` | `physical/final/pipeline.py` — `replace(params.moisture, months=…)` on both moisture builds |
| Moisture `acceptance_ok` requires `spinup_converged` | `physical/moisture/pipeline.py` |
| Heuristics kept as soft flag | `heuristic_fields_ok` (not sufficient for acceptance alone) |
| Final stage gates on moisture acceptance | `moisture_ok` / `moisture_spinup_converged` in final diagnostics |
| Landform `acceptance_ok` = structural only | `physical/landforms/pipeline.py` — `structural_ok`, `calibrated: false`; disabled ⇒ not OK |
| Godot YAML writes spin-up + monsoon peers | `godot/scenes/Main.gd` `_write_planet_config` |
| Tests | `tests/test_physical_realism_cr1.py` (+ moisture/final spin-up years for honest OK) |

`PlanetConfig.to_moisture_params()` already carried PR-7/PR-8 fields; the bug was the final rebuild omitting them.

---

## Acceptance

| Criterion | Result |
|---|---|
| Changing plume / land_store / ITCZ / monsoon in `FinalRecalcParams` changes ecology moisture diagnostics + precip | PASS |
| `spinup_converged=False` ⇒ moisture `acceptance_ok=False` | PASS |
| Landform disabled / uncalibrated not claimed as full acceptance | PASS (`calibrated: false`; disabled ⇒ `acceptance_ok=False`) |
| `pytest -m "not slow"` | PASS — 225 passed |

---

## Explicitly not done

- **F-03 remainder / F-04:** production default `spinup_max_years=4` still too short for many Quick seeds; land-store not in closure gate → **CR-3**  
- **F-05…F-12, F-14**  
- Raising default spin-up years or disabling monsoon in YAML (interim recommendation only)  
- Godot UI spins for every monsoon/spin-up peer (YAML defaults filled; Advanced UI still partial)

**Decision:** accept CR-1; stop. Next when instructed: **CR-2** only.
