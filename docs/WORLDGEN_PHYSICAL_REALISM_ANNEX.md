# Physical World Realism Annex

## Hypsometry, temperature, moisture, hydrology, and landform semantics

> **Status:** Accepted design guidance; **PR-0…PR-9 foundation implemented**; **CR-0–CR-9** accepted — [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md)  
> **Date:** 2026-08-16 (header amended 2026-08-17)  
> **Repository:** BartoszDawidowski/Conworld-History  
> **Audited commit:** 6a961161c2a10d322de0990e6cbec8317ea80a5c  
> **Primary objective:** Improve the physical credibility of generated worlds without materially exceeding the demonstrated capabilities of the target Apple M2 / 8 GB machine.  
> **Execution rule:** Convert this annex into small implementation milestones. Complete, validate, document, and stop after each milestone before starting the next one.  
> **Operational tracker:** [`docs/PHYSICAL_REALISM_PLAN.md`](PHYSICAL_REALISM_PLAN.md) (PR + CR status, conflict register).  
> **Production defects / CR-0…CR-9:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md).

---

# 1. Authority and relationship to existing documentation

This annex supplements:

- docs/WORLDGEN_ARCHITECTURE.md;
- docs/IMPLEMENTATION_PLAN.md;
- docs/ATLAS_PLAN_B.md;
- docs/HISTORY_SIMULATION_ARCHITECTURE.md.

Existing milestone statuses remain useful as a record that a baseline feature was delivered. They do not prove that every physical invariant is satisfied.

Where this annex identifies a demonstrated correctness problem, its corrective requirement takes precedence over an earlier qualitative acceptance statement. All unrelated architectural decisions remain valid.

In particular:

- Milestones 6, 9, 11, and 13 remain the delivered baseline;
- the issues below are scientific-hardening follow-ups, not a request to rewrite the entire generator;
- Plan B8 and B9 remain planned, but their mechanisms and order are amended by this annex;
- no B8 or B9 tuning should begin until the moisture correctness gate is complete;
- Python/worldsim remains the owner of canonical physical logic;
- Godot exposes parameters, starts runs, renders results, and inspects them, but must not own a second implementation of the algorithms.

The first Cursor task after receiving this annex was planning-only and is **done** (2026-08-16):

1. ~~read this annex completely;~~
2. ~~reconcile it with the three physical-world planning documents;~~
3. ~~add the corrective milestones and dependencies;~~ → `PHYSICAL_REALISM_PLAN.md`
4. ~~mark conflicts explicitly;~~ → conflict register C-01…C-10
5. ~~stop before implementation.~~

Next implementation step when instructed: **PR-0** only.

---

# 2. Status vocabulary

Every item in this annex uses one of the following meanings:

| Status | Meaning |
|---|---|
| **BASELINE IMPLEMENTED** | Code exists at the audited commit. This does not necessarily mean the new acceptance criteria are met. |
| **ACCEPTED** | The design direction has been agreed and should be planned for implementation. |
| **PLANNED** | The capability is wanted, but should be implemented only after its dependencies. |
| **DEFERRED** | Preserve the option and its reopening trigger, but do not implement it now. |
| **OUT OF SCOPE** | Do not add it under this annex. A separate design decision would be required. |

Do not describe an ACCEPTED or PLANNED item as implemented until code, tests, diagnostics, and a validation note all exist.

---

# 3. Goals, constraints, and non-goals

## 3.1 Goals

The updated generator should:

- produce more plausible distributions of land elevation;
- preserve the accepted landmass structure and current tectonic character;
- transport moisture in the declared wind direction;
- conserve the moisture proxy or explicitly account for every source and sink;
- remove the arbitrary January dry-start bias;
- use physical distance scales that do not change meaning between profiles;
- create a truly cylindrical E–W hydrological graph;
- distinguish exorheic and endorheic drainage;
- allow weak wadis to disappear while large allochthonous rivers survive arid corridors;
- preserve enough topographic semantics to identify mountain ranges and plateaus later;
- retain deterministic outputs, diagnostics, and reproducible effective configuration;
- keep current good performance as a first-class requirement.

## 3.2 Constraints

- The canonical terrain raster remains richer than the analytical hex grid.
- E–W wraps; N–S never wraps.
- The cylindrical equal-area projection remains the project projection.
- The current default tectonic configuration, including folding_ratio = 0.01, remains frozen during hypsometry calibration.
- The current Full terrain target of 4096 × 2048 remains valid unless a new benchmark disproves its viability.
- New parameters must use physical units or be explicitly dimensionless.
- Quick may be an approximate preview; Atlas and Full must preserve comparable physical meaning.
- New work must remain independently runnable and testable outside Godot.

## 3.3 Explicit non-goals

This annex does not require:

- a general circulation model;
- a full three-dimensional atmosphere;
- a multi-century dynamic ocean;
- dynamic plate tectonics during history;
- a full groundwater solver;
- detailed glacier dynamics;
- a sediment transport model;
- hydraulic simulation of every lake;
- automatic global hyperparameter optimisation;
- final art for mountain ranges or plateaus;
- separate landmass and relief surfaces at this time.

---

# 4. Executive decision register

| ID | Status | Decision |
|---|---|---|
| D-01 | **ACCEPTED** | Keep the current tectonic defaults, including folding_ratio = 0.01, while correcting hypsometry downstream. |
| D-02 | **ACCEPTED** | Replace single-maximum land normalisation with a monotonic, robustly anchored power_tail_v2 land hypsometry transform. |
| D-03 | **DEFERRED** | Do not add landmass_surface or relief_surface now. Preserve the option and reopening criteria in documentation. |
| D-04 | **ACCEPTED** | Add shared GridMetrics and express distance, gradient, and neighbourhood scales in physical units. |
| D-05 | **ACCEPTED** | Correct the analytical hex layout before climate or history calibration uses its latitude and area aggregates. |
| D-06 | **ACCEPTED** | Make base temperature thermal inertia periodic and capable of a seasonal lag, not only amplitude damping. |
| D-07 | **ACCEPTED** | Correct moisture advection direction, time-step scaling, precipitation budget, and annual spin-up before adding B8 or B9. |
| D-08 | **ACCEPTED** | B8 plume, recycling, and ITCZ terms must operate inside the moisture budget; they may not add post-hoc precipitation. |
| D-09 | **ACCEPTED** | B9 monsoon modifies wind and moisture transport first. A direct precipitation multiplier is not the primary mechanism. |
| D-10 | **ACCEPTED** | Hydrology must use one canonical periodic downstream graph on the original width; cropped products from independent padded copies are insufficient. |
| D-11 | **ACCEPTED** | Annual and monthly effective discharge must use consistent loss and runoff semantics. |
| D-12 | **ACCEPTED** | Lakes and basins must explicitly distinguish open, closed/endorheic, seasonal/playa, and frozen states where supported. |
| D-13 | **ACCEPTED** | Base moisture used to create hydrology and the later inland-water moisture correction require distinct provenance. |
| D-14 | **ACCEPTED** | Landforms use a multi-layer model: broad surface context, local form, geographic object, and tectonic provenance. |
| D-15 | **ACCEPTED** | LandformAnalysis reads the final unconditioned elevation_v2_m and does not feed back into tectonics or climate. |
| D-16 | **ACCEPTED** | Every milestone requires synthetic invariants, fixed-seed validation, and a performance report before defaults are retuned. |

