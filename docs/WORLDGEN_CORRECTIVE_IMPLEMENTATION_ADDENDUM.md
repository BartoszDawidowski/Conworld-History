# Worldgen Corrective Implementation Addendum

## Post-CR9 repairs, canonical integration, inspector expansion, and readable BiomeV2/landform map modes

> **Status:** Accepted corrective implementation guidance; implementation not started by this document  
> **Date:** 2026-08-17  
> **Repository:** `BartoszDawidowski/Conworld-History`  
> **Audited commit:** `6e7fb94466f35a26da8c85dc1496faf5267b04d9`  
> **Reference world:** Atlas profile, seed `183716`  
> **Parent design:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`  
> **Primary objective:** Correct the demonstrated regressions and incomplete integrations without changing the accepted tectonic character or materially exceeding the demonstrated performance of the target Apple M2 / 8 GB machine.

---

# 1. Authority and agent entry protocol

This addendum is a corrective successor to the physical-realism annex. It does not replace the valid architecture in:

- `docs/WORLDGEN_ARCHITECTURE.md`;
- `docs/IMPLEMENTATION_PLAN.md`;
- `docs/ATLAS_PLAN_B.md`;
- `docs/HISTORY_SIMULATION_ARCHITECTURE.md`;
- `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md`.

Where a validation note or plan marks CR-6, CR-7, CR-8, or CR-9 as accepted but this addendum demonstrates that a production invariant still fails, this addendum takes precedence. A green unit-test suite or the existence of a diagnostic field is not sufficient evidence that a physical contract is satisfied.

The first agent task after receiving this file is planning-only:

1. read this file completely;
2. read the parent physical-realism annex, especially sections 10–17 and 19–21;
3. inspect the current repository rather than relying on line numbers in this document;
4. reconcile the corrective work packages below with the current plans and validation notes;
5. mark CR-6–CR-9 as **BASELINE IMPLEMENTED — CORRECTION REQUIRED** wherever the production gates below fail;
6. add explicit dependencies, migration work, tests, and stop gates;
7. stop before implementation and present the revised plan for review.

After the plan is accepted, implement one corrective work package at a time. Every package ends with tests, a fixed-seed report, a performance note, and a stop. Do not combine correctness changes and default retuning in one pull request.

Python/worldsim remains the sole owner of canonical physics and classifications. Godot reads declared products, exposes parameters, renders them, and presents inspection data. Godot must not independently classify a biome, mountain, plateau, river state, or lake state.

---

# 2. Audited production baseline

The following results come from comparable Atlas runs of seed `183716`, before and after commit `6e7fb94`.

| Product metric | Previous audited version | `6e7fb94` | Interpretation |
|---|---:|---:|---|
| lake features drawn by Godot | 183 | 223 | The user's observation of more lakes is correct. |
| terrain cells drawn as lake water | 16,184 | 16,133 | The blue area is almost unchanged, but split into more objects. |
| drawn lake area as fraction of land | 10.64% | 10.61% | Visual lake inflation remains. |
| open + endorheic feature count | 46 | 167 | The semantic liquid footprint grew strongly. |
| open + endorheic terrain cells | 3,740 | 10,855 | Approximately 2.9 times the former footprint. |
| river cells | 782 | 2,694 | Rivers genuinely returned. |
| river vector segments | 111 | 421 | Vector coverage improved. |
| annual land precipitation mean, proxy | 1.962 | 1.771 | A modest reduction, not a new spatial regime. |
| land below annual precipitation proxy 1 | 61.94% | 61.49% | Dry-interior prevalence is almost unchanged. |
| old/new land temperature correlation | — | 0.99984 | Temperature is intentionally almost unchanged. |
| old/new land temperature MAE | — | 0.143 C | No temperature revolution should be expected. |
| first erosion mean absolute delta | 10.19 m | 0.204 m | Metric conversion made erosion almost a no-op. |
| final fluvial mean absolute delta | 3.77 m | 0.020 m | River incision is effectively disabled. |

The repository unit suite passed (`280 passed`, three deselected) and GitHub CI was green. The production Atlas result nevertheless reported overall `acceptance_ok = false`; moisture spin-up failed, while hydrology and landforms reported misleading positive acceptance because their gates omit demonstrated failures.

This distinction must remain visible in plans and validation notes:

~~~text
software tests passed
!= synthetic physical fixtures passed
!= fixed-seed integration passed
!= production profile accepted
~~~

---

# 3. Non-negotiable implementation rules

1. Keep `tectonics_folding_ratio = 0.01` frozen during these corrections.
2. Do not change sea level, ocean fraction, or folding to hide lake, erosion, hypsometry, or landform failures.
3. Preserve the current `power_tail_v2` hypsometry unless a dedicated multi-seed validation demonstrates a separate defect.
4. Use the final **unconditioned** `elevation_v2_m` for LandformAnalysis. Never classify landforms from the hydrologically filled DEM.
5. Keep physical thresholds in metres, kilometres, square kilometres, time, or declared discharge units. Cell counts may be fallback/representability constraints, not the primary world-scale definition.
6. Separate physical products from presentation products:
   - a basin envelope is not a lake surface;
   - a physical channel network is not a display LOD;
   - continuous mountain score is not mountain area fraction;
   - a display landform class is not the canonical semantic model.
7. No binary full-cell inland-water source may be used where a fractional area is known or can be cheaply derived.
8. Every generated field must have one owner, one unit, one grid, one no-data rule, one algorithm version, and one provenance chain.
9. Do not tune moisture transport before mass conservation and CFL tests pass.
10. Do not tune landform thresholds before erosion, analysis radii, land/ocean masking, and local-form rules are corrected.
11. Do not call a milestone accepted without at least one real Atlas seed and the required Full smoke/performance gate.
12. The target is a credible reduced-order world generator, not a general circulation, groundwater, sediment, or hydraulic model.

---

# 4. Corrected target pipeline

The intended post-correction derivation is:

~~~text
tectonics + robust hypsometry
    ↓
terrain refinement
    ↓
metric first erosion pass
    ↓
base climate / atmosphere / SST
    ↓
conservative periodic moisture M0
    ↓
canonical cylindrical drainage graph
    ↓
monthly runoff, channel loss, lake storage H0
    ↓
metric fluvial erosion
    ↓
final unconditioned elevation_v2_m
    ├── LandformAnalysis
    └── final climate / atmosphere / moisture M1
             ↓
       hydrology and lake storage H1
             ↓
       bounded optional moisture correction M2
             ↓
       bounded hydrology correction H2 only when convergence requires it
             ↓
       ecology / BiomeV2 / vectors / canonical WorldSpatialModel
             ↓
       hex cache / queries / atlas export / Godot
~~~

The feedback loop must be bounded and diagnosed. A permitted implementation is:

1. compute `M1` without inland-water evaporation;
2. compute `H1`, including actual monthly wet fractions;
3. compute `M2` with fractional lake/river evaporation;
4. recompute `H2` with the same drainage topology;
5. stop if lake-area Jaccard is at least 0.98 and total effective-Q change is at most 5%;
6. otherwise perform at most one additional damped correction or mark non-convergence.

Do not silently publish moisture from one hydrological state and rivers/lakes from a different state. Persist the input checksums and convergence metrics.

---

# 5. Canonical corrective data contracts

## 5.1 Inland-water semantics

Replace the overloaded single lake state with three independent axes:

~~~text
outlet_type:
    ocean_draining | open_lake | closed_endorheic

hydroperiod:
    permanent | seasonal | ephemeral_or_dry

ice_regime:
    normally_liquid | seasonally_frozen | perennially_frozen
~~~

`water_state` may remain temporarily as a derived compatibility field, but it must not be the canonical source of truth. Its derivation must be centralized and tested.

Minimum terrain-grid hydrology fields:

| Field | Type | Meaning |
|---|---|---|
| `basin_envelope_id` | `int32` | Topographic depression/catchment envelope; not a water mask. |
| `lake_id` | `int32` | Actual climatological liquid-water object ID; zero outside current liquid footprint. |
| `water_fraction_monthly` | `float32[12,H,W]` or streamed equivalent | Fraction of each cell covered by liquid water in each month. |
| `water_fraction_mean` | `float32[H,W]` | Annual mean liquid-water fraction. |
| `permanent_water_mask` | `uint8[H,W]` | Cells wet in every climatological month above a declared fraction. |
| `seasonal_water_mask` | `uint8[H,W]` | Cells wet in some but not all months. |
| `ice_fraction_monthly` | compact optional monthly field | Ice cover fraction when required for evaporation/rendering. |

Minimum lake-object fields:

- deterministic `feature_id` for the topographic basin and `water_body_id` for its current liquid-water object, plus `basin_id`;
- `outlet_type`, `hydroperiod`, and `ice_regime`;
- mean/minimum/maximum liquid area in km²;
- monthly liquid area or water fraction;
- monthly storage and water-surface elevation;
- floor minimum, spill elevation, and actual mean surface elevation;
- monthly effective inflow, evaporation, seepage/loss, spill, and outflow;
- `inlet_river_ids` and `outlet_river_id` derived from the canonical graph;
- algorithm version, configuration checksum, DEM checksum, and convergence state.

Do not renumber a topographic basin merely because climate reclassifies it from dry to seasonal or permanent. Prefer a deterministic `feature_id` derived from the canonical sink/spill topology, such as a versioned signature containing the master seed and canonical sink index. A changed shoreline must not create a new topographic identity.

The vector polygon in canonical `lakes.geojson` must describe the climatological mean liquid footprint, not the fill envelope. Basin envelopes belong in a separate diagnostic/canonical basin layer. Seasonal monthly shorelines are optional; monthly area and water level are required.

## 5.2 River semantics

Store separately:

- physical channel eligibility;
- visible atlas network after LOD;
- gross and effective monthly discharge;
- mean, minimum, maximum, and permanence fraction;
- state: `perennial`, `seasonal`, or `wadi`;
- contributing catchment area in km²;
- channel length in the cell and estimated channel width;
- bed-loss amount and loss-limited flag;
- upstream/downstream segment IDs and lake transitions.

The physical channel mask must use:

~~~text
effective_min_cells = max(
    ceil(river_min_catchment_km2 / cell_area_km2),
    river_min_accumulation_cells
)
~~~

If the requested catchment is smaller than one representable cell, diagnostics must report that fact. A global accumulation quantile may control display density only after the physical mask exists.

## 5.3 BiomeV2 semantics

BiomeV2 remains a seasonal ecological-regime layer parallel to Holdridge, not a claim to a complete Earth biome taxonomy.

Persist independent axes before deriving the simple display class:

- `frost_months`;
- `growing_season_months`;
- `water_deficit_mm`;
- `soil_moisture_growing_mean` or a clearly named climatological soil state;
- `thermal_regime_id`;
- `moisture_regime_id`;
- derived `biome_v2_class`;
- classification confidence or boundary distance if cheaply available.

The main display class may remain:

~~~text
ocean
ice
frost_seasonal
growing_moist
growing_deficit
arid
wetland
~~~

The canonical axes prevent a display-priority rule from erasing facts such as seasonal frost in a dry region.

## 5.4 Landform semantics

Retain the independent canonical layers from the parent annex:

- broad context: `plain`, `upland`, `plateau`, `basin`;
- local form: `flat`, `summit`, `ridge`, `shoulder`, `slope`, `footslope`, `valley`, `depression`, `escarpment`;
- provenance: `orogenic`, `volcanic`, `rift_related`, `residual_or_eroded`, `mixed`, `unknown`;
- continuous `mountain_score`, `plateau_score`, `hill_score`, and `confidence`;
- object IDs for ranges and plateaus.

Hex fields must distinguish a score mean from a classified fraction:

~~~text
mountain_score_mean
plateau_score_mean
mountain_terrain_fraction
mountain_range_fraction
plateau_context_fraction
plateau_object_fraction
~~~

Do not call the mean of `mountain_score` a `mountain_fraction`. `mountain_terrain_fraction` is the land fraction above the accepted terrain-class threshold; `mountain_range_fraction` is the land fraction belonging to an accepted range object. The same distinction applies to plateau context and plateau objects.

---

# 6. Corrective work packages

## C0 — Product-contract hotfixes and failing regression tests

**Priority:** P0  
**Purpose:** Stop visibly false output and establish tests that fail for the demonstrated reasons.

### Required changes

1. In `worldsim/src/worldsim/export/atlas_display.py`, preserve all lake state fields when re-exporting atlas GeoJSON.
2. In `godot/atlas/VectorLayerRenderer.gd`, use fail-closed semantics:
   - missing state must not silently mean permanent liquid water;
   - log one clear schema warning;
   - draw only records that explicitly qualify as liquid under the supported schema.
3. Fix the BiomeV2 precipitation unit error:

~~~python
precip_mm_m = precipitation_monthly_proxy * precip_scale_mm
~~~

   Do not divide monthly precipitation by the number of months a second time.
4. Add regression tests before changing the implementation:
   - atlas export round-trip containing open, endorheic, playa, and frozen fixtures;
   - renderer-side schema fixture with an intentionally missing state;
   - monthly precipitation equal to monthly PET gives zero annual deficit;
   - annual precipitation reconstructed from monthly values equals their sum exactly within floating tolerance.
5. Update validation statuses so a skipped Atlas run cannot produce `Accepted`.
6. Add explicit schema versions for the lake-vector contract and `atlas_display_v2`. If the canonical world schema remains unable to distinguish basin and water-body identity, increment it rather than overloading the old fields. At the audited commit this likely requires a `WorldSpatialModel` schema bump from v2 to v3; confirm the current constant before editing.
7. Add a complete `VectorStore` round-trip fixture for river/lake relationships. Verify that `RiverNode.lake_id`, `RiverSegment.from_lake_id`, and `RiverSegment.to_lake_id` survive save/load before adding more relationship fields.

### Acceptance

- seed `183716` no longer renders playa/frozen basin envelopes as permanent blue lakes;
- every exported lake feature contains the required state axes or an explicit compatibility state;
- BiomeV2 water-balance tests catch a deliberate factor-of-12 regression;
- no physics default is retuned in this package;
- create `docs/validation/worldgen_corrective_c0.md` and stop.

## C1 — Lake geometry from storage and discrete A–V–h curves

**Priority:** P0  
**Dependency:** C0

### Required algorithm

For every retained basin envelope:

1. collect land-cell floor elevations and cell areas;
2. sort the cells by elevation, using deterministic tie-breaking;
3. construct a discrete area–volume–height curve;
4. route monthly inflow and direct precipitation into storage;
5. remove evaporation and declared seepage/loss, capped by available storage;
6. compute actual water-surface elevation and wet area from storage;
7. rasterize only cells whose floor is below the current water level, with a fractional shoreline cell when useful;
8. spill only after storage reaches spill elevation;
9. route spill/outflow back into the canonical river graph;
10. repeat complete years until lake storage is periodic or the bounded spin-up limit is reached.

Apply the storage model to both open and closed basins. An open lake is not automatically filled to its spill envelope; it has an outlet only when storage reaches its spill relation. A dry closed depression remains a basin/playa rather than a lake.

The present linear `A(h)` approximation may be retained only as a temporary fallback behind an algorithm version. The discrete curve is preferred because the total depression footprint on the audited seed is small enough that its cost is negligible.

### Required consumers

Use actual liquid fractions for:

- lake vectors;
- evaporation;
- soil-store partitioning;
- Holdridge/BiomeV2 water overrides;
- hex aggregation;
- inspector fields;
- Godot rendering.

Never use `basin_envelope_id > 0` as a liquid-water mask.

### Tests

- empty closed basin remains dry;
- seasonally wet basin expands and contracts without becoming permanent;
- open basin below spill has no outflow;
- open basin above spill routes the exact excess;
- evaporation cannot remove more storage than exists;
- a frozen month suppresses or modifies liquid evaporation as declared;
- monotonicity: greater storage never produces a smaller wet area;
- rasterized wet area matches object metadata within one shoreline-cell tolerance;
- E–W seam basin remains one object;
- storage reaches a periodic annual state on a repeating climate fixture.

### Acceptance

- for Atlas seed `183716`, the ratio of rasterized liquid area to reported `wet_area_km2` is within 5%, not approximately 52 times too large;
- canonical lake polygons and raster masks agree;
- basin envelope area is reported separately and never presented as current water;
- create `docs/validation/worldgen_corrective_c1.md` and stop.

## C2 — River thresholds, channel losses, state export, and bounded coupling

**Priority:** P0/P1  
**Dependency:** C1

### Physical network versus display network

Build the physical channel network from catchment area and effective discharge. Apply display LOD afterward. Persist enough provenance to explain why a displayed reach exists or is hidden.

Replace transmission loss based on PET over a full raster cell with a flow-limited channel-bed loss, for example:

~~~text
potential_loss_m3 = loss_rate_m3_per_km_month
                    × channel_length_km
                    × optional_width_or_geology_factor

actual_loss_m3 = min(available_channel_flow_m3, potential_loss_m3)
~~~

The exact reduced-order formula may differ, but it must depend on channel geometry rather than full cell area, remain capped by available Q, and use identical monthly/annual semantics.

### Required output

- export river state and catchment area to `RiverSegment` and GeoJSON;
- export monthly effective discharge and bed loss;
- derive a fractional river-water area for atmospheric evaporation;
- keep channel state independent from display line width;
- ensure lakes cover river lines only where actual lake water exists;
- record pre/post coupling lake-mask Jaccard and effective-Q change.

### Tests and acceptance

- Nil-like river survives an arid corridor while a weak wadi terminates;
- annual effective Q matches the aggregation of monthly effective Q within a declared tolerance;
- channel loss never exceeds available Q;
- the physical channel candidate mask is not 100% of land under production defaults;
- Atlas/Full catchment thresholds retain comparable physical meaning;
- final moisture and final hydrology use converged or explicitly bounded-consistent water masks;
- create `docs/validation/worldgen_corrective_c2.md` and stop.

## C3 — Metric erosion recalibration and land-only coastal aggregation

**Priority:** P1  
**Dependency:** C0; may proceed in parallel with C1 after tests are isolated.

### Required changes

1. Keep the corrected metric slope and Laplacian.
2. Expose separate parameters for:
   - first-pass thermal transport coefficient;
   - first-pass fluvial coefficient;
   - final stream-power coefficient;
   - iterations, maximum per-step change, macro blend, and micro-fill depth where they materially affect output.
3. Rename parameters or document their effective units. Do not present the first-pass Godot `fluvial_k` as if it controlled final incision.
4. Add acceptance lower bounds so a no-op erosion pass cannot pass merely because it preserved correlation and did not increase roughness.
5. Use `downsample_land_elevation_mean` wherever a climate-grid land elevation is derived from a mixed coastal terrain block. Do not average negative bathymetry into the land temperature or ecology elevation.

### Initial calibration grid

These are starting experiments, not defaults:

| Parameter | Values to test | Initial centre |
|---|---|---:|
| first-pass `thermal_kappa` | 20, 50, 80 | 50 |
| final `stream_power_k` | 500, 1000, 1500 | 1000 |

Keep erosion iterations, maximum step, `folding_ratio = 0.01`, and hypsometry fixed during this grid. Record mean, median, p90, and maximum `|delta_elevation|`, roughness change, hypsogram change, depression count, river-profile incision, and runtime.

### Acceptance

- erosion is measurably non-zero but does not erase macro-relief;
- the ocean mask and coastline remain unchanged;
- the number and distribution of retained real basins are plausible across the seed suite rather than optimized for seed `183716`;
- no climate-grid land cell receives a negative elevation from coastal averaging;
- create `docs/validation/worldgen_corrective_c3.md` and stop before choosing new defaults.

## C3T — Temperature-state integrity and optional continental seasonality

**Priority:** P1 for state integrity; P2 for new continental amplitude  
**Dependency:** C3 for final DEM corrections; may otherwise be developed independently.

Temperature is currently the strongest component and must not be globally retuned during the P1 repair. Keep the initial comparison values fixed at `base_temp_c = 25`, lapse rate `6.5 C/km`, `sst_mix = 0.28`, and SST inland decay `1200 km`.

### Required integrity changes

1. `correct_climate_for_dem()` must update every named temperature state whose physical meaning depends on the DEM, including equilibrium, base/pre-SST, and final temperature arrays. A monsoon or other consumer must not read a stale pre-correction state.
2. Ocean/SST coupling must recompute temperature diagnostics from the resulting array. Do not append current metadata to statistics calculated from an earlier state.
3. Create one shared temperature-diagnostics function that accepts an explicitly named state.
4. Persist state provenance so a consumer can distinguish equilibrium, pre-SST/base, and final temperature.

### Optional continental seasonality

The current continentality mostly shortens an already short land response time and therefore barely changes seasonal amplitude. A later isolated experiment may amplify the anomaly around each cell's annual mean while preserving that mean, for example:

~~~text
T_adjusted = annual_mean
             + (T_equilibrium - annual_mean)
             × (1 + continentality × continental_seasonality_gain)
~~~

Expose the gain only after phase/amplitude tests exist. Sweep `continentality_scale_km = 300/500/800` and gain `0/0.25/0.5` without changing the global base temperature.

### Acceptance

- DEM and SST corrections update exactly the declared states once;
- temperature diagnostics reproduce direct calculations from final arrays;
- a mirrored fixture remains N–S symmetric;
- optional gain increases inland amplitude without changing each cell's annual mean beyond tolerance;
- create `docs/validation/worldgen_corrective_c3t.md` and stop.

## C4 — Conservative atmospheric moisture transport

**Priority:** P0  
**Dependency:** C0; retuning packages depend on C4.

### Required numerical contract

Replace the local `C × (q - q_upwind)` update with a shared face-flux divergence:

1. represent transported water as a density with explicit cell area or as cell mass `m = q × area`;
2. compute one flux for every shared E–W and N–S face;
3. apply equal and opposite contributions to adjacent cells;
4. wrap E–W faces and never wrap N–S faces;
5. use upwind or another positivity-preserving face value;
6. calculate the substep count from the full 2-D condition, for example `|Cx| + |Cy| <= CFL_limit`;
7. never hide instability through post-update clipping without recording the resulting mass error;
8. scale physical diffusion by substep time or apply one documented monthly conservative mixing operator.

Correct the topographic-wind sign convention. With rows increasing southward and `wind_v > 0` northward, the along-wind terrain term must use the same orientation as moisture orographic lift. Add explicit north/south ridge tests.

Rename the numerical meaning of `advect_steps` to `advect_max_substeps`, retaining an explicit legacy alias for old configurations. Required substeps control numerical safety; they do not define physical transport reach. If the required count exceeds the configured cap, fail the solver with diagnostics rather than clipping Courant numbers.

Treat the current soft plume as a compatibility experiment, not a permanent substitute for transport. After corrected advection is calibrated, test a default plume strength of zero before retaining any non-zero value.

### Moisture budget

For every month persist:

~~~text
storage_start
+ ocean evaporation
+ fractional lake evaporation
+ fractional river evaporation
+ water-limited land ET
- convective precipitation
- large-scale precipitation
- orographic precipitation
- ITCZ contribution already included in the above partition
- explicit export/sink
= storage_end + numerical_residual
~~~

All precipitation components compete for the same available moisture and sum exactly to total precipitation. Replace the current tautological overshoot diagnostic with a comparison between precipitation demand, allocated precipitation, and available pre-removal moisture.

### Spin-up

- warm-start later passes from the preceding converged `q` and land-store state;
- temporarily allow up to 48 complete years with early stopping;
- use initial hard candidates of relative L2 `q <= 0.5%`, p99 `q` change `<= 2%`, relative L1 land-store change `<= 1%`, and annual-precipitation field change `<= 0.5%`;
- report maximum closure, area-weighted RMSE, p99/p99.9 closure, annual precipitation change, and number of outlier cells;
- keep maximum closure as a warning, but do not let one isolated cell hide an otherwise stable field without reporting it;
- fail if annual precipitation remains materially unstable.

### Acceptance

- transport-only closed fixtures conserve relative mass to `1e-10` in float64 tests;
- the fully accounted production budget has relative residual at most `1e-6`, or a separately justified dtype-specific bound that remains far below the present 0.86%;
- four-direction impulse and E–W seam tests pass;
- increasing substeps changes the solution only within the convergence tolerance;
- Atlas seed `183716` reaches the declared production spin-up gate;
- create `docs/validation/worldgen_corrective_c4.md` and stop before transport tuning.

## C5 — Precipitation mechanisms and monsoon retuning

**Priority:** P1  
**Dependency:** C4 and C3

Current final precipitation is approximately 74% orographic while large-scale precipitation is approximately 0.01%. This reproduces narrow wet filaments and dry continental interiors even after other changes.

### Required changes

1. Use metric, appropriately smoothed ascent rather than raw per-cell height difference for orographic forcing.
2. Make supersaturation/convergence produce an actual large-scale/stratiform precipitation term rather than silently removing capacity excess.
3. Treat lee effects as reduced condensation efficiency or altered capacity, not an unreported water sink.
4. Make monsoon activation regional or landmass/coastal-sector based; hemispheric averaging may cancel legitimate regional monsoons.
5. Validate monsoon response through seasonal onshore wind and precipitation ratios, not only mean anomaly magnitude.

### Post-correctness calibration grid

Do not interpret these as approved defaults:

| Parameter | Sweep |
|---|---|
| `advect_wind_scale` | 0.2, 0.4, 0.8 |
| `orographic_frac` after revised definition | 0.25, 0.40, 0.55 |
| `large_scale_frac` | 0.25, 0.45, 0.65 |
| `convective_scale` | 1.5, 2.0 |
| `itcz_convective_scale` | 0.8, 1.2 |
| `monsoon_strength` | 0.35, 0.55, 0.75 |

Select defaults from the fixed seed suite and physical diagnostics. Do not target a particular biome percentage or make all interiors wet. Preserve meaningful rain shadows, subtropical dry belts, and seasonal contrasts.

### Acceptance

- no single precipitation mechanism dominates only because another mechanism is numerically inactive;
- continental interiors receive plausible transported/recycled moisture without erasing orographic shadows;
- monsoon sectors show a seasonal sign/strength response while unaffected trades remain coherent;
- the moisture budget remains closed for every sweep candidate;
- create `docs/validation/worldgen_corrective_c5.md` and stop.

## C6 — BiomeV2 correctness and canonical integration

**Priority:** P0 for units; P1 for integration  
**Dependencies:** C0; final calibration after C2/C5

### Required changes

1. Correct the precipitation unit as specified in C0.
2. Stop using a single December soil store from a one-year zero initialization as the climatological wetness input.
3. Supply monthly periodic soil store, growing-season mean soil moisture, or another explicitly named climatological statistic.
4. Keep thermal and moisture axes separately inspectable before deriving the seven-class display regime.
5. Make ecology acceptance include BiomeV2 validity, coverage, finite values, exact legend coverage, and water-mask consistency.
6. Add the following to `RasterStore`:

~~~text
ecology/biome_v2_class
ecology/frost_months
ecology/growing_season_months
ecology/water_deficit_mm
ecology/soil_state
ecology/thermal_regime_id
ecology/moisture_regime_id
~~~

7. Aggregate to hexes:

~~~text
biome_v2_dominant
frost_months_mean
growing_season_months_mean
water_deficit_mm_mean
soil_state_dominant
~~~

8. Extend queries and round-trip save/load tests.

### Acceptance

- a balanced monthly P/PET fixture gives zero deficit;
- rotating monthly labels rotates seasonal fields without changing annual totals;
- wetland classification requires climatological water availability and excludes a merely wet final month;
- lake overrides use actual liquid fraction/state rather than basin envelopes;
- Holdridge remains available and unchanged as a separate annual view;
- create `docs/validation/worldgen_corrective_c6.md` and stop.

## C7 — Landform scales, classes, masks, and objects

**Priority:** P1  
**Dependencies:** C3; calibration follows C7 correctness.

### Metric fields and masking

1. Replace the forced minimum radius of two analysis cells with a minimum of one cell.
2. Record requested and effective E–W/N–S radius in kilometres for every scale and profile.
3. Mark Quick as unable to distinguish scales that collapse to the same effective window.
4. Normalize coastal roughness/slope statistics by valid land fraction.
5. After upsampling, reapply the full-resolution ocean mask so no land is labelled ocean and no ocean is labelled land.
6. Express minimum object areas in km² and report their representable effective minimum.

### Local-form classification

Implement all declared classes or remove undeclared placeholders. At minimum:

- `summit` and `ridge` require positive topographic position/convexity with suitable slope context;
- `shoulder` represents the convex transition below a summit/ridge;
- `slope` is the ordinary inclined middle segment;
- `footslope` represents a concave lower transition;
- `valley` and `depression` use negative topographic position with distinct drainage/closure semantics;
- `escarpment` requires a narrow high-gradient/curvature transition and, for plateau rims, adjacency to a plateau interior.

Do not let a broad relief threshold alone classify most of a continent as escarpment. Use one internally consistent mountain threshold; remove hidden hard-coded `0.55` rules that conflict with the configured `0.60` threshold.

### Object geometry

- retain PCA only for orientation and elongation;
- derive range ridges from a skeleton or geodesic longest path constrained to the range mask;
- prune tiny branches and consecutive duplicate points;
- ensure every ridge sample remains inside its range mask;
- unwrap E–W coordinates during geometry calculations and split only presentation geometry at the seam;
- generate plateau interior and rim geometry separately;
- preserve deterministic IDs for the same DEM/config/algorithm version.

### Honest acceptance

Landform acceptance must include:

- requested/effective radius diagnostics;
- land/ocean mask consistency;
- non-zero and bounded mountain/plateau fractions;
- local-form coverage and a dominance alarm for escarpment;
- ridge-in-mask and duplicate-point checks;
- seam object tests;
- canonical store/query round-trip;
- fixed-seed distribution and runtime.

Broad alarms may start at mountain terrain 10–30%, plateau context 1–8%, and escarpment below 15–20% of land. These are failure alarms, not targets to fit one seed.

Keep `mountain_score_threshold = 0.60` as the initial comparison point. Calibrate only after C3 and C7 pass.

### Acceptance

- the synthetic cone, plateau, mountain-on-plateau, rolling upland, two-range divide, canyon, seam range, and N–S mirror fixtures pass;
- ridges lie inside their objects without duplicate consecutive vertices;
- local classes are represented where their fixtures require them;
- create `docs/validation/worldgen_corrective_c7.md` and stop.

## C8 — Canonical WorldSpatialModel, hex, query, and export integration

**Priority:** P1  
**Dependencies:** C1, C2, C6, C7

### World model

Extend `build_world_spatial_model()` and `_fill_rasters()` so canonical products include BiomeV2 and LandformAnalysis. Extend `VectorStore` with:

~~~text
mountain_ranges
mountain_ridges
plateaus
plateau_rims
~~~

`rebuild_hex_analysis_cache()` must preserve/reload and pass landforms rather than silently removing their aggregates.

### Hex contract

Export at least:

~~~text
# location / coverage
center_x, center_y, latitude_deg, cell_count
land_fraction, ocean_fraction

# terrain
elevation_mean_m, elevation_min_m, elevation_max_m, elevation_std_m
local_relief_mean_m, slope_mean_deg

# climate / ecology
temperature_annual_c, precipitation_annual_mm_or_declared_proxy
biome_v2_dominant, holdridge_dominant
frost_months_mean, growing_season_months_mean
water_deficit_mm_mean, soil_state_dominant

# water
permanent_water_fraction, seasonal_water_fraction
perennial_river_fraction, seasonal_river_fraction, wadi_fraction
mean_effective_discharge, basin_ids, river_ids, lake_ids

# landforms
context_dominant, local_form_dominant
mountain_score_mean, plateau_score_mean
mountain_terrain_fraction, mountain_range_fraction
plateau_context_fraction, plateau_object_fraction
terrain_barrier_strength or terrain_mobility_cost
mountain_range_ids, plateau_ids
~~~

Use `null`/no-data explicitly for ocean-only or uncovered hexes. Do not substitute zero where zero is a meaningful physical value.

### Queries

`SpatialQueries.hex_environment()` and object queries must return the same names and units as the exported contract. Add lookup by mountain-range ID, plateau ID, river ID, lake ID, and basin ID.

### Acceptance

- save/load/rebuild preserves all new rasters, vectors, hex fields, and IDs;
- exported field names match query field names;
- no field called a fraction is a score mean;
- canonical and atlas legends cover every emitted categorical ID;
- create `docs/validation/worldgen_corrective_c8.md` and stop.

## C9 — Godot BiomeV2, landform layers, legends, and inspector

**Priority:** P1  
**Dependency:** C8

Implement the display and inspector contracts in sections 7 and 8 as one isolated product-integration package.

### Required delivery

- backward-compatible `atlas_display_v2` mode descriptors;
- `biome_v2` and `landforms` primary modes;
- stable Python-owned legends and palettes;
- a dedicated `LandformLayerRenderer.gd`;
- a legend controller using the existing `Main.tscn` panel, with a new `LegendPanel.gd` only if needed;
- landform-object visibility controls;
- lake, river, range, and plateau picking;
- meaningful hex/environment inspection even when hex outlines are hidden;
- mode-aware and month-aware inspector formatting;
- safe handling of missing optional files and explicit warnings for missing required schema fields.

### Acceptance

- a generated Atlas world loads without Godot parse warnings;
- all primary modes and legends render at Fit and 4× zoom;
- categorical IDs, PNG colours, and legend entries agree exactly;
- object selection matches visual draw order;
- old `atlas_display_v1` fixtures still load through the compatibility path;
- no classification threshold or palette duplication exists in Godot;
- create `docs/validation/worldgen_corrective_c9.md` with screenshots and stop.

## C10 — Multi-seed calibration, Full memory gate, and release decision

**Priority:** P1  
**Dependencies:** C0–C9, including C3T state integrity

Only after every correctness and integration gate passes:

1. run the declared Quick and Atlas regression suite;
2. run at least one Full seed with peak-RSS measurement;
3. perform the bounded parameter grids from C3 and C5;
4. calibrate landform thresholds on distributions, not one seed;
5. compare absolute-scale and atlas-style images;
6. choose defaults with before/after metrics and documented trade-offs;
7. update canonical plans and validation status only after the user reviews the report.

Treat realism bands as multi-seed warnings during calibration, not hard rejection of every unusual world. Initial earth-like warnings may include:

- no precipitation mechanism above 75% in the median seed;
- approximate orographic share 15–55%, large-scale 10–45%, convection plus ITCZ 20–65%;
- mean land precipitation 500–1200 mm/year and median 350–900 mm/year after unit calibration;
- less than 45% of land below 250 mm/year;
- wet tropical land at least 15% wetter than subtropical land where both samples are sufficiently represented;
- windward slopes at least 20% wetter than comparable leeward slopes;
- inland seasonal temperature amplitude greater than comparable coastal amplitude;
- active monsoon regions changing wet-season precipitation by at least 10% relative to a no-monsoon control without material changes outside their declared reach.

These ranges require seed-suite review before becoming stable warnings and must never be fitted by violating conservation or topology.

### Acceptance

- new defaults are reproducible and persisted in YAML/Godot/manifests;
- major basins, climate gradients, rivers, ranges, and plateaus retain comparable physical meaning between Atlas and Full;
- performance and memory gates pass on the target machine;
- known limitations and deferred work remain explicit;
- create `docs/validation/worldgen_corrective_c10.md` and stop for the release decision.

---

# 7. Godot display specification

## 7.1 Display architecture

Godot reads preclassified rasters, legends, and object vectors. It does not reproduce Python thresholds.

Upgrade `atlas_meta.json` to a backward-compatible `atlas_display_v2` descriptor. Prefer structured mode descriptors:

~~~json
{
  "id": "biome_v2",
  "label": "Biome V2",
  "icon": "B2",
  "kind": "categorical",
  "file": "biome_v2.png",
  "legend": "biome_v2_legend.json",
  "monthly": false
}
~~~

Godot must still read the current legacy string list. New worlds should write only structured descriptors after the schema migration. `MapModeController` should expose the intersection of modes supported by the application and modes declared by the loaded atlas. Hide unavailable buttons for older worlds rather than leaving broken controls visible.

`RasterLayerRenderer` should resolve static file paths from the descriptor/`atlas_meta.files` first and use hard-coded paths only as a legacy fallback. Commit `_mode` and emit `mode_changed` only after the requested texture loads successfully; a missing file must not leave the previous texture under a newly active button.

Recommended main toolbar modes:

~~~text
El  elevation
Ba  bathymetry
Te  temperature
Pr  precipitation
Ho  Holdridge
B2  Biome V2
Lf  Landforms
~~~

Seven compact buttons remain readable. Diagnostic-only modes should not all occupy the main toolbar.

Reuse the existing legend container in `Main.tscn`. Add a small reusable `LegendPanel.gd` only if the existing node has no equivalent controller. The result must:

- load the legend referenced by the active mode descriptor;
- show a colour swatch and human-readable label;
- remain hidden when no legend exists;
- be collapsible;
- show only the relevant entries for the active mode;
- use the same Python-exported colours as the PNG;
- show line symbols for mountain range, ridge, plateau rim, river state, and seasonal water when those overlays are active.

Categorical rasters must use nearest-neighbour sampling with zero mode blur. Holdridge, BiomeV2, and Landforms must never be linearly interpolated into colours that imply nonexistent classes. The coastline/land-mask edge may remain smoothly filtered independently.

## 7.2 BiomeV2 main mode

Export:

~~~text
atlas_display/biome_v2.png
atlas_display/biome_v2_legend.json
~~~

Use one stable, subdued palette compatible with the existing blue oceans and beige/earth atlas style:

| Class | Suggested colour | Meaning |
|---|---|---|
| ocean | `#17365D` | Deep atlas blue. |
| year-round frost | `#E8F1F2` | Near-white blue. Do not call this permanent ice until a snow/ice mass balance exists. |
| frost seasonal | `#8FA9B3` | Muted blue-grey. |
| growing moist | `#5E8B57` | Muted vegetation green. |
| growing deficit | `#AAA05A` | Olive/ochre transition. |
| arid | `#D1A466` | Sand/orange. |
| wetland potential | `#397A72` | Dark teal-green. This remains a potential until persistent saturation/floodplain semantics are validated. |

