"""Closed-basin area–volume–level storage (12 scalar months, CR-7)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.hydrology.cylindrical_graph import CylindricalFlowGraph
from worldsim.physical.hydrology.discharge import SECONDS_PER_DAY, month_days
from worldsim.physical.hydrology.transmission import month_pet_fraction

_VOLUME_EPS_M3 = 1.0


def _sink_cell(
    graph: CylindricalFlowGraph, body: NDArray[np.bool_]
) -> tuple[int, int] | None:
    """Inland sink or highest-Q cell inside a lake body."""
    w = body.shape[1]
    ds = graph.downstream_flat
    rows, cols = np.where(body)
    if rows.size == 0:
        return None
    for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
        if int(ds[int(r) * w + int(c)]) < 0:
            return int(r), int(c)
    return int(rows[0]), int(cols[0])


def apply_closed_basin_storage(
    *,
    graph: CylindricalFlowGraph,
    lake_id: NDArray[np.integer],
    lake_records: list[dict[str, Any]],
    elevation_m: NDArray[np.floating],
    monthly_q_m3s: NDArray[np.floating],
    temperature_c: NDArray[np.floating],
    cell_area_km2: float,
    lake_min_depth_m: float = 2.0,
    frozen_temp_c: float = 1.0,
    spinup_years: int = 2,
) -> dict[str, Any]:
    """12 scalar A–V–h steps per closed basin. Mutates ``lake_records``."""
    q = np.asarray(monthly_q_m3s, dtype=np.float64)
    if q.ndim != 3:
        raise ValueError("monthly_q_m3s must be [months, y, x]")
    months = int(q.shape[0])
    elev = np.asarray(elevation_m, dtype=np.float64)
    ids = np.asarray(lake_id)
    if temperature_c.ndim == 3:
        temp_m = np.asarray(temperature_c, dtype=np.float64)
    else:
        annual = np.asarray(temperature_c, dtype=np.float64)
        temp_m = np.broadcast_to(annual, q.shape)

    area_m2_cell = float(cell_area_km2) * 1e6
    stepped = 0
    reclass_playa = 0
    reclass_endorheic = 0

    for rec in lake_records:
        if not rec.get("closed_basin"):
            continue
        if str(rec.get("water_state", "")) == "frozen_or_ice_covered":
            continue
        lid = int(rec["lake_id"])
        body = ids == lid
        n_cells = int(np.count_nonzero(body))
        if n_cells == 0:
            continue
        sink = _sink_cell(graph, body)
        if sink is None:
            continue
        sr, sc = sink
        a_max = n_cells * area_m2_cell
        z_floor = float(np.min(elev[body]))
        z_spill = float(rec.get("spill_elevation_m", z_floor + lake_min_depth_m))
        h_spill = max(z_spill - z_floor, float(lake_min_depth_m), 1.0)
        v_spill = 0.5 * a_max * h_spill
        mean_temp = float(np.mean(temp_m[:, body])) if months else 0.0
        if mean_temp < float(frozen_temp_c):
            continue

        volume = 0.0
        storage: list[float] = []
        level: list[float] = []
        wet_area: list[float] = []
        spill: list[float] = []
        years = max(int(spinup_years), 1)
        for _year in range(years):
            storage.clear()
            level.clear()
            wet_area.clear()
            spill.clear()
            for m in range(months):
                days = float(month_days(m))
                inflow = max(float(q[m, sr, sc]), 0.0) * days * SECONDS_PER_DAY
                bio = float(np.clip(np.mean(temp_m[m][body]), 0.0, 30.0))
                pet_mm = 58.93 * bio * month_pet_fraction(m)
                h = float(np.sqrt(max(2.0 * volume * h_spill / max(a_max, 1.0), 0.0)))
                h = min(h, h_spill)
                area = a_max * (h / h_spill) if h_spill > 0.0 else 0.0
                evap = (pet_mm / 1000.0) * area
                volume = max(volume + inflow - evap, 0.0)
                spilled = 0.0
                if volume > v_spill:
                    spilled = volume - v_spill
                    volume = v_spill
                h = float(np.sqrt(max(2.0 * volume * h_spill / max(a_max, 1.0), 0.0)))
                h = min(h, h_spill)
                area = a_max * (h / h_spill) if h_spill > 0.0 else 0.0
                storage.append(volume)
                level.append(h)
                wet_area.append(area / 1e6)
                spill.append(spilled)

        rec["storage_m3"] = [float(v) for v in storage]
        rec["level_m"] = [float(v) for v in level]
        rec["wet_area_km2"] = [float(v) for v in wet_area]
        rec["spill_m3"] = [float(v) for v in spill]
        rec["mean_storage_m3"] = float(np.mean(storage)) if storage else 0.0
        rec["months_wet"] = int(sum(1 for v in storage if v > _VOLUME_EPS_M3))
        rec["v_spill_m3"] = float(v_spill)
        rec["h_spill_m"] = float(h_spill)
        rec["storage_curve"] = "linear_a_of_h"
        stepped += 1

        months_wet = int(rec["months_wet"])
        if months_wet <= 0 or float(rec["mean_storage_m3"]) <= _VOLUME_EPS_M3:
            if rec.get("water_state") != "seasonal_or_playa":
                reclass_playa += 1
            rec["water_state"] = "seasonal_or_playa"
        elif months_wet >= 3:
            if rec.get("water_state") != "endorheic":
                reclass_endorheic += 1
            rec["water_state"] = "endorheic"
        else:
            rec["water_state"] = "seasonal_or_playa"
            reclass_playa += 1

    return {
        "basin_storage_stepped_count": stepped,
        "basin_storage_reclass_playa": reclass_playa,
        "basin_storage_reclass_endorheic": reclass_endorheic,
        "basin_storage_spinup_years": int(spinup_years),
    }