---

# 5. Audit summary at the baseline commit

The current implementation contains a strong modular foundation, monthly fields, deterministic stages, diagnostics, and a viable performance profile. The following gaps are significant because existing tests do not exercise the relevant invariant.

| Priority | Area | Confirmed baseline issue | Principal code locations |
|---|---|---|---|
| P0 | Moisture transport | Positive northward wind is documented as movement toward smaller row indices, but the upwind stencil samples the wrong side. | physical/moisture/transport.py: _upwind_advect |
| P0 | Moisture budget | Large-scale, orographic, and convective precipitation are summed independently and can exceed available q; clipping q afterward hides the excess. | physical/moisture/transport.py: build_monthly_moisture |
| P0 | Moisture state | q begins at zero in January and only one year is run, producing an arbitrary calendar-start transient. | physical/moisture/transport.py: build_monthly_moisture |
| P0 | Hydrology topology | Padding and cropping do not produce one periodic E–W drainage graph. Accumulation and basin IDs can disagree across the seam. | physical/hydrology/flow.py |
| P0 | River vectors | Reconstructing PyFlwDir from the cropped D8 raster can turn a seam-crossing downstream edge into a pit and split a river. | physical/vectorize/rivers.py: build_river_network |
| P0 | Hex geometry | Odd columns are shifted only south and clipped at y = -1, causing N–S asymmetry in centres and raster aggregation. | spatial/hex_grid/layout.py: hex_center_xy |
| P1 | Hypsometry | Every seed is normalised by one land maximum and therefore receives exactly land_scale_m as its highest point. Mid-elevation statistics become sensitive to one extreme. | physical/terrain/elevation.py: raw_to_elevation_m |
| P1 | Terrain detail | Local detail amplitude is scaled by the full peak-to-peak tectonic range, so one extreme can amplify detail globally. | physical/terrain/refine.py: refine_terrain |
| P1 | Temperature scale | Continentality and inland SST decay are expressed in cells; the same parameter has a different physical reach in Quick, Atlas, and Full. | physical/climate/temperature.py; physical/ocean/sst.py |
| P1 | Temperature seasonality | Current thermal inertia blends monthly equilibrium with the annual mean. It damps amplitude but cannot create an oceanic seasonal lag. | physical/climate/temperature.py: apply_thermal_inertia |
| P1 | Physical gradients | Several topographic and SST gradients are per cell rather than per metre, and boundary-current width is a fixed number of cells. | physical/atmosphere/circulation.py; physical/ocean/currents.py; physical/ocean/sst.py |
| P1 | River gating | Once a wet seed enters the candidate river mask, the mask is propagated downstream even where effective discharge falls to zero. | physical/hydrology/rivers.py: gate_river_mask_by_discharge |
| P1 | Discharge seasonality | Annual effective Q includes transmission loss, but monthly_discharge is gross accumulation without the same loss. | physical/hydrology/pipeline.py |
| P1 | Depression semantics | max_depth = -1 and edge outlets fill all depressions for routing; genuine endorheic basins are not explicit. | physical/hydrology/flow.py |
| P1 | Lake metadata | Every vector Lake is marked closed_basin = True, while inlet_river_ids and outlet_river_id are not populated from the graph. | physical/vectorize/lakes.py |
| P1 | Provenance | Final saved moisture is the second pass with inland-water evaporation, while final hydrology was produced from the first pass. | physical/final/pipeline.py |
| P2 | Terrain semantics | No canonical representation currently distinguishes a mountain range, massif, plateau interior, or plateau rim. | New physical/landforms package and downstream stores |

The audit also confirmed what should not be rewritten:

- base raster latitude is correctly derived from equal-area y through asin;
- the base temperature raster is broadly symmetric under a symmetric fixture;
- the current folding value is not itself evidence of a bug;
- the current modular stage structure can support the corrections;
- B8 and B9 are already marked pending and can be revised before implementation.

---

# 6. Corrected dependency graph

The intended physical derivation is:

~~~text
TECTONIC RAW FIELDS
    ↓
ROBUST TERRAIN REFINEMENT
    ↓
SEA-LEVEL CALIBRATION
    ↓
FROZEN OCEAN_MASK
    ├── ocean branch → bathymetry
    └── land branch  → power_tail_v2
                         ↓
                  TERRAIN / EROSION V1
                         ↓
          BASE CLIMATE + PERIODIC TEMPERATURE
                         ↓
                 ATMOSPHERE (ONE-WAY)
                         ↓
                    OCEAN + SST
                         ↓
                  FINAL TEMPERATURE
                         ↓
             PERIODIC BASE MOISTURE M1
                         ↓
             CYLINDRICAL HYDROLOGY H1
                         ↓
                  FLUVIAL EROSION
                         ↓
                 FINAL elevation_v2_m
                         ├── final climate/moisture/hydrology/vectors
                         └── LandformAnalysis from unconditioned DEM

Optional final moisture correction:

H_final lake/river masks
    ↓
inland-water evaporation
    ↓
M_ecology

M_ecology does not silently become the causal precipitation input of H_final.
~~~

The existing two-pass moisture arrangement may be retained because it cheaply avoids an uncontrolled feedback loop. It must be made explicit:

- moisture_hydrology_input identifies the field that created hydrology;
- moisture_ecology identifies the later field including river/lake evaporation;
- HydrologyResult stores the checksum or provenance identifier of its precipitation input;
- atlas diagnostics must not label moisture_ecology as the precipitation that caused the already-computed river network;
- adding a further hydrology correction from moisture_ecology requires a separately bounded iteration design.

The current one-way atmosphere/SST relationship is also acceptable as a reduced-order model if documented:

- atmosphere uses the post-DEM, pre-SST temperature state;
- SST then corrects the final surface temperature used by moisture and ecology;
- B9 adds a bounded monsoon wind anomaly explicitly rather than pretending that the entire atmosphere was recomputed;
- a coupled atmosphere iteration is deferred.

---

# 7. Shared physical grid metrics

## 7.1 Purpose

A cell count is not a physical length. It changes with profile resolution and, on the equal-area projection, with latitude and direction.

Add a shared module, preferably:

~~~text
worldsim/src/worldsim/spatial/metrics.py
~~~

It should expose a GridMetrics value object derived from:

- planet radius or circumference;
- projection;
- raster width and height;
- row latitude;
- E–W wrapping and N–S boundary rules.

## 7.2 Required capabilities

GridMetrics should provide or support:

- cell area;
- row-wise east–west centre spacing;
- north–south centre spacing;
- metric gradients;
- metric slope;
- physical path length for D8 edges;
- distance-to-mask in kilometres with E–W wrap;
- conversion of requested kilometre radii into an efficient row-aware neighbourhood;
- diagnostic conversion back to cells only where an underlying library requires it.

Use exact or sufficiently accurate spherical centre distances near the polar rows. Do not assume one isotropic cell size for the whole raster.

## 7.3 Parameter migration

Replace or deprecate:

- continentality scale_cells;
- inland_decay_cells;
- ocean boundary width_cells;
- any topographic gradient interpreted as metres per cell;
- any landform radius expressed only in cells.

New names must contain their units, for example:

- continentality_scale_km;
- sst_inland_decay_km;
- western_boundary_width_km;
- landform_relief_radius_km.