The legend title should be **Seasonal ecological regime (BiomeV2)** so the user is not misled into treating the seven classes as a complete biome taxonomy.

Minimum legend schema:

~~~json
{
  "schema": "biome_v2_legend_v1",
  "title": "Seasonal ecological regime (BiomeV2)",
  "classes": {
    "0": {"key": "ocean", "label": "Ocean", "color": "#17365D"},
    "1": {"key": "year_round_frost", "label": "Year-round frost", "color": "#E8F1F2"},
    "2": {"key": "frost_seasonal", "label": "Seasonal frost", "color": "#8FA9B3"},
    "3": {"key": "growing_moist", "label": "Growing — moist", "color": "#5E8B57"},
    "4": {"key": "growing_deficit", "label": "Growing — moisture deficit", "color": "#AAA05A"},
    "5": {"key": "arid", "label": "Arid", "color": "#D1A466"},
    "6": {"key": "wetland_potential", "label": "Wetland potential", "color": "#397A72"}
  }
}
~~~

Every emitted class ID must occur in this legend, and every legend colour must occur only for its declared class. The ocean entry may be visually replaced by the ordinary bathymetry background in the land-composite shader; document that behaviour in the legend/UI.

The mode is annual and does not respond to the month selector. Its inspector section still exposes frost months, growing-season months, deficit, and soil state.

