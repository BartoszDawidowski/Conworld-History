# worldsim-platec (vendored PyPlatec fork)

Vendored from [Mindwerks/plate-tectonics](https://github.com/Mindwerks/plate-tectonics)
Python bindings (`pyplatec` 1.4.x lineage) for Conworld History Milestone 3.

## Upstream vs fork

Upstream PyPI `pyplatec` exposes only heightmap + platesmap.

This fork additionally exposes observational native metadata already present
in the C API / lithosphere:

- `get_agemap(handle)`
- `get_plate_count(handle)`
- `get_plate_velocity(handle, plate_index)` → unit vector `(x, y)`
- `get_plate_speed(handle, plate_index)` → scalar speed

Simulation stepping is unchanged; new getters are read-only.

License: LGPL-3.0 (see `LICENSE`).

## Build

```bash
# macOS / Linux (C++20 compiler + Python 3.12)
python3.12 -m pip install -e .

# or with uv:
uv pip install -e .
```

Windows requires Visual Studio Build Tools with the C++ workload, then the
same editable install (see `scripts/build_windows.ps1`).
