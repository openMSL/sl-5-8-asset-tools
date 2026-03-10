"""Tests for polynomial evaluation, derivatives, normals, and spiral math."""

import math

import numpy as np
import pytest

from xodr_to_geojson_caller.geometry.curves import (
    calc_normal_vector,
    calc_polynom_derivative,
    calc_polynom_value,
    spiral_coords,
)


class TestPolynomValue:
    """Polynomial: f(ds) = a + b*ds + c*ds² + d*ds³."""

    def test_constant(self):
        assert calc_polynom_value(5.0, 0.0, 0.0, 0.0, ds=10.0) == 5.0

    def test_linear(self):
        assert calc_polynom_value(0.0, 2.0, 0.0, 0.0, ds=3.0) == 6.0

    def test_quadratic(self):
        assert calc_polynom_value(1.0, 0.0, 0.5, 0.0, ds=4.0) == pytest.approx(9.0)

    def test_cubic(self):
        # 1 + 2*3 + 0.5*9 + 0.1*27 = 1 + 6 + 4.5 + 2.7 = 14.2
        assert calc_polynom_value(1.0, 2.0, 0.5, 0.1, ds=3.0) == pytest.approx(14.2)

    def test_zero(self):
        assert calc_polynom_value(0.0, 0.0, 0.0, 0.0, ds=42.0) == 0.0


class TestPolynomDerivative:
    """Derivative: f'(ds) = b + 2*c*ds + 3*d*ds²."""

    def test_constant_derivative_is_zero(self):
        assert calc_polynom_derivative(0.0, 0.0, 0.0, ds=5.0) == 0.0

    def test_linear_derivative(self):
        assert calc_polynom_derivative(3.0, 0.0, 0.0, ds=5.0) == 3.0

    def test_full_derivative(self):
        # b=1, c=2, d=0.5 at ds=2: 1 + 2*2*2 + 3*0.5*4 = 1 + 8 + 6 = 15
        assert calc_polynom_derivative(1.0, 2.0, 0.5, ds=2.0) == pytest.approx(15.0)


class TestNormalVector:
    """Normal vector perpendicular to curve tangent."""

    def test_horizontal_tangent(self):
        # Heading 0 → tangent (1, 0) → normal (0, 1)
        nx, ny = calc_normal_vector(heading=0.0)
        assert nx == pytest.approx(0.0, abs=1e-10)
        assert ny == pytest.approx(1.0, abs=1e-10)

    def test_45_degree_tangent(self):
        nx, ny = calc_normal_vector(heading=math.pi / 4)
        expected = math.sqrt(2) / 2
        assert nx == pytest.approx(-expected, abs=1e-10)
        assert ny == pytest.approx(expected, abs=1e-10)

    def test_vertical_tangent(self):
        nx, ny = calc_normal_vector(heading=math.pi / 2)
        assert nx == pytest.approx(-1.0, abs=1e-10)
        assert ny == pytest.approx(0.0, abs=1e-10)


class TestSpiralCoords:
    """Fresnel-based clothoid (Euler spiral) coordinates."""

    def test_zero_length_returns_origin(self):
        x, y, hdg = spiral_coords(ds=0.0, curv_start=0.0, curv_dot=0.01)
        assert x == pytest.approx(0.0, abs=1e-10)
        assert y == pytest.approx(0.0, abs=1e-10)

    def test_straight_line_when_no_curvature(self):
        # Zero curvature start and zero curvature change → straight line
        x, y, hdg = spiral_coords(ds=10.0, curv_start=0.0, curv_dot=0.0)
        assert x == pytest.approx(10.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)

    def test_spiral_curves_away_from_axis(self):
        # With positive curvature change, spiral should curve left (positive y)
        x, y, _ = spiral_coords(ds=50.0, curv_start=0.0, curv_dot=0.001)
        assert x > 0
        assert y > 0

    def test_symmetric_spiral(self):
        # Opposite curvature change should mirror y
        _, y_pos, _ = spiral_coords(ds=50.0, curv_start=0.0, curv_dot=0.001)
        _, y_neg, _ = spiral_coords(ds=50.0, curv_start=0.0, curv_dot=-0.001)
        assert y_pos == pytest.approx(-y_neg, abs=1e-6)

    def test_heading_increases_with_curvature(self):
        _, _, hdg = spiral_coords(ds=20.0, curv_start=0.0, curv_dot=0.01)
        assert hdg > 0
