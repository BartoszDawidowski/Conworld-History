"""PR-7 — revised B8: plume, water-limited ET, ITCZ inside moisture budget."""

from __future__ import annotations

import numpy as np

from worldsim.physical.atmosphere.circulation import itcz_latitude_deg
from worldsim.physical.moisture.transport import (
    build_monthly_moisture,
    evaporation_components,
    partition_precipitation,
    soft_plume_mix,
    saturation_capacity,
)


def test_plume_conserves_mass_and_is_not_a_rain_source() -> None:
    h, w = 16, 32
    q = np.zeros((h, w), dtype=np.float64)
    q[:, 2:5] = 4.0
    u = np.full((h, w), 6.0)
    v = np.zeros((h, w))
    out = soft_plume_mix(q, u, v, strength=0.25)
    assert abs(float(np.sum(out)) - float(np.sum(q))) < 1e-9
    # Moisture moves inland (east) relative to the coastal strip.
    assert float(out[:, 8:14].sum()) > float(q[:, 8:14].sum())


def test_plume_does_not_erase_rain_shadow() -> None:
    h, w = 24, 48
    elev = np.zeros((h, w), dtype=np.float64)
    elev[:, 22:27] = 3000.0
    elev[:, 23:26] = 4500.0
    temp = np.full((1, h, w), 22.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :10] = True
    lat = np.linspace(20, -20, h)[:, None] * np.ones((1, w))
    wu = np.full((1, h, w), 8.0)
    wv = np.zeros((1, h, w))
    fields = build_monthly_moisture(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=1,
        advect_steps=8,
        plume_strength=0.3,
        land_store_capacity=8.0,
        itcz_convective_scale=0.0,
    )
    precip = fields["precipitation"][0]
    windward = float(precip[:, 20:23].mean())
    leeward = float(precip[:, 27:30].mean())
    assert windward > leeward * 1.05


def test_wet_land_et_exceeds_desert_at_matched_temperature() -> None:
    shape = (12, 20)
    temp = np.full(shape, 28.0)
    ocean = np.zeros(shape, dtype=bool)
    wet_store = np.full(shape, 6.0)
    dry_store = np.zeros(shape)
    wet = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        land_rate=0.4,
        land_store=wet_store,
        land_store_capacity=8.0,
    )["land_et"]
    dry = evaporation_components(
        temperature_c=temp,
        ocean_mask=ocean,
        land_rate=0.4,
        land_store=dry_store,
        land_store_capacity=8.0,
    )["land_et"]
    assert float(wet.mean()) > float(dry.mean()) * 5.0
    assert float(dry.max()) < 1e-12


def test_itcz_seasonal_band_moves_and_components_sum() -> None:
    h, w = 40, 24
    lat = np.linspace(40, -40, h)[:, None] * np.ones((1, w))
    q = np.full((h, w), 5.0)
    capacity = saturation_capacity(np.full((h, w), 30.0))
    june = itcz_latitude_deg(5)
    december = itcz_latitude_deg(11)
    assert june > december

    part_j = partition_precipitation(
        q=q,
        capacity=capacity,
        land_dry=np.ones((h, w)),
        lift=np.zeros((h, w)),
        temperature_c=np.full((h, w), 30.0),
        latitude_deg=lat,
        large_scale_frac=0.1,
        orographic_frac=0.0,
        convective_scale=1.0,
        lee_dry=0.0,
        itcz_latitude_deg=june,
        itcz_convective_scale=2.0,
        itcz_width_deg=8.0,
    )
    part_d = partition_precipitation(
        q=q,
        capacity=capacity,
        land_dry=np.ones((h, w)),
        lift=np.zeros((h, w)),
        temperature_c=np.full((h, w), 30.0),
        latitude_deg=lat,
        large_scale_frac=0.1,
        orographic_frac=0.0,
        convective_scale=1.0,
        lee_dry=0.0,
        itcz_latitude_deg=december,
        itcz_convective_scale=2.0,
        itcz_width_deg=8.0,
    )
    for part in (part_j, part_d):
        assert np.allclose(
            part["precipitation"],
            part["large_scale_precip"]
            + part["orographic_precip"]
            + part["convective_precip"]
            + part["itcz_precip"],
        )
        assert float(np.max(part["precipitation"] - q)) <= 1e-9

    # Peak of ITCZ precip shifts with season.
    row_j = int(np.argmax(part_j["itcz_precip"].mean(axis=1)))
    row_d = int(np.argmax(part_d["itcz_precip"].mean(axis=1)))
    assert row_j < row_d  # June peak farther north (smaller j)


def test_interior_reach_improves_with_plume() -> None:
    h, w = 16, 40
    elev = np.zeros((h, w), dtype=np.float64)
    temp = np.full((3, h, w), 24.0)
    ocean = np.zeros((h, w), dtype=bool)
    ocean[:, :5] = True
    lat = np.zeros((h, w))
    wu = np.full((3, h, w), 8.0)
    wv = np.zeros((3, h, w))
    common = dict(
        temperature_c=temp,
        wind_u=wu,
        wind_v=wv,
        elevation_m=elev,
        ocean_mask=ocean,
        latitude_deg=lat,
        months=3,
        advect_steps=6,
        land_store_capacity=8.0,
        itcz_convective_scale=0.0,
        spinup_max_years=2,
    )
    no_plume = build_monthly_moisture(**common, plume_strength=0.0)
    with_plume = build_monthly_moisture(**common, plume_strength=0.35)
    interior = np.zeros_like(ocean)
    interior[:, 20:] = True
    interior &= ~ocean
    assert float(with_plume["precipitation"][:, interior].mean()) > float(
        no_plume["precipitation"][:, interior].mean()
    )
    assert with_plume["budget"]["b8_terms_active"] is True
    assert abs(with_plume["budget"]["annual_numerical_residual"]) < 1e-4 * max(
        1.0, abs(with_plume["budget"]["annual_precipitation_sum"])
    )


def test_no_independent_post_hoc_rain_field() -> None:
    """Total precip equals budgeted components only (no extra rain layer)."""
    h, w = 12, 24
    fields = build_monthly_moisture(
        temperature_c=np.full((2, h, w), 26.0),
        wind_u=np.full((2, h, w), 4.0),
        wind_v=np.zeros((2, h, w)),
        elevation_m=np.zeros((h, w)),
        ocean_mask=np.zeros((h, w), dtype=bool),
        latitude_deg=np.linspace(20, -20, h)[:, None] * np.ones((1, w)),
        months=2,
        plume_strength=0.2,
        land_store_capacity=5.0,
        itcz_convective_scale=1.0,
        spinup_max_years=1,
    )
    err = fields["budget"]["max_abs_component_sum_error"]
    assert float(err) < 1e-9
    assert "itcz_precip" in fields
    assert float(np.sum(fields["itcz_precip"])) >= 0.0
