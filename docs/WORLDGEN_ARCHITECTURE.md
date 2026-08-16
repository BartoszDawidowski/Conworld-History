# WORLDGEN_ARCHITECTURE.md

> **Status:** Architecture specification — v0.2  
> **Date:** 2026-08-13  
> **Audience:** coding agents and developers implementing the physical-world generator and spatial substrate for a procedural conworld history simulator  
> **Authority:** This document is the canonical architecture specification for the physical world and spatial model.  
> **Target:** A deterministic Earth-like conworld generator whose output can support procedural history simulation from prehistory to the Renaissance, with Godot used primarily as an interactive atlas, visualization layer, and simulation front-end.

---

# 1. Purpose

Build a deterministic, modular procedural world-generation system that creates a **high-resolution physical world** and a **multi-representation spatial model** suitable for later simulation of long-term human history.

The project is no longer architected as a game whose final world is a 256 × 128 hex map.

The world must instead exist simultaneously in three complementary spatial representations:

1. **Raster fields** for continuous environmental variables.
2. **Vector objects and networks** for geographically discrete features.
3. **A 256 × 128 flat-top hex analysis grid** for aggregation, diffusion, spatial indexing, and later historical simulation.

The hex grid is NOT the canonical geometry of the world.

The canonical physical world must preserve more detailed terrain, rivers, coastlines, lakes, climate fields, and other environmental information than can be represented by the historical hex grid.

The high-level causal pipeline is:

**tectonics → terrain → ocean geometry → atmosphere → ocean currents → climate → erosion → hydrology → ecology → vector physical geography → spatial analysis grid**

Later historical systems will consume this physical substrate to simulate:

- population,
- subsistence,
- migration,
- settlement,
- cultures,
- languages,
- technologies,
- religions,
- institutions,
- trade,
- warfare,
- states,
- collapses,
- inheritance between cultures,
- long-term historical change.

Those historical systems are intentionally outside the detailed implementation scope of this document and SHOULD be specified separately in:

```text
HISTORY_SIMULATION_ARCHITECTURE.md
```

This document must nevertheless define a stable and sufficiently rich interface for them.

---

# 2. Core architectural principle

The central invariant of v0.2 is:

> **The hex grid is an analytical index over the world, not the world itself.**

The world is not destructively converted into hexes.

Instead:

```text
                     WORLD SPATIAL MODEL
                              |
            +-----------------+-----------------+
            |                 |                 |
            v                 v                 v
         RASTERS           VECTORS          HEX GRID
            |                 |                 |
   continuous fields    exact-ish objects   analysis/index
            |                 |                 |
            +-----------------+-----------------+
                              |
                              v
                       HISTORY SIMULATION
                              |
                              v
                          GODOT ATLAS
```

Examples:

### Raster source of truth

```text
elevation
bathymetry
temperature
precipitation
humidity
wind
ocean currents
soil moisture
tectonic potential
```

### Vector source of truth

```text
coastlines
rivers
lakes
watershed boundaries
later roads
later trade routes
later political borders
later settlement points
```

### Hex analytical cache

```text
mean elevation
land fraction
climate summaries
river IDs crossing cell
dominant watershed
agricultural suitability
population density
culture shares
state influence
```

The same real-world concept MAY have both a canonical representation and a cached representation.

Example:

```text
Canonical river:
    vector network + polyline geometry

Hex cache:
    river_ids[]
    river_crossing_mask
    discharge summary
```

The cache may always be rebuilt from canonical data.

---

# 3. Design philosophy

## 3.1 Primary objective

Generate worlds whose large-scale and medium-scale geography can be explained by the processes that created it.

Examples:

- mountains should preferentially arise from credible tectonic conditions;
- volcanic activity should correlate with appropriate tectonic settings;
- coastlines should retain detail beyond the historical analysis grid;
- ocean currents should react to basin geometry;
- warm/cold currents should modify coastal climate;
- precipitation should be transported by atmospheric circulation;
- mountains should create windward precipitation and leeward rain shadows;
- drainage networks should form coherent basins and tributary hierarchies;
- rivers should remain continuous geographic objects rather than chains of hex flags;
- ecological zones should derive from climate;
- later human geography should derive from the physical world rather than overwrite it.

## 3.2 Realism target

Target:

```text
PHYSICALLY PLAUSIBLE
```

not:

```text
DECORATIVE
```

and not:

```text
SCIENTIFIC GENERAL CIRCULATION MODEL
```

The implementation SHOULD preserve first-order causal relationships while remaining tractable enough for procedural generation.

The implementation MUST NOT attempt:

- full Navier–Stokes atmospheric simulation,
- production-grade ocean GCM,
- calibrated mantle convection,
- metre-scale hydrology,
- exact Earth palaeoclimate reconstruction,
- exact plate histories over hundreds of millions of years.

## 3.3 Simulation-first architecture

The physical world and later history simulation MUST be runnable without Godot.

Conceptually:

```text
worldsim --seed 12345 --generate-physical
worldsim --seed 12345 --simulate-until 1450
```

Godot is the preferred graphical front-end and interactive atlas, not the only environment in which the simulation can exist.

---

# 4. Locked project decisions

These decisions are accepted unless changed through an Architecture Decision Record.

| Parameter | Decision |
|---|---|
| Project type | procedural conworld history simulation / worldbuilding tool |
| Godot role | interactive atlas, visualization, controls, timeline UI |
| Simulation backend | separate Python module/process |
| Physical source of truth | mixed raster + vector |
| Historical spatial index | **256 × 128 flat-top hex grid** |
| Hex role | aggregation, diffusion, indexing, simulation cache |
| Hex geometry | equal-area analytical cells as far as practical |
| World topology | **Civ-like cylinder: east–west wrap; north/south do not wrap** |
| Map projection | cylindrical equal-area conceptual coordinate system |
| World type | Earth-like |
| Realism | plausible |
| Tectonics | extended PyPlatec |
| Tectonics fallback | standard PyPlatec + inferred metadata |
| Climate | 12 months |
| Ecology | Holdridge life zones |
| Hydrology | PyFlwDir primary |
| Hydrology fallback | WorldEngine only if PyFlwDir is technically unusable |
| Rivers | canonical vector network; hex river data is derived cache |
| Lakes | canonical vector/polygon objects plus hydrological metadata |
| Coastline | canonical vector geometry derived from high-res terrain |
| Erosion | two major passes |
| Python | 3.12.x |
| Godot | 4.7.1 stable baseline |
| Primary platform | Windows x86-64 |
| Secondary platform | macOS Apple Silicon if packaging remains practical |
| Historical grid | 256 × 128 |
| Tectonic working grid | target 1024 × 512 |
| Climate working grid | target 1024 × 512 |
| Terrain working grid | target 4096 × 2048 if benchmarks permit |
| Hydrology working grid | target 4096 × 2048 if benchmarks permit |
| Terrain/hydrology fallback resolution | 2048 × 1024 |
| Fast/debug physical mode | approximately 512 × 256 / 1024 × 512 depending stage |
| Environmental chronology | architecture must support time-dependent anomalies and later palaeo-environment extensions |

