"""Tests for CRS transformation utilities."""

import pytest

from preview_3d.geometry.transform import (
    create_transformer,
    transform_coord,
    transform_coords,
)


class TestCreateTransformer:
    def test_empty_proj4_returns_none(self):
        assert create_transformer("") is None

    def test_whitespace_proj4_returns_none(self):
        assert create_transformer("   ") is None

    def test_invalid_proj4_returns_none(self):
        assert create_transformer("not_a_valid_crs") is None

    def test_valid_proj4_returns_transformer(self):
        t = create_transformer("+proj=utm +zone=32 +datum=WGS84")
        assert t is not None


class TestTransformCoord:
    def test_none_transformer_passthrough(self):
        coord = (500000.0, 5000000.0, 100.0)
        assert transform_coord(coord, None) == coord

    def test_transforms_utm_to_wgs84(self):
        t = create_transformer("+proj=utm +zone=32 +datum=WGS84")
        lon, lat, z = transform_coord((500000.0, 5000000.0, 100.0), t)
        # UTM zone 32 center is ~9°E, lat ~45°N
        assert 8.0 < lon < 10.0
        assert 44.0 < lat < 46.0
        assert z == pytest.approx(100.0)


class TestTransformCoords:
    def test_none_transformer_passthrough(self):
        coords = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        assert transform_coords(coords, None) == coords

    def test_transforms_list(self):
        t = create_transformer("+proj=utm +zone=32 +datum=WGS84")
        result = transform_coords(
            [(500000.0, 5000000.0, 0.0), (500100.0, 5000100.0, 10.0)], t
        )
        assert len(result) == 2
        for lon, lat, z in result:
            assert 8.0 < lon < 10.0
            assert 44.0 < lat < 46.0

    def test_empty_list(self):
        t = create_transformer("+proj=utm +zone=32 +datum=WGS84")
        assert transform_coords([], t) == []
