from __future__ import annotations

from pathlib import Path

import numpy as np

from worldsim.physical.atmosphere import AtmosphereParams, build_atmosphere
from worldsim.physical.climate.pipeline import ClimateParams, build_base_climate
from worldsim.physical.erosion import ErosionParams, build_erosion_pass_one
from worldsim.physical.hydrology import HydrologyParams, build_hydrology
from worldsim.physical.hydrology.conditioning import dem_for_flow, ew_crop, ew_pad
from worldsim.physical.hydrology.flow import run_pyflwdir_core
from worldsim.physical.hydrology.rivers import (
    gate_lakes_by_water_supply,
    gate_river_mask_by_discharge,
    propagate_downstream_on_mask,
)
from worldsim.physical.moisture import MoistureParams, build_moisture
from worldsim.physical.ocean import OceanParams, build_ocean_circulation
from worldsim.physical.tectonics import PyPlatecParams, run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean


def _small_erosion_stack():
    tectonics = run_pyplatec_extended(
        seed=81,
        width=64,
        height=32,
        params=PyPlatecParams(num_plates=5),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(width=128, height=64, ocean_fraction_target=0.71),
        detail_seed=6,
    )
    climate = build_base_climate(
        terrain=terrain,
        params=ClimateParams(width=64, height=32),
    )
    atmosphere = build_atmosphere(climate=climate, params=AtmosphereParams())
    ocean = build_ocean_circulation(
        climate=climate, atmosphere=atmosphere, params=OceanParams()
    )
    moisture = build_moisture(
        climate=climate, atmosphere=atmosphere, ocean=ocean, params=MoistureParams()
    )
    erosion = build_erosion_pass_one(
        terrain=terrain,
        moisture=moisture,
        interpretation=interpretation,
        params=ErosionParams(iterations=3),
    )
    return erosion, moisture, climate


def test_ew_pad_roundtrip() -> None:
    a = np.arange(12, dtype=np.float64).reshape(3, 4)
    p = ew_pad(a, 2)
    assert p.shape == (3, 8)
    assert np.allclose(ew_crop(p, 2, 4), a)


def test_synthetic_drainage_accumulation() -> None:
    h, w = 24, 36
    elev = np.linspace(200, 20, w, dtype=np.float64)[None, :] * np.ones((h, 1))
    elev = elev + np.linspace(0, 30, h)[:, None]
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -3:] = True
    elev[ocean] = -50
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    assert core["isvalid"] is True
    assert float(core["flow_accumulation"][~ocean].max()) > 1.0
    land = ~ocean
    near = land & (np.arange(w)[None, :] >= w - 6)
    far = land & (np.arange(w)[None, :] < 8)
    assert float(core["flow_accumulation"][near].mean()) > float(
        core["flow_accumulation"][far].mean()
    )


def test_hydrology_from_small_world(tmp_path: Path) -> None:
    erosion, moisture, climate = _small_erosion_stack()
    hydro = build_hydrology(
        erosion=erosion,
        moisture=moisture,
        params=HydrologyParams(),
        temperature_c=climate.temperature_c,
    )
    assert hydro.flow_accumulation.shape == erosion.elevation_m.shape
    assert hydro.monthly_discharge.shape[0] == 12
    assert hydro.diagnostics["drainage_graph_valid"] is True
    assert hydro.diagnostics["sensible_accumulation_downstream"] is True
    assert hydro.diagnostics["acceptance_ok"] is True
    assert np.all(hydro.flow_accumulation[erosion.ocean_mask] == 0.0)
    hydro.save(tmp_path / "hydrology")
    assert (tmp_path / "hydrology" / "hydrology.npz").is_file()
    dem = dem_for_flow(erosion.elevation_m, erosion.ocean_mask)
    assert float(dem[erosion.ocean_mask].min()) < 0
    assert hydro.diagnostics.get("precip_gate") is True
    assert hydro.diagnostics["river_cells_after_gate"] <= hydro.diagnostics[
        "river_cells_before_gate"
    ]
    assert hydro.diagnostics["lake_count_after_gate"] <= hydro.diagnostics[
        "lake_count_before_gate"
    ]
    before_r = int(hydro.diagnostics["river_cells_before_gate"])
    after_r = int(hydro.diagnostics["river_cells_after_gate"])
    if before_r >= 20:
        assert after_r < before_r * 0.85