---

# 5. Technology baseline

Initial dependency baseline:

```text
Godot              4.7.1 stable
Python             3.12.x
PyPlatec           1.4.3, forked/extended
WorldEngine        0.20.0
PyFlwDir           0.5.12
NumPy              pinned compatible stable version
Numba              pinned compatible stable version
```

Versions MUST be pinned for reproducibility.

Dependency upgrades require regression testing.

## 5.1 Optional future spatial libraries

Do NOT immediately introduce a heavy GIS dependency stack.

Libraries such as:

```text
Shapely
GeoPandas
GDAL
Fiona
Rasterio
```

MAY be introduced only if a concrete vector or geometry requirement justifies them.

Prefer lightweight internal geometry structures during early milestones.

If Shapely materially simplifies robust line/polygon intersections and packaging remains acceptable, it MAY become the preferred vector geometry helper through an ADR.

Do not make GDAL a mandatory dependency without a demonstrated need.

---

# 6. Licensing

- PyPlatec / plate-tectonics: LGPL-3.0-or-later.
- WorldEngine: MIT.
- PyFlwDir: MIT.
- Godot: MIT.

The repository MUST include:

```text
THIRD_PARTY_NOTICES.md
licenses/
```

Modified PyPlatec code must remain available under applicable LGPL terms.

Do not assume LGPL requires opening the entire simulator.

---

# 7. Repository architecture

Recommended conceptual structure:

```text
repo/
│
├── godot/
│   ├── project.godot
│   ├── scenes/
│   ├── scripts/
│   ├── atlas/
│   │   ├── WorldAtlas.gd
│   │   ├── RasterLayerRenderer.gd
│   │   ├── VectorLayerRenderer.gd
│   │   ├── HexOverlayRenderer.gd
│   │   ├── TimelineController.gd
│   │   └── InspectorPanel.gd
│   └── simulation_bridge/
│       ├── SimulationRunner.gd
│       ├── SimulationProtocol.gd
│       └── ProgressController.gd
│
├── worldsim/
│   ├── pyproject.toml
│   ├── requirements.lock
│   ├── src/worldsim/
│   │   ├── __main__.py
│   │   ├── config.py
│   │   ├── seeds.py
│   │   ├── pipeline.py
│   │   ├── state.py
│   │   ├── coordinates.py
│   │   │
│   │   ├── physical/
│   │   │   ├── tectonics/
│   │   │   ├── terrain/
│   │   │   ├── ocean/
│   │   │   ├── climate/
│   │   │   ├── erosion/
│   │   │   ├── hydrology/
│   │   │   ├── ecology/
│   │   │   └── vectorize/
│   │   │
│   │   ├── spatial/
│   │   │   ├── raster_store/
│   │   │   ├── vector_store/
│   │   │   ├── hex_grid/
│   │   │   ├── spatial_index/
│   │   │   └── queries/
│   │   │
│   │   ├── environment_timeline/
│   │   ├── export/
│   │   └── diagnostics/
│   │
│   └── tests/
│
├── vendor/
│   └── pyplatec/
│
├── docs/
│   ├── WORLDGEN_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── HISTORY_SIMULATION_ARCHITECTURE.md   # future
│   ├── ADR/
│   └── validation/
│
├── licenses/
└── THIRD_PARTY_NOTICES.md
```

Exact paths may be adapted after repository inspection.

Conceptual module ownership MUST remain clear.

---

# 8. Godot ↔ simulation backend boundary

## 8.1 Development mode

During development Godot MAY launch:

```text
python -m worldsim ...
```

## 8.2 Packaged mode

End users MUST NOT need a separate Python installation.

Preferred packaged executables:

```text
Windows:
worldsim_worker.exe

macOS:
worldsim_worker
```

## 8.3 Worker responsibilities

The worker is responsible for:

- physical-world generation,
- environmental timeline generation,
- later historical simulation,
- persistence,
- validation,
- data queries that are expensive or inappropriate to duplicate in Godot.

## 8.4 Godot responsibilities

Godot is responsible for:

- interactive world atlas,
- layer visualization,
- timeline controls,
- object inspection,
- map modes,
- user configuration,
- progress UI,
- launching and controlling simulation runs.

Godot MUST NOT become the canonical implementation of physical simulation.

---

# 9. Communication protocol

Use newline-delimited JSON for process status/control initially.

Example:

```json
{"event":"started","seed":183716}
{"event":"stage_started","stage":"tectonics"}
{"event":"progress","stage":"tectonics","value":0.42}
{"event":"stage_complete","stage":"tectonics"}
{"event":"complete","world_path":".../world/"}
```

Future simulation example:

```json
{"event":"simulation_year","year":-4200}
{"event":"simulation_year","year":-4199}
```

Errors:

```json
{
  "event":"error",
  "stage":"hydrology",
  "code":"HYDROLOGY_FAILED",
  "message":"...",
  "trace_path":".../error.log"
}
```

Large world data MUST NOT be transmitted as JSON over stdout.

Godot should load persisted datasets or request structured subsets.

---

# 10. Spatial model overview

The core data structure is:

```text
WorldSpatialModel
```

Conceptually:

```python
WorldSpatialModel:
    coordinate_system
    raster_layers
    vector_layers
    hex_analysis_grid
    spatial_indexes
    metadata
```

The physical simulation writes into this model.

The historical simulation reads from it and later adds human layers.

---

# 11. Coordinate system and projection

## 11.1 Topology

Use a cylindrical world:

```text
east-west: wraps
north-south: does not wrap
```

## 11.2 Conceptual equal-area cylindrical projection

The displayed/simulated map uses normalised planar coordinates:

```text
x ∈ [0, 1)
y ∈ [-1, 1]
```

Interpret:

```text
longitude = 360° * x - 180°
latitude  = asin(y)
```

or equivalent scaled form.

