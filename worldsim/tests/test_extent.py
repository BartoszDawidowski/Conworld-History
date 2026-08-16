from __future__ import annotations

import pytest

from worldsim.config import load_planet_config, default_config_path
from worldsim.spatial.coordinates import CoordinateError
from worldsim.spatial.extent import GridIndex, SpatialExtent


def test_extent_shape_and_cell_count() -> None:
    extent = SpatialExtent.from_shape(1024, 512)
    assert extent.width == 1024
    assert extent.height == 512
    assert extent.cell_count == 1024 * 512


def test_from_planet_config_tectonics() -> None:
    config = load_planet_config(default_config_path())
    extent = SpatialExtent.from_planet_config(config, "tectonics")
    assert extent.width == 1024
    assert extent.height == 512
    assert extent.coordinate_system.wrap_x is True
    assert extent.coordinate_system.wrap_y is False


def test_column_wraps_east_west() -> None:
    extent = SpatialExtent.from_shape(8, 4)
    assert extent.wrap_column(-1) == 7
    assert extent.wrap_column(8) == 0
    assert extent.normalize_index(8, 1) == GridIndex(0, 1)
    assert extent.normalize_index(-1, 1) == GridIndex(7, 1)


def test_row_does_not_wrap_north_south() -> None:
    extent = SpatialExtent.from_shape(8, 4)
    with pytest.raises(CoordinateError, match="north–south"):
        extent.normalize_index(0, -1)
    with pytest.raises(CoordinateError, match="north–south"):
        extent.normalize_index(0, 4)
    assert extent.normalize_index(0, -1, clamp_ns=True) == GridIndex(0, 0)
    assert extent.normalize_index(0, 99, clamp_ns=True) == GridIndex(0, 3)


def test_neighbour_blocks_polar_crossing() -> None:
    extent = SpatialExtent.from_shape(16, 8)
    assert extent.neighbour(0, 0, 0, -1) is None
    assert extent.neighbour(0, 7, 0, 1) is None
    # East–west wrap still works at poles rows.
    assert extent.neighbour(0, 0, -1, 0) == GridIndex(15, 0)
    assert extent.neighbour(15, 7, 1, 0) == GridIndex(0, 7)


def test_pole_and_equator_cell_mapping() -> None:
    from worldsim.spatial.coordinates import y_to_lat

    extent = SpatialExtent.from_shape(360, 180)
    _x_n, y_n = extent.cell_center_xy(0, 0)
    _x_s, y_s = extent.cell_center_xy(0, extent.height - 1)
    # Equal-area cell centres never sit exactly on the poles; northernmost
    # row is still the highest latitude band.
    assert y_n > y_s
    assert y_to_lat(y_n) > 80.0
    assert y_to_lat(y_s) < -80.0
    assert extent.lonlat_to_index(0.0, 90.0).j == 0
    assert extent.lonlat_to_index(0.0, -90.0).j == extent.height - 1
    mid = extent.height // 2
    _lon_e, lat_e = extent.cell_center_lonlat(0, mid)
    assert abs(lat_e) < 1.0
    assert extent.lonlat_to_index(0.0, 0.0).j in {mid - 1, mid}


def test_xy_index_round_trip_centres() -> None:
    extent = SpatialExtent.from_shape(64, 32)
    for i, j in ((0, 0), (63, 0), (0, 31), (32, 16), (10, 20)):
        x, y = extent.cell_center_xy(i, j)
        back = extent.xy_to_index(x, y)
        assert back == GridIndex(i, j)


def test_lonlat_index_wraps_longitude_seam() -> None:
    extent = SpatialExtent.from_shape(36, 18)
    # lon ±180 map to column 0
    assert extent.lonlat_to_index(-180.0, 0.0).i == 0
    assert extent.lonlat_to_index(180.0, 0.0).i == 0
    # just west of seam
    idx = extent.lonlat_to_index(179.0, 0.0)
    assert idx.i == extent.width - 1