For one schema transition, old names may be accepted with a warning and an explicit conversion based on the profile for which the value was tuned. Do not silently reinterpret the same number as kilometres.

The effective converted value and schema version must be stored in the world manifest.

## 7.4 Analytical hex correction

The current odd-q lattice shifts odd columns south by half a row and clips them at the southern boundary. Replace it with a north–south balanced construction or an equivalent tessellation that preserves:

- exactly 256 × 128 analytical cells;
- E–W wrapping;
- no N–S wrapping;
- symmetric north and south coverage;
- invertible centre lookup;
- shared polygon edges without gaps.

The exact geometric construction is an implementation choice, but it must pass:

- no centre is clipped to y = +1 or y = -1;
- the latitude distribution mirrors under north–south reflection;
- the mean latitude is approximately zero;
- northern and southern mirror rows receive equivalent raster sample counts within a declared tolerance;
- xy_to_hex(hex_center_xy(q, r)) returns the original q, r;
- neighbour winding and E–W wrap remain correct;
- cached elevation and climate aggregates are rebuilt after the layout schema changes.

This is a P0 geometry fix before calibrating history against hex latitude or topography.

---

# 8. Hypsometry v2

## 8.1 Accepted scope

Implement power_tail_v2 only on the land branch after sea-level calibration has frozen ocean_mask and before climate, erosion, and hydrology consume metric elevations.

Do not modify:

- ocean_mask;
- the number or shape of land components;
- the relative ordering of land heights;
- PyPlatec folding_ratio = 0.01;
- ocean bathymetry semantics in this milestone.

The purpose is to correct the distribution of heights, not to solve land fragmentation.

## 8.2 Problem with the baseline mapping

The existing mapping divides every positive raw height by one seed-specific maximum and multiplies by land_scale_m. Consequences:

- every seed has exactly the same maximum height;
- one outlier controls all other land elevations;
- raising folding to improve landmass structure can inflate the full land hypsogram;
- calibration of lapse rate, orography, and erosion is performed on an unstable elevation distribution.

## 8.3 Algorithm contract

power_tail_v2 must be:

- deterministic;
- strictly monotonic for positive land values;
- anchored at sea level with zero mapping to zero;
- robustly normalised by a high land quantile rather than one maximum;
- compressive over low and middle land elevations;
- equipped with a continuous soft tail for rare extremes;
- independent of the landmass mask;
- free of newly introduced NaN or Inf values;
- implemented as a pure testable function.

A suitable implementation family is:

~~~text
u = max(raw_elevation - sea_level_raw, 0)
a = quantile(u on land, anchor_quantile)
x = u / max(a, epsilon)

body(x) = x ^ body_exponent

for x above the anchor:
    continue with a monotonic soft tail
    rather than renormalising the seed maximum to a fixed height

elevation_m = anchor_elevation_m * curve(x)
~~~

The final formula must be continuous at the anchor. Prefer a continuous first derivative unless testing demonstrates that a simpler continuous curve is visually and physically sufficient.

Configuration should include:

~~~text
terrain.hypsometry_mode
terrain.hypsometry_anchor_quantile
terrain.hypsometry_anchor_elevation_m
terrain.hypsometry_body_exponent
terrain.hypsometry_tail_softness
terrain.hypsometry_max_elevation_m
terrain.hypsometry_algorithm_version
~~~

The safety maximum is a guardrail, not the normalisation target. Treat it as a validation threshold or as the asymptote of a strictly monotonic soft tail. Do not hard-clip valid land cells: a hard clamp would create artificial plateaus and break rank preservation. The generator must not force every seed to hit the guardrail.

The agreed starting family includes a body exponent around the previously tested compressive power, but final defaults must be selected from a seed suite rather than one attractive map.

## 8.4 Robust terrain detail scale

In refine_terrain, replace use of the full peak-to-peak tectonic range as the sole scale of:

- detail noise;
- volcanic addition;
- orogenic addition.

Use a documented robust range, for example a configurable central quantile span, with a separately bounded extreme contribution.

Adding one synthetic extreme to elevation_raw must not materially change RMS detail over the unaffected 99% of the map.

This does not create a separate relief_surface.

## 8.5 Diagnostics

For each generated world record:

- p10, p25, p50, p75, p90, p95, p99, and maximum land elevation;
- mean land elevation;
- fraction of land above 1, 2, 3, 5, and 7 km;
- fraction of land below 200 m and 500 m;
- land component count before and after the transform;
- rank-order preservation;
- maximum and percentile slopes after erosion;
- transform parameters and algorithm version.

## 8.6 Acceptance

- ocean_mask is bit-identical immediately before and after the land transform;
- land component count and coastline are unchanged by the transform;
- 0 maps to 0;
- no positive input becomes negative;
- land rank ordering is preserved, apart from exact input ties;
- the maximum is not mechanically identical across all seeds;
- the selected distribution is acceptable across the fixed seed suite;
- climate and hydrology are rebuilt, not loaded from an incompatible cache;
- folding, sea-level target, and erosion parameters are not retuned in the same task;
- runtime is negligible relative to terrain generation;
- a validation note includes before/after hypsograms and absolute-scale maps.

## 8.7 Deferred separate surfaces

landmass_surface and relief_surface are explicitly DEFERRED, not rejected.

Reopen this option only if a multi-seed report shows that one monotonic land transform cannot simultaneously achieve:

- acceptable landmass continuity and island frequency;
- credible land hypsometry;
- credible regional relief;
- stable Atlas/Full behaviour;

without again increasing folding mainly to suppress oceanic islands.

Reopening requires a separate architecture decision. Do not introduce a second surface as an undocumented tuning trick.

---

# 9. Temperature v2

## 9.1 Preserve the valid foundation

Retain:

- equal-area latitude conversion through y = sin(latitude);
- monthly insolation;
- hemispheric seasonal inversion;
- lapse-rate cooling from final metric elevation;
- weaker ocean seasonal amplitude;
- one-way SST influence on final surface temperature.

Do not replace the current reduced-order climate with a GCM.

## 9.2 Fix periodic thermal inertia

Replace annual-mean blending as the canonical inertia mechanism with a cheap periodic first-order reservoir, conceptually:

~~~text
T[m] = T[m-1] + alpha * (T_equilibrium[m] - T[m-1])
alpha = 1 - exp(-delta_t / tau)
~~~

Use separate physical response times for ocean and land, with continentality allowed to shorten the inland land response.

Solve the 12-month cycle to periodic closure through either:

- a small bounded number of annual passes;
- an analytical cyclic solution;
- another method shown to be equivalent and cheaper.

The result must:

- damp ocean amplitude more than land amplitude;
- delay the ocean seasonal maximum relative to the forcing;
- avoid an arbitrary January initial condition;
- remain deterministic.

## 9.3 Name temperature states and owners

Diagnostics and, where useful, persisted results should distinguish:

- temperature_equilibrium_c;
- temperature_base_c after inertia and lapse;
- temperature_sst_coupled_c;
- temperature_final_c used by moisture and ecology.

Each correction has one owner:

- lapse: climate/final DEM correction;
- thermal inertia: climate;
- ocean/SST anomaly and inland decay: ocean coupling;
- any future snow/albedo correction: a separate bounded stage.

Do not apply lapse or SST twice during final recalculation.

## 9.4 Physical scales

Move to GridMetrics-backed:

- continentality_scale_km;
- sst_inland_decay_km;
- boundary-current widths in kilometres;
- SST and topographic gradients per physical distance.

Current Atlas-tuned cell values can be used to derive initial compatibility targets, but the conversion and source profile must be documented. Atlas and Full should then be calibrated to the same physical parameter values.

## 9.5 Climate-grid topographic aggregation

Mean elevation alone hides narrow high barriers. Without creating relief_surface, climate downsampling should optionally carry inexpensive subgrid statistics:

- mean elevation;
- p10 and p90 elevation or another robust relief span;
- maximum or high-quantile ridge elevation;
- RMS metric slope.

Use them only where physically justified, for example to avoid erasing an orographic barrier. Do not add all subgrid statistics directly to temperature.

## 9.6 Acceptance

- a symmetric synthetic world remains N–S symmetric in annual mean;
- northern and southern seasonal phases remain opposite;
- ocean amplitude is lower and ocean maximum later than matched coastal land;
- lapse-rate tests control for latitude and continentality;
- SST influence decreases with physical inland distance;
- the same physical distance parameter has comparable reach in Atlas and Full;
- changing profile resolution does not reproduce the prior eightfold scale change;
- no double lapse or double SST correction appears in provenance;
- fixed-seed absolute temperature distributions are reported before retuning base_temp_c.

Hypsometry v2 must be accepted before final temperature defaults are retuned, because lower median land elevation will itself warm much of the land through lapse-rate correction.

---

# 10. Moisture and precipitation v2

## 10.1 Correctness gate before B8 and B9

The following work is P0 and must precede any plume, recycling, ITCZ, or monsoon enhancement:

1. fix north–south advection direction;
2. make transport and diffusion time-step consistent;
3. enforce the moisture budget;
4. converge to a periodic annual state;
5. expose complete budget diagnostics;
6. preserve or improve the existing windward/leeward synthetic behaviour.

Do not attempt to repair the current output by further tuning advect_steps, wind scale, rainout, convection, or evaporation before this gate passes.

## 10.2 Direction convention

The canonical convention is:

~~~text
j = 0              north
increasing j       south
wind_v > 0         northward, toward decreasing j
wind_v < 0         southward, toward increasing j
wind_u > 0         eastward
wind_u < 0         westward
~~~

The transport stencil, orographic dot product, atmosphere, tests, and diagnostics must use the same convention.

Required impulse tests:

- positive u moves a compact q impulse east;
- negative u moves it west across the E–W seam;
- positive v moves it to a smaller row index;
- negative v moves it to a larger row index;
- no moisture wraps north–south.

## 10.3 Conservative transport and diffusion

Advection should be conservative in a closed synthetic domain, apart from declared boundary export.

The current weak diffusion is applied once per substep without scaling by delta_t. Therefore changing advect_steps changes physical diffusion.

Replace this with either:

- diffusion scaled by delta_t;
- a once-per-month physical mixing operator;
- a documented conservative numerical equivalent.

advect_steps should primarily control numerical accuracy, not redefine the climate.

Required test:

- with fixed physical parameters, increasing advect_steps changes the result only within a declared convergence tolerance.

## 10.4 Explicit moisture budget

Use one canonical moisture-proxy unit during the core correction. Every monthly update must account for:

~~~text
storage_start
+ ocean_evaporation
+ lake_evaporation
+ river_evaporation
+ land_ET
+ declared external source, if any
- precipitation
- declared atmospheric export or sink
= storage_end
+ numerical_residual
~~~

Large-scale, orographic, and convective precipitation are candidate demands on the same available q. Their combined removal may not exceed available moisture.

A valid implementation may:

- allocate sequentially in a documented order;
- compute candidate components and scale them proportionally to available q;
- use another conservative partition.

In all cases:

- total precipitation is capped by available q;
- component fields sum to total precipitation;
- lee drying is either reinterpreted as transport/export or recorded as an explicit sink;
- clipping q to zero must not hide an unreported deficit;
- diagnostics include global and monthly residuals.

## 10.5 Periodic annual spin-up

Do not initialise the reported January with q = 0.

Run complete 12-month cycles until:

- the end-of-year q state matches the next start state within tolerance; or
- a configured maximum spin-up count is reached and diagnostics mark non-convergence.

Persist only the final converged annual cycle as the reported climatology.

Parameters should include:

~~~text
moisture.spinup_max_years
moisture.spinup_tolerance_relative
moisture.spinup_tolerance_absolute
~~~

Use a physically motivated warm start or another acceleration if needed to preserve performance. The convergence result and number of spin-up years must be stored.

## 10.6 Land ET and B8 recycling

Baseline land ET currently depends mainly on temperature. B8 must introduce a small land-water store or equivalent wetness state so that recycling is water-limited.

Minimum semantics:

- precipitation adds to a monthly land store;
- ET cannot remove more than the available store plus the same-step allowed input;
- runoff and ET compete through documented fractions;
- wet land at the same temperature can recycle more than desert;
- the store has a bounded capacity and deterministic carryover.

This is a proxy soil-water bucket, not a groundwater model.

## 10.7 Revised B8

B8 retains its three goals but changes their implementation constraints:

### Soft inland plume

- transports or mixes existing atmospheric moisture;
- is preferably wind-conditioned or flow-aligned;
- does not add precipitation directly behind barriers;
- remains subject to orographic rainout and the q budget;
- an isotropic distance-to-ocean field may be a low-weight fallback or diagnostic, not an unconstrained final rain layer.

### Land ET recycling

- uses the bounded land-water store;
- cannot create moisture over persistently dry land from temperature alone.

### ITCZ

- strengthens moisture convergence and/or convection in the moving monthly band;
- is limited by available moisture;
- must not double-count the tropical convergence already present in circulation and the existing convective term;
- diagnostics separate the base convection and the added convergence effect.

## 10.8 Revised B9

The monsoon proxy should:

- derive a seasonal land–SST thermal contrast;
- create a bounded onshore/offshore wind anomaly;
- feed the corrected wind into moisture transport;
- preserve the base trade-wind field outside the affected region;
- avoid a standalone precipitation belt;
- allow only a small optional precipitation adjustment if a documented residual need remains after transport, and keep it inside the moisture budget.

## 10.9 Moisture provenance in the final pipeline

Persist or otherwise expose:

- moisture_hydrology_input;
- moisture_ecology;
- precipitation input checksum stored by HydrologyResult;
- whether inland lake/river evaporation was active;
- whether B8 or B9 terms were active;
- algorithm and configuration version.

## 10.10 Acceptance

Synthetic:

- four-direction impulse transport;
- conservation without sources and sinks;
- precipitation never exceeds available moisture;
- component precipitation sums exactly to total precipitation;
- annual constant-climate fixture has no January-to-December startup ramp;
- rotating month labels rotates the result rather than changing its climatology;
- ridge fixture produces windward enhancement and leeward reduction;
- plume does not erase a strong rain shadow;
- wet-land ET exceeds desert ET at matched temperature.

Diagnostics:

- monthly and annual evaporation;
- precipitation;
- land ET;
- storage change;
- explicit atmospheric sink/export;
- numerical residual;
- spin-up years and closure error;
- interior/coast precipitation ratio;
- windward/leeward ratio;
- ITCZ/off-band ratio.

Profile validation:

