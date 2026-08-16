# HISTORY_SIMULATION_ARCHITECTURE.md

> **Status:** Architecture annex — v0.1  
> **Date:** 2026-08-14  
> **Audience:** coding agents and developers implementing the first historical-simulation substrate  
> **Authority:** Companion specification to WORLDGEN_ARCHITECTURE.md  
> **Scope of this version:** abstract turns, automatic simulation runs, immutable history and playback, Godot configuration, and a minimal multi-species population-expansion model

---

# 1. Purpose

Define the first executable historical-simulation layer built on top of the physical world and the 256 × 128 analytical hex grid.

This annex deliberately starts below the level of cultures, settlements, technologies, states, warfare, or diplomacy.

The first historical milestone is:

~~~text
TURN ENGINE
    ↓
HISTORY STORAGE
    ↓
TIMELINE PLAYBACK
    ↓
ENVIRONMENT ADAPTER
    ↓
POPULATION GROWTH
    ↓
NEIGHBOUR EXPANSION
~~~

The population model is the first consumer of a generic turn engine. It MUST NOT define the turn engine itself.

The implementation must make it possible to:

- configure simulation and species parameters manually in Godot;
- select a generated world;
- define one or more species and spawn points;
- enter a number of turns to execute;
- run those turns automatically;
- observe progress;
- retain turn 0 and every completed turn in history;
- inspect any recorded turn with a timeline slider;
- run the same simulation headlessly without Godot;
- reproduce a run from the frozen configuration and seed.

---

# 2. Relationship to WORLDGEN_ARCHITECTURE.md

WORLDGEN_ARCHITECTURE.md remains authoritative for:

- canonical raster and vector geography;
- WorldSpatialModel;
- the 256 × 128 flat-top analytical hex grid;
- east–west wrapping and absence of north–south wrapping;
- physical and ecological data;
- EnvironmentTimeline;
- Python worker ownership;
- Godot atlas responsibilities;
- persistence and communication principles.

This annex is authoritative only for the first historical-simulation substrate described here.

If the documents conflict:

1. WORLDGEN_ARCHITECTURE.md controls physical and spatial architecture.
2. This document controls abstract turns, history playback, and Population v0.1.
3. A major unresolved conflict requires an ADR.

This annex preserves the core boundary:

~~~text
PYTHON / WORLDSIM WORKER
    canonical simulation logic
    turn execution
    population calculations
    history persistence
    validation

GODOT
    manual configuration
    run controls
    progress
    timeline slider
    atlas rendering
    inspection
~~~

Godot MUST NOT become the canonical implementation of population growth, migration, or turn resolution.

---

# 3. Scope

## 3.1 Included in v0.1

- abstract integer turns;
- automatic execution of a requested turn count;
- a deterministic run lifecycle;
- turn 0 as the initial state;
- immutable completed-turn records;
- separate computed and viewed turns;
- full-snapshot history for the first implementation;
- a replaceable HistoryStore interface;
- per-turn events and aggregate metrics;
- manually editable Godot configuration resources;
- serialisation of effective configuration to the worker;
- stable species and spawn definitions;
- multiple species;
- multiple species in one hex;
- continuous population values assigned to hexes;
- environment-dependent carrying capacity;
- density-limited local growth;
- density-driven dispersal;
- dispersal to one or more neighbouring hexes;
- at most one hex edge crossed by a population unit per turn;
- deterministic diagnostics and tests.

## 3.2 Explicitly deferred

- mapping turns to years, months, or dates;
- age and sex structure;
- births and deaths as separate demographic cohorts;
- explicit food stocks;
- seasonal subsistence;
- hunting depletion;
- agriculture;
- detailed resource competition;
- inter-species competition;
- predation;
- disease;
- culture;
- language;
- technology;
- religion;
- settlements;
- trade;
- states;
- diplomacy;
- warfare;
- dynamic borders;
- palaeoclimate implementation;
- branching or editing past history;
- user intervention during a completed turn;
- narrative generation.

The data model MUST remain extensible for these systems, but they MUST NOT be implemented as hidden complexity inside Population v0.1.

---

# 4. Locked decisions

| Topic | Decision |
|---|---|
| Simulation owner | Python worldsim worker |
| Godot role | configuration, run control, progress, atlas, timeline playback |
| Time unit in v0.1 | abstract integer turn |
| User start input | number of turns, seed, species, spawn points, editable model parameters |
| Turn execution | automatic after Start |
| Initial state | turn 0 |
| Result of N turns | states 0 through N, therefore N + 1 viewable states |
| History interaction | read-only slider/playback |
| Historical spatial substrate | 256 × 128 analytical hex grid |
| Population location | species population value per hex |
| Population numeric model | continuous non-negative quantity |
| Initial environment | static baseline or time-indexed query through a stable adapter |
| Growth | carrying-capacity limited |
| Expansion trigger | configurable local density pressure |
| Expansion destination | one or more eligible neighbouring hexes |
| Maximum movement per turn | one hex edge in Population v0.1 |
| State updates | simultaneous commit from a read-only turn input |
| Multiple species in one hex | allowed |
| Competition | absent in v0.1 |
| Detailed biome simulation as blocker | no |
| Reproducibility | master seed plus frozen resolved configuration |
| History implementation | full snapshots initially, hidden behind HistoryStore |

Changes to these decisions require either a new document version or an ADR.

---

# 5. Core architecture

Conceptual ownership:

~~~text
WorldSpatialModel
    │
    ├── canonical physical rasters/vectors
    ├── 256 × 128 analytical hex grid
    └── EnvironmentTimeline
              │
              ▼
EnvironmentAdapter
              │
              ▼
HistoricalSimulationState at turn t
              │
              ▼
TurnPipeline
    ├── PopulationGrowthSystem
    ├── PopulationDispersalSystem
    ├── CommitSystem
    └── ValidationAndMetricsSystem
              │
              ▼
HistoricalSimulationState at turn t + 1
              │
              ├── HistoryStore
              ├── EventStore
              └── MetricsStore
                         │
                         ▼
                    Godot atlas
~~~

The renderer MUST read persisted or queried state.

The renderer MUST NOT own canonical population state.

---

# 6. Repository extension

Recommended conceptual extension:

~~~text
repo/
│
├── godot/
│   ├── atlas/
│   │   ├── TimelineController.gd
│   │   ├── HistoricalMapModeController.gd
│   │   └── PopulationInspectorPanel.gd
│   │
│   ├── simulation_bridge/
│   │   ├── SimulationRunner.gd
│   │   ├── SimulationProtocol.gd
│   │   └── ProgressController.gd
│   │
│   ├── simulation_config/
│   │   ├── SimulationConfigResource.gd
│   │   ├── SpeciesConfigResource.gd
│   │   └── SpawnPointResource.gd
│   │
│   └── scenes/
│       └── simulation/
│
├── worldsim/
│   └── src/worldsim/
│       ├── history/
│       │   ├── config.py
│       │   ├── state.py
│       │   ├── runner.py
│       │   ├── turn_pipeline.py
│       │   ├── changes.py
│       │   ├── events.py
│       │   ├── metrics.py
│       │   ├── history_store.py
│       │   ├── environment_adapter.py
│       │   └── population/
│       │       ├── config.py
│       │       ├── capacity.py
│       │       ├── growth.py
│       │       ├── dispersal.py
│       │       └── validation.py
│       │
│       └── diagnostics/
│           └── history/
│
└── docs/
    ├── WORLDGEN_ARCHITECTURE.md
    └── HISTORY_SIMULATION_ARCHITECTURE.md
~~~

Exact paths may be adapted after repository inspection.

The separation of responsibilities MUST remain.

---

# 7. Time model

## 7.1 Abstract turns

In v0.1, simulation time is:

~~~text
turn_index: non-negative integer
~~~

No real-world duration is assigned to a turn.

Population parameters are therefore expressed per turn, not per year.

The implementation MUST NOT silently assume:

- one year per turn;
- ten years per turn;
- a calendar start date;
- a historical epoch.

## 7.2 Turn 0

Turn 0 is the fully validated initial state after:

- loading the selected world;
- resolving configuration;
- registering species;
- applying spawn points;
- validating carrying capacity and topology;
- before any growth or dispersal.

If a user requests N turns:

~~~text
requested_turns = N
computed transitions = N
viewable states = N + 1
viewable turn indexes = 0 ... N
~~~

A request for zero turns MAY be allowed and produces only turn 0.

## 7.3 Future temporal scale

A later schema may add:

~~~text
TemporalScale:
    duration_per_turn
    calendar_system
    epoch
    display_mapping
~~~

That future mapping MUST be an adapter over turn indexes.

It MUST NOT require replacing the turn engine.

---

# 8. Simulation run lifecycle

Recommended run states:

~~~text
CREATED
VALIDATING
RUNNING
CANCELLING
COMPLETED
CANCELLED
FAILED
~~~

Godot may display CREATED as IDLE.

Allowed primary transitions:

~~~text
CREATED → VALIDATING
VALIDATING → RUNNING
VALIDATING → FAILED
RUNNING → COMPLETED
RUNNING → CANCELLING
CANCELLING → CANCELLED
RUNNING → FAILED
~~~

A completed, cancelled, or failed run is immutable.

Starting again creates a new run.

It MUST NOT overwrite the previous run unless the user explicitly requests deletion outside the simulation process.

---

# 9. Automatic runner

The user provides:

- selected world dataset;
- requested number of turns;
- master seed;
- species definitions;
- spawn points;
- model parameters.

The worker then executes all requested turns automatically.

There is no required manual Next Turn interaction in v0.1.

Conceptual worker operation:

~~~text
validate request
resolve and freeze configuration
build initial state
save turn 0

for turn in 1 ... requested_turns:
    execute one complete turn
    validate committed state
    persist completed state
    persist events and metrics
    emit progress

finalise manifest
emit completion
~~~

The worker SHOULD support cancellation between turns.

Cancellation MUST NOT leave a half-committed turn visible as completed.

The latest valid state after cancellation is the last fully committed turn.

---

# 10. Computed turn vs viewed turn

The application MUST distinguish:

~~~text
computed_turn
    latest fully calculated and committed turn

viewed_turn
    history state currently displayed in Godot
~~~

Changing viewed_turn:

- changes only the atlas presentation;
- does not mutate the worker state;
- does not resume or reverse the simulation;
- does not create a new branch;
- does not alter later snapshots.

At completion:

~~~text
computed_turn = requested_turns
viewed_turn may be any integer from 0 to computed_turn
~~~

During a run, Godot MAY allow browsing already completed turns.

This is optional for the first UI, but the state model MUST not prevent it.

---

# 11. Turn pipeline

Every turn is a transaction.

All systems read from an immutable input state for turn t.

They produce changes that are committed together as state t + 1.

Canonical sequence for Population v0.1:

