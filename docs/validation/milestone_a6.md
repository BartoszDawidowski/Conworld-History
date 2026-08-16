# Milestone A6 acceptance record

**Date:** 2026-08-15  
**Scope:** Generation tuning knobs (modest) — no A7 hex contours

## Delivered

| Knob | YAML path | Default | Wired into |
|---|---|---|---|
| Ocean fraction | `ocean.fraction_target` | `0.71` | `TerrainParams` / sea-level calibrate |
| Plate count | `tectonics.num_plates` | `10` | `PyPlatecParams` |
| Tectonic cycles | `tectonics.cycle_count` | `2` | `PyPlatecParams` |
| Terrain detail | `terrain.detail_amplitude` | `0.08` | `TerrainParams` |
| Erosion iterations | `erosion.iterations` | `5` | `ErosionParams` |
| Fluvial strength | `erosion.fluvial_k` | `8.0` | `ErosionParams` |

| Item | Location |
|---|---|
| Defaults in packaged YAML | `worldsim/configs/default_planet.yaml` |
| Loader fields | `worldsim/src/worldsim/config.py` |
| Pipeline uses config (not hardcoded dataclass defaults alone) | `pipeline.py` |
| Godot Advanced foldout + temp `--config` | `Main.tscn` / `Main.gd` / `SimulationRunner.gd` |
| Run snapshot | `worlds/atlas_run_<seed>/planet_config.yaml` |

## Start-here (less shred / more continent)

1. Lower **ocean** fraction (more land).
2. Lower **plates** (larger masses, heuristic).
3. Lower **detail** amplitude (smoother macro coasts).
4. Then tune **erosion** / **fluvial k**.

## Acceptance

| Criterion | Result |
|---|---|
| Defaults reproduce prior behaviour | PASS (same numeric defaults as pre-A6 builders) |
| Ocean fraction from YAML reaches terrain | PASS (`test_a6_knobs_from_yaml` + pipeline wiring) |
| Ocean fraction change at fixed seed changes land share | PASS (sea-level quantile; see `test_sea_level_hits_ocean_fraction_target` + knobs load) |
| Godot Advanced → worker `--config` | PASS (skeleton asserts + write path) |
| README start-here | PASS (`godot/README.md`) |

## Explicitly not done

- A7 true hex contours
- Outline smoothing (§7)
- Full worldgen lab / hyperparameter search
- Reverting SubViewport nearest filter (coast “squarer” look — follow-up with §7)
