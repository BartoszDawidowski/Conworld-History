# Milestone B2 — Atlas UI chrome (layout)

**Date:** 2026-08-15  
**Plan:** `docs/ATLAS_PLAN_B.md`  
**Status:** ✅ Complete

## Scope

Reorganize the Godot atlas shell: top generation chrome, bottom map modes / layers / zoom, inspector on the left, compact Holdridge legend bottom-right.

## Delivered

| Item | Notes |
|---|---|
| Top bar | Seed, profile + (i) tips, Advanced… popup, Generate, path, Load, status, progress |
| Advanced popup | `PopupPanel` with A6 knobs; close via ✕ / outside click |
| Bottom bar | Icon mode buttons (El/Ba/Te/Pr/Ho) + Hex/Coast/Rivers/Lakes + month + zoom slider + Fit |
| Active mode | Amber border style on selected mode button |
| Zoom | Min = Fit (`1.0`), max = **16× Fit**; `WorldAtlas.ZOOM_FACTOR_*` + slider sync |
| Inspector | Left panel only (right panel removed) |
| Legend | Deferred — removed from B2 chrome (was covering the map); reintroduce later if needed |

## Acceptance

| Criterion | Result |
|---|---|
| Generate / Load / inspect still wired | Met |
| Mode buttons switch modes; active border | Met |
| Advanced opens/closes as popup | Met |
| Zoom slider Fit…16× | Met |

## Empiric note

Zoom max **16× Fit** is the Plan B starting cap; raise/lower after human try on Atlas/Full.

## Stop

B2 complete. Next when instructed: **B3** (land polygons export, Atlas).