~~~text
1. begin turn
2. query environment for turn t
3. calculate local population growth
4. calculate dispersal pressure and migration proposals
5. resolve valid migration proposals
6. commit all population changes simultaneously
7. apply numerical cleanup
8. validate invariants
9. calculate events and metrics
10. persist turn t + 1
11. emit turn-completed progress
~~~

No species or hex may benefit from being processed earlier in an iteration.

Newly arrived migrants MUST NOT disperse again during the same turn.

The same one-turn input snapshot must be used for all equivalent calculations.

---

# 12. Turn-system interface

Recommended conceptual interface:

~~~python
class TurnSystem:
    name: str
    order: int

    def validate_inputs(self, context): ...
    def propose(self, context, read_only_state): ...
    def validate_changes(self, context, change_set): ...
~~~

The central pipeline owns commit.

A system SHOULD return a ChangeSet rather than mutate HistoricalSimulationState directly.

Conceptual ChangeSet:

~~~text
ChangeSet:
    population_deltas
    emitted_events
    diagnostics
~~~

Future systems may require multi-phase resolution.

They must be added through explicit pipeline phases, not by introducing hidden mid-turn mutation.

---

# 13. Historical state

Recommended conceptual state:

~~~text
HistoricalSimulationState:
    schema_version
    run_id
    turn_index
    world_fingerprint
    species_registry
    population_by_species_and_hex
    future_human_layers
    metadata
~~~

Population storage SHOULD use compact numeric arrays indexed by:

~~~text
species_index × hex_index
~~~

Do not represent every population value as a Godot Node or a Python object.

Stable species IDs and stable hex IDs MUST be preserved across snapshots.

The physical world is referenced by fingerprint or dataset identity.

It is not duplicated inside every historical snapshot.

---

# 14. History records

Every completed turn produces a logical TurnRecord:

~~~text
TurnRecord:
    turn_index
    state_reference
    event_range
    metrics
    checksum
~~~

Turn records are immutable after successful commit.

The first implementation MAY store one full population snapshot per turn.

However, consumers MUST access history through:

~~~text
HistoryStore
~~~

and not through assumptions about filenames or snapshot layout.

Required conceptual API:

~~~python
history.first_turn()
history.latest_turn()
history.has_turn(turn_index)
history.load_state(turn_index)
history.load_metrics(turn_index)
history.load_events(turn_index)
~~~

This allows later replacement with:

~~~text
periodic full snapshots
+
deltas between snapshots
+
event log
~~~

without redesigning the Godot timeline.

---

# 15. History storage

Recommended conceptual layout:

~~~text
world/
└── timeline/
    └── history/
        └── runs/
            └── <run_id>/
                ├── manifest.json
                ├── config.resolved.json
                ├── species.json
                ├── spawn_points.json
                ├── snapshots/
                │   ├── turn_000000.*
                │   ├── turn_000001.*
                │   └── ...
                ├── metrics.*
                ├── events.*
                └── diagnostics/
~~~

Exact binary formats must align with the persistence decisions made for WorldSpatialModel.

Large population arrays MUST NOT be stored as JSON.

JSON is appropriate for:

- manifests;
- small configuration records;
- event metadata;
- debug fixtures.

Snapshot writes SHOULD be atomic.

A turn becomes visible to consumers only after:

1. state data is written successfully;
2. checksum and validation succeed;
3. the history index is updated.

---

# 16. Events and metrics

Snapshots answer:

> What did the world look like?

Events answer:

> What changed during this turn?

Metrics answer:

> What broad trend is occurring?

Population v0.1 SHOULD record at least:

~~~text
per species:
    total_population
    occupied_hex_count
    new_colonised_hex_count
    locally_extinct_hex_count
    total_local_growth
    total_emigrants
    total_immigrants

global:
    total_population
    total_occupied_species_hex_pairs
~~~

Candidate events:

~~~text
PopulationSpawned
PopulationExpanded
HexColonised
LocalPopulationExtinct
SimulationStarted
TurnCompleted
SimulationCompleted
SimulationCancelled
~~~

Events are diagnostic facts.

They are not narrative prose in v0.1.

---

# 17. Configuration architecture

## 17.1 Principle

All meaningful constants MUST be editable configuration or explicitly derived values.

Population rules MUST NOT hide arbitrary tuning values in algorithm code.

Godot is the preferred manual authoring surface.

The Python worker remains the canonical validator and executor.

## 17.2 Godot resources

Recommended editor-facing resources:

~~~text
SimulationConfigResource
PopulationModelConfigResource
SpeciesConfigResource
SpawnPointResource
~~~

Godot resources are convenient editable assets.

They are not the canonical portable run record.

At Start, Godot MUST:

1. resolve all referenced resources;
2. serialise them into the worker request schema;
3. send or persist the request;
4. receive validation success or structured errors;
5. preserve the resolved configuration returned by the worker.

## 17.3 Frozen run configuration

At the beginning of validation, the worker creates:

~~~text
config.resolved.json
~~~

or an equivalent versioned record.

The resolved record MUST include:

- schema version;
- requested turn count;
- master seed;
- world fingerprint;
- effective species parameters;
- effective spawn points;
- effective environment adapter settings;
- effective history settings;
- defaults expanded to explicit values.

Inspector changes made after Start MUST NOT alter the active run.

A changed configuration requires a new run.

---

# 18. Simulation configuration contract

Recommended logical schema:

~~~yaml
schema_version: 1

run:
  requested_turns: 100
  master_seed: 183716
  history_mode: full_snapshots
  progress_emit_interval_turns: 1

