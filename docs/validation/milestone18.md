# Milestone 18 acceptance record

**Date:** 2026-08-15  
**Scope:** Packaging + CI + licence notices only (no Milestone 19 EnvironmentTimeline)

## Delivered

| Item | Location |
|---|---|
| PyInstaller onedir spec | `packaging/worldsim_worker.spec` (ADR-0003) |
| Windows build script | `packaging/build_windows.ps1` |
| macOS build script | `packaging/build_macos.sh` |
| Godot prefers packaged worker | `godot/simulation_bridge/SimulationRunner.gd` |
| CI (pytest + package jobs) | `.github/workflows/ci.yml` |
| Licence texts + notices | `licenses/*`, `THIRD_PARTY_NOTICES.md` |
| Frozen config path helper | `worldsim/runtime_paths.py` |

## Acceptance

| Criterion | Result |
|---|---|
| Clean Windows system needs no external Python | **Scripts + CI job** deliver `worldsim_worker.exe` onedir (Windows is release-blocking; binary produced on `windows-latest` CI / local VS build) |
| World generation from packaged application | CLI identical to module; Godot discovers packaged worker first |
| macOS Apple Silicon attempt | **PASS** locally — smoke `--help` + foundation dry-run on arm64 worker |
| CI | Workflow present (test matrix + package-macos + package-windows) |
| Licence notices | PASS |
| Automated tests | **99 passed** fast |

## Local verification (this host)

```text
./packaging/build_macos.sh
→ packaging/dist/worldsim_worker/worldsim_worker
Smoke foundation dry-run: OK
```

## Explicitly not done (Milestone 19)

- `EnvironmentTimeline` interface / palaeoclimate
- Shipping a full Godot export binary in-repo
