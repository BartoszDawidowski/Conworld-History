# Third-Party Notices

This repository incorporates third-party components. Full license texts live
under `licenses/`. Packaged `worldsim_worker` builds redistribute the runtime
stack listed below (Milestone 18).

## Godot Engine

- Component: Godot Engine 4.7.1
- License: MIT — `licenses/GODOT_MIT.txt`
- Upstream: https://godotengine.org/
- Local engine binary (`Godot.app`) is a development convenience and is
  excluded from version control.

## PyPlatec / plate-tectonics

- Component: **worldsim-platec** `1.4.3+worldsim.3` (vendored fork under `vendor/pyplatec`)
- Based on: PyPlatec / plate-tectonics (Mindwerks)
- License: LGPL-3.0-or-later — `licenses/PYPLATEC_LGPL-3.0.txt` and `vendor/pyplatec/LICENSE`
- Upstream sources: https://github.com/Mindwerks/plate-tectonics
- ADR: `docs/ADR/ADR-0001-vendored-pyplatec-extended-bindings.md`
- Packaging: native extension shipped inside PyInstaller onedir tree (ADR-0003)

## PyFlwDir

- Component: PyFlwDir **0.5.12**
- License: MIT — `licenses/PYFLWDIR_MIT.txt`
- Upstream: https://github.com/Deltares/pyflwdir

## NumPy

- Component: NumPy **2.2.6**
- License: BSD-3-Clause — `licenses/NUMPY_BSD.txt`

## Numba / llvmlite

- Component: Numba / llvmlite (transitive via PyFlwDir)
- License: BSD — `licenses/NUMBA_BSD.txt`

## PyYAML

- Component: PyYAML **6.0.2**
- License: MIT — `licenses/PYYAML_MIT.txt`

## WorldEngine

- Component: WorldEngine (target 0.20.0) — reference / optional fallback only
- License: MIT
- Upstream: https://github.com/Mindwerks/worldengine
- Not bundled in the default packaged worker.

## PyInstaller (build-time)

- Component: PyInstaller **6.14.2** (packaging toolchain, not a runtime dep of the atlas)
- License: GPL-2.0-or-later with Bootloader exception (see upstream)
- Used only to produce `worldsim_worker`; end users do not install it.

## Project code

Unless otherwise noted, original Conworld History / worldsim / godot atlas code
in this repository is intended for the project owner’s use. Add an explicit
project license file when distribution policy is finalized.
