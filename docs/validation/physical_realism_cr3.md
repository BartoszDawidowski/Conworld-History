# Physical Realism CR-3 — moisture closure, SST anomaly, monsoon regime

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-3  
**Defects closed:** **F-03** remainder (spin-up years); **F-04** (land store in closure); **F-05** (SST anomaly); **F-06** (mix/decay after formula); **F-07** (local monsoon)

---

## Delivered

| Item | Location |
|---|---|
| Joint spin-up on `q` + land store (mean \|Δ\| for store) | `physical/moisture/transport.py` |
| Production `spinup_max_years: 20` | `configs/default_planet.yaml` |
| SST anomaly coupling vs zonal ocean mean | `physical/ocean/sst.py` (`anomaly_zonal_v1`) |
| `sst_mix: 0.28`, decay remains 1200 km | YAML + Godot default |
| Local coastal monsoon (not hemispheric means) | `physical/atmosphere/monsoon.py` `monsoon_local_coast_wind_v2` |
| Monsoon uses **pre-SST** climate land T | `physical/moisture/pipeline.py` |
| Modest re-enable `monsoon_strength: 0.35` | YAML |
| Tests | `tests/test_physical_realism_cr3.py` (+ updated ocean/PR-3/PR-8/config) |

---

## Acceptance

| Criterion | Result |
|---|---|
| Spin-up converges with store gated | PASS (fixture ≤24 y; default max 20) |
| Uniform SST does not pull land to absolute ocean T | PASS |
| Coastal SST anomaly ≫ deep inland ΔT | PASS |
| Seasonal onshore/offshore flip on tropical coast fixture | PASS (PR-8 + CR-3 local) |
| Local monsoon survives anti-phased SH land | PASS |
| `pytest -m "not slow"` | PASS — 236 passed |

---

## Explicitly not done

- Full Quick 1/42/100 regeneration audit (recommended follow-up, not blocking)  
- Moisture knob retune band (orographic/lee/plume/ITCZ) — leftover after CR-5  
- Endorheism / monthly Q (**CR-4**)  
- Hypsometry / landform calibration (**CR-5**)

**Decision:** accept CR-3; stop. Next when instructed: **CR-4** only.
