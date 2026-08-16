# Milestone A5 acceptance record

**Date:** 2026-08-15  
**Scope:** Coast merge + dateline seam — no A6 knobs

## Delivered

| Item | Location |
|---|---|
| Run-length merge of horizontal / vertical land–ocean edges | `physical/terrain/coastline.py` |
| Seam-safe `x` (no `1→0` wrap mid-edge; reject `|Δx|>0.5`) | same |
| Godot polyline unwrap for coast/rivers/lakes draw | `VectorLayerRenderer._to_pixels` |
| Tests | `tests/test_coastline_a5.py` |

## Metrics (local M2)

| Case | Micro-edges | Merged features | Ratio | Time |
|---|---|---|---|---|
| Atlas-like 1024×512 blocky | 15 008 | 256 | **58.6×** | 0.13 s |
| Full-like 4096×2048 blocky | 128 448 | 1 039 | **123.6×** | 2.19 s |

## Acceptance

| Criterion | Result |
|---|---|
| No full-width dateline chords | PASS (unit + clamp) |
| Order-of-magnitude fewer features | PASS (~50×+ on blocky land) |
| Vectors stage not stuck on micro-edge GeoJSON explosion | PASS (merge before export) |
| Coast toggles unchanged | PASS |

## Explicitly not done

- A6 generation knobs
- Outline smoothing (§7)
- PNG-only coasts
