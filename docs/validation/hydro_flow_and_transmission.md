# Hydro follow-ups — flow layer + transmission losses

**Date agreed:** 2026-08-16  
**Date implemented:** 2026-08-16  
**Status:** ✅ Implemented  
**Parent:** Plan B §6.3 / B7 (`docs/ATLAS_PLAN_B.md`, `docs/validation/milestone_b7.md`)

---

## 1. Flow-direction layer (Atlas UI)

| Item | Spec |
|---|---|
| Control | Bottom-bar **Flow** checkbox (`FlowCheck`) |
| Renderer | `godot/atlas/FlowLayerRenderer.gd` via `WorldAtlas.set_flow_overlay` |
| Source | `atlas_display/flow_direction.png` (R = D8 code, G = river_mask hint) |
| Draw | Land D8 ticks; at Fit prefer river cells (LOD); denser when zoomed |
| Not a map mode | Independent of elevation / Holdridge / … |

## 2. Transmission losses (“Nil OK, wadi dies”)

| Piece | Where |
|---|---|
| Sink | `transmission_sink` — `rate × max(0, PET−P)` in precip-proxy units |
| Routing | `effective_discharge_with_transmission` — topo sum along D8 (`idxs_seq` reversed) |
| Params | `hydrology.transmission_rate` (default `0.45`), uses `precip_scale_mm` for PET |
| Gates | Rivers/lakes use **effective** Q; `river_discharge_proxy` = effective; gross kept as `river_discharge_gross` |
| Distant lakes | River-touch + high body effective Q keeps arid terminal lakes (`lake_kept_distant`) |

Atmospheric `lake_evap_rate` / `river_evap_rate` unchanged (moisture #2 only).

## 3. Acceptance

| Criterion | Result |
|---|---|
| Thin arid / wadi weaker than wet→arid corridor | `test_effective_discharge_nil_vs_wadi` |
| Distant-fed arid lake kept | `test_gate_lakes_keeps_distant_fed_arid` |
| Flow layer toggle | Godot `FlowCheck` + skeleton tests |
| No moisture self-feed | Still moisture #1 → hydro → moisture #2 |

## 4. Regenerate

Atlas must be **re-generated** to pick up effective Q masks and `flow_direction.png`.