Disable the month control visually for static modes while preserving the previously selected month. Returning to temperature or precipitation restores that month.

Optional developer diagnostics may export `water_deficit.png`, `frost_months.png`, and `growing_season_months.png`, but they should live behind a Diagnostics submenu or manifest flag rather than the primary toolbar.

## 7.3 Landforms main mode

The main `landforms` mode is a simple derived presentation raster. It must not replace the independent canonical layers.

Derive a `display_landform_id` with documented presentation-only priority, for example:

~~~text
ocean
plain
upland_or_hills
mountain
plateau
basin
~~~

A mountain on a plateau may display as mountain while the inspector still reports plateau context. This is why `display_landform_id` must be marked derived.

Recommended presentation-only priority:

1. ocean always wins;
2. accepted mountain-range object wins over underlying plateau/upland context;
3. accepted plateau object/context wins over plain/upland;
4. basin wins over ordinary plain/upland but not an accepted range;
5. remaining upland/hill context;
6. plain.

Report overlap between accepted range and plateau objects. Do not destroy either canonical classification to make the display class exclusive.

Export:

~~~text
atlas_display/landforms.png
atlas_display/landform_legend.json
atlas_display/mountain_ranges.geojson
atlas_display/mountain_ridges.geojson
atlas_display/plateaus.geojson
atlas_display/plateau_rims.geojson
~~~

