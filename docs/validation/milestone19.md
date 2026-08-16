# Milestone 19 acceptance record

**Date:** 2026-08-15  
**Scope:** EnvironmentTimeline scaffold only (no full palaeoclimate)

## Delivered

| Item | Location |
|---|---|
| `EnvironmentTimeline` interface + impl | `worldsim/environment_timeline/` |
| Baseline snapshot | `baseline.json` under `world/timeline/environment/` |
| Anomaly schema (temp / precip scale / sea level / scope) | `schema.py` |
| Time-indexed query API (same façade as baseline) | `WorldSpatialModel.environment_at/sample_*` + `year=` |
| Persistence without redesigning WorldSpatialModel | `timeline/environment/` beside `physical/` |
| Wired into `run_world` | empty anomaly log + baseline at save |

## Acceptance

| Criterion | Result |
|---|---|
| Same spatial query retrieves baseline or time-indexed modifiers | PASS |
| Storage can later support climate/sea-level change without redesigning WorldSpatialModel | PASS (sparse anomalies; baseline points at rasters) |
| No full palaeoclimate | PASS (explicitly scaffold) |
| Automated tests | **102 passed** fast |

## Explicitly out of scope

- Palaeolithic palaeoclimate / ice sheets / coastline redraw
- HistoricalTimeline / population / culture (separate architecture)
