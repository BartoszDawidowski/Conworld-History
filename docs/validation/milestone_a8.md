# Milestone A8 acceptance record

**Date:** 2026-08-15 (updated: wiki-style labels, hex climate fields, elevation default)  
**Scope:** Holdridge inspector labels + atlas display polish

## Delivered

| Item | Location |
|---|---|
| Wikipedia-style life-zone names (e.g. Tropical moist forest) | `holdridge.py` `_LIFE_ZONE_DISPLAY` |
| Land-preferring hex Holdridge mode (coast ≠ Ocean on land) | `hex_grid/pipeline.py` |
| Legend + decode fallback in Godot | `HexOverlayRenderer.holdridge_label` |
| Hex aggregates: temp / precip / fractions | `hex_environment.json` + inspector |
| Default map mode **elevation**; **shaded_relief removed** | export + `MapModeController` |
| Hex stroke 0.75 px screen, alpha 0.3 | `HEX_WIDTH_SCREEN` / `HEX_LINE` |

## Why more than ~38 wiki zones?

Model uses a full 6×7 biotemperature × humidity grid (**42** life zones) plus 4 overrides. Classic Holdridge maps list ~38 *commonly realised* combinations; rare edge cells still get a physiognomic label.

## Acceptance

| Criterion | Result |
|---|---|
| Readable Holdridge names (not `Zone 36`) | PASS (legend + id decode) |
| Ocean/lake/ice/alpine labeled | PASS |
| Coastal land hexes not forced to Ocean | PASS after regenerate (`land_frac ≥ 0.05` → land mode) |
| Hex inspector shows climate aggregates | PASS (after regenerate) |
| Default elevation; no shaded_relief mode | PASS |

## Note

Regenerate world to refresh `holdridge_dominant` (land mode) and new hex climate fields. Labels alone work on old worlds via id decode.
