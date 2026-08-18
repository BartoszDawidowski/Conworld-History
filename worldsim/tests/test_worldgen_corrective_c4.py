"""C4 — conservative face-flux moisture transport, CFL fail-closed, topo sign."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.atmosphere.circulation import (
    apply_topographic_perturbation,
)
from worldsim.physical.moisture.transport import (
    MoistureTransportError,
    _cfl_substeps,
    _diffuse_moisture,
    _face_flux_advect,
    build_monthly_moisture,
    orographic_lift,
)


def test_production_moisture_knobs_not_retuned() -> None:
    cfg = load_planet_config(default_config_path())
    mp = cfg.to_moisture_params()
    assert mp.orographic_frac == pytest.approx(0.85)
    assert mp.large_scale_frac == pytest.approx(0.15)
    assert mp.advect_wind_scale == pytest.approx(0.2)
    assert mp.ocean_evap_rate == pytest.approx(1.4)
    assert mp.convective_scale == pytest.approx(2.0)
    assert mp.plume_strength == pytest.approx(0.18)
    assert mp.advect_steps == 32
    assert mp.advect_max_substeps == 32
    assert cfg.moisture_spinup_max_years == 48


def test_yaml_prefers_advect_max_substeps(tmp_path: Path) -> None:
    path = tmp_path / "c4.yaml"
    path.write_text(
        """
schema_version: 2
planet: {earth_like: true}
map: {topology: cylindrical, wrap_x: true, wrap_y: false, projection: cylindrical_equal_area}
analysis_grid: {width: 64, height: 32, orientation: flat_top}
resolution:
  tectonics: [64, 32]
  climate: [64, 32]
  terrain_target: [64, 32]
  terrain_production: [64, 32]
  hydrology_target: [64, 32]
climate: {months: 12, base_temp_c: 18.0}
generation: {quality: final}
moisture:
  advect_steps: 12
  advect_max_substeps: 7