def test_gate_river_drops_arid_headwater_keeps_wet_corridor() -> None:
    """Dry high-acc stubs drop; wet Q corridor stays without downstream inheritance."""
    h, w = 5, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    candidate = np.zeros((h, w), dtype=bool)
    candidate[2, :7] = True
    d8 = np.zeros((h, w), dtype=np.uint8)
    d8[2, :7] = 1
    q = np.full((h, w), 1.0, dtype=np.float64)
    q[ocean] = 0.0
    q[2, 0] = 0.05
    q[2, 1] = 0.08
    q[2, 2:7] = np.linspace(8.0, 40.0, 5)
    gated, diag = gate_river_mask_by_discharge(
        candidate, q, d8, ocean, candidate_quantile=0.40
    )
    assert not gated[2, 0], "arid headwater without wet Q should drop"
    assert gated[2, 3] and gated[2, 6], "wet catchment corridor must remain"
    assert diag["river_cells_after_gate"] < diag["river_cells_before_gate"]
    assert diag["river_inherit_downstream"] is False


def test_gate_river_wadi_no_downstream_inheritance() -> None:
    """PR-6 fixture: Q 100,80,20,0,0 → zeros not restored by inheritance."""
    h, w = 3, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    candidate = np.zeros((h, w), dtype=bool)
    candidate[1, :6] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    q = np.zeros((h, w), dtype=np.float64)
    q[1, :6] = [100.0, 80.0, 20.0, 0.0, 0.0, 0.0]
    gated, _ = gate_river_mask_by_discharge(
        candidate,
        q,
        d8,
        ocean,
        min_effective_discharge=10.0,
        inherit_downstream=False,
    )
    assert bool(gated[1, 0]) and bool(gated[1, 1]) and bool(gated[1, 2])
    assert not gated[1, 3] and not gated[1, 4] and not gated[1, 5]
    # Legacy inherit would fill zeros — ensure default does not
    gated_legacy, _ = gate_river_mask_by_discharge(
        candidate,
        q,
        d8,
        ocean,
        min_effective_discharge=10.0,
        inherit_downstream=True,
    )
    assert bool(gated_legacy[1, 5]), "legacy inherit still fills arid trunk"


def test_propagate_downstream_fills_arid_corridor() -> None:
    h, w = 3, 6
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    seeds = np.zeros((h, w), dtype=bool)
    seeds[1, 1] = True
    limit = np.zeros((h, w), dtype=bool)
    limit[1, :5] = True
    d8 = np.full((h, w), 1, dtype=np.uint8)
    kept = propagate_downstream_on_mask(seeds, d8, ocean, limit_mask=limit)
    assert bool(kept[1, 1]) and bool(kept[1, 4])
    assert not kept[1, 0]


def test_gate_lakes_drops_arid_and_cold() -> None:
    h, w = 8, 8
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    lake_mask = np.zeros((h, w), dtype=bool)
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_mask[1:3, 1:3] = True
    lake_id[1:3, 1:3] = 1
    lake_mask[1:3, 4:6] = True
    lake_id[1:3, 4:6] = 2
    lake_mask[5:7, 1:3] = True
    lake_id[5:7, 1:3] = 3
    lake_mask[5:7, 4:6] = True
    lake_id[5:7, 4:6] = 4

    precip = np.full((h, w), 1.0, dtype=np.float64)
    precip[ocean] = 0.0
    precip[1:3, 1:3] = 0.05
    precip[1:3, 4:6] = 5.0
    precip[5:7, 1:3] = 2.0
    precip[5:7, 4:6] = 1.2

    temp = np.full((h, w), 12.0, dtype=np.float64)
    temp[5:7, 1:3] = -8.0

    river = np.zeros((h, w), dtype=bool)
    river[5, 3] = True

    q_eff = np.full((h, w), 1.0, dtype=np.float64)
    q_eff[ocean] = 0.0

    keep, _new_id, n, diag = gate_lakes_by_water_supply(
        lake_mask,
        lake_id,
        precip,
        ocean,
        river_mask=river,
        discharge_effective=q_eff,
        temperature_annual_c=temp,
        precip_land_quantile=0.70,
        arid_precip_land_quantile=0.45,
        lake_min_mean_temp_c=1.0,
        inflow_land_quantile=0.95,
    )
    assert n == 2
    assert not np.any(keep[1:3, 1:3]), "desert playa must drop"
    assert np.all(keep[1:3, 4:6]), "rain-fed wet lake kept"
    assert not np.any(keep[5:7, 1:3]), "cold / ice-sheet lake must drop"
    assert np.all(keep[5:7, 4:6]), "river-fed non-arid lake kept"
    assert diag["lake_dropped_cold"] >= 1
    assert diag["lake_dropped_arid"] >= 1


