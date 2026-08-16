from __future__ import annotations

import math

import pytest

from worldsim.spatial.coordinates import (
    CoordinateError,
    CoordinateSystem,
    clamp_y,
    lat_to_y,
    lon_to_x,
    lonlat_to_normalised,
    normalised_to_lonlat,
    wrap_x,
    x_to_lon,
    y_to_lat,
)


def test_coordinate_system_rejects_ns_wrap() -> None:
    with pytest.raises(CoordinateError):
        CoordinateSystem(wrap_y=True)


def test_wrap_x_half_open_unit_interval() -> None:
    assert wrap_x(0.0) == 0.0
    assert wrap_x(0.25) == 0.25
    assert wrap_x(1.0) == 0.0
    assert wrap_x(1.25) == pytest.approx(0.25)
    assert wrap_x(-0.25) == pytest.approx(0.75)
    assert wrap_x(-1.0) == 0.0


def test_lon_x_round_trip() -> None:
    for lon in (-180.0, -90.0, 0.0, 45.0, 90.0, 179.999):
        x = lon_to_x(lon)
        assert 0.0 <= x < 1.0
        back = x_to_lon(x)
        if lon == -180.0:
            assert back == pytest.approx(-180.0)
        else:
            assert back == pytest.approx(lon, abs=1e-9)


def test_lon_seam_equivalence() -> None:
    assert lon_to_x(-180.0) == pytest.approx(0.0)
    assert lon_to_x(180.0) == pytest.approx(0.0)
    assert x_to_lon(0.0) == pytest.approx(-180.0)


def test_lat_y_round_trip_poles_and_equator() -> None:
    assert lat_to_y(0.0) == pytest.approx(0.0)
    assert lat_to_y(90.0) == pytest.approx(1.0)
    assert lat_to_y(-90.0) == pytest.approx(-1.0)
    assert y_to_lat(0.0) == pytest.approx(0.0)
    assert y_to_lat(1.0) == pytest.approx(90.0)
    assert y_to_lat(-1.0) == pytest.approx(-90.0)

    for lat in (-60.0, -30.0, 15.0, 45.0, 75.0):
        assert y_to_lat(lat_to_y(lat)) == pytest.approx(lat, abs=1e-9)


def test_y_equals_sin_latitude() -> None:
    lat = 30.0
    assert lat_to_y(lat) == pytest.approx(math.sin(math.radians(lat)))


def test_clamp_y_does_not_wrap() -> None:
    assert clamp_y(1.5) == 1.0
    assert clamp_y(-2.0) == -1.0
    with pytest.raises(CoordinateError):
        clamp_y(1.5, strict=True)


def test_lonlat_normalised_round_trip() -> None:
    lon, lat = 12.5, -33.0
    x, y = lonlat_to_normalised(lon, lat)
    lon2, lat2 = normalised_to_lonlat(x, y)
    assert lon2 == pytest.approx(lon)
    assert lat2 == pytest.approx(lat)


def test_invalid_latitude_rejected() -> None:
    with pytest.raises(CoordinateError):
        lat_to_y(90.1)
