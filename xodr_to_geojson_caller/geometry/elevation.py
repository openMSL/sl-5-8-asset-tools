"""Elevation, superelevation, and cross-sectional shape computations."""

from __future__ import annotations

import math

from xodr_to_geojson_caller.geometry.curves import calc_polynom_value


def get_elevation(
    s: float,
    t: float,
    elev_a: float,
    elev_b: float,
    elev_c: float,
    elev_d: float,
    elev_s: float,
    *,
    super_a: float = 0.0,
    super_b: float = 0.0,
    super_c: float = 0.0,
    super_d: float = 0.0,
    super_s: float = 0.0,
    level: bool = False,
) -> float:
    """Compute elevation at road position (s, t).

    Combines:
    1. Base elevation polynomial evaluated at s
    2. Superelevation (road banking) contribution: t * sin(alpha)

    Args:
        s: Global s-coordinate.
        t: Lateral offset from reference line.
        elev_*: Elevation polynomial coefficients and s-offset.
        super_*: Superelevation polynomial coefficients and s-offset.
        level: If True, ignore superelevation (for level lanes).
    """
    ds_elev = s - elev_s
    base_height = calc_polynom_value(elev_a, elev_b, elev_c, elev_d, ds=ds_elev)

    if level or (super_a == 0.0 and super_b == 0.0 and super_c == 0.0 and super_d == 0.0):
        return base_height

    ds_super = s - super_s
    alpha = calc_polynom_value(super_a, super_b, super_c, super_d, ds=ds_super)

    return base_height + t * math.sin(alpha)


def get_projected_width(
    t: float,
    *,
    super_a: float = 0.0,
    super_b: float = 0.0,
    super_c: float = 0.0,
    super_d: float = 0.0,
    super_s: float = 0.0,
    s: float = 0.0,
    level: bool = False,
) -> float:
    """Project lateral width accounting for superelevation.

    When the road is banked, the horizontal distance is compressed by cos(alpha).
    """
    if level or (super_a == 0.0 and super_b == 0.0 and super_c == 0.0 and super_d == 0.0):
        return t

    ds_super = s - super_s
    alpha = calc_polynom_value(super_a, super_b, super_c, super_d, ds=ds_super)
    return t * math.cos(alpha)
