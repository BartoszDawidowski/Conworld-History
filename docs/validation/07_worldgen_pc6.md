# Worldgen production closure PC6 — canonical products + Godot inspector

**Date:** 2026-08-19  
**Status:** ✅ **Delivered** (effective config, tier-mask persistence, inspector status row)  
**Authority:** [`docs/00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md`](../00_WORLDGEN_PRODUCTION_CLOSURE_AND_CRYOSPHERE_ADDENDUM.md) §10 + §11 PC6  
**Depends on:** [PC0](01_worldgen_pc0.md) … [PC5](06_worldgen_pc5.md)

---

## Delivered

| Item | Location |
|---|---|
| Effective config resolve/write | `effective_config.py` |
| Versioned product contracts | `spatial/product_contracts.py` |
| Save/load + re-export parity probes | `validation/production_closure/product_parity.py` |
| Tier masks in RasterStore | `spatial/model.py` `_fill_rasters` |
| Pipeline `effective_config.json` | `pipeline.py` |
| Inspector §10.3 status row | `spatial/canonical_acceptance.py`, `export/atlas_display.py`, `godot/atlas/InspectorPanel.gd` |
| Diagnostic hydrology PNGs (minimal) | `export/atlas_display.py` |
| PC6 synthetic tests | `tests/test_worldgen_pc6.py` |

---

## Contract change

**Before:** `effective_config.json` existed only in PR baseline capture; PC2 tier masks were not persisted on `WorldSpatialModel`; Godot inspector showed four climate gates only.

**After (PC6):**

1. Production pipeline writes `effective_config.json` (+ checksum) at run root and under `world/`;
2. `hydrology/channel_mask`, `hydrology/geomorphic_channel_mask`, `hydrology/display_river_mask` round-trip through save/load;
3. `climate_summary.json` publishes `inspector_status` for §10.3 (`Moisture`, `Snow/Firn`, `Hydro`, `Erosion`, `Landforms`);
4. Atlas export publishes `product_contract_version`, `inspector_contract_version`, and minimal diagnostic layers (`log_catchment`, tier networks).

`effective_config_schema_version`: `pc6_effective_config_v1`  
`product_contract_version`: `pc6_product_contract_v1`

---

## Acceptance

| Criterion | Result |
|---|---|
| `effective_config.json` schema + checksum | PASS |
| Save/load tier-mask parity | PASS |
| Hex export contract parity | PASS |
| `climate_summary` inspector status row | PASS |
| Godot Inspector reads `inspector_status` | PASS |
| `pytest -m pc6` | PASS |

Run: `pytest -m pc6 -q`

---

## Explicitly not done (→ C10 / presentation)

- Full Godot Advanced §10.1 grouped controls (YAML writer remains)
- Full §10.2 diagnostic catalogue
- Atlas `183716` regen in default CI

**Decision:** accept PC6 structural scope; pre-C10 repairs continue in readiness gate.