This corresponds conceptually to:

```text
y ∝ sin(latitude)
```

so equal planar area corresponds approximately to equal spherical area.

This is preferred to naïve equirectangular latitude spacing for the analytical grid.

## 11.3 Practical consequences

- east–west wrapping remains simple;
- historical hexes can represent approximately equal real surface areas;
- climate modules MUST convert projected Y to latitude;
- visual distortion near poles is accepted;
- exact spherical geometry is not required.

## 11.4 PyPlatec mismatch

PyPlatec's raster behaviour is effectively toroidal.

Downstream processing MUST correct this:

- select an appropriate east–west seam;
- prevent final north–south wrapping;
- interpret rows under the project coordinate model;
- apply polar correction as necessary.

No final vector or hex object may connect across north/south edges.

---

# 12. Multi-resolution strategy

The simulation does not use one universal grid.

## 12.1 Historical analytical grid

```text
256 × 128 flat-top hexes
32,768 cells
```

This is NOT the terrain resolution.

It is the main coarse spatial substrate for later historical field simulations such as:

- population density,
- culture shares,
- linguistic diffusion,
- subsistence pressure,
- disease pressure,
- political influence,
- religious influence,
- migration potential.

## 12.2 Tectonic grid

Target:

```text
1024 × 512
```

## 12.3 Climate grid

Target:

```text
1024 × 512
```

Climate at 8× terrain resolution is not required unless profiling demonstrates a meaningful benefit.

## 12.4 Terrain grid

Preferred target:

```text
4096 × 2048
```

Fallback:

```text
2048 × 1024
```

The local agent MUST benchmark memory/runtime before locking 4096 × 2048 as mandatory.

## 12.5 Hydrology grid

Preferred target:

```text
4096 × 2048
```

Fallback:

```text
2048 × 1024
```

Hydrology benefits strongly from high-resolution DEM geometry.

The final choice MUST be made from benchmarks, not assumption.

## 12.6 Fast mode

Provide a development quality profile that reduces all major grids substantially.

Fast mode exists for iteration and debugging.

It need not reproduce every local feature of final quality.

---

# 13. Resampling rules

Resampling is a first-class operation.

Continuous fields:

- bilinear/bicubic interpolation where appropriate;
- conservative aggregation where totals matter.

Categorical fields:

- nearest neighbour,
- dominant-area vote,
- explicit mixture fractions.

Identifiers:

```text
plate_id
watershed_id
lake_id
```

MUST NOT be interpolated numerically.

Every resampling stage MUST be documented and testable.

---

# 14. Canonical vs derived data

Every important dataset must declare whether it is:

```text
CANONICAL
DERIVED
CACHE
DEBUG
```

Examples:

| Data | Status |
|---|---|
| high-res DEM | canonical physical raster |
| monthly climate | canonical physical raster |
| river vector network | canonical physical vector |
| coastline vectors | canonical physical vector |
| lake polygons | canonical physical vector |
| hex mean elevation | derived cache |
| hex river crossing mask | derived cache |
| rendered biome PNG | debug |
| colourised elevation texture | debug/display |

A cache MUST be reproducible from canonical data.

---

# 15. Master physical world state

Recommended conceptual object:

```python
PhysicalWorldState:
    config
    seeds
    coordinates

    tectonics
    terrain
    ocean
    climate
    erosion
    hydrology
    ecology

    rasters
    vectors
    analysis_grid

    metadata
```

Avoid hidden global module state.

---

# 16. Seed architecture

Use one master seed.

Derive named seeds using a stable hash:

```text
hash(master_seed, module_name, schema_version)
```

Example:

```text
master_seed
├── tectonics
├── terrain_detail
├── ocean
├── climate
├── erosion_1
├── hydrology
├── erosion_2
├── vectorization
├── ecology
└── environment_timeline
```

Do not consume one global RNG sequentially.

Adding an unrelated random module must not change all downstream seeds.

---

# 17. PlanetConfig

Earth-like only for the first implementation.

Example:

```yaml
schema_version: 2

planet:
  earth_like: true
  axial_tilt_deg: 23.44
  orbital_eccentricity: 0.0167
  solar_constant_relative: 1.0
  rotation_period_hours: 24.0
  year_days: 365.2422

map:
  topology: cylindrical
  wrap_x: true
  wrap_y: false
  projection: cylindrical_equal_area

analysis_grid:
  width: 256
  height: 128
  orientation: flat_top

resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  hydrology_target: [4096, 2048]

climate:
  months: 12

generation:
  quality: final
```

Exact physical tuning constants remain calibratable parameters.

---

# 18. Stage A — extended PyPlatec tectonics

Use plate-tectonics / PyPlatec as the base tectonic simulator.

Do not recreate tectonics from noise.

Required outputs:

```text
elevation_raw
plate_id
crust_age
plate_velocity_x
plate_velocity_y
plate_speed if feasible
```

## 18.1 Binding extension

Fork PyPlatec and expose useful native information.

Preferred API:

```python
get_agemap()
get_plate_count()
get_plate_velocity()
get_plate_speed()
```

Keep the C++ extension narrow.

Do not expose arbitrary internal state without need.

## 18.2 Fallback

If extended metadata proves unstable:

```text
heightmap + plate_id
```

remains mandatory.

Missing metadata may be inferred through a compatible fallback result object.

The downstream API must remain stable.

---

# 19. Stage B — tectonic interpretation

Derive:

```text
boundary_mask
boundary_plate_a
boundary_plate_b
distance_to_boundary
boundary_normal
relative_velocity
boundary_type
tectonic_activity
convergence_strength
divergence_strength
transform_strength
subduction_potential
orogenic_potential
volcanic_potential
earthquake_potential
```

Boundary types:

```text
convergent
divergent
transform
oblique_convergent
oblique_divergent
weak/inactive
```

Use plate relative velocity projected onto boundary normal/tangent.

Do not classify from random labels.

---

# 20. Stage C — terrain and bathymetry

## 20.1 Macrostructure

Tectonics remains the dominant cause of macro-relief.

Terrain-detail noise must not relocate mountain chains.

## 20.2 Physical-ish elevation scale

Convert model output to metres relative to sea level.

Calibration may be empirical.

## 20.3 Ocean fraction

Sea level should be selected against a configurable Earth-like ocean-fraction target.

Do not hardcode an arbitrary Platec threshold as final sea level.

## 20.4 High-resolution refinement

Upsample terrain to target high resolution and add controlled local relief.