Suggested raster palette:

| Display class | Suggested colour |
|---|---|
| ocean | `#17365D` |
| plain | `#D8D0AA` |
| upland / hills | `#A99063` |
| mountain | `#736357` |
| plateau | `#B87855` |
| basin | `#8E9E78` |

`landform_legend.json` should contain `display_classes`, `broad_context`, `local_form`, and `provenance` sections. Extend the Python `legend_payload()` owner rather than duplicating class names in the exporter or Godot.

Suggested object styles, all zoom-invariant in screen pixels like existing rivers/coasts:

- mountain-range boundary: dark muted brown, 1.1–1.4 px;
- ridge centreline: darker brown-grey, 0.8–1.1 px;
- plateau interior: optional transparent terracotta fill, alpha at most 0.12;
- plateau rim: burnt-orange line, 1.1–1.4 px;
- selected object: existing gold accent, approximately `#F2B847`, 2 px.

Create a separate `LandformLayerRenderer.gd` rather than continuing to enlarge the hydro-focused `VectorLayerRenderer.gd`. Draw order should be:

~~~text
base raster
land composite
landform polygon tint
range/plateau outlines and ridges
rivers
lakes
flow diagnostic
hex grid
selection highlight
~~~

Provide one **Landform objects** toggle in the normal UI. An advanced subpanel may independently toggle range outlines, ridges, plateau interiors, and rims. When `landforms` mode is selected, the combined landform object overlay may turn on by default; preserve the user's explicit toggle thereafter.

