# ADR-0003 — Package worldsim_worker with PyInstaller (onedir)

- **Status:** Accepted
- **Date:** 2026-08-15
- **Milestone:** 18

## Context

Architecture §8.2 requires end users to run generation without installing
Python. Preferred artefacts are `worldsim_worker.exe` (Windows, release-blocking)
and `worldsim_worker` (macOS). The worker includes native extensions (`platec`
C++/pybind, `numba`/`llvmlite` via PyFlwDir).

## Decision

Use **PyInstaller 6.14.x onedir** COLLECT layout (`packaging/worldsim_worker.spec`):

- Console EXE/binary named `worldsim_worker`.
- Bundle `worldsim/configs/` into the freeze root.
- Prefer onedir over onefile so `.so` / `.pyd` loading stays reliable.
- Godot `SimulationRunner` discovers the packaged binary first, then falls back
  to `python -m worldsim` for development.

Windows builds run via `packaging/build_windows.ps1` (and CI).
macOS Apple Silicon builds run via `packaging/build_macos.sh` (attempt/support).

## Consequences

- LGPL `platec` remains a separate native module inside `_internal/` / COLLECT
  tree (not statically merged into a single binary blob beyond PyInstaller
  norms); source remains under `vendor/pyplatec/`.
- CI uploads packaged artefacts; clean Windows systems use the EXE without
  Python.
- If PyInstaller + numba proves fragile on a given runner, document the failure
  in validation notes and keep the scripts as the supported path.
