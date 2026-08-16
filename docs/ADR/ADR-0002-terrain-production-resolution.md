# ADR-0002 — Lock terrain production resolution after Milestone 5 benchmark

- **Status:** Accepted
- **Date:** 2026-08-14
- **Milestone:** 5

## Context

Architecture prefers terrain/hydrology at 4096×2048 with fallback 2048×1024,
subject to local memory/runtime benchmarks (§12.4, Milestone 5).

## Decision

On this Apple M2 / 8 GB host, a working-set estimate of ~10 float64 fields and
full pipeline timings were measured for both candidates (see
`docs/validation/milestone5_benchmark.json`):

| Resolution | Est. working set | Full pipeline | Seconds (carrier 256×128) |
|---|---|---|---|
| 4096×2048 | ~671 MB | yes | ~20 s |
| 2048×1024 | ~168 MB | yes | ~5 s |

Both fit the 2 GB working-set budget. **Production resolution is locked to
4096×2048** as the highest viable full-pipeline size.

`resolution.terrain_production` in `worldsim/configs/default_planet.yaml`
records this lock. `terrain_target` remains the architectural aspiration (same
value here).

## Consequences

- Default `--stage terrain` uses 4096×2048 unless overridden by CLI.
- Machines with tighter RAM may override via `--terrain-width/height` or config.
- Hydrology target aligned to the same production size for Milestone 11 planning.
