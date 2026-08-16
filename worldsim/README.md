# worldsim

Python simulation worker for Conworld History.

## Requirements

- Python **3.12.x** (on this machine: `python3.12`, not system `python3`)

## Setup

Preferred on macOS 26+ (Homebrew `pip` may fail when `platform.mac_ver()` is empty):

```bash
cd worldsim
# requires: https://github.com/astral-sh/uv
uv venv .venv --python 3.12
source .venv/bin/activate
# Milestone 3 vendored PyPlatec (extended bindings)
uv pip install -e ../vendor/pyplatec
uv pip install -e ".[dev]"
```

Alternative (when system pip works):

```bash
cd worldsim
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ../vendor/pyplatec
python -m pip install -e ".[dev]"
```

## Run worker

Foundation only:

```bash
python -m worldsim --seed 183716 --output ../worlds/smoke --stage foundation
```

Tectonics + interpretation:

```bash
python -m worldsim --seed 183716 --output ../worlds/tectonics --stage tectonics
```

Milestone 5 terrain/ocean (uses locked `terrain_production`):

```bash
python -m worldsim --seed 183716 --output ../worlds/terrain --stage terrain
```

Milestone 6 base seasonal climate (climate grid 1024×512):

```bash
python -m worldsim --seed 183716 --output ../worlds/climate --stage climate
```

Milestone 7 atmosphere (pressure + monthly winds on climate grid):

```bash
python -m worldsim --seed 183716 --output ../worlds/atmosphere --stage atmosphere
```

Milestone 8 ocean circulation (currents + SST on climate grid):

```bash
python -m worldsim --seed 183716 --output ../worlds/ocean --stage ocean
```

Milestone 9 moisture / precipitation:

```bash
python -m worldsim --seed 183716 --output ../worlds/moisture --stage moisture
```

Milestone 10 erosion pass one / DEM v1:

```bash
python -m worldsim --seed 183716 --output ../worlds/erosion --stage erosion
```

Milestone 11 PyFlwDir hydrology:

```bash
python -m worldsim --seed 183716 --output ../worlds/hydrology --stage hydrology
```

Milestone 12 canonical vectors:

```bash
python -m worldsim --seed 183716 --output ../worlds/vectors --stage vectors
```

Milestone 13 fluvial erosion + final recalculation:

```bash
python -m worldsim --seed 183716 --output ../worlds/final --stage final
```

Milestone 14 soils + Holdridge ecology (default stage):

```bash
python -m worldsim --seed 183716 --output ../worlds/ecology --stage ecology
```

Emits newline-delimited JSON progress events on stdout. Ecology artefacts land under
``<output>/ecology/``.

Hydrology requires ``pyflwdir`` (pinned in ``pyproject.toml``; pulls ``numba``).

## Tests

```bash
pytest
# include full 1024×512 acceptance (~10s):
pytest -m slow
```

## Scope

- Milestone 0: config, seeds, progress protocol, CLI
- Milestone 1: cylindrical coordinates + spatial extent
- Milestone 2: PyPlatec baseline (height + plate_id, E–W seam)
- Milestone 3: vendored extended PyPlatec (crust age + plate velocity)
- Milestone 4: tectonic interpretation (boundaries, classes, proxies)
- Milestone 5: high-res terrain/ocean + coastline prototype (production 4096×2048)
- Milestone 6: base seasonal climate (`temperature_c[12]`, insolation, lapse, inertia)
- Milestone 7: atmosphere (pressure proxy, monthly winds, zones, Coriolis, topo)
- Milestone 8: ocean circulation (`current_u`/`v`, basins, SST, coastal coupling)
- Milestone 9: moisture / precipitation (evap, advection, orographic, convection)
- Milestone 10: erosion pass one (climate-informed DEM v1)
- Milestone 11: PyFlwDir hydrology (flow, basins, rivers, lakes, discharge)
- Milestone 12: canonical vectors (coast, river network, lakes, spatial index)
- Milestone 13: fluvial erosion + final climate/hydro/vector recalculation
- Milestone 14: soils + Holdridge ecology (biotemp, PET, zones)
- Milestone 15: 256×128 analytical hex grid (aggregation cache, neighbourhood, river_edge_mask)
- Milestone 16: WorldSpatialModel persistence + spatial queries (`world/` dataset)
- Milestone 17: Godot atlas (`godot/`) + `atlas_display` export
- Milestone 18: packaged `worldsim_worker` (PyInstaller), CI, licence notices
- Milestone 19: EnvironmentTimeline scaffold (baseline + sparse anomalies, `year=` queries)

Atlas UX follow-up (not Physical World M0–19): see repo `docs/ATLAS_UX_PLAN.md`.