- physical transport reach is comparable in Atlas and Full;
- advect_steps convergence passes;
- runtime and memory remain within the milestone budget;
- no NaN or Inf;
- all fixed-seed maps use an absolute scale in addition to any display stretch.

Separate vapour/cloud reservoirs and delayed fallout remain optional future refinements. They are not required for this correction if the conservative single-reservoir model satisfies the tests.

---

# 11. Hydrology v2

## 11.1 Canonical cylindrical graph

Padding may remain an implementation aid for DEM conditioning, but it cannot be the canonical graph.

After flow direction is selected, construct one downstream index array on the original H × W grid:

- E–W neighbours use column modulo W;
- N–S neighbours outside the grid are invalid;
- ocean contacts and explicit closed-basin sinks are typed outlets;
- each routable land cell has at most one downstream target;
- graph cycles are detected and resolved deterministically or represented explicitly if physically intended.

Compute from this one graph:

- upstream accumulation;
- drainage basin and watershed IDs;
- stream order;
- gross discharge;
- effective discharge;
- transmission loss routing;
- downstream diagnostics;
- raster-to-vector river paths.

PyFlwDir may continue to provide useful conditioning or local flow-direction functionality. Canonical periodic graph operations should live behind a narrow project-owned interface, for example:

~~~text
worldsim/src/worldsim/physical/hydrology/cylindrical_graph.py
~~~

Do not call pyflwdir.from_array on a cropped non-periodic D8 raster to generate canonical seam-crossing river vectors.

## 11.2 Required topology invariants

- A seam-crossing downstream edge preserves accumulation and basin ID.
- A basin remains one basin after longitude rotation and inverse rotation.
- No outlet is created merely because a river reaches column 0 or W - 1.
- Accumulation does not decrease downstream without an explicit sink or typed lake transition.
- River vectors remain continuous through the seam using locally unwrapped geometry.
- Raster, graph, and vector representations share the same downstream relation.
- A diagnostic checks every eligible edge or a deterministic exhaustive reduced fixture, not a random sample with an 85% pass threshold.

## 11.3 River persistence and wadis

Do not propagate the visible river mask unconditionally from a wet seed through every downstream candidate cell.

River presence should be derived from:

- canonical effective Q;
- minimum physical drainage area;
- optional persistence/hysteresis that prevents one-cell flicker;
- a display LOD threshold separate from the physical network.

If effective Q reaches zero and remains below the physical threshold, the visible channel may terminate.

A large river with sufficient upstream Q may survive an arid corridor despite local loss.

Required fixture:

~~~text
effective Q along path = 100, 80, 20, 0, 0, ...

Expected:
- the strong upstream portion is retained;
- cells after physical extinction are not restored only by downstream inheritance.
~~~

## 11.4 Annual and monthly runoff

Annual and monthly fields must use compatible semantics.

The current annual field applies transmission loss while monthly_discharge does not. Correct this by routing monthly effective Q with the same graph and loss model.

Add a cheap seasonal runoff layer:

- partition precipitation between rain and snow using temperature;
- carry a bounded snow store;
- release melt with a simple temperature-dependent rule;
- optionally retain a small soil store from the moisture bucket;
- compute monthly runoff before channel routing;
- do not add full groundwater or baseflow in this milestone.

Acceptance:

- monthly effective discharge sums or aggregates consistently with the annual water balance within tolerance;
- cold-season snow is not immediately counted as rainfall runoff;
- thaw produces a delayed pulse;
- gross and effective monthly fields remain separately inspectable.

## 11.5 Resolution-independent river thresholds

Global quantiles can remain useful for display LOD but should not define all river physics.

Prefer physical configuration such as:

- minimum catchment area in km²;
- minimum mean or seasonal effective discharge in declared units;
- optional permanence fraction of months;
- optional display quantile applied after the physical mask.

Changing grid resolution should not force the same percentage of land cells to be rivers.

## 11.6 Depression conditioning and endorheic basins

Separate:

1. small numerical depressions that may be filled or breached for stable routing;
2. real topographic depressions that should become lake-basin or endorheic objects.

Do not fill all depressions to an edge and then label every resulting Lake as closed.

The minimum implementation should:

- expose maximum numerical fill depth and/or scale;
- retain qualifying closed sinks;
- record spill elevation where one exists;
- distinguish ocean outlet, open-lake outlet, and closed-basin sink;
- allow a dry endorheic depression to remain a playa rather than permanent water.

## 11.7 Lake state and metadata

Lake classification should use catchment water balance, not only mean precipitation over the depression itself.

Suggested states:

~~~text
open
endorheic
seasonal_or_playa
frozen_or_ice_covered
~~~

Populate from the canonical graph:

- inlet_river_ids;
- outlet_river_id;
- closed_basin;
- basin_id;
- spill elevation;
- mean and seasonal effective inflow;
- water-state classification.

An open lake has a graph-valid outlet. An endorheic lake has none. Metadata must agree with river nodes and segments after save/load.

## 11.8 Acceptance

Synthetic:

- seam-crossing basin and river;
- longitude-rotation invariance;
- Nil-like large river crossing an arid corridor;
- weak wadi extinction;
- open lake with one outlet;
- closed basin with no outlet;
- dry playa;
- frozen seasonal store;
- two tributaries merging across the seam.

Global:

- exhaustive downstream graph validation;
- basin ID continuity;
- no untyped pits except explicitly permitted sinks;
- monthly/annual effective Q consistency;
- river raster/vector consistency across the seam;
- lake inlet/outlet graph consistency;
- fixed-seed counts and distributions for exorheic and endorheic basins;
- Atlas/Full convergence for drainage area and major rivers;
- performance report on Full.

---

# 12. LandformAnalysis

## 12.1 Status and purpose

Status: **PLANNED after final terrain semantics are stable**.

The immediate requirement is to preserve the data contract and implementation path. Final graphics are not part of this annex.

LandformAnalysis answers:

- what the final terrain looks like;
- which cells form a mountain, ridge, valley, plateau interior, or escarpment;
- which connected regions form a mountain range, massif, or plateau;
- which tectonic process is the likely provenance.

It does not modify terrain or decide how tectonics should have generated it.

## 12.2 Why relative height alone is insufficient

Large local relief is necessary evidence for many mountains, but it can also identify:

- the rim of a plateau;
- a canyon wall;
- a coastal escarpment;
- a deeply incised high plain.

A plateau interior may be high but locally smooth. A mountain on a plateau may be locally prominent while sharing the plateau's broad context.

Therefore the internal representation must not force one exclusive choice between mountain and plateau.

## 12.3 Semantic layers

Store at least three independent meanings:

### Broad surface context

~~~text
plain
upland
plateau
basin
~~~

### Local landform element

~~~text
flat
summit
ridge
shoulder
slope_or_flank
footslope
valley
depression
escarpment
~~~

### Provenance

~~~text
orogenic
volcanic
rift_related
residual_or_eroded
mixed
unknown
~~~

Tectonic interpretation supplies provenance and may contribute to confidence. It must not be a hard gate for mountain classification.

## 12.4 Input and pipeline position

Run base LandformAnalysis:

- after final fluvial erosion has created elevation_v2_m;
- on the unconditioned final DEM;
- before or as part of final vector geography;
- independently of the hydrological filled DEM.

Hydrology-dependent additions such as passes, canyons, and incised valleys belong in a later derived stage.

Any change to:

- hypsometry algorithm or parameters;
- erosion algorithm or parameters;
- final DEM checksum;
- landform algorithm version;

invalidates the landform result.

## 12.5 Multi-scale fields

Use physical kilometre scales through GridMetrics.

Candidate features include:

- metric slope;
- RMS or robust roughness;
- robust local relief, such as p95 - p05;
- regional relief;
- topographic position relative to a neighbourhood or surrounding ring;
- fraction of steep cells;
- fraction of near-flat interior;
- ridge and valley continuity;
- optional smoothed curvature or geomorphon-like local form.

Use at least:

- a fine or subgrid scale for local ruggedness;
- a mesoscale for ridges and mountain terrain;
- a macroscale for broad plateau uplift and continental swells.

Exact radii are calibration parameters in kilometres, not constants in cells.

## 12.6 Efficient analysis grid

Do not run naive large moving windows over 4096 × 2048 for every scale.

Recommended default:

- aggregate the final terrain to the climate/landform analysis grid;
- carry mean, p10, p90, standard deviation, and RMS slope from underlying terrain blocks;
- compute mesoscale and macroscale features using a pyramid or separable filters;
- process one scale at a time and reuse buffers;
- use full terrain only for optional later refinement of peaks and passes.

Quick may return a coarse preview. Atlas and Full must retain the same physical scale definitions and similar major objects.

## 12.7 Continuous scores before hard labels

Persist or derive:

~~~text
mountain_score
plateau_score
hill_score
confidence
~~~

Mountain terrain tends to combine:

- large fine and mesoscale relief;
- steep slopes and ruggedness;
- connected ridges and valleys;
- meaningful peak prominence.

Plateau interior tends to combine:

- elevation above a broad surrounding base;
- a large connected near-level interior;
- low or moderate fine relief;
- a separately detected rim or escarpment.

Plateau rim is an escarpment adjacent to a plateau interior. It is not sufficient evidence that the entire plateau is a mountain range.

A dominant display class may be derived, but it is not the sole canonical meaning.

## 12.8 Canonical objects

### MountainRange

Minimum fields:

- deterministic id within world and algorithm version;
- polygon or component mask reference;
- ridge centreline or skeleton;
- area, length, width, elongation, and orientation;
- mean, maximum, and base elevation;
- local and regional relief;
- peak IDs;
- major saddle/pass candidates when available;
- provenance fractions and confidence.

### Plateau

Minimum fields:

- deterministic id within world and algorithm version;
- interior polygon;
- rim/escarpment geometry;
- area;
- mean surface elevation;
- surrounding base elevation;
- internal relief and slope;
- drainage class;
- provenance fractions and confidence.

Later optional objects:

- Massif;
- Peak;
- Pass;
- Canyon;
- MajorValley.

## 12.9 Stable ID scope

Guarantee deterministic IDs for:

- the same world seed;
- the same effective configuration;
- the same final DEM;
- the same algorithm version;
- the same execution environment where exact determinism is supported.

Do not promise that IDs survive an algorithm-version or regenerated-terrain change. Cross-version migration is a separate problem.

Component extraction and ID ordering must:

- respect E–W wrapping;
- avoid unordered set/dictionary iteration as an ordering source;
- sort by a deterministic spatial and geometric signature;
- record the input DEM checksum and algorithm version.

## 12.10 Storage and integration

Suggested package:

~~~text
worldsim/src/worldsim/physical/landforms/
    params.py
    metrics.py
    classify.py
    objects.py
    pipeline.py
~~~

Suggested persisted outputs:

~~~text
final/landforms/landform_rasters.npz
final/landforms/landform_diagnostics.json
final/vectors/mountain_ranges.geojson
final/vectors/plateaus.geojson
~~~

Compact raster contract:

- context_id: uint8;
- local_form_id: uint8;
- provenance_id or provenance fractions: compact type;
- confidence: uint8;
- mountain_score and plateau_score: uint8 or float32 if justified;
- mountain_range_id: int32;
- plateau_id: int32.

Intermediate float fields should be persisted only in diagnostic mode unless another canonical consumer requires them.

Extend:

- FinalRecalcResult;
- VectorGeographyResult and VectorStore;
- spatial indexes and queries;
- hex aggregation;
- atlas exports.

Hex caches should include:

- dominant broad context;
- mountain_fraction;
- plateau_fraction;
- mean relief and slope;
- intersecting mountain_range_ids;
- intersecting plateau_ids;
- derived terrain_barrier_strength or terrain_mobility_cost.

History must consume derived movement cost through EnvironmentAdapter. It must not equate mountain with impassable or interpret raw landform rasters independently.

Godot may display:

- a landform raster mode;
- range polygons and ridge centre lines;
- plateau interior and rim;
- object IDs and statistics in the inspector.

Godot does not reclassify the DEM.

## 12.11 Synthetic acceptance fixtures

Required:

1. isolated cone → mountain or massif, not plateau;
2. elevated flat block with steep rim → plateau interior plus escarpment;
3. mountain on a plateau → both plateau context and local mountain feature;
4. rolling high plain → upland or plateau, not a mountain range;
5. long connected ridge → one range with coherent orientation;
6. two ridges separated by a broad low divide → two objects;
7. canyon cut through a plateau → plateau remains a plateau, canyon is local form;
8. range crossing the E–W seam → one object and one ID;
9. N–S mirrored fixtures → mirrored scores and objects within tolerance.

## 12.12 Scientific basis

The design follows the general principle that elevation alone does not define mountains:

- Meybeck, Green, and Vörösmarty distinguish mountains from high plateaus by combining elevation with relief roughness: https://www.geobotany.org/library/pubs/MaybeckM2001_mrd_34-45.pdf
- Iwahashi and Pike combine slope, local convexity, and surface texture in DEM classification: https://pubs.usgs.gov/publication/70029913
- Jasiewicz and Stepinski provide an efficient, scale-adaptive pattern-recognition approach to local landform elements: https://doi.org/10.1016/j.geomorph.2012.11.005

These references motivate the feature families. They do not require copying one Earth-specific threshold table into a fictional planet.

---

# 13. Canonical data and provenance contracts

Every saved physical field must document:

- canonical or derived/cache status;
- source grid and shape;
- unit;
- dtype;
- valid range and no-data semantics;
- E–W/N–S topology;
- algorithm version;
- input checksums;
- effective configuration;
- creation stage.

Minimum provenance chain examples:

~~~text
final river vector
← canonical periodic river graph
← effective monthly/annual discharge
← runoff and channel losses
← moisture_hydrology_input
← final temperature and wind
← final DEM
← power_tail_v2 land terrain
← frozen ocean mask
← refined tectonic raw field
~~~

~~~text
MountainRange
← LandformAnalysis object extraction
← multi-scale metric terrain fields
← unconditioned elevation_v2_m
~~~

Do not use the same field name for two causal states. In particular, distinguish:

- base and final temperature;
- moisture_hydrology_input and moisture_ecology;
- gross and effective discharge;
- unconditioned and hydrologically conditioned DEM;
- landform context and dominant display class.

---

# 14. Configuration and Godot exposure

## 14.1 General rules

- Parameters that materially affect the generated world remain manually configurable in Godot Advanced settings.
- The portable request freezes the effective configuration at Start.
- The Python worker validates and persists the effective values.
- Unit-bearing parameters include the unit in the name or schema.
- Algorithm versions are explicit.
- UI ranges are broad enough for experimentation but safe against numerical failure.
- New defaults are not retuned in the same milestone that fixes correctness.