The first readable delivery may show only the derived raster plus seam-safe ridge centre lines. Activate mountain-range polygons, plateau fills, and rims only after C7 proves that their polygons are seam-safe, track their masks, and do not create oversized bounding boxes. Exporting a canonical object is not sufficient reason to draw unreliable geometry.

Hex, coast, river, lake, flow, and landform checkboxes remain independent user choices. Changing map mode must not reset them. Ridge geometry may be effectively visible only in `landforms` mode while retaining the stored checkbox state.

Optional developer modes may include `landform_context`, `landform_local`, `mountain_score`, and `plateau_score`. They are validation tools and should not crowd the main toolbar.

## 7.4 Vector selection priority

Picking order should match visible draw order:

1. actual liquid lake polygon;
2. visible river reach;
3. selected/visible plateau or range object;
4. analytical hex/environment fallback.

Do not return a river hidden below actual lake water. Basin envelopes are selectable only when an explicit diagnostic basin layer is active.

Use one generic `inspect_feature(kind, info)` signal internally. Keep compatibility wrappers for existing `inspect_river`/`inspect_hex` until callers migrate.

## 7.5 Optional hydrology diagnostics

Do not add a separate primary-toolbar button for every diagnostic. Provide one **Hydrology diagnostics** selector or developer submenu that can expose, when exported:

~~~text
basin envelope IDs
mean and maximum lake-water fraction
lake wet months / hydroperiod
physical channel state
log catchment area
log mean effective discharge
transmission-loss fraction
routing-conditioning elevation delta
hydrology water-balance residual
hydrology–moisture iteration delta
~~~

Recommended presentation rules:

- basin envelopes use outlines or categorical IDs and are never the same blue as liquid water;
- permanent water is atlas blue, seasonal water is lighter/desaturated blue, and playa is a pale neutral/salt colour;
- perennial channels are solid, seasonal channels lighter/thinner, and wadis optional/dashed or muted;
- continuous diagnostics use stable absolute legends, never per-seed min–max stretch alone.

These layers are primarily for validation and inspector context. They may be omitted from ordinary export when `diagnostic_export = false`.

## 7.6 Optional climate diagnostics

Keep the main toolbar limited to the seven primary modes. A single Diagnostics selector may offer:

- annual precipitation in mm/year;
- annual temperature range;
- dominant precipitation mechanism;
- annual mean humidity/RH proxy;
- monsoon influence, only when available.

Use stable absolute legends across seeds. Suggested boundaries include annual precipitation at `0, 100, 250, 500, 1000, 2000, 4000, 8000 mm`, annual temperature range `0–50 C`, and RH proxy `0–120%` with overflow marked. The dominant-mechanism map is categorical and must use the same component accounting as the moisture budget.

---

# 8. Inspector expansion

## 8.1 Interaction rule

The current point inspector returns only UV coordinates unless the hex overlay is visible. Change this behaviour:

- clicking a visible vector object selects that object;
- otherwise, always resolve the analytical hex under the cursor, even when hex outlines are hidden;
- the hex overlay remains a visual toggle, not a prerequisite for meaningful inspection;
- the selected month and active map mode are passed to the inspector;
- missing fields are hidden or shown as `No data`, never fabricated as zero.

Keep the existing `RichTextLabel` implementation initially. Reformat it into stable sections rather than dumping alphabetically sorted raw keys.

## 8.2 Hex/environment inspector layout

Render sections only when data exists.

### Location

- hex ID;
- latitude and normalized longitude or user-facing longitude degrees;
- cell count and coverage state;
- land, ocean, permanent-water, and seasonal-water fraction.

### Terrain

- mean/min/max elevation in metres;
- elevation standard deviation or local relief in metres;
- mean slope in degrees;
- broad landform context;
- dominant local form;
- mountain terrain/range fractions and mean score;
- plateau context/object fractions and mean score;
- terrain barrier/mobility proxy.

### Climate

- selected-month temperature in C;
- annual mean temperature in C;
- annual temperature range in C;
- selected-month precipitation in mm/month or explicitly labelled proxy;
- annual precipitation in mm/year or explicitly labelled proxy;
- wettest and driest month;
- selected-month humidity explicitly labelled `RH proxy` until it is a physical relative humidity;
- frost months;
- growing-season months;
- water deficit in mm/year;
- soil-state label.

### Ecology

- BiomeV2 label as the primary seasonal regime;
- Holdridge label as the annual diagnostic;
- do not show only numeric IDs when a legend label exists.

### Hydrology

- basin IDs;
- permanent and seasonal lake fraction;
- perennial, seasonal, and wadi channel fraction;
- mean effective discharge where representable;
- river IDs and lake IDs.

