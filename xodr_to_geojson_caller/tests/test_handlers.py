"""Tests for geometry handlers — sth→xyz coordinate transformations."""

import math

import pytest

from xodr_to_geojson_caller.geometry.handlers import (
    arc_sth2xyz,
    calc_heading,
    line_sth2xyz,
    param_poly3_sth2xyz,
    poly3_sth2xyz,
    spiral_sth2xyz,
    sth2xyz,
)
from xodr_to_geojson_caller.models.geometry import Arc, Line, ParamPoly3, Poly3, Spiral


class TestLineSth2Xyz:
    def test_origin_heading_east(self, line_geometry):
        x, y, z = line_sth2xyz(line_geometry, s=10.0, t=0.0, h=0.0)
        assert x == pytest.approx(10.0)
        assert y == pytest.approx(0.0)
        assert z == pytest.approx(0.0)

    def test_lateral_offset(self, line_geometry):
        # t=5 with heading 0 → 5m to the left (positive y)
        x, y, z = line_sth2xyz(line_geometry, s=0.0, t=5.0, h=0.0)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(5.0)

    def test_heading_north(self):
        geom = Line(s=0.0, x=0.0, y=0.0, hdg=math.pi / 2, length=100.0)
        x, y, z = line_sth2xyz(geom, s=10.0, t=0.0, h=0.0)
        assert x == pytest.approx(0.0, abs=1e-10)
        assert y == pytest.approx(10.0)

    def test_with_offset_origin(self):
        geom = Line(s=0.0, x=100.0, y=200.0, hdg=0.0, length=50.0)
        x, y, z = line_sth2xyz(geom, s=10.0, t=0.0, h=5.0)
        assert x == pytest.approx(110.0)
        assert y == pytest.approx(200.0)
        assert z == pytest.approx(5.0)

    def test_s_offset_within_geometry(self):
        geom = Line(s=50.0, x=100.0, y=0.0, hdg=0.0, length=50.0)
        x, y, z = line_sth2xyz(geom, s=60.0, t=0.0, h=0.0)
        assert x == pytest.approx(110.0)


class TestArcSth2Xyz:
    def test_quarter_circle(self, arc_geometry):
        # Arc with curvature 0.01 → radius 100m
        # Quarter circle (pi/2 / curvature = ~157m but our arc is 50m)
        x, y, z = arc_sth2xyz(arc_geometry, s=0.0, t=0.0, h=0.0)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)

    def test_arc_moves_forward(self, arc_geometry):
        x, y, z = arc_sth2xyz(arc_geometry, s=10.0, t=0.0, h=0.0)
        assert x > 0  # Should move forward
        assert y > 0  # Left-curving arc → positive y

    def test_negative_curvature_mirrors(self):
        geom_pos = Arc(s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0, curvature=0.01)
        geom_neg = Arc(s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0, curvature=-0.01)
        _, y_pos, _ = arc_sth2xyz(geom_pos, s=25.0, t=0.0, h=0.0)
        _, y_neg, _ = arc_sth2xyz(geom_neg, s=25.0, t=0.0, h=0.0)
        assert y_pos == pytest.approx(-y_neg, abs=1e-6)


class TestSpiralSth2Xyz:
    def test_spiral_at_start(self, spiral_geometry):
        x, y, z = spiral_sth2xyz(spiral_geometry, s=0.0, t=0.0, h=0.0)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)

    def test_spiral_moves_forward(self, spiral_geometry):
        x, y, z = spiral_sth2xyz(spiral_geometry, s=20.0, t=0.0, h=0.0)
        assert x > 0


class TestPoly3Sth2Xyz:
    def test_straight_poly(self):
        geom = Poly3(s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0, a=0.0, b=0.0, c=0.0, d=0.0)
        x, y, z = poly3_sth2xyz(geom, s=10.0, t=0.0, h=0.0)
        assert x == pytest.approx(10.0)
        assert y == pytest.approx(0.0)

    def test_quadratic_offset(self, poly3_geometry):
        # v(ds) = 0.001 * ds², at ds=10: v=0.1
        x, y, z = poly3_sth2xyz(poly3_geometry, s=10.0, t=0.0, h=0.0)
        # u=10, v=0.1 rotated by hdg=0 → x≈10, y≈0.1
        assert x == pytest.approx(10.0, abs=0.5)
        assert y == pytest.approx(0.1, abs=0.05)


class TestParamPoly3Sth2Xyz:
    def test_straight_param_poly(self):
        geom = ParamPoly3(
            s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0,
            a_u=0.0, b_u=1.0, c_u=0.0, d_u=0.0,
            a_v=0.0, b_v=0.0, c_v=0.0, d_v=0.0,
            p_range="arcLength",
        )
        x, y, z = param_poly3_sth2xyz(geom, s=10.0, t=0.0, h=0.0)
        assert x == pytest.approx(10.0)
        assert y == pytest.approx(0.0, abs=1e-6)


class TestDispatch:
    def test_dispatch_line(self, line_geometry):
        x, y, z = sth2xyz(line_geometry, s=10.0, t=0.0, h=0.0)
        assert x == pytest.approx(10.0)

    def test_dispatch_arc(self, arc_geometry):
        x, y, z = sth2xyz(arc_geometry, s=0.0, t=0.0, h=0.0)
        assert x == pytest.approx(0.0, abs=1e-6)

    def test_dispatch_unknown_raises(self):
        with pytest.raises(TypeError):
            sth2xyz("not a geometry", s=0.0, t=0.0, h=0.0)


class TestCalcHeading:
    def test_line_heading_constant(self, line_geometry):
        hdg = calc_heading(line_geometry, s=50.0)
        assert hdg == pytest.approx(0.0)

    def test_arc_heading_changes(self, arc_geometry):
        hdg = calc_heading(arc_geometry, s=25.0)
        assert hdg > 0  # Left-curving arc increases heading