environment:
  adapter: baseline_hex_environment
  productivity_field: primary_productivity_proxy
  movement_cost_field: terrain_mobility_cost

population_model:
  numerical_epsilon: configurable
  allow_multiple_species_per_hex: true

species:
  - species_id: species_1
    display_name: Species 1
    display_color: configurable
    initial_population_default: configurable
    growth_rate_per_turn: configurable
    maximum_density_at_productivity_one: configurable
    dispersal_rate: configurable
    expansion_threshold: configurable
    minimum_founders: configurable
    habitat_suitability_profile: configurable
    movement_cost_sensitivity: configurable

spawn_points:
  - species_id: species_1
    hex_id: configurable
    initial_population: configurable
~~~

The values shown as configurable are intentionally not calibrated in this document.

The local agent MUST expose them with:

- Inspector descriptions;
- valid ranges;
- validation errors;
- sensible development defaults clearly labelled as provisional.

Calibration is a later empirical task.

---

# 19. Validation of user configuration

The worker MUST reject invalid configuration before turn 0.

Required checks include:

- requested_turns is a non-negative integer;
- master_seed is valid for the seed system;
- species IDs are unique and stable;
- referenced species exist;
- referenced hex IDs exist;
- spawn populations are positive;
- spawn hexes are inhabitable for the species under the selected adapter;
- growth rate is within the supported numerical range;
- dispersal rate is between 0 and 1;
- expansion threshold is between 0 and 1 and below 1 for the v0.1 formula;
- minimum founders is non-negative;
- maximum density is positive;
- movement costs are finite and positive where movement is permitted;
- no NaN or Inf appears in configuration;
- history output location is writable;
- the world schema is compatible.

Validation errors MUST identify:

- field path;
- invalid value;
- reason;
- expected range or type.

The worker MUST NOT silently clamp invalid user configuration at run start.

---

# 20. Species definition

SpeciesDefinition v0.1 contains ecological and demographic parameters, not culture.

Recommended fields:

~~~text
species_id
display_name
display_color
growth_rate_per_turn
maximum_density_at_productivity_one
dispersal_rate
expansion_threshold
minimum_founders
habitat_suitability_profile
movement_cost_sensitivity
~~~

Display fields do not affect simulation.

Simulation fields are frozen per run.

The architecture MUST permit two or more species to occupy the same hex.

In v0.1:

- each species has its own carrying capacity calculation;
- species do not reduce each other's carrying capacity;
- species do not kill, displace, assimilate, or hybridise with one another;
- one species does not affect another species' growth or movement.

This independence is intentional scaffolding, not a claim of ecological realism.

---

# 21. Spawn points

A spawn point creates initial population in turn 0.

Required fields:

~~~text
species_id
hex_id
initial_population
~~~

Optional display metadata MAY be added.

Multiple spawn points for the same species are allowed.

Multiple species may spawn in the same hex.

If multiple spawn definitions target the same species and hex, the worker SHOULD sum them deterministically and record the resolved value.

Spawn validation occurs before turn 0 is persisted.

Spawn placement MUST respect:

- valid hex topology;
- environment suitability;
- passability;
- finite carrying-capacity inputs.

---

# 22. Environment adapter

Population logic MUST NOT read raw climate rasters or Holdridge data directly.

It consumes a stable EnvironmentAdapter.

Required conceptual queries:

~~~python
environment.hex_area(hex_id)
environment.is_passable(hex_id, species_id, turn_index)
environment.productivity(hex_id, species_id, turn_index)
environment.habitat_suitability(hex_id, species_id, turn_index)
environment.movement_cost(from_hex, to_hex, species_id, turn_index)
environment.neighbours(hex_id)
~~~

The adapter may initially use:

- land fraction;
- primary_productivity_proxy;
- Holdridge fractions;
- freshwater access;
- terrain mobility cost;
- slope or roughness;
- coast or river information where justified.

Detailed biome simulation is NOT a prerequisite for Population v0.1.

The minimum useful environment is:

~~~text
passability
productivity
movement cost
hex area
~~~

The first technical fixture MAY use:

~~~text
uniform productivity on passable land
water impassable
uniform neighbour movement cost
~~~

The population module must still obtain these values through the adapter, so the fixture can later be replaced without changing population algorithms.

---

# 23. Carrying capacity

Each species–hex pair receives a carrying capacity:

~~~text
K(hex, species, turn)
~~~

Recommended v0.1 derivation:

~~~text
K =
    habitable_land_area
    × maximum_species_density
    × productivity
    × habitat_suitability
~~~

Where:

~~~text
habitable_land_area ≥ 0
maximum_species_density > 0
productivity ∈ [0, 1]
habitat_suitability ∈ [0, 1]
K ≥ 0
~~~

The calculation SHOULD be isolated in a CarryingCapacityProvider.

Population growth and dispersal MUST request K through this provider.

They MUST NOT duplicate its formula.

For a static baseline environment, K may be cached for the whole run.

For a future time-varying environment, K is queried or recalculated by turn.

Population v0.1 does not require detailed food categories.

K is an intentionally aggregated ecological constraint.

---

# 24. Local population growth

Population is represented as a continuous non-negative value:

~~~text
N(hex, species, turn) ≥ 0
~~~

Continuous values are preferred over integer rounding because:

- population is an aggregate;
- repeated rounding creates artificial extinctions or growth;
- later large populations make individual-level precision meaningless.

The default v0.1 model SHOULD use a stable carrying-capacity-limited recurrence.

