# Milestone A2 acceptance record

**Date:** 2026-08-15  
**Scope:** Generation profiles (default Full) only — no A3 layer toggles

## Delivered

| Item | Location |
|---|---|
| Profile constants Quick / Atlas / Full | `godot/simulation_bridge/SimulationRunner.gd` |
| Full = no `--*-width/height` CLI overrides | `_build_args` match `full` / default |
| Quick = prior smoke overrides (128×64 climate) | same |
| Atlas = mid (512×256 climate, 1024×512 terrain) | same |
| UI selector + RAM/time hint | `Main.tscn` / `Main.gd` |
| Default selected = Full | `profile_option.select(2)` |
| README note | `godot/README.md` |
| Loaded resolution in status | existing `Loaded atlas %dx%d` |

## Acceptance

| Criterion | Result |
|---|---|
| Default Generate → climate 1024×512 chain without manual CLI | PASS (no size flags for Full; config defaults) |
| Quick available and labeled | PASS |
| Loaded atlas reports resolution | PASS |

## Explicitly not done (A3+)

- Coast / Rivers / Lakes toggles
- Coastline artefact verification doc
- Hex contours / Holdridge labels