Inputs may include:

- tectonic uplift,
- distance to boundaries,
- base elevation,
- volcanic potential,
- low-amplitude multi-scale noise.

## 20.5 Bathymetry

Generate:

- continental shelves,
- slopes,
- abyssal plains,
- trenches,
- ridge tendencies.

Outputs:

```text
elevation_m
ocean_mask
ocean_depth_m
shelf_mask
```

---

# 21. Stage D — ocean and coastline geometry

Identify connected water bodies under cylindrical topology.

Raster outputs:

```text
water_body_id
ocean_basin_id
coast_distance
```

Then derive **canonical coastline vectors**.

## 21.1 Coastline vectorization

The coastline must be retained as a detailed vector geometry.

It must NOT be converted to hex stair-steps.

Canonical coastline object:

```text
CoastlineFeature
    id
    geometry
    water_body_id
    land_region_id if useful
```

The initial vectorization may use contour extraction / marching squares.

Geometry may later be simplified at multiple LODs for rendering.

---

# 22. Stage E — seasonal insolation and base temperature

Climate uses 12 months.

Use projected Y → latitude conversion.

Temperature should depend on:

- monthly insolation,
- elevation lapse rate,
- land/ocean thermal inertia,
- continentality,
- SST,
- ice/snow albedo.

Random noise may be a minor perturbation only.

Outputs:

```text
temperature_c[12,y,x]
```

---

# 23. Stage F — atmospheric circulation

Produce monthly coherent fields:

```text
wind_u
wind_v
pressure_proxy
```

Model first-order:

- Hadley circulation,
- subtropical highs,
- ITCZ migration,
- Ferrel-zone behaviour,
- polar circulation,
- trade winds,
- mid-latitude westerlies,
- polar easterlies,
- Coriolis deflection.

Topography may perturb flow locally.

No full fluid solver is required.

Independent random wind arrows are forbidden.

---

# 24. Stage G — ocean circulation

Custom reduced ocean model.

Monthly outputs:

```text
current_u
current_v
sst_c
```

Inputs:

- surface winds,
- Coriolis,
- coast geometry,
- basin connectivity,
- latitude,
- bathymetry where useful.

Should produce basin-scale circulation when possible.

The model SHOULD allow:

- subtropical gyres,
- warm western boundary currents,
- cooler eastern boundary currents,
- equatorial currents,
- polar constraints,
- simplified upwelling.

Currents MUST NOT cross land.

---

# 25. Stage H — moisture transport and precipitation

Replace noise-based precipitation with explicit moisture transport.

Monthly state:

```text
atmospheric_moisture
evaporation
precipitation
humidity
```

## 25.1 Moisture sources

- ocean evaporation;
- lakes;
- optional land evapotranspiration proxy.

## 25.2 Advection

Transport moisture primarily downwind.

## 25.3 Orographic effects

Windward uplift increases condensation.

Leeward regions experience moisture depletion.

Rain shadows MUST be emergent.

## 25.4 Convection

Warm humid regions may receive a convection proxy.

## 25.5 Continentality

Air moving far inland without recharge should dry.

---

# 26. Coupled climate iteration

Iterate:

```text
insolation
→ temperature
→ winds
→ currents
→ SST
→ temperature correction
→ evaporation
→ moisture transport
→ precipitation
→ snow/albedo
↺
```

Use a bounded iteration count.

Expose convergence diagnostics.

Do not wait indefinitely for numerical convergence.

---

# 27. Stage I — first erosion pass

Use climate-informed erosion.

Inputs may include:

- precipitation,
- runoff,
- slope,
- rock-resistance proxy.

Goal:

- reduce numerical terrain artefacts,
- form broad drainage tendencies,
- preserve tectonic macro-relief.

---

# 28. Stage J — hydrology with PyFlwDir

PyFlwDir is the primary hydrology backend.

Operate at the highest practical DEM resolution.

Required raster outputs:

```text
flow_direction
flow_accumulation
basin_id
watershed_id
stream_order
river_mask
river_discharge_proxy
outlet_points
```

Optional:

```text
subbasin_id
distance_to_outlet
```

## 28.1 DEM conditioning

Handle:

- flats,
- depressions,
- ocean outlets,
- intentional closed basins.

## 28.2 Seasonal discharge

Prefer:

```text
static river topology
monthly discharge[12]
```

rather than twelve independent river networks.

---

# 29. Stage K — canonical vector hydrology

This is a major change from v0.1.

The final river representation is NOT a property of hexes.

PyFlwDir raster hydrology must be converted into canonical vector/network objects.

## 29.1 River network object

Conceptual:

```text
RiverNetwork
    nodes[]
    segments[]
    basins[]
```

River node:

```text
RiverNode
    id
    x
    y
    type:
        source
        confluence
        lake_inlet
        lake_outlet
        mouth
```

River segment:

```text
RiverSegment
    id
    from_node
    to_node
    geometry
    strahler_order
    mean_discharge
    monthly_discharge[12]
    basin_id
    length
```

## 29.2 Vector geometry

River geometry should follow the high-resolution drainage path.

It may later be simplified for display at low zoom.

Canonical simulation geometry remains separate from display LOD.

## 29.3 Lakes

Canonical lake:

```text
Lake
    id
    polygon
    surface_elevation
    basin_id
    inlet_river_ids[]
    outlet_river_id
    closed_basin
```

A lake is not a single raster or hex flag.

---

# 30. Stage L — second erosion and final hydrology

Pipeline:

```text
climate v1
→ erosion v1
→ hydrology v1
→ fluvial erosion
→ terrain v2
→ climate correction
→ hydrology final
→ vector hydrology final
```

Only two major feedback passes are required for v1.

No indefinite geological loop.

---

# 31. Stage M — soils, permeability, land potential

Generate first-order environmental layers.

Possible outputs:

```text
permeability
soil_depth
soil_moisture
fertility_proxy
erosion_risk
```

These remain raster fields.

Later historical simulation will derive:

```text
agricultural_capacity
pastoral_capacity
forest_resources
settlement_suitability
```

from them and from technology.

Do not encode human technological assumptions directly into physical soil variables.

---

# 32. Stage N — Holdridge life zones

Primary terrestrial ecological classification:

```text
Holdridge
```

Calculate from:

```text
annual_biotemperature
annual_precipitation
PET ratio
```

Preserve raw monthly climate.

Output raster:

```text
holdridge_zone_id
```

Special overrides:

- ocean,
- lake,
- permanent ice,
- optionally wetlands,
- bare alpine terrain.

The biome/ecological map is a derived layer, never the primary world state.

---

# 33. Stage O — spatial analysis hex grid

Only after canonical physical geography exists should the 256 × 128 grid be populated.

## 33.1 Purpose

The hex grid provides:

- spatial aggregation,
- fast historical diffusion,
- neighbourhood relationships,
- historical field simulation,
- query acceleration,
- coarse statistics.

## 33.2 Hexes do not replace canonical geometry

Example:

```text
River 41 crosses Hex 20017.
```

This is stored as a relation.

River 41 remains a vector feature.

## 33.3 Hex environmental cache

Each hex may cache:

```text
latitude
land_fraction
ocean_fraction
lake_fraction

elevation_mean
elevation_min
elevation_max
elevation_std
slope_mean
roughness

dominant_plate_id
tectonic_activity_mean
volcanic_potential_mean

temperature_mean[12]
precipitation_mean[12]
humidity_mean[12]
runoff_mean[12]

wind_mean_u[12]
wind_mean_v[12]

sst_mean[12]
current_mean_u[12]
current_mean_v[12]

dominant_watershed_id
holdridge_fraction_by_zone
soil_summary
```

## 33.4 Object references

Hexes may also cache:

```text
river_ids[]
lake_ids[]
coastline_segment_ids[]
```

Later:

```text
settlement_ids[]
road_ids[]
trade_route_ids[]
```

---

# 34. Optional derived river crossing mask

`river_edge_mask` is retained only as a convenience cache.

It is NOT canonical.

Example:

```text
bit 0 = NE
bit 1 = E
bit 2 = SE
bit 3 = SW
bit 4 = W
bit 5 = NW
```

This may help:

- coarse routing,
- map overlays,
- local historical movement costs.

It must be rebuildable from vector river geometry.

---

# 35. Spatial query layer

Later history simulation must not manually inspect raw raster arrays everywhere.

Provide a stable query layer.

Conceptual API:

```python
world.environment_at(x, y)
world.hex_at(x, y)

world.rivers_in_bbox(...)
world.lakes_in_bbox(...)
world.coast_distance(x, y)

world.sample_elevation(x, y)
world.sample_climate(x, y, month)

world.hex_environment(hex_id)
world.neighbour_hexes(hex_id)
world.rivers_crossing_hex(hex_id)
```

Future historical API:

```python
world.settlements_in_region(...)
world.states_at(year)
world.cultures_at(year)
```

Keep physical spatial details behind the interface.

---

# 36. Historical simulation interface

The future history simulation should consume stable physical abstractions.

Minimum physical inputs useful to later history:

```text
topography
slope
river access
river discharge
coast access
harbour potential later
climate
seasonality
soil
ecosystem
water availability
natural barriers
passability
distance/cost surfaces
resource geology later
```

The history simulator should NOT directly call PyPlatec or PyFlwDir.

It should access the finished `WorldSpatialModel`.

---

# 37. Future time-varying environment

A history generator from prehistory to the Renaissance should not assume perfectly static environment.

The architecture MUST reserve a time-dependent environmental layer:

```text
EnvironmentTimeline
```

Conceptually:

```text
baseline climatology
+
time-dependent anomalies
```

Potential future drivers:

```text
decadal variability
multi-decadal drought
century-scale temperature anomalies
volcanic forcing
long-term wet/dry shifts
sea-level change
ice extent
```

## 37.1 V1 requirement

The storage/API schema MUST support environmental snapshots or anomalies.

The first physical generator MAY initially output a stable baseline climatology.

## 37.2 Prehistory extension

Because future history may begin in the Palaeolithic, the architecture SHOULD later support:

```text
palaeoclimate baseline
glacial/interglacial state
sea level
ice sheets
changing coastline
```

Do not implement this inside the first tectonic milestone.

Do not design storage in a way that makes changing coastline impossible later.

---

# 38. Time and snapshots

Future history requires time-indexed state.

Recommended separation:

```text
PhysicalWorld
    mostly static high-resolution substrate

EnvironmentTimeline
    slow environmental changes

HistoricalTimeline
    human simulation state/events
```

Possible persistence strategy:

```text
base world
+
periodic snapshots
+
event/change log
```

Do not store a complete duplicate of all high-resolution physical rasters for every year.

---

# 39. Storage architecture

The world dataset must preserve high-resolution canonical data.

Recommended conceptual layout:

```text
world/
│
├── manifest.json
│
├── config.json
│
├── physical/
│   ├── rasters/
│   │   ├── terrain.npz
│   │   ├── tectonics.npz
│   │   ├── climate.npz
│   │   ├── hydrology.npz
│   │   └── ecology.npz
│   │
│   ├── vectors/
│   │   ├── coastlines.*
│   │   ├── rivers.*
│   │   ├── lakes.*
│   │   └── watersheds.*
│   │
│   └── analysis_grid/
│       └── hex_environment.*
│
├── timeline/
│   ├── environment/
│   └── history/
│
└── debug/
```

Exact binary/vector formats should be selected during implementation after profiling.

---

# 40. Vector storage format

Do not force one format prematurely.

Required properties:

- deterministic serialization,
- stable IDs,
- easy Python read/write,
- practical Godot ingestion,
- efficient spatial queries or indexability,
- versionable schema.

Potential initial implementations:

```text
custom binary + metadata
GeoJSON for debug only
MessagePack-like structured binary
SQLite-based store later if justified
```

GeoJSON is acceptable for diagnostics and small fixtures.

It SHOULD NOT automatically become the production format for millions of historical features.

---

# 41. Raster storage format

Use NumPy-friendly storage internally.

Recommended:

```text
.npz
.npy
```

during development/cache.

Final persisted world may use a more compact chunked format if required.

Do not store large numeric raster datasets as JSON.

---

# 42. Godot atlas architecture

Godot now renders a **multi-layer atlas**, not a TileMap-only game board.

Conceptual:

```text
WorldAtlas
├── raster base renderer
├── coastline renderer
├── river renderer
├── lake renderer
├── hex analysis overlay
├── future settlement renderer
├── future road/trade renderer
├── future border renderer
├── map-mode controller
└── inspector
```

## 42.1 Raster display

Godot should display high-resolution terrain without forcing it into hex tiles.

Possible techniques:

- generated texture,
- tiled/chunked textures,
- shader-based colourisation,
- LOD pyramid later.

The renderer must remain independent of physical storage.