Recommended Beverton–Holt form:

~~~text
R = 1 + growth_rate_per_turn

N_grown =
    (R × N)
    /
    (1 + (R - 1) × N / K)
~~~

For:

~~~text
N ≥ 0
K > 0
R ≥ 1
~~~

This provides:

- near-multiplicative growth when N is small relative to K;
- slowing growth near K;
- a stable approach toward K;
- positive values without logistic-map oscillation for normal positive parameters.

If future models require negative intrinsic growth, shocks, or explicit mortality, they should add a separate mortality or stress term through a versioned model.

For K = 0, v0.1 MUST forbid spawning and colonisation.

Handling a previously inhabited hex that becomes uninhabitable belongs to the future dynamic-environment mortality model.

---

# 25. Expansion pressure

Expansion is driven by local density relative to carrying capacity.

Define:

~~~text
density_ratio = N_grown / K
threshold = expansion_threshold
~~~

Recommended pressure:

~~~text
pressure =
    clamp(
        (density_ratio - threshold)
        /
        (1 - threshold),
        0,
        1
    )
~~~

Potential emigrants:

~~~text
emigrant_pool =
    N_grown
    × dispersal_rate
    × pressure
~~~

Consequences:

- below the threshold, no density-driven expansion occurs;
- above the threshold, expansion increases smoothly;
- near or above carrying capacity, the dispersal fraction approaches its configured maximum;
- there is no arbitrary single population-number trigger shared by all hex sizes and species.

The threshold and dispersal rate MUST be editable per species.

---

# 26. Eligible destination hexes

A neighbouring hex is eligible only when:

- it is a true neighbour under the analytical-grid topology;
- east–west wrap is handled correctly;
- north–south wrap is absent;
- the target is passable for the species;
- target carrying capacity is positive;
- movement cost is finite and positive;
- the environment adapter does not mark the edge as blocked.

No target outside the immediate neighbour set is eligible in v0.1.

Future route, river, maritime, or long-distance migration systems may add other movement graphs.

They MUST NOT be simulated by silently allowing multi-hex jumps in this model.

---

# 27. Destination weights

Potential emigrants may be distributed among multiple eligible neighbouring hexes.

This avoids forcing every expansion to choose one arbitrary direction.

Recommended components:

~~~text
free_capacity_ratio =
    max(0, 1 - target_population / target_K)

destination_weight =
    free_capacity_ratio
    × target_habitat_suitability
    × movement_permeability
~~~

Movement permeability may initially be:

~~~text
1 / movement_cost
~~~

or another monotonic transformation controlled by movement_cost_sensitivity.

Only positive finite weights are valid.

If all destination weights are zero:

- no migration occurs;
- the potential emigrants remain in the source hex.

Valid weights are normalised to distribute the emigrant pool.

---

# 28. Founder threshold and establishment

For an unoccupied target hex:

~~~text
incoming_population ≥ minimum_founders
~~~

is required to establish a new local population.

If proposed incoming population is below the threshold:

- colonisation fails;
- the rejected amount returns to the source population in v0.1;
- no hidden migration mortality is applied;
- a diagnostic event MAY record the failed attempt.

For an already occupied target hex of the same species, minimum founders need not apply.

The algorithm MUST resolve thresholds deterministically.

It MUST not depend on dictionary or hash iteration order.

---

# 29. Simultaneous migration commit

Migration is a redistribution within a species.

For each accepted transfer:

~~~text
source_delta = -migrants
target_delta = +migrants
~~~

All transfers are calculated before any are applied.

Required invariants before later mortality is added:

~~~text
sum of source losses
=
sum of target gains
~~~

No population may:

- move from A to B;
- then move from B to C;
- during the same turn.

Incoming migration may temporarily raise a target above K.

Do not silently delete surplus population by clamping to K.

Later turns will respond through density pressure and carrying-capacity-limited growth.

---

# 30. Multiple species

Population arrays are keyed by species and hex.

Example:

~~~text
Hex 100:
    species_1 = 840
    species_2 = 215
~~~

This is valid in v0.1.

Growth and movement are calculated independently for each species.

Population v0.1 MUST NOT assume:

~~~text
one hex = one species
~~~

The future competition system may introduce:

- shared resources;
- competitive coefficients;
- niche overlap;
- predation;
- displacement;
- coexistence equilibria.

These must be explicit later systems, not implicit behaviour in the current carrying capacity formula.

---

# 31. Numerical rules

The implementation MUST enforce:

- no NaN;
- no Inf;
- no negative population after commit;
- deterministic ordering;
- stable handling of values near zero;
- documented numeric dtype;
- no silent integer truncation.

A configurable numerical epsilon MAY convert extremely small positive values to zero.

If enabled, the cleanup:

- occurs after commit;
- records local extinction when appropriate;
- uses one frozen epsilon for the run.

Exact computation and persistence dtypes must be selected after profiling.

The choice MUST be documented and covered by round-trip tests.

---

# 32. Determinism

The same:

- world dataset;
- world fingerprint;
- resolved configuration;
- master seed;
- code/schema version;
- target numeric implementation;

MUST produce the same historical run within the documented determinism guarantees.

Population v0.1 may be fully deterministic without random draws.

The architecture must nevertheless reserve named random streams.

Recommended named derivation:

~~~text
hash(
    master_seed,
    "history",
    system_name,
    turn_index,
    stable_entity_id,
    schema_version
)
~~~

Do not consume one mutable global RNG across all systems.

Adding an unrelated future system must not shift all population random draws.

