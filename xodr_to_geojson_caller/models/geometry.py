"""OpenDRIVE geometry type dataclasses.

Each geometry type represents a segment of a road's reference line (planView).
All share base attributes (s, x, y, hdg, length) and add type-specific params.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GeometryBase:
    """Base attributes shared by all planView geometry elements."""

    s: float  # s-coordinate of geometry start along reference line
    x: float  # inertial x position at start
    y: float  # inertial y position at start
    hdg: float  # inertial heading at start (radians)
    length: float  # length of this geometry segment

    @property
    def s_end(self) -> float:
        return self.s + self.length


@dataclass(frozen=True, slots=True)
class Line(GeometryBase):
    """Straight line segment."""

    pass


@dataclass(frozen=True, slots=True)
class Arc(GeometryBase):
    """Circular arc with constant curvature."""

    curvature: float  # 1/radius; positive = left turn

    @property
    def radius(self) -> float:
        return 1.0 / abs(self.curvature) if self.curvature != 0 else math.inf


@dataclass(frozen=True, slots=True)
class Spiral(GeometryBase):
    """Euler spiral (clothoid) with linearly varying curvature."""

    curv_start: float
    curv_end: float

    @property
    def curv_dot(self) -> float:
        """Rate of curvature change per meter."""
        return (
            (self.curv_end - self.curv_start) / self.length if self.length > 0 else 0.0
        )


@dataclass(frozen=True, slots=True)
class Poly3(GeometryBase):
    """Cubic polynomial: v(ds) = a + b*ds + c*ds² + d*ds³."""

    a: float
    b: float
    c: float
    d: float


@dataclass(frozen=True, slots=True)
class ParamPoly3(GeometryBase):
    """Parametric cubic polynomial with independent u(p) and v(p).

    p_range controls the parameter domain:
    - "arcLength": p ∈ [0, length]
    - "normalized": p ∈ [0, 1]
    """

    a_u: float
    b_u: float
    c_u: float
    d_u: float
    a_v: float
    b_v: float
    c_v: float
    d_v: float
    p_range: Literal["arcLength", "normalized"] = "arcLength"


# Union type for any geometry
Geometry = Line | Arc | Spiral | Poly3 | ParamPoly3
