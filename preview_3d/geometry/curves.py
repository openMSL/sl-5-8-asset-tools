"""Curve math: polynomial evaluation, derivatives, normals, and Fresnel spirals."""

from __future__ import annotations

import math

import numpy as np
from scipy.special import fresnel


def calc_polynom_value(a: float, b: float, c: float, d: float, *, ds: float) -> float:
    """Evaluate cubic polynomial: f(ds) = a + b*ds + c*ds² + d*ds³."""
    return a + b * ds + c * ds * ds + d * ds * ds * ds


def calc_polynom_derivative(b: float, c: float, d: float, *, ds: float) -> float:
    """Derivative of cubic polynomial: f'(ds) = b + 2c*ds + 3d*ds²."""
    return b + 2.0 * c * ds + 3.0 * d * ds * ds


def calc_normal_vector(heading: float) -> tuple[float, float]:
    """Unit normal vector perpendicular to tangent at given heading.

    Normal points to the left of the travel direction (positive t side).
    Returns (nx, ny).
    """
    return (-math.sin(heading), math.cos(heading))


def spiral_coords(
    ds: float, curv_start: float, curv_dot: float
) -> tuple[float, float, float]:
    """Compute (x, y, heading) on a clothoid curve using Fresnel integrals.

    Args:
        ds: Distance along the spiral from its start.
        curv_start: Curvature at the spiral start.
        curv_dot: Rate of curvature change (curv_end - curv_start) / length.

    Returns:
        (x, y, heading) in the spiral's local coordinate system.
    """
    if ds == 0.0:
        return (0.0, 0.0, 0.0)

    if curv_dot == 0.0 and curv_start == 0.0:
        # Degenerate case: straight line
        return (ds, 0.0, 0.0)

    if curv_dot == 0.0:
        # Constant curvature: circular arc
        r = 1.0 / curv_start
        theta = ds * curv_start
        x = r * math.sin(theta)
        y = r * (1.0 - math.cos(theta))
        return (x, y, theta)

    # General clothoid via Fresnel integrals
    # Heading at distance s: theta(s) = curv_start * s + 0.5 * curv_dot * s²
    heading = curv_start * ds + 0.5 * curv_dot * ds * ds

    # Numerical integration using small steps for accuracy
    n_steps = max(int(abs(ds) * 10), 100)
    s_vals = np.linspace(0.0, ds, n_steps + 1)
    theta_vals = curv_start * s_vals + 0.5 * curv_dot * s_vals * s_vals

    # Trapezoidal integration of cos(theta) and sin(theta)
    cos_vals = np.cos(theta_vals)
    sin_vals = np.sin(theta_vals)
    x = float(np.trapezoid(cos_vals, s_vals))
    y = float(np.trapezoid(sin_vals, s_vals))

    return (x, y, heading)