### Landform objects

- intersecting mountain-range IDs;
- intersecting plateau IDs;
- object names may be added later, but IDs must remain stable within the declared version scope.

### Optional solver diagnostics

Keep these collapsed by default:

- atmospheric `q` proxy and land-store fill;
- annual local shares of large-scale, orographic, convective, and ITCZ precipitation;
- continentality;
- metric orographic lift;
- wind speed and direction;
- local monsoon anomaly and active region ID;
- water-source/coupling-iteration provenance.

## 8.3 Object inspector layouts

### River

- ID and state (`perennial`, `seasonal`, `wadi`);
- Strahler order;
- catchment area in km²;
- mean/min/max effective discharge in declared units;
- selected-month discharge and a compact 12-month list;
- bed-loss fraction or amount;
- basin ID;
- upstream/downstream segment IDs;
- connected source/destination lake IDs.

### Lake

- ID and basin ID;
- outlet type, hydroperiod, and ice regime;
- current selected-month liquid area, mean area, and basin envelope area in km²;
- current/mean water-surface elevation and spill elevation;
- months wet and months ice-covered;
- mean effective inflow, selected-month inflow/outflow/evaporation;
- inlet river IDs and outlet river ID;
- convergence warning when storage spin-up failed.

### Mountain range

- ID;
- area, length, width, orientation, and elongation;
- mean/max/base elevation;
- local/regional relief;
- provenance label and confidence;
- seam-crossing flag;
- peak/pass counts when later available.

### Plateau

- ID;
- interior area and rim length;
- mean surface and surrounding base elevation;
- internal relief and mean slope;
- drainage class;
- provenance label and confidence;
- seam-crossing flag.

## 8.4 Formatting and usability

- use human labels and units, not raw snake_case, in the default view;
- format fractions as percentages and scores to two decimals;
- format metres, km², C, mm, and discharge consistently;
- highlight the field relevant to the active mode at the top of its section;
- provide a compact **Technical IDs/details** disclosure only if necessary;
- show schema or convergence warnings in amber, not as ordinary data;
- do not translate category names independently in Godot; read labels from legend files.

Do not enlarge `hex_environment.json` with many verbose monthly float lists. Use a compact sidecar:

~~~text
inspection_grid.json   # schema, field descriptors, units, dtype, scale, no-data, byte offsets
inspection_grid.bin    # field-major → month-major → hex, little-endian int16/uint16 or float32
~~~

At minimum include selected-month temperature, precipitation, and humidity/RH proxy. Quantized 16-bit storage for three 12-month fields over 32,768 hexes is only about 2.25 MiB. Godot may seek directly to a field/month/hex value rather than loading a large JSON cube. Add exact encode/decode and no-data round-trip tests.

The ordinary JSON retains annual summaries, class IDs, fractions, and sparse object-reference lists.

## 8.5 Compact production status

Generate `climate_summary.json` in Python as the only owner of the status shown by Godot. It should include at least:

~~~text
temperature_integrity_ok
moisture_spinup_ok
moisture_budget_ok
hydrology_coupling_ok
biome_v2_ok
landforms_ok
overall_acceptance_ok
warnings[]
~~~

Display a compact first inspector row such as:

~~~text
Temperature ✓   Spin-up ⚠   Water budget ✕   Hydro feedback ✓
~~~

Detailed metrics remain in the relevant section or validation files. Godot must not recompute acceptance from rounded display data.

---

# 9. File-level implementation checklist

The agent must confirm current paths before editing. Expected areas include:

## Python/worldsim

- `worldsim/src/worldsim/physical/hydrology/basins_storage.py`
- `worldsim/src/worldsim/physical/hydrology/lakes_meta.py`
- `worldsim/src/worldsim/physical/hydrology/pipeline.py`
- `worldsim/src/worldsim/physical/hydrology/rivers.py`
- `worldsim/src/worldsim/physical/hydrology/transmission.py`
- `worldsim/src/worldsim/physical/vectorize/lakes.py`
- `worldsim/src/worldsim/physical/vectorize/rivers.py`
- `worldsim/src/worldsim/physical/vectorize/pipeline.py`
- `worldsim/src/worldsim/physical/erosion/pass_one.py`
- `worldsim/src/worldsim/physical/erosion/fluvial.py`
- `worldsim/src/worldsim/physical/final/pipeline.py`
- `worldsim/src/worldsim/physical/moisture/transport.py`
- `worldsim/src/worldsim/physical/moisture/pipeline.py`
- `worldsim/src/worldsim/physical/atmosphere/circulation.py`
- `worldsim/src/worldsim/physical/ecology/biome_v2.py`
- `worldsim/src/worldsim/physical/ecology/pipeline.py`
- `worldsim/src/worldsim/physical/landforms/metrics.py`
- `worldsim/src/worldsim/physical/landforms/classify.py`
- `worldsim/src/worldsim/physical/landforms/objects.py`
- `worldsim/src/worldsim/physical/landforms/pipeline.py`
- `worldsim/src/worldsim/spatial/model.py`
- `worldsim/src/worldsim/spatial/vector_store/`
- `worldsim/src/worldsim/spatial/hex_grid/pipeline.py`
- `worldsim/src/worldsim/spatial/queries/`
- `worldsim/src/worldsim/export/atlas_display.py`
- `worldsim/src/worldsim/config.py`
- packaged default YAML files and manifest schemas.

## Godot

- `godot/atlas/MapModeController.gd`
- `godot/atlas/RasterLayerRenderer.gd`
- `godot/atlas/LandLayerRenderer.gd`
- `godot/atlas/VectorLayerRenderer.gd`
- new `godot/atlas/LandformLayerRenderer.gd`
- new `godot/atlas/LegendPanel.gd`
- `godot/atlas/HexOverlayRenderer.gd`
- `godot/atlas/InspectorPanel.gd`
- `godot/atlas/WorldAtlas.gd`
- `godot/scenes/Main.gd`
- `godot/scenes/Main.tscn`
- `godot/simulation_bridge/SimulationRunner.gd` where configuration serialization is owned.

## Required new or extended atlas files

~~~text
atlas_meta.json                       # atlas_display_v2 descriptors
biome_v2.png
biome_v2_legend.json
landforms.png
landform_legend.json
mountain_ranges.geojson
mountain_ridges.geojson
plateaus.geojson
plateau_rims.geojson
hex_environment.json                 # extended canonical names
inspection_grid.json                 # monthly inspector schema and offsets
inspection_grid.bin                  # compact month/hex values
climate_summary.json                 # Python-owned acceptance/status summary
lakes.geojson                        # actual mean liquid footprint + state axes
rivers.geojson                       # river state/catchment/effective Q
~~~

---

# 10. Configuration exposure

Parameters that materially affect output must be parsed from YAML, persisted in the effective manifest, and exposed in Godot Advanced settings with units and safe ranges.

Avoid maintaining a second complete default configuration in `Main.gd`. The preferred contract is:

1. Python owns the canonical packaged defaults and validation;
2. Godot writes only user-changed values to a small `planet_overrides.json`;
3. the worker deep-merges overrides into the packaged defaults and runs the ordinary validator;
4. generation freezes `effective_config.json`, its schema version, and checksum;
5. Godot displays the effective values when loading a generated world.

If the override migration is too large for the first hotfix, add parity tests that compare every Godot-written key against the canonical defaults and schedule the override architecture before further configuration growth.

Divide the Advanced popup into collapsible groups rather than extending one long list:

~~~text
Terrain and erosion
Temperature and ocean coupling
Moisture and precipitation
Monsoon
Hydrology and lakes
BiomeV2 and landforms
Solver / expert
Display-only LOD
~~~

Keep numerical safety parameters and display-only thresholds out of the ordinary physical-controls group.

## Erosion

- first-pass thermal coefficient;
- first-pass fluvial coefficient;
- final stream-power coefficient;
- final fluvial iterations;
- macro blend and maximum step if retained as user-tunable;
- micro-fill maximum depth in metres.

