# Milestone 0 acceptance record

**Date:** 2026-08-14  
**Host:** macOS 26.1 / Apple M2 / arm64  

## Checks

| Criterion | Result |
|---|---|
| Worker launches (`python -m worldsim ... --dry-run`) | PASS |
| Progress protocol valid (NDJSON §9 events) | PASS |
| Seed manifest deterministic across runs | PASS |
| Automated tests | **12 passed** |

## Environment notes

- Local `pip` on Homebrew Python 3.12 fails on this macOS because `platform.mac_ver()` returns empty (truststore bug).
- Milestone 0 verification used **`uv`** to create `.venv` and install `.[dev]`.
- `Godot.app` is gitignored via `*.app/`.

## Explicitly not done (later milestones)

- Coordinate helpers (Milestone 1)
- PyPlatec / physical stages
- Godot project under `godot/`