def test_gate_lakes_keeps_distant_fed_arid() -> None:
    """Nil-like: arid lake body but high effective Q + river touch → keep."""
    h, w = 6, 6
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -1] = True
    lake_mask = np.zeros((h, w), dtype=bool)
    lake_id = np.zeros((h, w), dtype=np.int32)
    lake_mask[2:4, 2:4] = True
    lake_id[2:4, 2:4] = 1
    precip = np.full((h, w), 2.0, dtype=np.float64)
    precip[ocean] = 0.0
    precip[2:4, 2:4] = 0.05  # arid local
    temp = np.full((h, w), 20.0, dtype=np.float64)
    river = np.zeros((h, w), dtype=bool)
    river[2, 1] = True
    q_eff = np.full((h, w), 1.0, dtype=np.float64)
    q_eff[2:4, 2:4] = 50.0
    keep, _id, n, diag = gate_lakes_by_water_supply(
        lake_mask,
        lake_id,
        precip,
        ocean,
        river_mask=river,
        discharge_effective=q_eff,
        temperature_annual_c=temp,
        precip_land_quantile=0.70,
        arid_precip_land_quantile=0.50,
        inflow_land_quantile=0.80,
    )
    assert n == 1
    assert np.all(keep[2:4, 2:4])
    assert diag["lake_kept_distant"] == 1


def test_effective_discharge_nil_vs_wadi() -> None:
    from worldsim.physical.hydrology.flow import run_pyflwdir_core
    from worldsim.physical.hydrology.transmission import (
        effective_discharge_with_transmission,
        transmission_sink,
    )

    h, w = 20, 48
    elev = np.linspace(300, 10, w, dtype=np.float64)[None, :] * np.ones((h, 1))
    elev = elev + np.linspace(0, 15, h)[:, None]
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, -2:] = True
    elev[ocean] = -50
    core = run_pyflwdir_core(elevation_m=elev, ocean_mask=ocean)
    flw = core["flw"]
    pad = int(core["pad"])
    precip = np.full((h, w), 0.15, dtype=np.float64)
    precip[:, :10] = 6.0  # wet highland
    precip[ocean] = 0.0
    temp = np.full((h, w), 28.0, dtype=np.float64)
    temp[:, :10] = 12.0
    sink = transmission_sink(
        precip, temp, ocean, transmission_rate=0.55, precip_scale_mm=200.0
    )
    q_eff = effective_discharge_with_transmission(
        flw, pad=pad, width=w, ocean_mask=ocean, precip=precip, sink=sink
    )
    # Wet source builds large Q; corridor still carries some of it (Nil).
    assert float(q_eff[:, 8:11].max()) > 40.0
    assert float(q_eff[:, 14:20].max()) > 5.0
    # Far arid interior without that trunk is dry (wadi / evaporated).
    assert float(q_eff[8:12, 28:36].mean()) < 1.0
    # Losses shrink the wet footprint vs gross accuflux.
    from worldsim.physical.hydrology.flow import accuflux_on_land

    q_g = accuflux_on_land(
        flw, pad=pad, width=w, ocean_mask=ocean, weights=precip
    )
    assert int(np.count_nonzero(q_eff > 1.0)) < int(np.count_nonzero(q_g > 1.0))
