from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple, Union
import math

Number = Union[int, float]


@dataclass(frozen=True, slots=True)
class Vec2D:
    """Small 2D vector helper used across xodr tools."""

    x: float
    y: float

    @staticmethod
    def from_tuple(t: Sequence[Number]) -> "Vec2D":
        # Accept any 2-sequence of numbers.
        return Vec2D(float(t[0]), float(t[1]))

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def __add__(self, other: "Vec2D") -> "Vec2D":
        return Vec2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2D") -> "Vec2D":
        return Vec2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Number) -> "Vec2D":
        return Vec2D(self.x * float(scalar), self.y * float(scalar))

    def __rmul__(self, scalar: Number) -> "Vec2D":
        return self.__mul__(scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def distance_to(self, other: "Vec2D") -> float:
        return (self - other).length()

    def rotate(self, radians: float) -> "Vec2D":
        # Rotate around origin by angle in radians.
        c = math.cos(radians)
        s = math.sin(radians)
        return Vec2D(self.x * c - self.y * s, self.x * s + self.y * c)

    def end_position(self, heading: float, length: float) -> "Vec2D":
        # Calculate end position from this start position, heading and length.
        end_x = self.x + math.cos(heading) * float(length)
        end_y = self.y + math.sin(heading) * float(length)
        return Vec2D(end_x, end_y)


class Box2D:
    """2D axis-aligned bounding box.

    Provides both camelCase (xMin/xMax/...) and snake_case (x_min/x_max/...) attribute
    access for compatibility with existing modules.
    """

    __slots__ = ("_x_min", "_y_min", "_x_max", "_y_max")

    def __init__(
        self,
        x_min: float = math.inf,
        y_min: float = math.inf,
        x_max: float = -math.inf,
        y_max: float = -math.inf,
    ) -> None:
        self._x_min = float(x_min)
        self._y_min = float(y_min)
        self._x_max = float(x_max)
        self._y_max = float(y_max)

    # ---- Compatibility properties (snake_case) ----
    @property
    def x_min(self) -> float:
        return self._x_min

    @x_min.setter
    def x_min(self, v: Number) -> None:
        self._x_min = float(v)

    @property
    def y_min(self) -> float:
        return self._y_min

    @y_min.setter
    def y_min(self, v: Number) -> None:
        self._y_min = float(v)

    @property
    def x_max(self) -> float:
        return self._x_max

    @x_max.setter
    def x_max(self, v: Number) -> None:
        self._x_max = float(v)

    @property
    def y_max(self) -> float:
        return self._y_max

    @y_max.setter
    def y_max(self, v: Number) -> None:
        self._y_max = float(v)

    # ---- Compatibility properties (camelCase) ----
    @property
    def xMin(self) -> float:
        return self._x_min

    @xMin.setter
    def xMin(self, v: Number) -> None:
        self._x_min = float(v)

    @property
    def yMin(self) -> float:
        return self._y_min

    @yMin.setter
    def yMin(self, v: Number) -> None:
        self._y_min = float(v)

    @property
    def xMax(self) -> float:
        return self._x_max

    @xMax.setter
    def xMax(self, v: Number) -> None:
        self._x_max = float(v)

    @property
    def yMax(self) -> float:
        return self._y_max

    @yMax.setter
    def yMax(self, v: Number) -> None:
        self._y_max = float(v)

    # ---- Construction helpers ----
    @classmethod
    def invalid(cls) -> "Box2D":
        # Start with an "empty" box that can be expanded by points/boxes.
        return cls(math.inf, math.inf, -math.inf, -math.inf)

    @classmethod
    def from_points(cls, points: Iterable[Union[Vec2D, Sequence[Number]]]) -> "Box2D":
        # Build a box from any iterable of points.
        box = cls.invalid()
        for pos in points:
            if isinstance(pos, Vec2D):
                box.expand_by_pos(pos)
            else:
                box.expand_by_pos(Vec2D(float(pos[0]), float(pos[1])))
        return box

    # ---- Derived values ----
    def is_valid(self) -> bool:
        return self._x_min <= self._x_max and self._y_min <= self._y_max

    def width(self) -> float:
        return self._x_max - self._x_min

    def height(self) -> float:
        return self._y_max - self._y_min

    def center(self) -> Vec2D:
        return Vec2D(
            (self._x_min + self._x_max) * 0.5, (self._y_min + self._y_max) * 0.5
        )

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self._x_min, self._y_min, self._x_max, self._y_max)

    # ---- Spatial ops ----
    def contains(self, x: Number, y: Number) -> bool:
        fx, fy = float(x), float(y)
        return self._x_min <= fx <= self._x_max and self._y_min <= fy <= self._y_max

    def intersects(self, other: "Box2D") -> bool:
        # True if rectangles overlap with positive area.
        x_overlap = max(
            0.0, min(self._x_max, other._x_max) - max(self._x_min, other._x_min)
        )
        y_overlap = max(
            0.0, min(self._y_max, other._y_max) - max(self._y_min, other._y_min)
        )
        return x_overlap > 0.0 and y_overlap > 0.0

    # Backwards-compatible name used in xodr_trim_to_box
    def intersection(self, box2: "Box2D") -> bool:
        return self.intersects(box2)

    def expand_by_box(self, box_expand: "Box2D") -> None:
        if box_expand._x_min < self._x_min:
            self._x_min = box_expand._x_min
        if box_expand._x_max > self._x_max:
            self._x_max = box_expand._x_max
        if box_expand._y_min < self._y_min:
            self._y_min = box_expand._y_min
        if box_expand._y_max > self._y_max:
            self._y_max = box_expand._y_max

    def expand_by_pos(self, pos: Vec2D) -> None:
        if pos.x < self._x_min:
            self._x_min = pos.x
        if pos.x > self._x_max:
            self._x_max = pos.x
        if pos.y < self._y_min:
            self._y_min = pos.y
        if pos.y > self._y_max:
            self._y_max = pos.y

    def expand_by_seam(self, seam: Number) -> None:
        s = float(seam)
        self._x_min -= s
        self._x_max += s
        self._y_min -= s
        self._y_max += s
