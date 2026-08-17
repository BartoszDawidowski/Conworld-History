# Physical Realism CR-0 — CI and harness honesty

**Date:** 2026-08-17  
**Status:** ✅ **Accepted**  
**Authority:** [`docs/PHYSICAL_REALISM_CORRECTIONS.md`](../PHYSICAL_REALISM_CORRECTIONS.md) §5 CR-0  
**Defects closed:** **F-01** (CI / stale PR-0 probes / Windows packaging path)

---

## Delivered

| Item | Location / evidence |
|---|---|
| PR-0 fixture probes assert post–PR-4 physics | `worldsim/tests/test_physical_realism_pr0.py::test_fixture_probes_run` — northward mass, `max_overshoot ≤ 1e-9`, flat January spin-up |
| Windows pyplatec package root | `vendor/pyplatec/scripts/build_windows.ps1` — `$PkgRoot = parent of scripts` (no `vendor\vendor\pyplatec`) |
| CI green on `main` | Run [`31996630241`](https://github.com/BartoszDawidowski/Conworld-History/actions/runs/31996630241) — all five jobs success |
| Local pytest | `221 passed, 3 deselected` (`-m "not slow"`) |

Code landed in:

- `b38309c` — Fix PR-0 fixture probes for post-PR-4 moisture physics  
- `c07c5cc` — Fix Windows pyplatec build path (avoid vendor/vendor)

---

## Acceptance

| Criterion | Result |
|---|---|
| Fixture probes match corrected N–S advection / budget / spin-up | PASS |
| Packaging script resolves `vendor/pyplatec` once | PASS |
| `pytest` ubuntu / macOS / Windows | PASS |
| `package Windows worker` / `package macOS worker` | PASS |
| Local `pytest -m "not slow"` | PASS |

---

## Explicitly not done

- F-02…F-14 (parameter wire, SST, monsoon, endorheism, subgrid, calibration, …)  
- Changing production climate defaults (`monsoon_strength`, spin-up years, hypsometry mode)  
- CR-1+

**Decision:** accept CR-0; stop. Next when instructed: **CR-1** only.
