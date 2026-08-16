# Godot atlas (Milestone 17)

Interactive multi-layer atlas for **Conworld History**. Godot visualises and controls runs; it is **not** the world database.

## Requirements

- Godot **4.7.1** (local `Godot.app` in repo root is fine; do not commit it)
- Python worker: `worldsim/.venv` with `python -m worldsim`

## Open

```bash
"/Users/…/Conworld History/Godot.app/Contents/MacOS/Godot" --path godot
```

Map navigation (Milestone A1): mouse wheel over the map to zoom (toward cursor), drag to pan, or use **− / Fit / +** in the sidebar. Raster uses linear filtering.

Vector layers (Milestone A3): sidebar toggles **Coast / Rivers / Lakes / Hex overlay** — show/hide only (no regeneration). Coast stroke is intentionally thin; bright outlines are the Coast vector, not the PNG.

Coast (A5): merged seam-safe polylines — regenerate world to drop old micro-edge GeoJSON / dateline chords.

Vector strokes: coast **0.2**; rivers **0.07…0.22** (Strahler); opaque rivers under opaque lakes.

**Advanced generation** (A6 + **B5**): open **Advanced…** for geography, SST coupling (`sst_mix`, inland decay, west/east anomalies), and moisture inland knobs. Defaults match packaged `default_planet.yaml` / engine constants — no silent retune. Each Generate writes `worlds/atlas_run_<seed>/planet_config.yaml` and passes `--config`.

**Start here (less shred / more continent):** ocean fraction ↓ → plates ↓ → detail amplitude ↓ → then erosion / fluvial k.

Hex overlay (Milestone A7): **flat-top hex contours** drawn in Godot (optional toggle). LOD when zoomed out. Click-inspect still works with overlay on. Does **not** alter geography.

Holdridge (Milestone A8): hex inspector shows a **readable life-zone / override label** plus numeric `holdridge_id`. Requires `atlas_display/holdridge_zone_legend.json` (written on Generate; regenerate older worlds).

Outline smoothing deferred (§7). Continentality / hypsometry not in A1–A8 critical path.

## Generate / load

1. Choose a **Generate profile** (Milestone A2 / A4b):
   - **Atlas** (default) — mid quality (climate 512×256, terrain 1024×512).
   - **Full** — packaged `default_planet.yaml` resolutions: climate/tectonics **1024×512**, terrain **4096×2048**. Expect **several minutes** and substantial RAM on 8 GB Macs.
   - **Quick** — smoke/UI (climate 128×64); not for detailing.
2. Optionally open **Advanced…** and adjust geography / coupling / moisture knobs.
3. **Generate world** — launches `python -m worldsim --stage world` into `worlds/atlas_run_<seed>/` (Full adds **no** size CLI overrides; knobs via `--config`).
4. On `complete`, the atlas loads `world/atlas_display/` (PNG map modes + GeoJSON vectors + hex overlay). Status shows loaded raster size (e.g. `Loaded atlas 1024x512`).
5. Or paste a path to an existing `world/` directory and click **Load world**.

## Atlas behaviour

| Control | Behaviour |
|---|---|
| Map mode | elevation (default), bathymetry, monthly temperature/precipitation, Holdridge |
| Month | Applies to temperature / precipitation modes |
| Coast / Rivers / Lakes | Toggle GeoJSON vector overlays (visibility only) |
| Hex overlay | Flat-top hex **contours** (A7); analysis cache only — does **not** alter geography |
| Click | River hit-test → river inspector; with hex overlay on → hex aggregate; else terrain UV |

## Layout produced by worker

```text
world/
  manifest.json
  physical/…
  atlas_display/
    atlas_meta.json
    elevation.png …
    rivers.geojson …
    hex_overlay.png
```

## Packaged worker (Milestone 18)

Release builds use `packaging/dist/worldsim_worker/worldsim_worker(.exe)` so users
do not need Python. Place that folder next to the Godot export, or copy
`worldsim_worker(.exe)` + `_internal/` beside the game binary.

Dev mode still uses `worldsim/.venv` via `python -m worldsim` when no packaged
worker is found. See `packaging/README.md`.
