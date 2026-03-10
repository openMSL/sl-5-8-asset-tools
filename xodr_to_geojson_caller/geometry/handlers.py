"""Geometry handlers: convert (s, t, h) road coordinates to (x, y, z) inertial.

Each handler implements the OpenDRIVE coordinate transformation for a specific
geometry type (Line, Arc, Spiral, Poly3, ParamPoly3). The `sth2xyz` dispatcher
selects the right handler based on geometry type.
"""

from __future__ import annotations

import math
from functools import singledispatch

from xodr_to_geojson_caller.geometry.curves import (
    calc_normal_vector,
    calc_polynom_derivative,
    calc_polynom_value,
    spiral_coords,
)
from xodr_to_geojson_caller.models.geometry import (
    Arc,
    Geometry,
    Line,
    ParamPoly3,
    Poly3,
    Spiral,
)


def _rotate_translate(
    u: float, v: float, hdg: float, x0: float, y0: float
) -> tuple[float, float]:
    """Rotate (u, v) by heading and translate to (x0, y0)."""
    cos_h = math.cos(hdg)
    sin_h = math.sin(hdg)
    x = x0 + u * cos_h - v * sin_h
    y = y0 + u * sin_h + v * cos_h
    return x, y


def _apply_lateral_offset(
    u: float, v: float, t: float, local_hdg: float
) -> tuple[float, float]:
    """Apply lateral offset t along the normal at local heading."""
    if t == 0.0:
        return u, v
    nx, ny = calc_normal_vector(local_hdg)
    return u + nx * t, v + ny * t


# --- Individual handlers ---


def line_sth2xyz(
    geom: Line, s: float, t: float, h: float
) -> tuple[float, float, float]:
    ds = s - geom.s
    u, v = ds, 0.0
    u, v = _apply_lateral_offset(u, v, t, 0.0)
    x, y = _rotate_translate(u, v, geom.hdg, geom.x, geom.y)
    return x, y, h


def arc_sth2xyz(
    geom: Arc, s: float, t: float, h: float
) -> tuple[float, float, float]:
    ds = s - geom.s
    c = geom.curvature
    if c == 0.0:
        return line_sth2xyz(
            Line(s=geom.s, x=geom.x, y=geom.y, hdg=geom.hdg, length=geom.length),
            s, t, h,
        )

    sign = math.copysign(1.0, c)
    r = abs(1.0 / c)
    theta = ds * c

    # Point on the arc centerline in local coords
    u = r * math.sin(theta)
    v = sign * r * (1.0 - math.cos(theta))

    # Local heading at this point
    local_hdg = theta
    u, v = _apply_lateral_offset(u, v, t, local_hdg)
    x, y = _rotate_translate(u, v, geom.hdg, geom.x, geom.y)
    return x, y, h


def spiral_sth2xyz(
    geom: Spiral, s: float, t: float, h: float
) -> tuple[float, float, float]:
    ds = s - geom.s
    u, v, local_hdg = spiral_coords(ds, geom.curv_start, geom.curv_dot)
    u, v = _apply_lateral_offset(u, v, t, local_hdg)
    x, y = _rotate_translate(u, v, geom.hdg, geom.x, geom.y)
    return x, y, h


def poly3_sth2xyz(
    geom: Poly3, s: float, t: float, h: float
) -> tuple[float, float, float]:
    ds = s - geom.s
    u = ds
    v = calc_polynom_value(geom.a, geom.b, geom.c, geom.d, ds=ds)

    # Local heading from polynomial derivative
    dv = calc_polynom_derivative(geom.b, geom.c, geom.d, ds=ds)
    local_hdg = math.atan2(dv, 1.0)

    u, v = _apply_lateral_offset(u, v, t, local_hdg)
    x, y = _rotate_translate(u, v, geom.hdg, geom.x, geom.y)
    return x, y, h


def param_poly3_sth2xyz(
    geom: ParamPoly3, s: float, t: float, h: float
) -> tuple[float, float, float]:
    ds = s - geom.s
    # Map ds to parameter p
    p = ds / geom.length if geom.p_range == "normalized" and geom.length > 0 else ds

    u = calc_polynom_value(geom.a_u, geom.b_u, geom.c_u, geom.d_u, ds=p)
    v = calc_polynom_value(geom.a_v, geom.b_v, geom.c_v, geom.d_v, ds=p)

    # Local heading from parametric derivatives
    du = calc_polynom_derivative(geom.b_u, geom.c_u, geom.d_u, ds=p)
    dv = calc_polynom_derivative(geom.b_v, geom.c_v, geom.d_v, ds=p)
    local_hdg = math.atan2(dv, du) if (du != 0.0 or dv != 0.0) else 0.0

    u, v = _apply_lateral_offset(u, v, t, local_hdg)
    x, y = _rotate_translate(u, v, geom.hdg, geom.x, geom.y)
    return x, y, h


# --- Dispatcher ---

_HANDLER_MAP = {
    Line: line_sth2xyz,
    Arc: arc_sth2xyz,
    Spiral: spiral_sth2xyz,
    Poly3: poly3_sth2xyz,
    ParamPoly3: param_poly3_sth2xyz,
}


def sth2xyz(
    geom: Geometry, s: float, t: float, h: float
) -> tuple[float, float, float]:
    """Dispatch to the appropriate handler based on geometry type."""
    handler = _HANDLER_MAP.get(type(geom))
    if handler is None:
        raise TypeError(f"Unsupported geometry type: {type(geom)}")
    return handler(geom, s, t, h)


def calc_heading(geom: Geometry, s: float) -> float:
    """Calculate the inertial heading at position s on the geometry."""
    ds = s - geom.s

    if isinstance(geom, Line):
        return geom.hdg

    if isinstance(geom, Arc):
        return geom.hdg + ds * geom.curvature

    if isinstance(geom, Spiral):
        _, _, local_hdg = spiral_coords(ds, geom.curv_start, geom.curv_dot)
        return geom.hdg + local_hdg

    if isinstance(geom, Poly3):
        dv = calc_polynom_derivative(geom.b, geom.c, geom.d, ds=ds)
        return geom.hdg + math.atan2(dv, 1.0)

    if isinstance(geom, ParamPoly3):
        p = ds / geom.length if geom.p_range == "normalized" and geom.length > 0 else ds
        du = calc_polynom_derivative(geom.b_u, geom.c_u, geom.d_u, ds=p)
        dv = calc_polynom_derivative(geom.b_v, geom.c_v, geom.d_v, ds=p)
        return geom.hdg + math.atan2(dv, du)

    raise TypeError(f"Unsupported geometry type: {type(geom)}")