## 14.2 Suggested groups

~~~text
planet_metrics
hypsometry
temperature_response
ocean_temperature_coupling
moisture_transport
moisture_budget_and_spinup
hydrology_runoff_and_losses
endorheic_and_lake_rules
landform_analysis
~~~

## 14.3 Backward compatibility

When replacing cell-based parameters:

- increment configuration schema version;
- read old names only through an explicit compatibility layer;
- record the assumed source profile;
- emit a warning;
- write only the new physical-unit names in new manifests;
- invalidate incompatible cached climate, hydrology, hex, and landform results.

---

# 15. Cursor implementation sequence

The sequence below is normative unless a validation result demonstrates a dependency problem.

## PR-0 — Baseline and regression harness

**Deliver:**

- fixed synthetic fixtures;
- fixed world seed suites;
- current output metrics;
- current time and peak-memory baselines;
- absolute-scale diagnostic maps;
- checksums and effective config capture.

**Acceptance:**

- no production behaviour changes;
- baseline can be reproduced;
- audit failures have tests that fail for the correct reason;
- existing qualitative tests remain available.

**Stop.**

## PR-1 — GridMetrics and analytical hex geometry

**Deliver:**

- physical grid metrics;
- metric distance and gradient helpers;
- balanced hex layout;
- config migration framework for physical length parameters.

**Acceptance:**

- metric and hex synthetic tests pass;
- no pole clipping;
- Atlas/Full distance tests pass;
- affected caches are versioned and rebuilt;
- performance impact is measured.

**Stop.**

## PR-2 — Hypsometry power_tail_v2

**Deliver:**

- pure transform;
- robust terrain-detail scale;
- pipeline/config/manifest integration;
- diagnostics and seed report;
- default initially disabled or identity-equivalent, followed by a separate calibration step.

**Acceptance:**

- mask and rank invariants;
- seed-suite hypsograms;
- no simultaneous folding retune;
- Full benchmark.

**Stop.**

## PR-3 — Temperature periodic response and physical scales

**Deliver:**

- periodic first-order thermal response;
- named temperature states;
- physical continentality and SST reach;
- metric gradients and boundary widths where used by temperature/ocean coupling;
- subgrid relief statistics contract.

**Acceptance:**

- phase-lag, amplitude, lapse, symmetry, and profile convergence tests;
- provenance proves one application of each correction;
- defaults remain unretuned until the validation report is reviewed.

**Stop.**

## PR-4 — Moisture correctness core

**Deliver:**

- corrected v sign;
- conservative transport;
- delta_t-scaled diffusion;
- precipitation budget;
- annual spin-up;
- budget/provenance diagnostics.

**Acceptance:**

- all P0 moisture invariants pass;
- startup ramp removed;
- advect_steps convergence;
- existing rain-shadow and wet/dry tests pass;
- Full performance is acceptable.

**Stop.**

## PR-5 — Canonical cylindrical hydrology graph

**Deliver:**

- canonical downstream index;
- periodic accumulation, basins, order, and routing;
- seam-aware vector construction;
- exhaustive graph validation.

**Acceptance:**

- seam and longitude-rotation fixtures;
- no seam pits or split basins;
- raster/vector continuity;
- deterministic graph and IDs;
- Full performance report.

**Stop.**

## PR-6 — Effective runoff, wadis, endorheic basins, and lakes

**Deliver:**

- monthly runoff and simple snow store;
- monthly transmission losses;
- physical river thresholds;
- Q-aware river termination;
- explicit basin/lake states;
- inlet/outlet metadata.

**Acceptance:**

- annual/monthly water consistency;
- Nil and wadi fixtures;
- open and closed lake fixtures;
- metadata round-trip;
- Atlas/Full major-river convergence.

**Stop.**

## PR-7 — Revised B8

**Deliver:**

- budgeted moisture mixing/plume;
- water-limited ET recycling;
- non-duplicative ITCZ convergence;
- configuration and diagnostics.

**Acceptance:**

- interior reach improves without erasing rain shadows;
- budget remains closed;
- wet/dry ET contrast;
- ITCZ seasonal movement;
- no independent post-hoc rain field.

**Stop.**

## PR-8 — Revised B9

**Deliver:**

- bounded seasonal land–SST wind anomaly;
- transport-first monsoon response;
- diagnostics and modest configurable strength.

**Acceptance:**

- seasonal onshore/offshore contrast;
- precipitation seasonality follows transport;
- trade winds outside the active region remain coherent;
- moisture budget remains closed.

**Stop.**

## PR-9 — LandformAnalysis foundation

This may be split into:

- PR-9A contract and synthetic fixtures;
- PR-9B multi-scale metric fields and scores;
- PR-9C objects and seam-aware IDs;
- PR-9D storage, vectors, hex aggregation, queries, and Godot display;
- PR-9E seed-suite calibration and performance gate.

Do not tune landform thresholds until power_tail_v2 and final erosion are stable.

Hydrology-dependent peaks, passes, valleys, and canyons are a later follow-up and must not block base range/plateau recognition.

---

# 16. Validation strategy

## 16.1 Four required levels

1. software invariants;
2. synthetic physical fixtures;
3. fixed-seed spatial validation;
4. distribution and performance validation across seed suites.

Passing only an image-based visual review is insufficient.

## 16.2 Seed suites

Maintain:

- very small deterministic fixtures for every commit;
- fixed Quick seeds for fast regression;
- fixed Atlas seeds for integration;
- fixed Full seeds before changing defaults;
- the broader 25 fast / 10 final-quality suite when calibrating distributions.

Report median, range, and outliers. Do not select defaults from one seed.

## 16.3 Cross-profile convergence

For the same planet parameters:

- physical length parameters are identical in kilometres;
- major climate gradients are comparable;
- major river basins and ranges remain recognisable;
- expected detail increases with resolution without changing the large-scale physical meaning;
- Quick limitations are labelled rather than silently treated as final quality.

## 16.4 Absolute diagnostics

Save both:

- visually useful stretched images;
- absolute-scale images with stable legends.

Min–max stretching alone can make a numerically small or physically wrong change look convincing.

## 16.5 Validation notes

Each implementation milestone creates:

~~~text
docs/validation/physical_realism_prN.md
~~~

The note includes:

- code/config version;
- seeds and profile;
- tests run;
- before/after metrics;
- diagnostic images;
- runtime and peak RSS;
- known limitations;
- explicit decision to accept, revise, or stop.

---

# 17. Performance and memory gates

The audited repository records approximately 20 seconds for the Full terrain pipeline and an estimated working set below the existing 2 GB budget on the target host. Preserve that general performance class.

Rules:

- benchmark before and after each milestone;
- avoid naive O(N × radius²) moving-window algorithms;
- cache GridMetrics by shape and planet configuration;
- use float32 for large working fields unless precision testing requires float64;
- use uint8/int16 for classes and int32 for IDs;
- process multi-scale landform fields one scale at a time;
- do not keep all monthly full-resolution diagnostics resident;
- keep diagnostic intermediates optional;
- prefer array operations, separable filters, pyramids, and project-owned O(N) graph passes;
- bound moisture spin-up and report non-convergence;
- preserve a disabled/identity path with negligible overhead for optional stages.

