from __future__ import annotations

from pathlib import Path

import pytest

from worldsim.config import ConfigError, default_config_path, load_planet_config


def test_default_config_loads() -> None:
    config = load_planet_config(default_config_path())
    assert config.schema_version == 2
    assert config.is_earth_like_cylindrical
    assert config.analysis_width == 256
    assert config.analysis_height == 128
    assert config.climate_months == 12
    assert config.tectonics_resolution == (1024, 512)
    assert config.ocean_fraction_target == 0.71
    assert config.tectonics_num_plates == 7
    assert config.tectonics_cycle_count == 3
    assert config.terrain_detail_amplitude == 0.02
    assert config.tectonics_folding_ratio == 0.01
    assert config.tectonics_sea_level == 0.65
    assert config.tectonics_erosion_period == 100
    assert config.land_scale_m == 9000.0
    assert config.ocean_scale_m == 10000.0
    assert config.orogeny_boost == 0.05
    assert config.to_pyplatec_params().folding_ratio == 0.01
    assert config.erosion_iterations == 5
    assert config.erosion_fluvial_k == 8.0
    assert config.sst_mix == 0.28
    assert config.inland_decay_cells == 60.0
    assert config.sst_inland_decay_km == 1200.0
    assert config.western_warm_c == 2.2
    assert config.eastern_cool_c == 1.8
    assert config.moisture_advect_steps == 32
    assert config.moisture_advect_wind_scale == 0.2
    assert config.moisture_large_scale_frac == 0.15
    assert config.moisture_convective_scale == 2.0
    assert config.moisture_ocean_evap_rate == 1.4
    assert config.moisture_land_et_rate == 0.4
    assert config.moisture_spinup_max_years == 20
    assert config.moisture_monsoon_strength == 0.35
    assert config.moisture_continentality_dry == 0.4
    assert config.moisture_lake_evap_rate == 0.75
    assert config.moisture_river_evap_rate == 0.40
    assert config.to_ocean_params().sst_mix == 0.28
    assert config.to_moisture_params().advect_steps == 32
    assert config.to_moisture_params().lake_evap_rate == 0.75
    assert config.base_temp_c == 25.0
    assert config.precip_scale_mm == 200.0
    assert config.hydrology_transmission_rate == 0.45
    assert config.hydrology_fill_max_depth_m == 25.0
    assert config.to_hydrology_params().fill_max_depth_m == 25.0
    assert config.hypsometry_mode == "power_tail_v2"
    assert config.hypsometry_body_exponent == pytest.approx(1.5)
    assert config.hypsometry_tail_softness == pytest.approx(1.0)
    assert config.hydrology_river_min_catchment_km2 == pytest.approx(500.0)
    lf = config.to_landform_params()
    assert lf.mountain_score_threshold == pytest.approx(0.60)
    assert lf.fine_radius_km == pytest.approx(60.0)
    assert lf.min_range_km2 == pytest.approx(800.0)


def test_b5_knobs_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "b5.yaml"
    path.write_text(
        """
schema_version: 2
planet: {earth_like: true}
map: {topology: cylindrical, wrap_x: true, wrap_y: false, projection: cylindrical_equal_area}
analysis_grid: {width: 256, height: 128, orientation: flat_top}
resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  terrain_production: [4096, 2048]
  hydrology_target: [4096, 2048]
ocean: {fraction_target: 0.71, sst_mix: 0.5, inland_decay_cells: 8.0, western_warm_c: 3.0, eastern_cool_c: 1.0}
tectonics: {num_plates: 10, cycle_count: 2}
terrain: {detail_amplitude: 0.08}
erosion: {iterations: 5, fluvial_k: 8.0}
climate: {months: 12, base_temp_c: 18.0}
ecology:
  precip_scale_mm: 500.0
moisture:
  advect_steps: 12
  advect_wind_scale: 0.08
  large_scale_frac: 0.3
  orographic_frac: 0.5
  convective_scale: 2.0
  ocean_evap_rate: 1.5
  land_et_rate: 0.4
  continentality_dry: 0.2
  lee_dry: 0.05
generation: {quality: final}
""",
        encoding="utf-8",
    )
    config = load_planet_config(path)
    assert config.sst_mix == 0.5
    assert config.inland_decay_cells == 8.0
    assert config.western_warm_c == 3.0
    assert config.eastern_cool_c == 1.0
    assert config.base_temp_c == 18.0
    assert config.moisture_advect_steps == 12
    assert config.moisture_advect_wind_scale == 0.08
    assert config.moisture_large_scale_frac == 0.3
    assert config.precip_scale_mm == 500.0
    m = config.to_moisture_params()
    assert m.advect_steps == 12
    assert m.large_scale_frac == 0.3
    assert config.to_ecology_params().precip_scale_mm == 500.0
    o = config.to_ocean_params()
    assert o.sst_mix == 0.5
    assert o.inland_decay_cells == 8.0


def test_a6_knobs_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "knobs.yaml"
    path.write_text(
        """
schema_version: 2
planet: {earth_like: true}
map: {topology: cylindrical, wrap_x: true, wrap_y: false, projection: cylindrical_equal_area}
analysis_grid: {width: 256, height: 128, orientation: flat_top}
resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  terrain_production: [4096, 2048]
  hydrology_target: [4096, 2048]
ocean: {fraction_target: 0.55}
tectonics: {num_plates: 6, cycle_count: 3}
terrain: {detail_amplitude: 0.04}
erosion: {iterations: 7, fluvial_k: 5.0}
climate: {months: 12}
generation: {quality: final}
""",
        encoding="utf-8",
    )
    config = load_planet_config(path)
    assert config.ocean_fraction_target == 0.55
    assert config.tectonics_num_plates == 6
    assert config.tectonics_cycle_count == 3
    assert config.terrain_detail_amplitude == 0.04
    assert config.erosion_iterations == 7
    assert config.erosion_fluvial_k == 5.0


def test_ocean_fraction_rejects_bounds(tmp_path: Path) -> None:
    path = tmp_path / "bad_ocean.yaml"
    path.write_text(
        """
schema_version: 2
planet: {earth_like: true}
map: {topology: cylindrical, wrap_x: true, wrap_y: false, projection: cylindrical_equal_area}
analysis_grid: {width: 256, height: 128, orientation: flat_top}
resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  hydrology_target: [4096, 2048]
ocean: {fraction_target: 1.0}
climate: {months: 12}
generation: {quality: final}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="fraction_target"):
        load_planet_config(path)


def test_wrap_y_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
schema_version: 2
planet: {earth_like: true}
map: {topology: cylindrical, wrap_x: true, wrap_y: true, projection: cylindrical_equal_area}
analysis_grid: {width: 256, height: 128, orientation: flat_top}
resolution:
  tectonics: [1024, 512]
  climate: [1024, 512]
  terrain_target: [4096, 2048]
  hydrology_target: [4096, 2048]
climate: {months: 12}
generation: {quality: final}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="wrap_y"):
        load_planet_config(path)