Algorithms MUST NOT depend on unordered map iteration.

Parallelisation MUST preserve deterministic reduction and commit order.

---

# 33. Godot manual configuration

The Godot interface SHOULD provide two levels.

## 33.1 Editor configuration

Reusable Resource assets for:

- simulation defaults;
- population model defaults;
- species definitions;
- optional spawn presets.

Inspector fields SHOULD use:

- categories;
- tooltips;
- numeric ranges;
- units stated as per turn;
- warnings for provisional defaults.

## 33.2 Run setup interface

Before Start, the user should be able to:

- select a world;
- enter requested turn count;
- enter or randomise master seed;
- select species resources;
- add, remove, and edit spawn points;
- choose spawn hexes from the map if practical;
- review validation warnings;
- start the run.

The first UI MAY require spawn hex IDs to be entered manually if map picking is not yet available.

The architecture SHOULD allow map picking later without changing the worker schema.

---

# 34. Godot run controls

Minimum controls:

~~~text
Requested turns: [numeric input]
Seed:            [numeric/text input]

[ Start simulation ]
[ Cancel ] when running

Progress:
    completed turn / requested turns
    percentage
    worker status
~~~

Pause is optional in v0.1.

Cancellation between turns is preferred to a complex pause/resume implementation.

The UI MUST display structured worker errors rather than only a generic failure.

---

# 35. Timeline playback UI

After at least turn 0 is available:

~~~text
[ |< ] [ < ]  Turn 37 / 100  [ > ] [ >| ]

Timeline: 0 ─────────────●──────────── 100
~~~

Minimum behaviour:

- slider range is 0 through latest available turn;
- selecting a turn loads that exact immutable state;
- previous and next buttons move one turn;
- first and last buttons jump to boundaries;
- current viewed turn is displayed;
- loading state shows progress if not immediate;
- map rendering updates without changing simulation state.

Optional later behaviour:

- playback animation;
- playback speed;
- follow-latest toggle while simulation runs;
- metric graphs;
- event markers;
- comparison between two turns.

The timeline controller MUST use HistoryStore APIs.

It MUST NOT construct filenames directly.

---

# 36. Population atlas mode

The first historical map mode SHOULD allow:

- selecting one species;
- showing population amount;
- showing population density;
- showing occupancy;
- optionally showing density ratio N / K;
- inspecting all species present in a clicked hex.

The display should distinguish:

~~~text
population amount
population density
environmental carrying capacity
relative pressure N / K
~~~

These are not interchangeable.

A useful diagnostic map is:

~~~text
density pressure = N / K
~~~

because it explains why expansion is or is not occurring.

---

# 37. Worker communication protocol

Use the newline-delimited JSON control/status protocol established by WORLDGEN_ARCHITECTURE.md.

Suggested events:

~~~json
{"event":"history_validation_started"}
{"event":"history_validation_complete","run_id":"..."}
{"event":"history_started","run_id":"...","requested_turns":100}
{"event":"history_turn_started","turn":1}
{"event":"history_turn_complete","turn":1,"progress":0.01}
{"event":"history_turn_complete","turn":100,"progress":1.0}
{"event":"history_complete","run_id":"...","latest_turn":100,"history_path":"..."}
~~~

Cancellation:

~~~json
{"command":"cancel_history","run_id":"..."}
~~~

Error:

~~~json
{
  "event":"error",
  "stage":"history",
  "turn":37,
  "code":"HISTORY_TURN_FAILED",
  "message":"...",
  "trace_path":"..."
}
~~~

Large snapshots MUST NOT be transmitted over stdout as JSON.

Godot should load them from persisted storage or a structured query interface.

---

# 38. Headless operation

The same simulation must run without Godot.

Conceptual development command:

~~~text
python -m worldsim simulate-history \
    --world <world_path> \
    --request <history_request.json>
~~~

Conceptual packaged command:

~~~text
worldsim_worker simulate-history \
    --world <world_path> \
    --request <history_request.json>
~~~

A run launched from Godot and an equivalent headless run MUST use the same worker logic.

Godot-specific configuration resources must be resolved into the same portable request schema.

---

# 39. Performance and responsiveness

Turn count may become large.

Therefore:

- the worker runs outside the Godot render loop;
- Godot remains responsive while simulation runs;
- progress events are rate-limited if turns are extremely fast;
- snapshot writes are profiled;
- population arrays use compact contiguous storage where practical;
- the atlas loads only the viewed turn;
- history loading may be cached;
- full snapshots are accepted for the first implementation only after a memory estimate.

Before committing to full snapshots for a production-scale run, estimate:

~~~text
species_count
× hex_count
× stored_turn_count
× bytes_per_population_value
~~~

For v0.1, correctness and inspectability take priority over delta compression.

HistoryStore must make later optimisation possible.

---

# 40. Failure and recovery

A failed turn MUST NOT corrupt the previous valid turn.

The run manifest should distinguish:

~~~text
requested_turns
latest_committed_turn
run_status
failure_turn if any
failure_code if any
~~~

On failure:

- persist diagnostic information;
- retain earlier committed turns;
- mark the run FAILED;
- do not mark the incomplete turn as available;
- allow Godot to browse earlier valid turns.

Resuming a failed run is deferred.

The first implementation may require starting a new run after correction.

---

# 41. Software invariants

## 41.1 Turn engine

- turn indexes are contiguous from 0;
- turn 0 always exists for a validated run;
- N requested transitions yield latest turn N;
- completed states are immutable;
- no half-turn is visible;
- computed_turn and viewed_turn are independent;
- a cancelled run ends on a fully committed turn;
- system order is explicit and versioned.