Useful memory facts:

- one 4096 × 2048 float32 raster is approximately 32 MiB;
- one uint8 raster at that resolution is approximately 8 MiB;
- analysis on the 1024 × 512 Full climate grid is much cheaper.

Initial performance targets:

- power_tail_v2: no more than approximately 3% of total generation time;
- cached GridMetrics: negligible repeated cost;
- LandformAnalysis: target no more than approximately 15% of total generation time;
- optional LandformAnalysis disabled: no meaningful core-physics overhead;
- any milestone adding more than approximately 15% total median runtime or 128 MiB peak RSS requires a written optimisation attempt or explicit user acceptance.

These are engineering gates, not reasons to weaken correctness tests silently.

---

# 18. Deferred work and reopening triggers

## 18.1 landmass_surface and relief_surface

Status: **DEFERRED**.

Reopen only under the criteria in section 8.7.

## 18.2 Separate vapour and cloud reservoirs

Status: **DEFERRED**.

Consider if the conservative single-reservoir moisture core cannot reproduce transport delay, orographic fallout, and seasonal closure without unstable tuning.

## 18.3 Fully coupled climate iteration

Status: **DEFERRED**.

The accepted reduced-order chain remains one-way with explicitly bounded corrections. A future coupled loop must define convergence, iteration cap, and performance cost.

## 18.4 Baseflow and groundwater

Status: **DEFERRED**.

The simple soil/snow stores are sufficient for this annex. Persistent groundwater and aquifers require their own water-budget design.

## 18.5 Dynamic lakes and glaciers

Status: **DEFERRED**.

Static climatological lake states and a snow store are sufficient. Dynamic shoreline volume and glacier flow are not required.

## 18.6 Landform passes and canyon networks

Status: **PLANNED AFTER BASE LANDFORMS AND STABLE HYDROLOGY**.

They may combine ridge topology with the river/valley graph without changing the base mountain/plateau classification.

---

## 18.7 Post–PR-9 production hardening (CR track)

Status: **CR-0–CR-9 accepted** — see [`PHYSICAL_REALISM_CORRECTIONS.md`](PHYSICAL_REALISM_CORRECTIONS.md). Atlas regen leftovers remain.

Reopen / continue when fixed-seed production metrics contradict a PR acceptance note (spin-up, SST form, monsoon regime, endorheism, subgrid layout, resolution-invariant scales). Do not substitute parameter retuning for those defects.

---

# 19. Explicit prohibitions

Cursor must not:

- retune folding while implementing power_tail_v2;
- change sea level to hide a hypsometry problem;
- add rainfall directly as independent noise or an unconstrained plume;
- implement B8/B9 before the moisture correctness gate;
- count the same ITCZ or SST effect twice;
- use cell counts as permanent physical distance parameters;
- use a padded copy as the canonical periodic hydrology graph;
- recreate seam-crossing river vectors from a non-periodic cropped D8 graph;
- classify every filled depression as a permanent closed lake;
- propagate river visibility after effective Q has physically vanished;
- derive LandformAnalysis from the conditioned/fill DEM;
- define mountain solely by absolute elevation or local max-minus-min;
- force mountain and plateau to be mutually exclusive;
- make mountain automatically impassable;
- store all landform intermediates by default;
- move canonical physics into Godot;
- mark a milestone complete without its validation note and performance measurement.

---

# 20. Traceability matrix

| Requirement | Main modules | Required tests | Diagnostic artefacts |
|---|---|---|---|
| GRID-01 physical metrics | spatial/metrics.py; spatial/extent.py | distance, slope, latitude, Atlas/Full convergence | grid_metrics.json |
| GRID-02 balanced hexes | spatial/hex_grid/layout.py; aggregate.py | mirror symmetry, inverse lookup, sample counts | hex_geometry.png; hex_metrics.json |
| HYP-01 power_tail_v2 | physical/terrain/elevation.py; pipeline.py | monotonicity, mask identity, quantiles | hypsometry_before_after.json; hypsogram.png |
| HYP-02 robust detail | physical/terrain/refine.py | outlier-insensitivity | terrain_detail_metrics.json |
| TEMP-01 periodic inertia | physical/climate/temperature.py | phase lag, amplitude, cyclic start | temperature_response.json |
| TEMP-02 physical SST reach | physical/ocean/sst.py; currents.py | km reach, Atlas/Full | sst_inland_transects.csv |
| MOIST-01 wind sign | physical/moisture/transport.py | four impulses and seam | moisture_impulses.npz |
| MOIST-02 conservation | physical/moisture/transport.py; pipeline.py | local/global budget | moisture_budget.json |
| MOIST-03 annual spin-up | physical/moisture/transport.py | periodic closure, month rotation | moisture_spinup.json |
| MOIST-04 revised B8 | moisture modules; atmosphere coupling | plume/ridge, ET store, ITCZ | moisture_b8_metrics.json |
| MOIST-05 revised B9 | atmosphere and moisture modules | seasonal onshore flow | monsoon_metrics.json |
| HYD-01 periodic graph | hydrology/cylindrical_graph.py; flow.py | seam basin, rotation invariance | hydrology_graph.json |
| HYD-02 river extinction | hydrology/rivers.py; transmission.py | Nil/wadi | river_q_transect.csv |
| HYD-03 monthly runoff | hydrology/pipeline.py | snow/melt, annual consistency | runoff_budget.json |
| HYD-04 lake semantics | hydrology and vectorize/lakes.py | open/closed/playa/frozen | lake_graph_consistency.json |
| LFORM-01 fields/scores | physical/landforms | synthetic landforms | landform_rasters.npz |
| LFORM-02 objects | landforms; vectorize; vector_store | seam ID, deterministic objects | mountain_ranges.geojson; plateaus.geojson |
| LFORM-03 consumers | hex_grid; queries; export | aggregation and round-trip | landform_diagnostics.json |

---

# 21. Global Definition of Done

This realism update is complete only when:

- the final DEM has a documented and reproducible derivation order;
- power_tail_v2 preserves the frozen land mask and does not require a simultaneous folding retune;
- terrain detail is not globally controlled by one extreme;
- temperature has a periodic response and profile-independent physical scales;
- moisture moves in the declared direction;
- moisture and precipitation close their budget within tolerance;
- the reported year is a periodic climatology rather than a January dry start;
- B8 and B9 operate through the conservative moisture system;
- hydrology uses one canonical E–W periodic graph;
- raster, basin, discharge, and river vectors agree through the seam;
- weak wadis can terminate and large upstream-fed rivers can survive dry corridors;
- annual and monthly effective discharge are consistent;
- endorheic basins and lake inlet/outlet metadata are explicit;
- both moisture passes have unambiguous provenance;
- LandformAnalysis, when implemented, reads unconditioned elevation_v2_m;
- mountains and plateaus can overlap semantically;
- range and plateau objects have deterministic IDs within the defined version scope;
- hex and history consumers use derived caches and EnvironmentAdapter rather than raw physical rasters;
- fixed-seed, cross-profile, round-trip, and performance tests pass;
- every milestone has a validation note;
- deferred landmass_surface and relief_surface options remain documented with reopening triggers;
- performance remains acceptable on the target machine.

At that point, the physical generator will be a materially stronger substrate for atlas rendering and later history without becoming a computationally disproportionate climate or landscape model.
