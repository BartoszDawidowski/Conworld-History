# Milestone A4 acceptance record

**Date:** 2026-08-15  
**Scope:** Vector stroke polish (presentation only) — no A5 coast merge / worker changes

## Formula (rivers)

```text
COAST_WIDTH = 0.2
STRAHLER_K  = 0.35
RIVER_WIDTH_MAX = 0.85

w(order) = clamp(COAST_WIDTH * (1 + STRAHLER_K * (order - 1)), COAST_WIDTH, RIVER_WIDTH_MAX)
```

| Strahler | Width |
|---|---|
| 1 | 0.20 |
| 2 | 0.27 |
| 3 | 0.34 |
| 5 | 0.48 |
| ≥ ~10 | 0.85 (cap) |

Lakes fill alpha: **0.48** (was 0.35). Geometry unchanged.

## Delivered

| Item | Location |
|---|---|
| Coast ~4× thinner vs A3 (`0.75` → `0.2`) | `VectorLayerRenderer.gd` |
| Rivers ≈ coast baseline + Strahler scale | `river_width_for_strahler` |
| Lakes slightly less transparent | `LAKE_FILL` alpha 0.48 |

## Acceptance

| Criterion | Result |
|---|---|
| Rivers no longer solid blobs over lakes | PASS (widths ≤ 0.85 vs prior ≤ 3.5) |
| Coasts less dominant | PASS |
| Lakes still readable | PASS (higher alpha) |
| A3 toggles unchanged | PASS |
| No worker/GeoJSON changes | PASS |

## Explicitly not done (A5+)

- Coast merge / dateline seam
- Generation knobs
- Hex contours / Holdridge labels
