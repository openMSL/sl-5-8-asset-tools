"""Shared test fixtures for preview_3d tests."""

import math

import pytest


@pytest.fixture
def line_geometry():
    """A simple straight-line geometry starting at origin heading east."""
    from preview_3d.models.geometry import Line

    return Line(s=0.0, x=0.0, y=0.0, hdg=0.0, length=100.0)


@pytest.fixture
def arc_geometry():
    """An arc geometry with curvature 0.01 (radius=100m)."""
    from preview_3d.models.geometry import Arc

    return Arc(s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0, curvature=0.01)


@pytest.fixture
def spiral_geometry():
    """A spiral (clothoid) from curvature 0 to 0.02 over 100m."""
    from preview_3d.models.geometry import Spiral

    return Spiral(
        s=0.0,
        x=0.0,
        y=0.0,
        hdg=0.0,
        length=100.0,
        curv_start=0.0,
        curv_end=0.02,
    )


@pytest.fixture
def poly3_geometry():
    """A poly3 geometry: v(ds) = 0 + 0*ds + 0.001*ds² + 0."""
    from preview_3d.models.geometry import Poly3

    return Poly3(
        s=0.0, x=0.0, y=0.0, hdg=0.0, length=50.0, a=0.0, b=0.0, c=0.001, d=0.0
    )


@pytest.fixture
def param_poly3_geometry():
    """A paramPoly3 geometry with simple u/v polynomials."""
    from preview_3d.models.geometry import ParamPoly3

    return ParamPoly3(
        s=0.0,
        x=0.0,
        y=0.0,
        hdg=0.0,
        length=50.0,
        a_u=0.0,
        b_u=1.0,
        c_u=0.0,
        d_u=0.0,
        a_v=0.0,
        b_v=0.0,
        c_v=0.001,
        d_v=0.0,
        p_range="arcLength",
    )