## 41.2 Population

- population values are finite and non-negative;
- no invalid species or hex IDs;
- no colonisation of K = 0;
- no movement across non-neighbour edges;
- E–W wrap follows WorldSpatialModel;
- N–S wrap never occurs;
- migration conserves population in v0.1;
- rejected founder groups return to source;
- newly arrived migrants cannot move again in the same turn;
- co-located species remain independent in v0.1.

## 41.3 History

- snapshot turn index matches its record;
- state checksum matches persisted data;
- configuration is frozen;
- world fingerprint matches the loaded world;
- history round-trip preserves population state;
- the slider cannot mutate state.

---

# 42. Required tests

## 42.1 Turn tests

- zero requested turns produces only turn 0;
- one requested turn produces turns 0 and 1;
- one hundred requested turns produces turns 0 through 100;
- all turn records are contiguous;
- a deliberate failure leaves the preceding turn valid;
- cancellation exposes only fully committed turns;
- changing viewed_turn does not change computed_turn.

## 42.2 Determinism tests

- same world, config, seed, and version produce identical checksums;
- different UI iteration order does not change the result;
- species registration order does not change stable-ID results;
- adding an unused random stream does not shift existing streams.

## 42.3 Growth tests

- N = 0 remains zero without a spawn or immigrants;
- positive N and K remain finite and non-negative;
- growth is approximately multiplicative when N is far below K;
- growth slows as N approaches K;
- populations above K move toward K without invalid values;
- K = 0 rejects spawn and colonisation.

## 42.4 Dispersal tests

- below threshold, density-driven emigration is zero;
- above threshold, emigration is positive when a valid target exists;
- no valid targets means all population remains in source;
- migrants split deterministically among multiple targets;
- total migration source loss equals target gain;
- a new colony cannot expand again in the same turn;
- failed founder allocation returns to source;
- no movement crosses the north or south map boundary;
- movement across the east–west seam uses valid neighbours.

## 42.5 Multi-species tests

- two species may occupy the same hex;
- growth of species A does not change species B in v0.1;
- migration of species A does not move species B;
- each species uses its own K and configuration.

## 42.6 History and UI integration tests

- turn 0 renders correctly;
- the final turn renders correctly;
- random slider selections load matching checksums;
- stepping backward and forward is stable;
- an equivalent Godot-launched and headless run match;
- changing Inspector resources after Start does not mutate the active run.

---

# 43. Diagnostics

Every development run SHOULD be able to produce:

~~~text
population_total_by_turn
occupied_hexes_by_turn
colonisations_by_turn
extinctions_by_turn
migration_volume_by_turn
population_map for selected turns
density_ratio_map for selected turns
carrying_capacity_map per species
movement_cost_map
spawn_point_overlay
~~~

Diagnostic output MUST identify:

- run ID;
- turn;
- species;
- configuration hash;
- world fingerprint.

Population expansion should be visually inspectable across several fixed seeds and spawn locations.

---

# 44. Calibration policy

This document defines algorithms and parameter meaning.

It does not canonically set:

- growth rate;
- maximum density;
- expansion threshold;
- dispersal rate;
- minimum founder population;
- movement-cost sensitivity;
- numerical extinction epsilon.

Initial values are development defaults only.

Calibration should occur after:

1. the turn engine is verified;
2. history playback is verified;
3. uniform-environment expansion is understood;
4. environment-dependent K is integrated;
5. metrics exist across multiple worlds and spawn points.

Do not tune parameters to make one seed look attractive.

Use fixed test suites and report distributions.

---

# 45. Milestone plan

These history milestones are separate from physical-world milestone numbers.

Use the prefix H.

## Milestone H0 — repository inspection and implementation plan

Deliver:

- read WORLDGEN_ARCHITECTURE.md and this annex completely;
- inspect actual worldsim and Godot repository structure;
- map conceptual history modules to real paths;
- identify existing protocol, persistence, and atlas components to reuse;
- create or update IMPLEMENTATION_PLAN.md;
- list conflicts requiring ADR;
- stop before implementing H1.

Acceptance:

- no duplication of existing worker, protocol, or timeline infrastructure;
- physical–history ownership boundary remains intact;
- H1 can begin without architectural ambiguity.

## Milestone H1 — abstract turn engine

Deliver:

- HistoricalSimulationState scaffold;
- run lifecycle;
- automatic N-turn runner;
- TurnSystem interface;
- immutable input and ChangeSet commit;
- turn 0;
- dummy deterministic turn system;
- headless execution;
- structured progress and error events.

Acceptance:

- N requested turns produce states 0 through N;
- run works without Godot;
- cancellation/failure cannot expose a half-turn;
- deterministic checksums pass.

## Milestone H2 — history store and playback contract

Deliver:

- HistoryStore interface;
- full-snapshot first implementation;
- TurnRecord;
- EventStore;
- MetricsStore;
- versioned run manifest;
- round-trip tests;
- computed_turn and viewed_turn separation.

Acceptance:

- arbitrary recorded turns can be loaded;
- states remain immutable;
- history round-trip passes;
- no physical rasters are duplicated per turn.

## Milestone H3 — Godot configuration and timeline UI

Deliver:

- editable configuration resources;
- run setup controls;
- request serialisation;
- worker validation display;
- automatic Start flow;
- progress UI;
- Cancel control;
- timeline slider and step controls;
- dummy-state atlas integration.

