# Packaging (Milestone 18)

Frozen `worldsim_worker` so end users do **not** need a separate Python install
(architecture §8.2). Godot remains the atlas UI and launches this worker.

## Outputs

| Platform | Artefact |
|---|---|
| Windows x86-64 (**release-blocking**) | `packaging/dist/worldsim_worker/worldsim_worker.exe` (+ `_internal/`) |
| macOS (Apple Silicon attempt) | `packaging/dist/worldsim_worker/worldsim_worker` |

Onedir layout (not onefile) keeps native extensions (`platec`, `numba`/`llvmlite`) reliable.

## Build

### macOS

```bash
chmod +x packaging/build_macos.sh
./packaging/build_macos.sh
```

Requires `worldsim/.venv` with platec + worldsim installed.

### Windows

Developer PowerShell for VS (C++ tools) + Python 3.12:

```powershell
.\packaging\build_windows.ps1
```

Builds vendored `platec`, then PyInstaller.

## Godot integration

`SimulationRunner` prefers a packaged binary when found under:

- next to the Godot / game executable as `worldsim_worker(.exe)`
- `packaging/dist/worldsim_worker/worldsim_worker(.exe)` in the repo (dev)

Otherwise it falls back to `python -m worldsim` (development mode).

Suggested release layout:

```text
ConworldHistory/
  ConworldHistory.exe   # Godot export
  worldsim_worker.exe
  _internal/            # PyInstaller COLLECT folder contents
  …
```

Copy the entire `packaging/dist/worldsim_worker/` directory beside the game, or
flatten so `worldsim_worker.exe` and `_internal/` sit next to the Godot binary.

## Smoke

Packaged CLI is the same as the module:

```text
worldsim_worker --seed 1 --output out --stage foundation --dry-run
```

## Licences

Bundled third-party notices: repo root `THIRD_PARTY_NOTICES.md` and `licenses/`.
LGPL `platec` remains dynamically linked as a native extension inside the
frozen tree — see ADR-0003.