""",
        encoding="utf-8",
    )
    cfg = load_planet_config(path)
    assert cfg.moisture_advect_steps == 7
    assert cfg.to_moisture_params().advect_max_substeps == 7


def test_transport_only_mass_closed_float64() -> None:
    h, w = 17, 32
    q = np.zeros((h, w), dtype=np.float64)
    q[8, 10:14] = 3.0
    q[4, 20] = 1.5
    u = np.full((h, w), 2.0, dtype=np.float64)
    v = np.full((h, w), -1.5, dtype=np.float64)
    mass0 = float(q.sum())
    clip = 0.0
    for _ in range(24):
        q, diag = _face_flux_advect(q, u, v, dt=0.2, wind_scale=0.2)
        clip += float(diag["advect_clip_mass"])
        q, dclip = _diffuse_moisture(q, dt=0.2, mix_per_month=0.08)
        clip += float(dclip)
    assert clip == pytest.approx(0.0, abs=1e-15)
    assert abs(float(q.sum()) - mass0) / mass0 <= 1e-10


def test_ew_wrap_and_no_ns_wrap_impulse() -> None:
    h, w = 15, 20
    q = np.zeros((h, w), dtype=np.float64)
    q[7, 0] = 1.0
    u = np.full((h, w), -4.0)
    v = np.zeros((h, w))
    out = q.copy()
    for _ in range(6):
        out, _d = _face_flux_advect(out, u, v, dt=0.2, wind_scale=0.3)
    assert float(out[:, -1].sum()) > float(out[:, 1:4].sum())
    assert abs(float(out.sum()) - 1.0) <= 1e-12

    qn = np.zeros((h, w), dtype=np.float64)
    qn[7, 10] = 1.0
    vn = np.full((h, w), 8.0)
    u0 = np.zeros((h, w))
    out_n = qn.copy()
    for _ in range(8):
        out_n, _d = _face_flux_advect(out_n, u0, vn, dt=0.15, wind_scale=0.25)
    assert float(out_n[-1, :].sum()) < 1e-9
    assert abs(float(out_n.sum()) - 1.0) <= 1e-12


def test_cfl_fail_closed_does_not_clip_courant() -> None:
    h, w = 8, 16
    u = np.full((h, w), 10.0)
    v = np.full((h, w), 10.0)
    with pytest.raises(MoistureTransportError) as err:
        _cfl_substeps(u, v, wind_scale=0.2, max_steps=1)
    diag = err.value.diagnostics
    assert diag["advect_substeps_required"] > 1
    assert diag["advect_max_substeps"] == 1
    n, c2d, csub = _cfl_substeps(u, v, wind_scale=0.2, max_steps=32)
    assert n >= 2
    assert csub <= 0.9 + 1e-12
    assert c2d > 0.9


def test_month_budget_residual_and_precip_demand() -> None:
    h, w = 12, 24
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :5] = True
    fields = build_monthly_moisture(
        temperature_c=np.full((12, h, w), 24.0),
        wind_u=np.full((12, h, w), 5.0),
        wind_v=np.zeros((12, h, w)),
        elevation_m=np.zeros((h, w)),
        ocean_mask=ocean,
        latitude_deg=np.zeros((h, w)),
        months=12,
        advect_steps=8,
        spinup_max_years=4,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
        large_scale_frac=0.2,
        orographic_frac=0.4,
        convective_scale=0.5,
        ocean_evap_rate=1.0,
        land_et_rate=0.2,
    )
    budget = fields["budget"]
    assert budget["algorithm"] == "moisture_budget_spinup_v6_c5"
    assert budget["advect_algorithm"] == "face_flux_cfl_v1"
    assert float(budget["max_month_residual_rel"]) <= 1e-6
    assert budget["moisture_budget_ok"] is True
    assert float(budget["max_precip_overshoot"]) <= 1e-9
    assert float(budget["annual_precip_allocated_sum"]) <= float(
        budget["annual_precip_demand_sum"]
    ) + 1e-9
    precip = fields["precipitation"]
    assert np.allclose(
        precip,
        fields["large_scale_precip"]
        + fields["orographic_precip"]
        + fields["convective_precip"]
        + fields["itcz_precip"],
    )


def test_north_south_ridge_orographic_lift() -> None:
    h, w = 21, 16
    elev = np.zeros((h, w), dtype=np.float64)
    j0 = 10
    elev[j0 - 1, :] = 1500.0
    elev[j0, :] = 4000.0
    elev[j0 + 1, :] = 1500.0
    u = np.zeros((h, w))
    v_north = np.full((h, w), 8.0)
    v_south = np.full((h, w), -8.0)
    lift_n = orographic_lift(wind_u=u, wind_v=v_north, elevation_m=elev)
    lift_s = orographic_lift(wind_u=u, wind_v=v_south, elevation_m=elev)
    # Northward wind hits the south face; southward wind hits the north face.
    assert float(lift_n[j0 + 1, :].mean()) > 0.0
    assert float(lift_n[j0 - 1, :].mean()) < 0.0
    assert float(lift_s[j0 - 1, :].mean()) > 0.0
    assert float(lift_s[j0 + 1, :].mean()) < 0.0


def test_topographic_wind_uses_lift_orientation() -> None:
    h, w = 21, 16
    elev = np.zeros((h, w), dtype=np.float64)
    j0 = 10
    elev[j0, :] = 4000.0
    u0 = np.zeros((h, w))
    v_north = np.full((h, w), 6.0)
    _u, v_out = apply_topographic_perturbation(u0, v_north, elev, drag_amp=2.0, divert_amp=0.0)
    # South of the ridge, northward flow is into the upslope → slowed (v decreases).
    assert float(v_out[j0 + 1, :].mean()) < 6.0
    # North of the ridge, northward flow is downslope → sped up.
    assert float(v_out[j0 - 1, :].mean()) > float(v_out[j0 + 1, :].mean())


def test_warm_start_records_q_init() -> None:
    h, w = 8, 16
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :3] = True
    q0 = np.full((h, w), 2.5, dtype=np.float64)
    store0 = np.where(~ocean, 1.0, 0.0)
    fields = build_monthly_moisture(
        temperature_c=np.full((12, h, w), 22.0),
        wind_u=np.full((12, h, w), 3.0),
        wind_v=np.zeros((12, h, w)),
        elevation_m=np.zeros((h, w)),
        ocean_mask=ocean,
        latitude_deg=np.zeros((h, w)),
        months=12,
        advect_steps=6,
        spinup_max_years=2,
        plume_strength=0.0,
        land_store_capacity=4.0,
        itcz_convective_scale=0.0,
        q_init=q0,
        land_store_init=store0,
    )
    assert fields["budget"]["warm_started"] is True
    assert fields["land_store"].shape == (12, h, w)


def test_substep_cap_is_safety_not_reach() -> None:
    months = 12
    h, w = 10, 20
    kwargs = dict(
        temperature_c=np.full((months, h, w), 22.0),
        wind_u=np.full((months, h, w), 4.0),
        wind_v=np.zeros((months, h, w)),
        elevation_m=np.zeros((h, w)),
        ocean_mask=np.zeros((h, w), dtype=bool),
        latitude_deg=np.zeros((h, w)),
        months=months,
        advect_wind_scale=0.08,
        diffusion_mix_per_month=0.08,
        large_scale_frac=0.2,
        orographic_frac=0.0,
        convective_scale=0.0,
        plume_strength=0.0,
        land_store_capacity=0.0,
        itcz_convective_scale=0.0,
        spinup_max_years=3,
        ocean_evap_rate=0.8,
        land_et_rate=0.0,
    )
    a = build_monthly_moisture(**kwargs, advect_max_substeps=8)["precipitation"]
    b = build_monthly_moisture(**kwargs, advect_max_substeps=32)["precipitation"]
    mean_a = float(a.mean())
    mean_b = float(b.mean())
    denom = max(abs(mean_a), abs(mean_b), 1e-9)
    assert abs(mean_a - mean_b) / denom < 0.15
