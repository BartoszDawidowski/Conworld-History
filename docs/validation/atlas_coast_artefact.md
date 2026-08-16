# Atlas coastline bright-outline verification (Milestone A3)

**Date:** 2026-08-15  
**Scope:** Presentation diagnosis only — **no coastline geometry generator change**

## Checklist

| Step | Action | Expected if presentation stroke | Observed |
|---|---|---|---|
| 1 | Load or Generate **Full** world; map mode **shaded relief** | Atlas loads with vectors on by default | PASS (human, Full atlas) |
| 2 | Turn **Coast / Rivers / Lakes** all **off** | Bright land outlines vanish; raster unchanged | PASS — outlines gone with Coast off (human) |
| 3 | Enable **Coast only** | Bright outlines return along land/water boundary | PASS — outlines return (human) |
| 4 | Optional: open `world/atlas_display/shaded_relief.png` outside Godot | PNG alone lacks the bright vector stroke | PASS (by construction: stroke is `draw_polyline` over GeoJSON) |
| 5 | Lakes toggle | Show/hide only; lake styling unchanged | PASS (toggle only; no lake restyle in A3) |

## Screenshots

Optional paths (not required for A3 close):

- `docs/validation/screenshots/coast_vectors_off.png` — *(not captured in-repo)*
- `docs/validation/screenshots/coast_only_on.png` — *(not captured in-repo)*

## Verdict

| Question | Result |
|---|---|
| Bright paint is coastline **vector presentation**? | **YES** |
| Remains in shaded-relief PNG without vectors? | **NO** (engine composite stroke) |
| Generator / SoT coastline geometry bug requiring ADR? | **NO** for “wrong ocean mask”; **YES** follow-up for **micro-segment + dateline wrap** draw artefacts |
| Follow-up (planned) | **A4** thinner coast / Strahler rivers / lake alpha; **A5** coast merge + seam fix — see `docs/ATLAS_UX_PLAN.md` |

## Controls delivered (A3)

Sidebar toggles: **Coast**, **Rivers**, **Lakes**, **Hex overlay** — visibility only; no world regeneration.

## Later observations (2026-08-15, Atlas / seed 124)

- Flicker / bluish ghosts: Coast on → present; Coast off → gone.
- Full-width horizontal bright lines: Coast layer; attributed to **x-wrap mid-segment** (plan **A5**).
- Thick rivers mistaken for lakes; lakes themselves acceptable (plan **A4**).
