# Worldgen corrective C9.1.3 — honest river terminals

**Date:** 2026-08-18  
**Status:** ✅ **Delivered** (fixtures + suite; no Atlas regen; no river-fraction retune)  
**Authority:** [`docs/WORLDGEN_CORRECTIVE_C91_ADDENDUM.md`](../WORLDGEN_CORRECTIVE_C91_ADDENDUM.md) §C9.1.3  
**Closes:** P-91-09; diagnoses P-91-08  
**Depends on:** C9.1.1  
**Audited commit before this package:** post-C9.1.2 working tree

---

## Delivered

| Item | Location |
|---|---|
| Canonical terminals: `ocean_mouth`, `lake_inlet`, `lake_outlet`, `endorheic_sink`, `lod_cutoff` | `vectorize/rivers.py` |
| Never coerce leftover `junction` / `out==0` to `mouth` | path-end classifier + post-pass |
| `mouth` only as legacy alias of `ocean_mouth` | `RiverNode.to_dict` `legacy_type` |
| Counts per type; `ocean_mouth` must neighbour ocean (fraction = 1) | vector diagnostics; `acceptance_ok` gated |
| Physical vs display cell counts | `channel_physical_cell_count` / `channel_display_cell_count` |
| GeoJSON Point layer for node round-trip | `river_nodes.geojson` |
| Tests | `tests/test_worldgen_corrective_c91_3.py` |

`HydrologyParams.river_acc_fraction = 0.035` and `river_discharge_candidate_quantile = 0.50` are **unchanged**. P-91-08 (physical vs display density) is diagnosed by the count pair, not “fixed” by retuning LOD.

---

## Terminal rules

| Type | Meaning |
|---|---|
| `ocean_mouth` | last display channel cell adjacent to ocean (or D8 into ocean) |
| `lake_inlet` | display path ends in a wet lake envelope |
| `lake_outlet` | display path starts in a wet lake (spill / leave) |
| `endorheic_sink` | inland stop: no ocean, no lake, physical channel does not continue |
| `lod_cutoff` | physical `channel_mask` continues but display `river_mask` stopped |

---

## Acceptance

| Criterion | Result |
|---|---|
| Ocean-mouth nodes are ocean-adjacent (fraction 1) | PASS |
| Inland `out==0` is `endorheic_sink`, not `mouth` | PASS |
| Lake inlet/outlet survive GeoJSON + VectorStore round-trip | PASS |
| LOD cutoff when physical channel continues | PASS |
| Display filter defaults not retuned | PASS |
| Focused suite | PASS — 40 passed (C9.1.3 + PR-5 + A4b + C0 + C2) |

Atlas seed `183716` was **not** regenerated. Production “8/18 mouths not at ocean” is the same class as the old `out==0 → mouth` coercion and is a regen leftover.

---

## Explicitly not done

- BiomeV2 NON_GROWING / wetland predicate (**C9.1.4**)
- Plateau interior vs rim / range split (**C9.1.5**)
- Canonical world `acceptance_ok` aggregator (**C9.1.6**)
- `river_acc_fraction` / Q-quantile retune (C10 / P-91-08 calibration)
- Atlas `183716` regeneration

**Decision:** accept C9.1.3; stop. Next: **C9.1.4** only. **C10 remains blocked.**
