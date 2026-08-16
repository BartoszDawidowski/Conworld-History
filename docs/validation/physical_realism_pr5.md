# Physical Realism PR-5 — canonical cylindrical hydrology graph

**Date:** 2026-08-16  
**Status:** ✅ **Accepted**  
**Authority:** `docs/WORLDGEN_PHYSICAL_REALISM_ANNEX.md` §11.1–11.2 / §15 PR-5  
**Depends on:** PR-0…PR-4  

---

## Delivered

| Item | Location |
|---|---|
| `CylindricalFlowGraph` + downstream flat index (E–W wrap) | `physical/hydrology/cylindrical_graph.py` |
| Accumulation, basins, Strahler order, outlets from one graph | same |
| Exhaustive validation (no 85% sample) | `validate_graph` |
| PyFlwDir only for DEM fill / D8 proposal; products recomputed | `physical/hydrology/flow.py` |
| Gross + effective discharge on canonical graph | `flow.py` / `transmission.py` |
| River vectors from graph paths (no cropped `pyflwdir.from_array`) | `physical/vectorize/rivers.py` |
| Seam-unwrapped polylines | `cell_path_to_norm_geometry` |
| Tests | `tests/test_physical_realism_pr5.py` |

---

## Acceptance

| Criterion | Result |
|---|---|
| Seam-crossing edges keep basin ID | PASS |
| Longitude rotation preserves basin partition relation | PASS |
| Accumulation never decreases along land→land edges | PASS |
| River network topology valid without non-periodic Flwdir | PASS |
| Path unwrap continuous across seam | PASS |
| Graph products ~0.5M cells &lt; 30 s | PASS (~budget check) |

---

## Explicitly not done (PR-6)

- Monthly transmission / snow–runoff stores  
- Q-aware wadi extinction without downstream mask inheritance  
- Open / endorheic lake metadata from graph  

**Decision:** accept PR-5; stop. Next when instructed: **PR-6**.
