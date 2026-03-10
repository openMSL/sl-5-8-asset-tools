"""Tests for elevation, superelevation, and shape profile calculations."""

import pytest

from xodr_to_geojson_caller.geometry.elevation import (
    get_elevation,
    get_projected_width,
)


class TestGetElevation:
    def test_flat_road(self):
        # No elevation, no superelevation
        h = get_elevation(s=10.0, t=0.0, elev_a=0.0, elev_b=0.0, elev_c=0.0, elev_d=0.0, elev_s=0.0)
        assert h == pytest.approx(0.0)

    def test_constant_elevation(self):
        h = get_elevation(s=10.0, t=0.0, elev_a=5.0, elev_b=0.0, elev_c=0.0, elev_d=0.0, elev_s=0.0)
        assert h == pytest.approx(5.0)

    def test_linear_slope(self):
        # a=10, b=0.05 → at ds=20: 10 + 0.05*20 = 11.0
        h = get_elevation(s=20.0, t=0.0, elev_a=10.0, elev_b=0.05, elev_c=0.0, elev_d=0.0, elev_s=0.0)
        assert h == pytest.approx(11.0)

    def test_with_superelevation(self):
        # Superelevation adds t * sin(alpha)
        # alpha = 0.1 rad, t = 5m → additional height = 5 * sin(0.1) ≈ 0.4995
        import math

        h = get_elevation(
            s=0.0, t=5.0,
            elev_a=10.0, elev_b=0.0, elev_c=0.0, elev_d=0.0, elev_s=0.0,
            super_a=0.1, super_b=0.0, super_c=0.0, super_d=0.0, super_s=0.0,
        )
        assert h == pytest.approx(10.0 + 5.0 * math.sin(0.1))

    def test_elevation_with_s_offset(self):
        # elev_s=5, queried at s=8 → ds=3, a=0, b=1 → height=3
        h = get_elevation(s=8.0, t=0.0, elev_a=0.0, elev_b=1.0, elev_c=0.0, elev_d=0.0, elev_s=5.0)
        assert h == pytest.approx(3.0)


class TestGetProjectedWidth:
    def test_no_superelevation(self):
        w = get_projected_width(t=5.0)
        assert w == pytest.approx(5.0)

    def test_with_superelevation(self):
        import math

        # alpha=0.1 → projected width = 5 * cos(0.1)
        w = get_projected_width(
            t=5.0,
            super_a=0.1, super_b=0.0, super_c=0.0, super_d=0.0,
            super_s=0.0, s=0.0,
        )
        assert w == pytest.approx(5.0 * math.cos(0.1))

    def test_level_lane_ignores_superelevation(self):
        w = get_projected_width(
            t=5.0,
            super_a=0.5, super_b=0.0, super_c=0.0, super_d=0.0,
            super_s=0.0, s=0.0,
            level=True,
        )
        assert w == pytest.approx(5.0)