## 42.2 Vector display

Rivers and coastlines are rendered as vector/polyline geometry.

Use LOD/simplification at low zoom if required.

## 42.3 Hex overlay

Hex grid visibility is optional.

Example UI:

```text
[ ] Show analysis grid
```

The map should remain visually detailed when the grid is hidden.

---

# 43. Godot inspector

Clicking different map elements should inspect their canonical object.

Examples:

### Point on terrain

```text
Elevation
temperature
precipitation
soil
watershed
```

### River

```text
River ID
basin
Strahler order
monthly discharge
source
mouth
tributaries
```

### Lake

```text
Lake ID
area
inlets
outlet
closed basin
```

### Hex

```text
aggregated environment
later population
later cultures
later states
```

This distinction is important.

A hex is not the only clickable object.

---

# 44. Map modes

At minimum the physical atlas SHOULD support:

```text
shaded relief
elevation
bathymetry
plate IDs
tectonic boundaries
tectonic activity
volcanic potential
temperature by month
annual temperature
precipitation by month
annual precipitation
winds by month
ocean currents by month
watersheds
river order
Holdridge zones
soil/permeability
analysis grid
```

Later historical modes may include:

```text
population
culture
language
religion
technology
states
trade
wars
```

---

# 45. Diagnostics

Every stage MUST produce inspectable outputs.

Do not rely only on the final atlas.

Recommended debug outputs:

```text
elevation.png
plate_ids.png
crust_age.png
tectonic_boundaries.png
volcanic_potential.png
bathymetry.png
temperature_01.png
temperature_07.png
wind_01.png
currents_01.png
precipitation_01.png
precipitation_07.png
annual_precipitation.png
flow_accumulation.png
watersheds.png
rivers.png
lakes.png
holdridge.png
hex_overlay.png
```

Vector diagnostics should render canonical geometry over terrain.

---

# 46. Validation philosophy

Validation has four levels:

1. software invariants,
2. physical plausibility,
3. spatial consistency,
4. distributional/world-quality validation.

---

# 47. Software invariants

Examples:

- no unexpected NaN/Inf;
- expected array dimensions;
- correct monthly shapes;
- deterministic seed output;
- no invalid object IDs;
- no north–south topology connections;
- stable serialization round-trip.

---

# 48. Spatial consistency invariants

## Coastline

- vector coastline matches raster land/water boundary within tolerance;
- no large unexplained gaps;
- E–W seam remains continuous.

## Rivers

- river segments connect through node IDs;
- downstream direction is acyclic except explicitly modelled special cases;
- non-endorheic rivers terminate in ocean/lake/another river;
- confluences are topologically valid;
- vector paths correspond to high-flow raster cells within tolerance.

## Lakes

- lake polygon overlaps hydrological depression/water cells;
- outlet metadata matches drainage network.

## Hex caches

- cached river IDs correspond to actual vector intersections;
- cached environmental means match raster aggregation within tolerance;
- caches can be rebuilt.

---

# 49. Physical plausibility tests

## Tectonics

Across many seeds:

- high activity enriched near plate boundaries;
- convergence correlates with uplift;
- divergent oceanic regions correlate with ridge tendencies;
- subduction proxies correlate with volcanic potential.

## Temperature

- annual means colder toward poles;
- higher terrain colder on average;
- ocean seasonal amplitude lower than continental interior;
- opposite seasonal phase across hemispheres.

## Winds

- trade-wind tendencies in tropics;
- westerly tendencies at mid-latitudes;
- hemisphere-correct Coriolis behaviour.

## Ocean currents

- currents remain in water;
- basin-scale circulation often emerges;
- coast geometry affects current paths;
- warm/cold current contrasts occur where expected.

## Precipitation

- tropical convergence zones generally wetter;
- subtropical belts often drier;
- windward slopes wetter than leeward matched slopes;
- continental interiors tend to dry;
- cold air transports less absolute moisture.

## Hydrology

- flow accumulation grows downstream;
- tributaries merge;
- major rivers drain large basins;
- closed basins are explicit, not accidental dead ends.

---

# 50. Earth-like calibration

Do not force exact Earth statistics per seed.

Calibrate broad distributions across seed suites.

Candidate metrics:

```text
ocean fraction
land fraction
number of major landmasses
mean land elevation
mountain fraction
coastline complexity
polar ice fraction
arid fraction
forest-compatible fraction
number of major basins
major river count
river density
endorheic fraction
lake fraction
```

Recommended seed suites:

```text
25 fast seeds
10 final-quality seeds
```

---

# 51. Regression testing

Maintain fixed golden seeds.

Save:

- configuration,
- summary metrics,
- checksums where exact determinism is expected,
- selected diagnostic thumbnails,
- vector feature counts,
- river network statistics.

Dependency upgrades must run the regression suite.

---

# 52. Performance principles

The move away from destructive hexification increases retained data.

Therefore:

- profile memory;
- use compact NumPy dtypes;
- do not keep duplicate raster copies unnecessarily;
- use memory mapping/chunking later if needed;
- use vector LOD for display;
- cache spatial indexes;
- load atlas layers on demand;
- avoid keeping all monthly full-resolution display layers resident in Godot.

Godot does not need every canonical raster in RAM simultaneously.

It needs access to them.

---

# 53. History-oriented physical metrics

The physical generator SHOULD eventually expose derived, technology-neutral cost/potential layers useful for history:

```text
terrain_mobility_cost
river_crossing_cost
navigable_river_potential
coastal_access
freshwater_access
growing_season
primary_productivity_proxy
aridity
floodplain_potential
harbour_geometry_proxy
mountain_pass_candidates
```

These are derived physical features.

Technology-dependent historical use belongs in the future history simulator.

Example:

```text
river is physically navigable potential
```

is physical.

Whether a culture can exploit it with current boats is historical.

---

# 54. Later human vector layers

The spatial architecture MUST be capable of adding canonical human objects later.

Examples:

```text
SettlementPoint
RoadSegment
TradeRoute
Canal
Fortification
AdministrativeBoundary
PoliticalControlPolygon
CulturalRegion
```

Not every human concept should necessarily become a hard polygon.

Culture/language/religion may often be better represented as continuous or mixed fields on the historical grid.

State borders may be derived from control fields and settlement networks.

This is deferred to `HISTORY_SIMULATION_ARCHITECTURE.md`.

---

# 55. Political/cultural geometry principle

Future history must allow multiple spatial concepts to overlap.

Do not assume:

```text
culture border
=
language border
=
religion border
=
state border
=
real control border
```

The physical/spatial model must support independent layers.

---

# 56. Use of WorldEngine

WorldEngine is reference/library material, not the master pipeline.

Allowed uses:

- ocean utilities,
- terrain helpers,
- permeability ideas,
- biome/Holdridge references,
- serialization ideas,
- tests.

Do NOT call the full WorldEngine generator and accept it as final.

Do NOT use WorldEngine precipitation as final climate.

Do NOT use WorldEngine watermap as final hydrology unless fallback is explicitly activated.

---

# 57. PyFlwDir fallback

Primary:

```text
PyFlwDir
```

Fallback only if:

- packaging proves unsolvable,
- target platform is incompatible,
- topology mismatch is fatal.

Fallback:

```text
adapted WorldEngine hydrology
```

Requires ADR.

---

# 58. Extended PyPlatec fallback

Primary:

```text
extended PyPlatec
```

Fallback:

```text
standard PyPlatec
+ inferred tectonic metadata
```

Downstream interfaces must remain the same.

---

# 59. Pipeline stage interface

Recommended:

```python
class WorldGenStage:
    name: str

    def validate_inputs(self, state): ...
    def run(self, state, config, seed): ...
    def validate_outputs(self, state): ...
    def write_diagnostics(self, state, path): ...
```

Vectorization and grid aggregation are separate stages.

Do not create one monolithic function.

---

# 60. Data provenance

Document derivation chains.

Example:

```text
river vector
← PyFlwDir flow network
← conditioned DEM
← eroded high-res terrain
← tectonic terrain
```

Example:

```text
hex annual precipitation
← area-weighted aggregation
← canonical monthly precipitation raster
```

Example:

```text
Holdridge zone
← annual biotemperature
← monthly temperature
+ annual precipitation
+ PET ratio
```

Later historical agents must be able to understand what a field actually means.

---

# 61. Architecture Decision Records

Any major deviation requires:

```text
docs/ADR/ADR-XXXX-title.md
```

Examples requiring ADR:

- dropping PyFlwDir,
- dropping extended PyPlatec,
- reverting to hex-only geography,
- changing projection/topology,
- changing primary ecological system,
- moving canonical simulation logic into Godot,
- removing monthly climate,
- changing canonical river representation,
- introducing a heavyweight GIS stack.

---

# 62. Milestone plan

The local coding agent must create a detailed `IMPLEMENTATION_PLAN.md`, but use the following sequence.

---

## Milestone 0 — repository and environment foundation

Deliver:

- inspect repository;
- confirm Godot/Python environment;
- create `worldsim/`;
- pin dependencies;
- CLI worker;
- config loader;
- deterministic seeds;
- progress protocol;
- test framework;
- licensing files.

Acceptance:

- worker launches;
- progress protocol valid;
- deterministic seed manifest.

---

## Milestone 1 — coordinate system and spatial substrate

Deliver:

- cylindrical equal-area coordinate helpers;
- E–W wrapping utilities;
- latitude conversion;
- no N–S wrapping;
- spatial extent model;
- tests.

Acceptance:

- coordinate round-trips;
- pole/equator mapping valid;
- wrap behaviour valid.

---

## Milestone 2 — PyPlatec baseline

Deliver:

- upstream PyPlatec integration;
- 1024×512 height/plate map;
- seam selection;
- diagnostics.

Acceptance:

- deterministic;
- seam consistent;
- no final N–S connectivity.

---

## Milestone 3 — extended PyPlatec

Deliver:

- fork/vendor;
- crust age;
- plate velocity;
- tests;
- Windows build;
- macOS build attempt.

Acceptance:

- metadata accessible;
- simulation output unchanged where extension should be observational only.

---

## Milestone 4 — tectonic interpretation

Deliver:

- boundaries;
- normals;
- relative motion;
- boundary class;
- tectonic/volcanic/seismic proxies.

Acceptance:

- expected spatial correlations.

---

## Milestone 5 — high-resolution terrain and ocean

Deliver:

- terrain refinement;
- benchmark 4096×2048 vs 2048×1024;
- sea-level calibration;
- bathymetry;
- water bodies;
- coastline extraction prototype.

Acceptance:

- selected production resolution justified by benchmark;
- no E–W seam artefact;
- detailed coast retained independently of hex grid.

---

## Milestone 6 — base seasonal climate

Deliver:

- monthly insolation;
- latitude handling;
- temperature;
- lapse rate;
- ocean/land thermal inertia.

Acceptance:

- correct seasonal inversion;
- polar/elevation temperature trends.

---

## Milestone 7 — atmosphere

Deliver:

- pressure proxy;
- monthly wind vectors;
- circulation zones;
- Coriolis;
- topographic perturbation.

Acceptance:

- coherent fields;
- expected zonal tendencies.

---

## Milestone 8 — ocean circulation

Deliver:

- monthly currents;
- basin constraints;
- SST;
- climate coupling.

Acceptance:

- no land crossing;
- coherent circulation.

---

## Milestone 9 — moisture and precipitation

Deliver:

- evaporation;
- advection;
- orographic precipitation;
- rain shadows;
- convection;
- monthly precipitation.

Acceptance:

- downwind moisture transport;
- detectable windward/leeward effect;
- broad Earth-like wet/dry tendencies.

---

## Milestone 10 — erosion pass one

Deliver:

- climate-informed erosion;
- high-res DEM v1;
- before/after diagnostics.

Acceptance:

- drainage quality improves;
- tectonic macro-relief preserved.

---

## Milestone 11 — PyFlwDir hydrology

Deliver:

- DEM conditioning;
- flow direction;
- accumulation;
- watersheds;
- river mask;
- Strahler order;
- discharge;
- lakes.

Acceptance:

- valid drainage graph;
- sensible accumulation downstream.

---

## Milestone 12 — canonical vector physical geography

Deliver:

- final coastline vectors;
- river node/segment network;
- river polylines;
- lake polygons;
- basin metadata;
- spatial indexes.

Acceptance:

- raster/vector consistency tests pass;
- river topology valid;
- vector features persist independently of hex grid.

---

## Milestone 13 — second erosion and final physical recalculation

Deliver:

- fluvial erosion;
- revised terrain;
- climate correction;
- final hydrology;
- final vector hydrology.

Acceptance:

- stable final geography;
- no catastrophic feedback.

---

## Milestone 14 — soils and Holdridge ecology

Deliver:

- permeability;
- soil-depth/moisture proxies;
- biotemperature;
- PET ratio;
- Holdridge zones.

Acceptance:

- every land point/classifiable raster cell receives valid ecological state or explicit override.

---

## Milestone 15 — 256×128 analytical hex grid

Deliver:

- flat-top grid;
- equal-area projected placement;
- area/sample aggregation;
- object intersection caches;
- neighbourhood topology;
- optional river crossing mask.

Acceptance:

- exactly 32,768 cells;
- correct E–W wrap;
- no N–S wrap;
- cache values match canonical raster/vector data within tolerance.

---

## Milestone 16 — WorldSpatialModel persistence and queries

Deliver:

- canonical raster store;
- canonical vector store;
- hex cache store;
- manifest;
- load/save;
- spatial query API;
- schema versioning.

Acceptance:

- round-trip preserves world;
- query API works without Godot;
- caches can be rebuilt.

---

## Milestone 17 — Godot atlas

Deliver:

- launch worker;
- progress UI;
- high-resolution raster terrain display;
- vector coast/rivers/lakes;
- optional hex overlay;
- map modes;
- inspector;
- monthly climate controls.

Acceptance:

- detailed world is visible without hexification;
- toggling hex grid does not alter geography;
- clicking river inspects river;
- clicking hex inspects aggregate cell.

---

## Milestone 18 — packaging

Deliver:

- Windows packaged worker;
- Windows Godot integration;
- macOS Apple Silicon attempt/support;
- CI;
- licence notices.

Acceptance:

- clean Windows system requires no external Python;
- world generation works from packaged application.

Windows is release-blocking.

macOS may be deferred without architecture change if packaging cost is disproportionate.

---

## Milestone 19 — environmental timeline scaffold

Deliver:

- `EnvironmentTimeline` interface;
- baseline environment snapshot;
- anomaly schema;
- time-indexed query API;
- no full palaeoclimate implementation yet.

Acceptance:

- the same spatial query can retrieve baseline or time-indexed environmental modifiers;
- storage can later support changing climate/sea level without redesigning `WorldSpatialModel`.

---

# 63. What is explicitly NOT in this document

Do not implement detailed historical simulation merely because the physical architecture exposes hooks.

Out of scope here:

```text
population demography
culture genesis
language evolution
technology diffusion
religious memes
settlement hierarchy
trade economics
state formation
war
collapse
political borders
historical narrative generation
```

These require a dedicated architecture document.

Only generic spatial support for those systems belongs here.

---

# 64. Immediate local-agent workflow

Before Milestone 0, the local agent should:

1. read this document completely;
2. inspect the full repository;
3. inspect current Godot project structure;
4. verify Python 3.12;
5. inspect C/C++ build tools;
6. inspect CI;
7. assess PyPlatec extension feasibility;
8. assess PyFlwDir packaging;
9. assess practical 4096×2048 raster memory/runtime;
10. create `docs/IMPLEMENTATION_PLAN.md`;
11. map conceptual modules to actual paths;
12. list true architecture conflicts;
13. stop before implementation.

Minor implementation choices should be resolved autonomously.

---

# 65. Agent implementation rules

## MUST

- preserve canonical raster/vector data;
- treat hex data as derived/cache data;
- preserve deterministic seeds;
- make physical simulation executable without Godot;
- validate every stage;
- produce diagnostics;
- maintain stable IDs for vector objects;
- separate display LOD from canonical geometry;
- implement spatial query APIs;
- benchmark high-resolution stages before locking memory-heavy choices.

## MUST NOT

- discard high-resolution terrain after hex aggregation;
- replace exact river geometry with hex flags;
- turn coastlines into hex stair-steps as canonical geography;
- use TileMap as the world database;
- paint biomes directly;
- generate precipitation as independent noise;
- generate rivers as random paths;
- make Godot the only way to run the simulation;
- collapse culture/language/state into one future ownership field;
- add north–south wrapping.

---

# 66. Source/reference baseline

Primary technical references:

- Godot Engine documentation
- PyPlatec / plate-tectonics
- WorldEngine
- PyFlwDir

Verified architecture observations from prior research:

1. WorldEngine uses PyPlatec for tectonic generation.
2. WorldEngine provides useful reference implementations but its climate/hydrology are not sufficient as the final target.
3. Native plate-tectonics exposes more useful tectonic metadata than the standard Python binding.
4. PyFlwDir is the preferred hydrology engine.
5. PyPlatec topology requires downstream correction for cylindrical-world semantics.
6. High-resolution raster generation and a separate analytical grid are compatible with the selected toolchain.

---

# 67. Final architecture invariant

The causal physical pipeline remains:

```text
TECTONICS
    ↓
HIGH-RES TOPOGRAPHY
    ↓
OCEAN GEOMETRY
    ↓
ATMOSPHERE + OCEAN CIRCULATION
    ↓
MONTHLY CLIMATE
    ↓
EROSION
    ↓
HYDROLOGY
    ↓
ECOLOGY
    ↓
CANONICAL RASTER + VECTOR WORLD
    ↓
256×128 ANALYTICAL HEX INDEX
    ↓
FUTURE HISTORY SIMULATION
    ↓
GODOT INTERACTIVE ATLAS
```

The world MUST remain richer than the analysis grid.

---

# 68. Definition of Done for Physical World v1

Physical World v1 is complete when:

- a master seed deterministically creates an Earth-like cylindrical world;
- canonical high-resolution terrain is preserved;
- extended PyPlatec or documented fallback drives tectonic interpretation;
- bathymetry and detailed coastlines exist independently of the hex grid;
- monthly climate is physically motivated;
- coherent winds exist;
- coherent ocean currents affect SST;
- moisture transport produces precipitation and rain shadows;
- two-stage erosion produces stable terrain;
- PyFlwDir produces coherent drainage and watersheds;
- rivers exist as a canonical vector/network representation;
- lakes exist as canonical geographic objects;
- Holdridge zones derive from climate;
- the 256×128 hex grid aggregates rather than replaces physical geography;
- spatial query APIs work without Godot;
- canonical data can be saved and reloaded;
- Godot can render detailed raster/vector geography and optionally overlay the analytical hex grid;
- diagnostic layers expose every major causal stage;
- fixed-seed regression tests pass;
- Windows packaging works without requiring a user-installed Python runtime;
- the storage model can later accept environmental anomalies and historical layers without architectural replacement.

At that point, the physical world is ready to become the substrate for a separate long-term history simulation architecture.