Acceptance:

- parameters can be changed manually in Godot;
- the effective config is frozen at Start;
- slider browsing does not modify computed state;
- equivalent headless and Godot requests match.

## Milestone H4 — environment adapter and carrying capacity

Deliver:

- EnvironmentAdapter;
- uniform-land fixture;
- baseline WorldSpatialModel adapter;
- passability;
- productivity;
- movement cost;
- CarryingCapacityProvider;
- per-species K diagnostic map.

Acceptance:

- population code has no direct dependency on raw rasters;
- K can be replaced without changing growth code;
- water and other blocked cells cannot be colonised;
- WorldSpatialModel topology is respected.

H4 may use the analytical-grid fixture before physical Milestones 15–16 are complete.

Final integration requires the real analytical grid and query interface.

## Milestone H5 — single-species population

Deliver:

- spawn points;
- carrying-capacity-limited growth;
- density pressure;
- neighbour weighting;
- founder threshold;
- simultaneous migration commit;
- population events and metrics;
- population and pressure map modes.

Acceptance:

- all growth and dispersal tests pass;
- expansion moves no more than one edge per turn;
- migration conserves population;
- uniform-environment fronts are explainable;
- environment differences alter expansion through the adapter.

## Milestone H6 — multiple independent species

Deliver:

- stable species registry;
- multiple configuration resources;
- multiple spawn points;
- co-location;
- species selection in atlas;
- per-species and global metrics.

Acceptance:

- two or more species run in one simulation;
- two species may occupy one hex;
- no unintended interaction occurs;
- output is deterministic.

## Milestone H7 — robustness and performance gate

Deliver:

- fixed-seed regression suite;
- memory and runtime benchmark;
- snapshot-size report;
- cancellation and failure recovery tests;
- diagnostic export;
- documented recommendation for full snapshots versus checkpoint plus delta storage.

Acceptance:

- target development turn counts are usable;
- history size is measured rather than assumed;
- no state corruption after interruption;
- the next history-system milestone can build on stable interfaces.

---

# 46. Dependencies on physical-world milestones

History work does not need to wait for the entire physical generator.

Recommended dependency relationship:

~~~text
H1–H3
    may use synthetic hex fixtures

H4 fixture
    may use a small deterministic analytical grid

H4 final integration
    requires Physical Milestone 15 and preferably 16

H5–H7 final world tests
    require real WorldSpatialModel queries

dynamic environment response
    depends on Physical Milestone 19 and a later history version
~~~

This permits early validation of turns and history without coupling them to unfinished physical generation.

---

# 47. Future extension path

After H7, recommended conceptual order:

~~~text
Population v0.1
    ↓
resource-limited demography
    ↓
competition and coexistence
    ↓
subsistence strategies
    ↓
settlement emergence
    ↓
mobility and route networks
    ↓
cultural and linguistic fields
    ↓
technology diffusion
    ↓
institutions, states, diplomacy, and war
~~~

This sequence is not yet a detailed architecture for those systems.

Each major layer requires its own explicit rules, tests, and persistence contract.

---

# 48. Agent implementation rules

## MUST

- keep canonical simulation logic in Python;
- expose user-facing parameters in Godot;
- freeze effective configuration at Start;
- preserve turn 0;
- execute requested turns automatically;
- separate computed_turn from viewed_turn;
- calculate changes from an immutable turn input;
- commit simultaneously;
- preserve deterministic seeds and stable IDs;
- use WorldSpatialModel and EnvironmentAdapter;
- keep multiple species representable in one hex;
- store history behind an interface;
- validate and persist every completed turn;
- provide diagnostics and tests.

## MUST NOT

- implement population simulation only in GDScript;
- make the timeline slider mutate history;
- tie simulation results to frame rate;
- assume a real-world duration per turn in v0.1;
- process new migrants twice in one turn;
- use unordered iteration where it can alter results;
- delete surplus population by silently clamping to K;
- hard-code tuning constants inside algorithms;
- block Population v0.1 on a detailed food-web model;
- treat biome colour as carrying capacity;
- restrict one hex to one species;
- add hidden competition;
- duplicate the physical world inside every snapshot;
- transmit large snapshot arrays as JSON progress messages.

---

# 49. Definition of Done for Population Foundation v0.1

Population Foundation v0.1 is complete when:

- Godot can manually configure a portable simulation request;
- a user can enter a turn count and launch the worker;
- the worker automatically executes exactly that many complete transitions;
- turn 0 and turns 1 through N are available;
- progress and structured errors are visible;
- the simulation is also runnable headlessly;
- effective configuration and seed are frozen and persisted;
- timeline playback can display any completed turn without mutating state;
- full-snapshot history is accessed through HistoryStore;
- a static or time-indexed EnvironmentAdapter supplies passability, productivity, movement cost, and area;
- per-species carrying capacity is derived rather than hard-coded into growth;
- spawn points create validated turn-0 populations;
- local growth is density-limited;
- population pressure can produce expansion;
- migrants may reach multiple immediate neighbours;
- migrants cannot cross more than one hex edge per turn;
- migration updates commit simultaneously;
- migration conserves population in the absence of explicit mortality;
- two or more species may occupy the same hex;
- species remain independent because competition is explicitly deferred;
- fixed-world, fixed-config, fixed-seed regression tests pass;
- history round-trip and slider integration tests pass;
- runtime and storage costs are measured.

At that point, the project has a stable temporal and demographic substrate on which later ecology, subsistence, culture, settlement, technology, conflict, and state systems can be designed.