## Moisture

- conservative transport scale;
- `advect_max_substeps` and CFL limit as expert numerical settings, with legacy `advect_steps` read-only migration;
- physical monthly diffusion/mixing;
- spin-up maximum years and robust tolerances;
- orographic, large-scale, convective, ITCZ, and monsoon strengths;
- lake and river evaporation rates, clearly labelled as fractional-area rates.

## Hydrology and lakes

- soil capacity and quickflow fraction;
- snow/melt parameters already affecting runoff;
- physical minimum catchment area in km²;
- fallback minimum accumulation cells as a representability control;
- channel state/Q thresholds;
- bed-loss reference rate and reach length;
- basin numerical-fill threshold;
- lake storage spin-up years/tolerance;
- evaporation/seepage terms where supported;
- display LOD thresholds in a separate UI group.

## Landforms

- enable/disable analysis;
- fine/meso/macro radius in km;
- mountain and plateau score thresholds;
- minimum range/plateau area in km²;
- optional diagnostic export toggle.

The Godot control for first-pass `fluvial_k` must not be labelled or positioned as though it controlled final stream-power incision. Group controls by physical stage and add tooltips explaining whether a setting changes physics, classification, or display only.

New manifests must use physical-unit names. Legacy cell-based names may be read through a versioned compatibility layer but must not be written again.

---

# 11. Validation and release gates

## 11.1 Required seed/profile suite

For every correctness package:

- tiny deterministic synthetic fixtures on every commit;
- Quick seeds `1`, `42`, and `100` as smoke tests;
- Atlas seeds `42` and `183716` as mandatory integration tests;
- at least one Full seed before changing defaults;
- 25 Quick / 10 Atlas-or-final-quality seeds before distribution calibration.

Do not choose defaults from seed `183716`; it is a regression anchor, not a target world.

## 11.2 Visual artefacts

Save both absolute and display maps:

- elevation with fixed metre scale plus the ordinary atlas style;
- annual and representative monthly precipitation on a fixed scale;
- lake basin envelope versus actual liquid footprint;
- permanent/seasonal water fraction;
- physical versus displayed river network and river state;
- BiomeV2 with stable legend;
- landform display class, broad context, local form, mountain score, plateau score, and object overlays;
- before/after screenshots at identical viewport, zoom, month, and layer settings.

## 11.3 Production acceptance summary

The final validation note must report at least:

- moisture mass residual and spin-up metrics;
- contributions of orographic, large-scale, convective, and ITCZ precipitation;
- lake count by outlet/hydroperiod/ice regime;
- basin-envelope area versus actual liquid area;
- river cells and length by state;
- monthly/annual effective-Q consistency;
- erosion delta distribution and roughness;
- BiomeV2 class distribution and water-balance diagnostics;
- landform class/object distributions and geometry failures;
- canonical save/load/query/export round-trip;
- Godot mode, legend, and inspector integration tests;
- runtime, peak RSS, and output size.

An overall `acceptance_ok` must be the conjunction of relevant component gates. A component may expose warnings, but a known failed production invariant may not be omitted from the conjunction to preserve a green status.

For monthly/annual discharge, prefer a volume identity over comparing two independently nonlinear shortcuts:

~~~text
sum(monthly_effective_q_m3s × seconds_in_month)
= annual_routed_effective_volume_m3
~~~

Broad earth-like sanity alarms may initially include:

- liquid inland water outside approximately 0.2–5% of land: warning, not automatic tuning target;
- liquid inland water above 8% of land: hard catastrophe gate unless the configuration explicitly requests a water-rich world;
- displayed river coverage outside approximately 0.5–5% of land: warning;
- physical channel eligibility equal to 100% of land: hard failure;
- rendered water area above 110% of the A–V–h-derived area: hard failure.

These alarms do not replace mass balance, topology, or object-level geometry tests.

## 11.4 UI acceptance

- all seven primary map buttons load from a generated Atlas world;
- categorical colours exactly match the exported legends;
- BiomeV2 and landforms remain readable at Fit and at 4× zoom;
- the month selector affects only monthly modes and monthly inspector values;
- clicking without visible hex outlines still returns meaningful environmental information;
- clicking each supported vector object returns the appropriate structured inspector;
- missing optional diagnostic layers degrade gracefully;
- a missing required schema field produces a warning and safe omission, not fabricated liquid water;
- old `atlas_display_v1` worlds still load through compatibility code;
- one headless Godot smoke test loads the generated atlas without parse warnings.

---

# 12. Performance and memory rules

Atlas performance is currently acceptable and must remain so. Correctness retuning of coefficients should not materially change asymptotic cost.

Required practices:

- build lake A–V–h curves only for depression cells and reuse them across months;
- retain two-dimensional state and annual summaries where full monthly terrain cubes are unnecessary;
- stream hydrology months for Full rather than retaining many `12 × 4096 × 2048` float64 arrays;
- use float32 for large stored climate/hydrology fields after precision tests;
- use uint8 for classes and int32 for IDs;
- cache the cylindrical topology and use compact arrays/CSR rather than Python list-of-lists for Full;
- process landform scales sequentially and reuse buffers;
- do not move base landform analysis to the 4096 × 2048 terrain grid;
- load optional Godot diagnostic rasters only when their mode is selected;
- keep legends and object metadata in small JSON/GeoJSON files;
- measure Atlas and Full load time after extending `hex_environment`.

Performance warning thresholds:

- more than 15% median total runtime increase;
- more than 128 MiB additional peak RSS in Atlas;
- excessive Godot load latency from inspector JSON;
- Full peak memory above the target machine's safe working set.

Crossing a warning threshold requires an optimization attempt and a written result. It is not permission to silently weaken correctness.

---

# 13. Temporary baseline before the full correction

If a clean comparison world is required before C1–C5 are complete:

- keep `folding_ratio`, sea level, hypsometry, base temperature, lapse rate, and SST parameters unchanged;
- ensure playa and frozen basin envelopes are hidden from liquid-water rendering;
- set lake and river evaporation to zero or a clearly marked diagnostic minimum so inflated masks do not reshape precipitation and ecology;
- do not increase `advect_wind_scale` until conservative transport passes;
- keep monsoon at the present value or zero for a clean atmosphere baseline; its present effect is small;
- do not repair lake count by raising only minimum lake depth;
- do not lower river thresholds merely to compensate for hidden reaches under false lake polygons.

These settings are temporary diagnostic isolation, not approved final defaults.

---

# 14. Global Definition of Done

This corrective programme is complete only when:

- Godot never treats a missing lake state as liquid water;
- basin envelopes and actual water surfaces are separate products;
- monthly storage determines lake area, level, spill, evaporation, ecology, and rendering;
- river thresholds and losses have physical, resolution-aware meanings;
- final moisture and hydrology are converged or explicitly bounded-consistent;
- metric erosion has a validated non-trivial effect without changing tectonic defaults;
- conservative transport closes the moisture budget and passes full 2-D CFL tests;
- large-scale and orographic precipitation are both operational and diagnostically separated;
- BiomeV2 uses correct units and climatological soil state;
- BiomeV2 and landforms survive canonical save/load, hex aggregation, queries, and atlas export;
- landform scales, local classes, masks, objects, and ridges pass synthetic and fixed-seed gates;
- the main Godot UI contains readable BiomeV2 and Landforms modes with stable legends;
- the inspector presents meaningful climate, ecology, water, and landform data without requiring visible hex outlines;
- every visible range, plateau, river, and lake can expose its canonical metadata;
- old atlas worlds remain loadable through explicit compatibility handling;
- Atlas performance remains acceptable and Full hydrology stays within the target machine's memory budget;
- every package has a validation note and no known production invariant is hidden behind a positive aggregate acceptance flag.

At that point the generator will have a coherent causal water system, a usable seasonal ecology product, and a readable terrain-semantics layer suitable both for later history and for future graphical mountain/plateau treatment.
