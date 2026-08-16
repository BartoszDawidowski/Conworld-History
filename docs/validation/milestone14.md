# Milestone 14 acceptance record

**Date:** 2026-08-14  
**Scope:** Soils + Holdridge ecology only (no Milestone 15 hex grid)

## Delivered

| Item | Location |
|---|---|
| Permeability, soil depth/moisture, fertility, erosion risk | `worldsim/physical/ecology/soils.py` |
| Annual biotemperature + PET / PET ratio | `ecology/biotemperature.py` |
| Holdridge zones + overrides (ocean/lake/ice/alpine) | `ecology/holdridge.py` |
| Ecology pipeline | `ecology/pipeline.py` |
| CLI | `--stage ecology` (default) |
| Artefacts | `ecology/ecology.npz`, `holdridge_zone_legend.json` |

## Acceptance

| Criterion | Result |
|---|---|
| Every land cell has life zone (≥10) or explicit override | PASS |
| Ocean cells marked as ocean override | PASS |
| Automated tests | **83 passed** fast (includes ecology suite) |

## Explicitly not done (Milestone 15+)

- 256×128 analytical hex grid
- Agricultural / pastoral capacity (history layer)
- Indefinite climate–ecology feedback
