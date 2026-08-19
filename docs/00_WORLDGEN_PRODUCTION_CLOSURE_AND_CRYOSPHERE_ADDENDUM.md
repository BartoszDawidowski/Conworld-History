# Worldgen Production Closure and Cryosphere Addendum

## Post-C9.1 hydrology, erosion, landform closure; cryosphere foundation; C10 and C11 sequencing

> **Status:** Accepted corrective implementation guidance; implementation not started by this document  
> **Date:** 2026-08-19  
> **Repository:** `BartoszDawidowski/Conworld-History`  
> **Audited commit:** `68d0ce93c24a030e9581a810ceadc228289de19f`  
> **Reference world:** Atlas profile, seed `183716`  
> **Parent documents:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` and `docs/WORLDGEN_CORRECTIVE_IMPLEMENTATION_ADDENDUM.md`  
> **Target machine:** Apple M2 / 8 GB  
> **Primary decision:** C10 calibration remains blocked. Complete the production-closure packages below first. Implement only the mass-conserving snow/firn foundation before C10; implement dynamic and geomorphic glaciation later as C11.

---

# 1. Authority, scope, and agent entry protocol

This addendum is the corrective successor to the two parent documents named above. It does not invalidate their still-correct architectural decisions. It takes precedence where a C9.1 validation note describes a package as delivered but the production Atlas result at the audited commit fails the corresponding physical invariant.

In particular:

- passing unit tests and green CI do not establish production acceptance;
- a field or diagnostic existing in code does not prove that it is computed at the correct point in the pipeline;
- hiding a non-converged water body is not the same as solving its storage equilibrium;
- a display river mask must never control physical erosion;
- a cold-climate class is not evidence of actual land ice;
- Python/worldsim owns canonical physics, classifications, diagnostics, and acceptance;
- Godot configures, renders, and inspects declared products. It must not independently derive physical classes.

## 1.1 First task for the implementation agent

The first task after receiving this file is planning-only:

1. read this file completely;
2. read both parent documents, current validation notes for C9.1.1–C9.1.6, and the current repository implementation;
3. verify the current HEAD and record whether it differs from the audited commit;
4. map every requirement below to the current file/function names rather than trusting historical line numbers;
5. add the production-closure packages PC0–PC7 and the deferred C11 phases to the canonical project plan;
6. mark C9.1 as **IMPLEMENTED ON FIXTURES — PRODUCTION CLOSURE REQUIRED**;
7. preserve completed work that already satisfies the contracts below;
8. present the reconciled plan, dependency order, estimated runtime/memory effects, and migration risks;
9. stop before implementation for review.

After approval, implement one package at a time. Every package ends with:

- unit and synthetic invariant tests;
- Quick fixed-seed evidence;
- Atlas `183716` evidence when required by the package;
- updated diagnostics and canonical acceptance;
- runtime, peak-RSS, and output-size notes where the package affects production work;
- a validation note under `docs/validation/`;
- a stop before changing defaults or beginning the next major package.

Do not combine structural correctness changes and default retuning in one package or pull request.

## 1.2 Status vocabulary

| Status | Meaning |
|---|---|
| **IMPLEMENTED ON FIXTURES** | Code and focused tests exist, but a required production profile has not passed. |
| **PRODUCTION FAILING** | A required fixed-seed integration or physical gate fails. |
| **READY FOR CALIBRATION** | Structural contracts, mass balances, stores, exports, and performance gates pass. |
| **CALIBRATED** | A multi-seed/profile grid has been reviewed and defaults have been deliberately selected. |
| **DEFERRED** | Preserve contracts and reopening criteria, but do not implement now. |

No component may be described as accepted merely because its own incomplete `acceptance_ok` expression returns true.

---

# 2. Verified production baseline at `68d0ce9`

The audited commit passes the full local test run and multi-platform CI. A newly generated Atlas world for seed `183716` nevertheless correctly ends with:

~~~text
overall_acceptance_ok = false
failed_gates = hydrology_ok, erosion_or_fluvial_ok
~~~

The new canonical aggregator is a real improvement: the world is no longer declared accepted solely because the analytical hex layer passes. The remaining failures are substantive.

## 2.1 Baseline measurements

| Product | Audited value | Interpretation |
|---|---:|---|
| physical channel cells | 25,260 | A substantial drainage skeleton exists. |
| cells after `river_acc_fraction=0.035` | 888 | The first display-oriented filter removes 96.5% of the physical network. |
| final displayed river cells | 444 | Q quantile `0.50` removes half again. |
| raster river components | 58 | The displayed network is fragmented. |
| singleton river components | 22 | Many visible candidates cannot become useful vector reaches. |
| vector river segments | 46 | Essentially unchanged from the previous audited version. |
| coast-adjacent mouth labels | 8 | Very few visible reaches terminate at the ocean. |
| first erosion mean absolute delta | 0.1965 m | The first terrain pass remains almost inactive. |
| first erosion median absolute delta | 0.0182 m | Most land changes by only centimetres. |
| final fluvial mean absolute delta | 0.01559 m | River incision remains visually negligible. |
| final fluvial median absolute delta | 0.00376 m | The typical change is millimetric. |
| liquid lake candidates | 140 | Candidate water bodies exist. |
| periodic liquid lakes | 25 | Only 17.9% converge under the current storage solver. |
| non-periodic candidates withheld | 115 | Non-convergence is mostly hidden rather than solved. |
| mountain ranges | 488, previously 116 | Object extraction exploded into small fragments. |
| mountain systems | 484 | Only four systems were meaningfully split. |
| plateaus | 95, previously 25 | Most new objects are below useful representability. |
| plateau context fraction of land | 0.742% | Plateau coverage is below its own warning band. |
| plateau-context escarpment fraction | 87.68% | Plateau semantics remain internally contradictory. |
| Atlas runtime | 163.9 s, previously 134.3 s | Runtime increased by approximately 22%, above the 15% warning. |
| output size | approximately +7.5% | New products and object proliferation have a material cost. |

The rendered DEM is genuinely almost unchanged, not merely visually normalized:

- new/previous final DEM mean absolute difference: approximately `0.000056 m`;
- final hipsometry remains approximately median `567 m`, p95 `3,000 m`, maximum `6,436 m`;
- `folding_ratio=0.01` and `power_tail_v2` are not implicated by this regression.

## 2.2 What C9.1 did improve

Preserve the following work unless a new test demonstrates a defect:

- canonical world acceptance now includes the main physical stages;
- simple single-lake double routing is partly prevented;
- monthly liquid-water and lake-ice fractions exist;
- obvious false `mouth` labels were reduced;
- BiomeV2 no longer classifies zero-growing-season cells as `Growing–Moist`;
- BiomeV2 wetland is derived from inundation rather than generic saturated soil;
- BiomeV2 export, legend, and Godot mode are materially functional.

BiomeV2 changed approximately 41% of land cells on the reference Atlas. It should not be retuned before final hydrology is stable, but it should not be rewritten as part of this closure.

## 2.3 Configuration inconsistency to resolve before calibration

The current packaged YAML, Python default, and Godot value use:

~~~text
precip_scale_mm = 200
~~~

At least one planning document describes the current value as `300`. Treat `200` as the audited effective value, fix the documentation/configuration discrepancy, and do not change the value as part of PC0–PC7.

---

# 3. Binding decisions and prohibitions

| ID | Decision |
|---|---|
| D-PC-01 | C10 calibration is blocked until PC0–PC7 production gates pass. |
| D-PC-02 | Keep `folding_ratio=0.01`, sea level, ocean mask policy, `power_tail_v2`, base temperature, lapse rate, and SST settings frozen during production closure. |
| D-PC-03 | Keep `precip_scale_mm=200` frozen until the documented C10 unit/calibration grid. |
| D-PC-04 | Condense every retained lake envelope into a hydrological supernode for routing and storage. |
| D-PC-05 | Route monthly water once through a single loss-aware graph. Lake spill is an ordinary graph contribution, not a post-hoc addition. |
| D-PC-06 | Compute river products only after final lake-aware discharge exists. |
| D-PC-07 | Maintain three distinct channel products: physical, geomorphic, and presentation LOD. |
| D-PC-08 | Erosion consumes the geomorphic network, never the display river mask. |
| D-PC-09 | Conditioning/fill deltas are separate from erosion deltas and never count toward erosion acceptance. |
| D-PC-10 | Snow, soil, firn, and later land ice must conserve mass; seasonal stores require periodicity while persistent accumulation requires an explicit transfer/evolution gate. |
| D-PC-11 | Implement only the cryosphere foundation before C10. Dynamic and geomorphic glaciation is C11. |
| D-PC-12 | Do not use glaciation to compensate for broken routing, sparse river LOD, weak erosion, or plateau extraction. |
| D-PC-13 | Keep landform score thresholds at mountain `0.60` and plateau `0.40` until object geometry and acceptance are repaired. |
| D-PC-14 | Small features below the analysis grid's representability may remain raster candidates or unresolved features; they may not become misleading canonical one-cell objects. |
| D-PC-15 | No new large monthly float64 cubes at Full terrain resolution. |

Explicitly prohibited during PC0–PC7:

- increasing folding to obtain stronger relief;
- changing sea level to suppress lakes;
- lowering river thresholds before final-Q routing exists;
- raising erosion coefficients while erosion still consumes display LOD;
- declaring non-periodic lakes dry solely so that acceptance becomes green;
- silently clipping snow storage;
- calling cold cells glaciers without positive snow/ice mass balance;
- adding full 3-D or full-Stokes ice dynamics;
- calibrating only seed `183716`;
- weakening gates to accept the current output.

---

# 4. Corrected target pipeline

## 4.1 Production closure pipeline

~~~text
tectonics + robust hypsometry
    ↓
terrain refinement
    ↓
metric first terrain process
    ├── thermal / hillslope delta
    ├── first fluvial delta
    └── separate conditioning delta
    ↓
base climate + periodic moisture M0
    ↓
mass-conserving rain / snow / soil / firn foundation G0
    ↓
canonical cylindrical drainage topology
    ↓
lake-condensed monthly routing and storage H0
    ↓
final effective Q
    ├── physical_channel_mask
    ├── geomorphic_channel_mask → metric fluvial erosion
    └── display_river_mask → vectors / atlas only
    ↓
final unconditioned elevation_v2_m
    ├── final climate / moisture M1
    └── LandformAnalysis
             ↓
       final runoff + lake-condensed hydrology H1
             ↓
       optional bounded inland-water moisture M2
             ↓
       one damped H2 consistency correction when required
             ↓
       ecology / vectors / canonical WorldSpatialModel
             ↓
       hex / queries / atlas / Godot
~~~

The final river mask, vector graph, lake relations, ecology water overrides, and erosion provenance must all record which hydrology result produced them.

## 4.2 Required separation of channel products

### Physical channel network

Purpose: hydrological state and routing eligibility.

Derived from physical catchment area, final effective discharge, hydroperiod, and declared minimum representable area. It may include reaches too minor to display.

### Geomorphic channel network

Purpose: long-term fluvial erosion.

Derived from persistent or climatologically significant effective discharge, catchment area, slope, and channel state. It must not use a global display quantile. It may be narrower than the complete physical network but must remain topologically continuous through its downstream path unless a reach physically dries or terminates.

### Display river network

Purpose: readable atlas and vector LOD.

Derived only after final Q and channel state exist. Its density controls visual complexity, not physics. A selected headwater/main-stem reach should be traced downstream to an explicit ocean, lake, endorheic, or physical dry termination so that LOD does not create arbitrary gaps.

Required fields:

~~~text
physical_channel_mask
geomorphic_channel_mask
display_river_mask
channel_state_monthly_or_summary
channel_catchment_km2
channel_q_effective_monthly_m3s
channel_q_effective_mean_m3s
channel_bed_loss_monthly_m3
channel_length_km
channel_width_m
~~~

No consumer may use the generic name `river_mask` without declaring which tier it means.

---

# 5. Canonical lake-supernode hydrology

## 5.1 Graph contract

Replace envelope-local blocking plus post-hoc spill injection with a condensed directed graph.

Minimum node kinds:

~~~text
LAND_CELL
LAKE_SUPERNODE
OCEAN_OUTLET
ENDORHEIC_TERMINAL
DOMAIN_TERMINAL
~~~

Use an explicit compact target-kind field rather than one overloaded `SINK`, for example:

~~~text
LAND_CELL
LAKE_NODE
OCEAN_CELL
CLOSED_SINK
BOUNDARY_SINK
CYCLE_BREAK
~~~

Store the kind and target reference in compact `uint8`/`int32` arrays. A target reference is a cell index, lake-node ID, or declared terminal ID according to its kind.

For every retained basin envelope:

1. map all envelope cells to one `lake_supernode_id` for routing purposes;
2. preserve the full raster envelope separately for A–V–h and shoreline calculations;
3. collect all external incoming graph edges;
4. identify the lowest valid spill saddle or explicit ocean target;
5. store one downstream `spill_edge`, if it exists;
6. preserve a deterministic topological identity independent of current wetness;
7. assert that the condensed routing graph is acyclic after declared conditioning;
8. compute and persist its topological order.

Required topology fields:

~~~text
node_kind
downstream_node_id
sink_kind
ocean_target_row_col
lake_supernode_id
spill_target_node_id
spill_saddle_row_col
spill_elevation_m
basin_envelope_id
~~~

Do not collapse pit, ocean contact, N/S domain termination, broken cycle, and display truncation into the same sentinel.

## 5.2 Monthly routing algorithm

Use volume as the internal conserved quantity. Convert to m³/s only for declared discharge products.

For each spin-up year and month:

1. partition cell area into land, liquid water, and ice fractions;
2. generate local land runoff only from the land fraction;
3. add direct precipitation on actual water fraction exactly once;
4. process nodes in topological order;
5. apply channel loss to water actually traversing a land reach, capped by available volume;
6. accumulate all upstream contributions at a lake supernode;
7. solve that lake's storage, evaporation, seepage, freezing/open-water state, and spill for the month;
8. pass the released spill through the same loss-aware downstream router;
9. allow the spill to enter and affect a downstream lake during the same monthly traversal;
10. record a ledger entry for every source, sink, and storage change.

Repeat complete climatological years from the previous December state until all relevant stores satisfy the declared periodicity tolerance or the maximum is reached.

Do not first solve all lakes and then inject all spill. That ordering is invalid for lake cascades.

## 5.3 Storage and A–V–h contract

Retain the discrete A–V–h requirements from the parent corrective addendum:

- deterministic floor-elevation sorting;
- cell-area-aware cumulative volume;
- fractional shoreline cell where useful;
- monotonic storage → level → area mapping;
- explicit spill volume only above spill storage;
- separate basin envelope, water-present fraction, open-water fraction, and lake-ice fraction.

Recommended independent state axes:

~~~text
outlet_type: ocean_draining | open_lake | closed_endorheic
hydroperiod: permanent | seasonal | ephemeral_or_dry
ice_regime: normally_liquid | seasonally_frozen | perennially_frozen
convergence_state: periodic | bounded_nonperiodic | failed
~~~

`water_fraction_monthly` means water present in the basin. `open_water_fraction_monthly` means liquid surface available for evaporation. `lake_ice_fraction_monthly` means lake ice. Do not use the unqualified name `ice_fraction_monthly` after migration.

## 5.4 Required water ledger

For each lake and globally, persist the monthly identity:

~~~text
initial_storage
+ local_land_runoff_entering_node
+ upstream_channel_inflow
+ upstream_lake_release
+ direct_precipitation_on_water
= final_storage
+ downstream_release
+ open_water_evaporation
+ seepage
+ channel_bed_loss_assigned_to_reaches
+ explicitly_declared_other_sink
~~~

Diagnostics must report absolute and relative residuals. The residual may not be inferred only from `Q_effective <= Q_gross`; that inequality is not a complete mass balance.

## 5.5 Non-convergence policy

A lake that fails storage periodicity:

- remains present as a basin candidate with diagnostics;
- is not silently relabelled dry;
- may be withheld from the canonical liquid-water product for safety;
- must force hydrology and overall production acceptance to false when it materially affects the published world;
- must report initial/final storage, trend, limiting process, and whether a bounded analytic/fixed-point fallback was attempted.

Prefer an annual fixed-point solve on bounded storage `[0, V_spill]` or adaptive iteration over a hard-coded eight-year limit. Large slow-filling lakes may require more years but should not require storing more monthly raster cubes.

If a closed envelope accumulates beyond the volume represented by its declared A–V–h domain and no valid spill target exists, publish `storage_domain_exceeded=true` and fail hydrology. Do not discard the excess, invent an outlet, or silently keep the store at its maximum.

## 5.6 Synthetic tests required before implementation is accepted

1. One open lake on a chain: `10 m³/s` entering must not become `20 m³/s` downstream.
2. Two-lake cascade A → B → ocean: A's release must enter B's storage in the same routed month.
3. Closed basin with a valid saddle: overflow must follow the declared saddle edge.
4. Spill through two lossy reaches: release must incur the same capped losses as ordinary runoff.
5. Direct precipitation partition: water-area precipitation must not also appear as land runoff.
6. Dry depression: basin exists but liquid fraction remains zero.
7. Seasonal basin: monthly area changes monotonically with storage and reaches the reported annual mean.
8. Frozen month: water may be present while open-water evaporation is suppressed.
9. E–W seam lake: one deterministic supernode and one object.
10. Non-convergent fixture: hydrology and world status become red with an explicit reason.
11. Global ledger fixture: source minus sink minus storage residual is below tolerance.

## 5.7 Production acceptance

For Atlas `183716`:

- `q_through_lake_once=true` must be backed by the ledger, not only a ratio heuristic;
- zero material cells may have unexplained `Q_effective > Q_gross`;
- no spill may disappear because an optional outlet field is `None`;
- no spill may bypass declared channel losses;
- any `Q_effective > Q_gross` must be explained exactly by a separately ledgered source such as direct precipitation on water; the inequality alone is neither a sufficient failure nor a sufficient acceptance test;
- every published liquid lake must be periodic or use a documented, mass-balanced bounded solution;
- rasterized fractional water area and object-reported area agree within 5%;
- hydrology acceptance must fail if any material coupling or storage convergence gate fails.

---

# 6. Final-Q rivers, vector topology, and mouths

## 6.1 Required order

The production order is binding:

~~~text
candidate basins
→ lake-condensed monthly routing
→ periodic storage
→ final effective Q
→ channel states
→ physical network
→ geomorphic network
→ display LOD
→ vector graph and terminal classes
~~~

Never compute and retain a display mask from preliminary Q.

## 6.2 Physical thresholds and display LOD

Physical channel eligibility uses physical area/Q units and representability:

~~~text
effective_min_cells = max(
    ceil(min_catchment_km2 / representative_cell_area_km2),
    fallback_min_cells
)
~~~

For equal-area cells the representative area is stable. If mixed/fractional land area is used, document the selected convention.

Display LOD may use a fraction or quantile after final Q exists. Store the effective threshold and the number of cells/reaches removed by each stage.

The initial post-closure experiment is not a default:

| Parameter | Conservative comparison | Initial centre | Upper comparison |
|---|---:|---:|---:|
| `river_acc_fraction` | 0.10 | 0.15 | 0.20 |
| `river_discharge_candidate_quantile` | 0.25 | 0.35 | 0.45 |

On the audited final-Q field, `0.15 / 0.35` would yield approximately 2,475 cells and 373 segments rather than 444 cells and 46 segments. These values may be evaluated only after the routing and final-mask order is repaired.

## 6.3 Vector graph rules

1. Build all segments and nodes before assigning semantic node types.
2. Determine source, confluence, bifurcation if supported, lake inlet, lake outlet, ocean mouth, and endorheic sink from graph degree and explicit targets.
3. Apply terminal classification only to nodes with `outdegree=0` in the published graph.
4. A confluence with an outgoing edge may never be an `endorheic_sink`.
5. An `ocean_mouth` requires an explicit ocean target, not only coastal adjacency.
6. Split river geometry at the actual fractional lake shoreline and populate `from_lake_id`/`to_lake_id`.
7. Preserve singleton physical channels diagnostically; either vectorize them as points/short reaches or record why display LOD omitted them.
8. Keep state (`perennial`, `seasonal`, `wadi`) independent from draw width and LOD.

Prefer two independent vector-node fields:

~~~text
role: source | confluence | junction | ordinary
terminal_type: none | ocean_mouth | lake_inlet | endorheic_sink | lod_cutoff
~~~

This avoids forcing a confluence or source role into the same enum as a terminal destination.

Required vector diagnostics:

~~~text
source_count
confluence_count
lake_inlet_count
lake_outlet_count
ocean_mouth_count
endorheic_sink_count
lod_terminal_count
invalid_terminal_with_outgoing_edge_count
mouth_without_ocean_target_count
singleton_component_count
~~~

Production acceptance requires both invalid counts to be zero.

---

# 7. Snow, soil, firn, and land-ice foundation G0

## 7.1 Why G0 belongs before C10

The current runoff spin-up compares runoff fields but not the states that generate them. A repeating cold fixture can report periodic runoff while snow storage keeps increasing. A hard snow-store cap can later delete mass silently.

On Atlas `183716` at the audited commit:

- runoff was reported periodic after three years;
- the published-vs-repeat runoff difference was small;
- repeating from the published December state changed total snow storage by approximately 25%;
- approximately 4.65% of terrain land retained snow in all twelve months.

This is already a hydrology defect, independent of future glacier graphics. G0 therefore belongs in production closure.

## 7.2 Canonical stores and units

Use physical water-equivalent units internally and declare them in schemas.

Minimum G0 state and diagnosed transfer:

~~~text
seasonal_snow_swe_m
soil_water_m
firn_swe_m_or_bounded_reservoir
firn_gain_m_swe_per_year
~~~

C11 later adds canonical `land_ice_fraction` and `ice_thickness_m`. Those fields are absent/`None` in G0 rather than zero-filled products that could be mistaken for a completed glacier simulation.

Minimum monthly fluxes:

~~~text
rainfall_m
snowfall_m_swe
snowmelt_m_swe
firn_formation_m_swe
firn_melt_m_swe
ice_melt_m_swe
refreezing_m_swe
sublimation_m_swe
runoff_to_hydrology_m
~~~

Lake ice remains a hydrology/lake surface product named `lake_ice_fraction_monthly`. Land ice belongs to the cryosphere package.

## 7.3 G0 algorithm

G0 is a mass-conserving storage foundation, not yet dynamic glaciation:

1. partition rain/snow with a smooth temperature band;
2. add snowfall to seasonal snow;
3. melt available snow before firn or land ice;
4. route meltwater exactly once to soil/runoff;
5. transfer declared persistent snow surplus to a firn-gain flux or bounded firn reservoir instead of clipping it;
6. do not create canonical land ice in G0;
7. record sublimation/refreezing only when explicitly modelled;
8. iterate climatological years until seasonal snow and soil repeat; cells with persistent accumulation must close through an explicit firn-transfer flux rather than an ever-growing unaccounted seasonal store;
9. publish mass residuals and state deltas;
10. never discard cap overflow.

G0 publishes firn/perennial-snow potential but no `CurrentLandIceState`. Positive climatic accumulation is not a numerical failure if seasonal stores repeat and the firn-transfer flux closes the ledger. It becomes the source term for G1/C11 rather than disappearing or growing an unbounded hidden state.

G0 becomes the single owner of precipitation phase partition. Hydrology consumes, but does not independently recalculate:

~~~text
SurfaceWaterForcing
    rainfall_monthly
    seasonal_snowmelt_monthly
    glacier_melt_monthly       # absent or zero before C11
    liquid_input_monthly       # exact sum of the three components
~~~

Every component is injected exactly once. A schema/version migration must prevent the legacy runoff snow model and G0 from operating simultaneously.

## 7.4 Required tests

- cold and dry: no snowfall means no firn or land ice;
- cold and wet: snow accumulates, then moves to firn rather than disappearing;
- warm seasonal cycle: snow melts and appears once in runoff;
- repeating non-accumulating climate: seasonal snow and soil repeat within tolerance;
- repeating accumulating climate: seasonal stores repeat and positive surplus appears exactly as firn transfer;
- zero-runoff cold fixture with growing snow: must not be called periodic;
- deliberately small storage cap: overflow ledger remains zero because mass is transferred, not clipped;
- conservation: precipitation equals ET/sublimation + runoff + storage change within tolerance;
- cross-profile fixture: the same physical climate gives comparable store/flux meaning.

## 7.5 Ecology migration

Until a true land-ice fraction exists:

- rename or describe BiomeV2 `ICE` as `ice_climate_potential` or an equivalent honest compatibility label;
- rename Holdridge `Permanent ice` display text to indicate thermal potential where necessary;
- do not let temperature alone create canonical glacier objects;
- preserve compatibility IDs through a legend/schema migration.

When G1 later publishes `land_ice_fraction`, ecology may derive actual ice cover from that product.

---

# 8. Erosion production closure

## 8.1 Separate process deltas

Persist independent rasters and diagnostics:

~~~text
thermal_or_hillslope_delta_m
first_fluvial_delta_m
conditioning_or_pit_fill_delta_m
final_stream_power_delta_m
total_erosion_delta_m       # excludes conditioning
total_dem_adjustment_m      # may include conditioning
~~~

Conditioning/fill may be required for routing, but it is not erosion and must not satisfy an erosion lower bound.

Keep the final unconditioned bedrock/topographic DEM as the canonical LandformAnalysis input. A conditioned routing surface is a hydrology product.

## 8.2 Geomorphic network input

`apply_fluvial_erosion()` must consume:

- `geomorphic_channel_mask`;
- final or explicitly named precursor effective Q;
- catchment area;
- metric slope/step length;
- rock-resistance proxy;
- an influence distance in kilometres or a Q/width-derived physical corridor.

It must not consume `display_river_mask`. A constant halo of two raster cells is resolution-dependent and may affect a 60–100 km corridor on Atlas.

## 8.3 Reduced-order erosion contract

A complete sediment model is not required. The reduced model should nevertheless satisfy:

- incision is non-negative in declared erosional cells unless deposition is a separate product;
- incision increases monotonically with Q and slope under a fixed resistance fixture;
- incision remains bounded by `max_step_m` per iteration;
- macro-relief and coastline are preserved;
- off-channel terrain remains stable outside the declared corridor;
- downstream profiles do not acquire systematic artificial uphill steps;
- natural retained depressions are not erased merely to satisfy routing.

The first pass's precipitation × local slope term must not be described as accumulated fluvial erosion. Rename it or use accumulated flow if it remains part of the physical model.

## 8.4 Domain-specific acceptance

Do not apply the same land-wide mean threshold to hillslope processing and narrow river incision.

### First terrain pass

Report on its active hillslope domain:

- mean/median/p90 absolute thermal delta;
- mean/median/p90 first-fluvial delta;
- roughness before/after at declared scales;
- macro-elevation correlation and hypsogram drift;
- count and depth distribution of retained/removed minima;
- separate conditioning magnitude.

### Final fluvial pass

Report on channel core, geomorphic corridor, and off-channel land:

- mean/median/p90 incision;
- fraction of active cells changed above 0.1, 1, 5, and 10 m;
- maximum bounded change;
- downstream-profile monotonicity/knickpoint diagnostics;
- basin/channel topology Jaccard before and after erosion;
- off-channel preservation;
- runtime.

## 8.5 Post-closure experiment grid

These are experiments, not approved defaults:

| Parameter | Values | Conservative first run |
|---|---|---:|
| first-pass `thermal_kappa` | 20, 50, 80 | 20 |
| final `stream_power_k` | 500, 1000, 1500 | 500 |

Use the repaired geomorphic network and metric corridor. Keep folding, hipsometry, sea level, iteration count, and maximum step fixed while comparing coefficients.

The reference saved DEM indicates that `thermal_kappa=20` already produces a measurable mean change of several metres while preserving macro-relief. A geomorphic-network `stream_power_k=500` is a safer initial run than applying `1000` to an unverified corridor. The grid, not this document, selects the default.

---

# 9. Landform object and acceptance repair

## 9.1 Representability policy

The audited Atlas landform analysis cell is larger than some configured minimum object areas. Do not convert that mismatch into hundreds of one-cell canonical objects.

Use a two-stage approach:

1. compute broad scores/context on the existing efficient analysis grid;
2. refine only candidate object regions on the terrain grid or a local intermediate grid when required for object segmentation;
3. retain below-resolution features as raster score/context or `unresolved_candidate`, not as a named range/plateau;
4. record requested and effective minimum area and width;
5. fail or warn explicitly when a configured object cannot be represented.

Global multi-scale filters must not be moved blindly to the Full terrain grid. Candidate-local refinement is preferred.

## 9.2 Mountain systems and ranges

Required hierarchy:

~~~text
mountain terrain score/mask
    ↓
mountain_system_id          # broad connected orogen/system
    ↓
mountain_range_id           # children split at meaningful passes/saddles
    ↓
ridge graph / centreline
~~~

Replace the narrow single-path cut rule with marker-controlled watershed or an equivalent pass/prominence segmentation using elevation, mountain score, TPI/relative height, and metric saddle depth/neck width.

Requirements:

- every child cell belongs to exactly one range or an explicitly unresolved system boundary;
- `system_id` remains stable across child segmentation changes within the declared version scope;
- the largest system must be tested against meaningful split metrics, not only object count;
- no one-cell range becomes a canonical `MountainRange` with a fabricated ridge;
- ridge extraction follows a crest/skeleton graph constrained inside the range mask;
- ridge cost must prefer higher/crest-like terrain rather than low paths;
- E–W seam coordinates are unwrapped for geometry and split only for presentation;
- duplicate points and ocean samples are prohibited.

## 9.3 Plateaus and rims

A canonical plateau requires:

- elevated regional position;
- relatively low internal fine relief/slope;
- a contiguous interior with a minimum physical width;
- a meaningful surrounding base contrast;
- an object area representable on the selected/refined grid.

Do not mechanically repaint all interior escarpment cells merely to pass a classification test. Do not define `rim = perimeter` when too few real escarpment segments exist.

Export:

~~~text
plateau_interior_polygon
plateau_rim_multiline
plateau_context_mask
plateau_object_id
small_highland_or_unresolved_candidate   # optional honest fallback
~~~

## 9.4 Binding acceptance conjunction

Landform `acceptance_ok` must include, at minimum:

- land/ocean mask consistency;
- requested/effective scale diagnostics;
- representability of configured semantic objects or an explicit unresolved policy;
- mountain and plateau alarm status;
- total and plateau-context escarpment dominance;
- plateau interior existence and rim validity;
- range/system size and split diagnostics;
- ridge coverage, in-mask, no-duplicate, and no-ocean checks;
- seam fixtures;
- canonical store/query/export round-trip;
- runtime and object-count catastrophe gates.

It may not omit a diagnostic merely because that diagnostic is currently red.

Initial catastrophe guards should include zero canonical semantic objects below the declared semantic floor, ridges for at least 95% of ranges that are large enough to support them, zero ocean ridge samples, complete/non-overlapping child partition of a split system, no fallback `rim = full perimeter`, and an explicit justification for every very large unsplit system.

Keep classification thresholds at mountain `0.60` and plateau `0.40` until this conjunction and geometry pass. Later C10 may compare mountain `0.60/0.62/0.65` and plateau `0.35/0.40`.

---

# 10. Configuration, products, Godot modes, and inspector

## 10.1 Configuration ownership

Python owns canonical defaults and validation. Prefer Godot writing a small override object that is merged with packaged defaults. If the current full-YAML writer remains temporarily, add a parity test covering every emitted key.

Resolve and persist effective values in:

~~~text
effective_config.json
effective_config_schema_version
effective_config_checksum
~~~

Separate UI groups:

~~~text
Hydrology physics
Lake storage
Snow / firn foundation
Erosion physics
Landform classification
Display-only river and object LOD
Solver / expert
~~~

Minimum newly exposed controls:

### Hydrology physics

- minimum physical catchment area in km²;
- fallback representability cells;
- channel Q/state thresholds;
- channel-bed loss rate and units;
- lake-storage spin-up maximum/tolerance;
- seepage/evaporation terms that are actually implemented.

### Display-only LOD

- `river_acc_fraction`;
- discharge candidate quantile;
- minimum rendered segment length if retained;
- diagnostic visibility of physical/geomorphic/display networks.

### Erosion

- first-pass thermal coefficient;
- clearly named first-pass local/fluvial coefficient;
- final stream-power coefficient;
- metric influence distance or width rule;
- iterations, maximum step, macro blend, and micro-fill threshold when retained.

### Snow/firn

- rain/snow transition and band;
- snowmelt factor and physical units;
- snow-to-firn rule;
- spin-up maximum and state tolerances;
- diagnostic SMB toggle after G1 exists.

Do not expose a parameter before its physical meaning, units, validator, manifest persistence, and consumer are consistent.

## 10.2 Required diagnostic layers

Use one diagnostics selector rather than adding many main-toolbar buttons.

### Hydrology diagnostics

- basin envelope ID;
- mean/monthly water-present fraction;
- mean/monthly open-water fraction;
- lake storage convergence state;
- physical channel network;
- geomorphic channel network;
- display river network;
- log catchment area;
- log final effective Q;
- channel state;
- channel loss fraction;
- explicit terminal kind;
- global/local mass residual.

### Erosion diagnostics

- thermal/hillslope delta;
- first-fluvial delta;
- conditioning/pit-fill delta;
- final stream-power delta;
- total erosion excluding conditioning;
- geomorphic corridor.

Use a fixed signed legend around zero for deltas. Conditioning must use a visually distinct palette so it cannot be mistaken for incision.

### Landform diagnostics

- mountain score and terrain mask;
- mountain system IDs;
- mountain range IDs and ridges;
- plateau score/context;
- plateau interior objects and real rim segments;
- unresolved/below-resolution candidates;
- object-confidence or representability warning.

### Cryosphere diagnostics

G0:

- seasonal snow SWE;
- perennial snow/firn SWE;
- store periodicity delta;
- snow/firn mass residual.

C11, when implemented:

- surface mass balance;
- perennial snow fraction;
- land-ice fraction and thickness;
- glacier IDs and margins;
- glacial erosion/deposition and inherited provenance.

Categorical layers use Python-owned legends. Continuous layers use stable absolute scales, not only per-seed min/max stretches.

## 10.3 Inspector extensions

Keep a compact status row at the top:

~~~text
Moisture ✓  Snow/Firn ✕  Hydro ✕  Erosion ✕  Landforms ⚠
~~~

Godot reads this status from Python diagnostics and does not recalculate it.

### Hex/environment hydrology

- basin and lake IDs;
- outlet type, hydroperiod, ice regime, convergence state;
- basin envelope area versus mean/monthly water area;
- selected-month storage, inflow, release, evaporation, seepage, and residual;
- physical/geomorphic/display channel membership;
- channel state, catchment km², selected-month and mean Q;
- explicit downstream target kind.

### River object

- IDs and state;
- physical/geomorphic/display membership;
- upstream/downstream segment IDs;
- catchment area and Q summary;
- bed loss;
- source/confluence/lake/ocean/endorheic semantics;
- connected lake IDs;
- warning when geometry is a presentation truncation.

### Lake object

- basin ID and water-body ID;
- outlet/hydroperiod/ice/convergence axes;
- floor, current level, spill level;
- basin envelope, mean and selected-month water area;
- full monthly storage ledger summary;
- inlet rivers and outlet target;
- mass residual and spin-up years.

### Erosion

- total elevation and each process delta at the inspected location;
- whether the cell belongs to the geomorphic corridor;
- local Q, slope, resistance, and applied bounded step;
- conditioning value shown separately.

### Landforms

- system ID, range/plateau ID, local form;
- score, area, length/width, orientation, relief;
- ridge/rim status;
- representability/confidence warning;
- glacial provenance later, distinct from present ice.

### Cryosphere

- snow, firn, and land-ice stores;
- selected-month accumulation/melt/runoff;
- annual mass balance and convergence;
- present glacier ID and inherited glacial-landform provenance as separate fields.

Missing fields render as `No data`; they never become zero or an inferred class.

---

# 11. Production-closure work packages

## PC0 — Baseline, failing regressions, and status correction

**Priority:** P0  
**Purpose:** Make the demonstrated failures reproducible before changing algorithms.

Required:

- freeze Atlas `183716` baseline metrics from section 2;
- add synthetic failures for lake cascade, spill loss, stale river mask, false confluence/sink, runoff state non-periodicity, conditioning counted as erosion, and landform false acceptance;
- correct documentation status from production accepted to fixture-implemented where applicable;
- resolve `precip_scale_mm` documentation parity while keeping the effective value at `200`;
- add per-stage runtime and peak-RSS measurement;
- stop with `docs/validation/01_worldgen_pc0.md`.

No physics or default changes in PC0.

## PC1 — Lake-supernode graph and single monthly router

**Priority:** P0  
**Dependency:** PC0

Implement sections 5.1–5.4:

- condensed graph;
- explicit targets/saddles;
- topological monthly traversal;
- one loss-aware volume router;
- global and per-lake ledger;
- source/sink partition by land/water fraction.

Stop after synthetic cascade and balance fixtures. Do not retune lake parameters.

## PC2 — Periodic storage, fractional water, and final-Q network

**Priority:** P0  
**Dependency:** PC1

Implement:

- bounded/adaptive storage periodicity;
- honest non-convergence;
- water-present/open-water/lake-ice separation;
- final effective Q;
- physical, geomorphic, and display channel products;
- vector topology and explicit ocean targets;
- Atlas `183716` integration.

Stop with `docs/validation/03_worldgen_pc2.md`. C10 remains blocked.

## PC3 — Mass-conserving snow/soil/firn foundation G0

**Priority:** P0/P1  
**Dependency:** PC0; may be developed in parallel with PC1, integrated before PC2 acceptance

Implement section 7 without dynamic ice flow:

- seasonal-store periodicity and explicit firn transfer for accumulating cells;
- explicit firn transfer instead of clipping;
- runoff coupling exactly once;
- physical units and ledger;
- honest ecology labels.

Stop with cold/wet/dry/melt fixtures and Atlas store diagnostics.

## PC4 — Geomorphic erosion and process-specific gates

**Priority:** P1  
**Dependencies:** PC2

Implement section 8:

- geomorphic channel input;
- metric corridor;
- process deltas;
- conditioning separation;
- channel/hillslope-specific gates;
- hydrological topology stability diagnostics.

Run the coefficient grid only after the structural package passes. Do not select a new default in the same change.

## PC5 — Landform systems, ranges, plateaus, and honest acceptance

**Priority:** P1  
**Dependencies:** PC4

Implement section 9:

- candidate-local refinement or explicit unresolved policy;
- meaningful mountain-system split;
- crest-constrained ridges;
- plateau interior/rim semantics;
- complete acceptance conjunction;
- object-count/performance guards.

Keep thresholds frozen and stop before calibration.

## PC6 — Canonical products, Godot configuration, modes, and inspector

**Priority:** P1  
**Dependencies:** PC2–PC5

Implement section 10 and ensure:

- RasterStore/VectorStore/queries/hex/export use the same field names and units;
- save/load/rebuild preserves products and IDs;
- Godot exposes effective physical and display settings in separate groups;
- diagnostic layers and inspector fields are loaded from exported contracts;
- Python-owned legends and acceptance remain canonical;
- backward compatibility is versioned and fail-safe.

## PC7 — Production suite, performance recovery, and C10 readiness

**Priority:** P0 release gate  
**Dependencies:** PC0–PC6

Required suite:

- Quick seeds `1`, `42`, `100`;
- Atlas seeds `42`, `183716`;
- at least one Full smoke run with peak RSS;
- cross-profile physical-scale comparison;
- before/after fixed-scale images;
- Godot headless load/inspector smoke test;
- runtime, RSS, and artifact-size report.

The current Atlas runtime is already approximately 22% above the previous audited run. PC7 must identify the stage responsible and make a documented optimization attempt before adding dynamic glaciation. C10 readiness requires all relevant canonical gates green; warning-only realism bands may remain warnings.

---

# 12. C10 calibration after production closure

C10 begins only after PC7 reports **READY FOR CALIBRATION**.

## 12.1 Calibration order

1. Verify units and choose the precipitation-scale grid without changing routing semantics.
2. Calibrate atmospheric transport and precipitation on multiple seeds.
3. Calibrate physical/geomorphic channel criteria.
4. Calibrate display river LOD separately.
5. Calibrate erosion coefficients with folding and hipsometry frozen.
6. Calibrate mountain/plateau thresholds after object geometry passes.
7. Review ecology/BiomeV2 distributions last because they consume the preceding products.

## 12.2 Initial grids retained for review

| Area | Grid |
|---|---|
| precipitation physical scale | `250 / 300 / 350`, with actual baseline `200` retained as control |
| display river fraction | `0.10 / 0.15 / 0.20` |
| display Q quantile | `0.25 / 0.35 / 0.45` |
| thermal erosion | `20 / 50 / 80` |
| final stream power | `500 / 1000 / 1500` |
| mountain threshold | `0.60 / 0.62 / 0.65` |
| plateau threshold | `0.35 / 0.40` |

Do not run a full Cartesian product. Use staged one-factor/bracketed comparisons with fixed baselines, then verify interactions for finalists.

No value in this table is an approved new default.

---

# 13. C11 — staged glaciation after the baseline world is stable

## 13.1 Decision

Glaciation is worth implementing because it can add physically meaningful snow/firn storage, glacier-fed runoff, ice-carved terrain, postglacial lakes, morainic provenance, and later sea-level change. It is not the repair for the current river or erosion failures.

C11 must distinguish:

~~~text
present cryosphere state
    seasonal snow / firn / active land ice

inherited paleoglacial geomorphology
    eroded bedrock / till / moraine / overdeepening / glacial provenance
~~~

A present-day cold cell must not automatically imply either active glacier ice or inherited glacial terrain.

Paleoglacial provenance requires a `history_complete` flag. When the simulated history is absent or incomplete, lack of a glacier means `unknown`, not `simulated_non_glacial`. Never infer inherited glaciation by reversing present temperature, elevation, or land-ice state.

## 13.2 G1 — Diagnostic surface mass balance

**Dependency:** PC3 and C10 temperature/precipitation unit decision

Use final monthly temperature and physical precipitation with subgrid elevation bands derived from available p10/p90/ridge statistics.

Do not invent arbitrary weights from p10/mean/p90 when terrain aggregation can provide better data. Extend climate-grid topographic aggregation to publish three or four approximately equal-area elevation bands with their actual mean elevations and land-fraction weights. P10/p90/ridge may remain diagnostics or a compatibility fallback, marked lower confidence.

Recommended reduced-order components:

- smooth rain/snow partition;
- expected positive degree days or an equivalent monthly temperature-index method;
- separate snow and ice melt factors;
- snow melts before firn/ice;
- optional small refreezing term;
- annual surface mass balance in metres water equivalent per year;
- connected perennial-snow/firn potential components.

Outputs:

~~~text
accumulation_mwe_yr
ablation_mwe_yr
surface_mass_balance_mwe_yr
perennial_snow_fraction
firn_fraction_or_store
land_ice_potential
equilibrium_line_altitude_or_equivalent_diag
~~~

G1 is diagnostic. It must not modify the DEM, coastline, or climate feedback. Validate cold-dry, cold-wet, warm-ablation, elevation-band, and E–W seam fixtures.

## 13.3 G2 — Reduced ice thickness and flow

**Dependency:** accepted G1 and performance review

Use a conservative 2-D shallow-ice/SIA-lite solver on the climate/cryosphere grid, or a validated reduced flowline model for suitably narrow components. Do not run full ice dynamics on the 4096 × 2048 terrain grid.

Minimum state and products:

~~~text
ice_thickness_m
ice_surface_elevation_m
land_ice_fraction
ice_velocity_or_flux_summary
ice_margin_mask
glacier_id
glacier_melt_runoff_monthly
ice_volume_m3
mass_balance_residual
~~~

Numerical requirements:

- finite-volume or otherwise explicitly conservative fluxes;
- E–W periodicity and closed/declared N/S boundaries;
- adaptive stable timestep;
- non-negative thickness without silent clipping loss;
- bounded equilibrium spin-up;
- explicit calving/outflow only if implemented;
- runoff delivered at the glacier margin exactly once;
- no ordinary surface rivers rendered across grounded ice.

Before enabling snow/ice albedo feedback, audit and remove or explicitly replace any legacy fixed cold-cell temperature correction. Otherwise the same ice feedback may be counted once by the legacy temperature rule and again by the new fractional snow/ice albedo.

The OGGM model architecture is an appropriate example of a reduced modular chain from gridded climate through temperature-index mass balance to simplified glacier dynamics: <https://gmd.copernicus.org/articles/12/909/2019/index.html>.

## 13.4 G3 — Paleoglacial geomorphology

**Dependency:** accepted G2 and stable non-glacial erosion/hydrology

Present equilibrium ice alone cannot create inherited moraines and postglacial lakes. Use a small number of stylized quasi-equilibrium climate states rather than simulating every year of a 100,000-year cycle:

~~~text
glacial maximum
→ retreat/deglaciation
→ present climate
~~~

Reduced geomorphic outputs may include:

~~~text
glacial_erosion_delta_m
glacial_deposition_delta_m
till_thickness_m_or_score
moraine_score_or_object
overdeepening_mask
glacial_provenance_id
inherited_glacial_landform_class
history_complete
~~~

A first glacial-erosion law may depend on basal sliding/ice flux and resistance. Such reduced models can produce broad U-shaped valleys, hanging valleys, and overdeepenings, but their calibration is uncertain; preserve this uncertainty in diagnostics and do not fit a single seed. Relevant reduced-model references include:

- <https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007JF000807>
- <https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016JF003960>

After G3 modifies the inherited bedrock/topographic surface:

1. run the ordinary hydrology on the postglacial DEM;
2. treat overdeepenings as basin candidates, not automatically full lakes;
3. let the repaired lake-storage model determine actual water;
4. preserve active present ice separately from inherited glacial provenance;
5. classify small moraines below grid resolution as semantic/graphic texture rather than exaggerated DEM walls.

## 13.5 G4 — Sea level, shoreline, isostasy, and advanced ice

**Status:** DEFERRED

Possible later work:

- global ice-volume to sea-level relation;
- shoreline regeneration;
- glacial isostatic adjustment;
- calving and marine-terminating glaciers;
- ice streams and basal hydrology;
- history-era climate transitions.

This is high-complexity work because the present pipeline fixes the ocean mask early and many downstream products depend on it. G4 requires a separate architecture decision and must not be smuggled into G1–G3.

## 13.6 C11 performance budget

Recommended first grid: Atlas climate grid `512 × 256`; Full cryosphere grid no larger than `1024 × 512` without new evidence.

Use:

- float32 for large continuous fields after precision tests;
- uint8 for fractions/classes when quantized products suffice;
- int32 for IDs;
- two-dimensional state plus streamed monthly forcing;
- sequential/reused work buffers;
- sparse/local refinement for glacier tongues or moraine objects.

Target additional working memory:

- G0/G1 Atlas: preferably below 40–64 MiB;
- G2 Full: preferably below 128 MiB additional peak RSS;
- no new terrain-resolution 12-month cubes;
- no unbounded outer climate–ice iteration.

Measured against the stabilized PC7 baseline, initial runtime warnings are:

- G0/G1 Atlas above `+15%`;
- present-land-ice G2 above `+35%`;
- opt-in paleoglacial G3 above approximately `2×` the non-glacial Atlas runtime.

These are review thresholds, not permission to weaken conservation. Report SMB, ice-flow, feedback, and geomorphology time separately.

Runtime and RSS thresholds remain those in the parent corrective addendum. Crossing them requires an optimization attempt and written evidence.

---

# 14. File-level implementation map

The implementation agent must verify current names before editing. Likely primary locations are:

## Python/worldsim

### Hydrology

- `worldsim/src/worldsim/physical/hydrology/cylindrical_graph.py`
  - preserve explicit target kinds;
  - add or support condensed lake-supernode topology;
  - provide topological traversal and compact graph arrays.
- `worldsim/src/worldsim/physical/hydrology/basins_storage.py`
  - solve one supernode's A–V–h storage from complete inflow;
  - expose bounded periodic/fixed-point state and ledger.
- `worldsim/src/worldsim/physical/hydrology/pipeline.py`
  - reorder final Q, channel states, networks, and vectors;
  - remove post-hoc spill accumulation;
  - publish the three channel tiers and canonical diagnostics.
- `worldsim/src/worldsim/physical/hydrology/runoff.py`
  - migrate store-state convergence and remove silent clipping.
- `worldsim/src/worldsim/physical/hydrology/channels.py`, `rivers.py`, `discharge.py`, `transmission.py`
  - physical/geomorphic/display split;
  - loss-aware volume routing;
  - state and threshold contracts.
- `worldsim/src/worldsim/physical/vectorize/rivers.py` and lake vectorization
  - build semantics after graph construction;
  - preserve explicit ocean/lake targets and shoreline splits.

Suggested new focused modules, if they reduce coupling:

~~~text
physical/hydrology/condensed_graph.py
physical/hydrology/mass_ledger.py
physical/hydrology/network_tiers.py
~~~

### Cryosphere

Suggested package:

~~~text
physical/cryosphere/__init__.py
physical/cryosphere/params.py
physical/cryosphere/snow_firn.py
physical/cryosphere/mass_balance.py       # G1
physical/cryosphere/ice_flow.py           # G2, later
physical/cryosphere/geomorphology.py      # G3, later
physical/cryosphere/pipeline.py
~~~

G0 may initially reuse runoff rain/snow helpers, but canonical ownership must end in one package; do not maintain two snow models.

### Erosion

- `physical/erosion/pass_one.py`
  - separate process outputs and conditioning;
  - clarify the first local precipitation/slope term.
- `physical/erosion/fluvial.py`
  - consume geomorphic channels and metric corridor.
- `physical/erosion/pipeline.py` and `physical/final/pipeline.py`
  - correct inputs, provenance, gates, and final products.

### Landforms

- `physical/landforms/params.py`
  - honest representability and refined-analysis settings.
- `physical/landforms/objects.py`
  - watershed/pass segmentation, ridge graph, plateau rim.
- `physical/landforms/classify.py`
  - remove mechanical acceptance repainting.
- `physical/landforms/pipeline.py`
  - complete acceptance conjunction and object catastrophe guards.

### Canonical products

- `worldsim/src/worldsim/config.py` and `worldsim/configs/default_planet.yaml`;
- `spatial/canonical_acceptance.py`;
- `spatial/model.py`, RasterStore, VectorStore, queries, and hex pipeline;
- atlas export and legend generation;
- manifest/effective-config schema.

## Godot

- `godot/scenes/Main.gd` / `Main.tscn`
  - remove hard-coded divergence from canonical defaults;
  - expose physical and display groups separately.
- `godot/atlas/MapModeController.gd`
  - one diagnostics selector with versioned layer descriptors.
- `godot/atlas/RasterLayerRenderer.gd`, `VectorLayerRenderer.gd`, `LandformLayerRenderer.gd`
  - consume exported semantics and legends only.
- `godot/atlas/InspectorPanel.gd`
  - implement structured hydrology, erosion, landform, and later cryosphere sections.
- `godot/atlas/LegendPanel.gd`
  - stable absolute continuous legends and Python-owned categorical legends.

---

# 15. Validation matrix and canonical acceptance

## 15.1 Four required evidence levels

| Level | Purpose |
|---|---|
| Unit | Pure transformations, units, schemas, and small functions. |
| Synthetic physical fixture | Conservation, topology, periodicity, and geometry invariants. |
| Fixed-seed integration | Real stage ordering, consumer consistency, maps, and object distributions. |
| Production/performance | Atlas/Full runtime, RSS, output size, Godot loading, and canonical acceptance. |

No level substitutes for the next.

## 15.2 Canonical acceptance gates

The final world conjunction must include relevant versions of:

~~~text
temperature_integrity_ok
moisture_spinup_ok
moisture_budget_ok
snow_soil_state_periodic_or_firn_transfer_ok
snow_soil_firn_mass_balance_ok
lake_graph_topology_ok
lake_storage_periodic_ok
hydrology_mass_balance_ok
hydrology_coupling_ok
final_q_network_order_ok
river_vector_topology_ok
erosion_hillslope_ok
erosion_fluvial_ok
conditioning_separate_ok
biome_v2_ok
landforms_representability_ok
landforms_geometry_ok
canonical_store_export_ok
hex_layout_ok
performance_gate_ok_or_reviewed_warning
~~~

For C11 add:

~~~text
cryosphere_mass_balance_ok
ice_flow_stability_ok
ice_nonnegative_ok
glacier_runoff_once_ok
glacial_geomorphology_ok
~~~

An omitted diagnostic that is known to fail is a failed acceptance implementation, not a warning.

## 15.3 Required production report

Each Atlas/Full validation note must include:

- effective config and checksum;
- component algorithm versions and input checksums;
- source/sink/storage mass ledgers;
- lake candidates, periodic/non-periodic counts, area and states;
- physical/geomorphic/display channel cells, length, components, states, and terminal kinds;
- erosion process-delta distributions and active-domain metrics;
- landform scores, systems, objects, representability, ridge/rim failures;
- BiomeV2 distribution without retuning unless the package is C10;
- runtime per stage, total runtime, peak RSS, and output size;
- fixed-scale PNGs and ordinary atlas screenshots;
- canonical acceptance with every failed gate named.

---

# 16. Definition of Done

Production closure PC0–PC7 is complete only when:

- every lake is routed as one supernode and lake cascades conserve monthly mass;
- spill enters downstream lakes in the same routed traversal and incurs declared losses;
- water area, open-water area, and lake ice are separate fractional products;
- seasonal snow and soil repeat, persistent surplus transfers explicitly to firn, and no cap deletes mass;
- final Q is computed before any river mask or vector topology;
- physical, geomorphic, and display networks are separate and named;
- ocean mouths have explicit ocean targets and confluences cannot be sinks;
- erosion uses the geomorphic network, has process-specific deltas/gates, and excludes conditioning from erosion acceptance;
- landform objects are representable or explicitly unresolved, mountain systems split meaningfully, ridges follow crests, and plateau rims are real escarpment segments;
- every red landform diagnostic required by this document participates in acceptance;
- canonical stores, queries, hex products, atlas exports, Godot modes, legends, and inspector agree on names, units, IDs, and no-data rules;
- Quick and Atlas suites pass and one Full smoke/performance run is documented;
- the runtime regression is explained and an optimization attempt is documented;
- C10 readiness is explicitly reviewed by the user.

C11 is complete only when, in addition:

- cold climate, perennial snow, firn, active land ice, lake ice, and inherited glacial provenance are distinct products;
- diagnostic SMB is physically unit-consistent and mass-balanced;
- any dynamic ice flow conserves volume, remains non-negative, and stays within the target-machine budget;
- glacier melt enters hydrology once at a declared location;
- glacial erosion/deposition modifies inherited terrain separately from present ice;
- postglacial depressions become basin candidates and are not automatically painted as lakes;
- shoreline/sea-level work remains deferred unless separately approved.

The intended result is a credible reduced-order world generator with transparent limitations, not a complete Earth-system model.
