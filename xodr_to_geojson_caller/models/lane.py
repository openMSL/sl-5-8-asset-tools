"""Lane-related dataclasses: Lane, LaneSection, Lanes, Width, Height."""

from __future__ import annotations

from dataclasses import dataclass, field

from xodr_to_geojson_caller.models.roadmark import RoadMark


@dataclass
class LaneWidth:
    """Lane width polynomial: w(ds) = a + b*ds + c*ds² + d*ds³."""

    s_offset: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0


@dataclass
class LaneHeight:
    """Lane height offsets (inner and outer edge)."""

    s_offset: float = 0.0
    inner: float = 0.0
    outer: float = 0.0


@dataclass
class Lane:
    """A single lane within a lane section."""

    id: int = 0
    type: str = ""
    level: bool = False
    widths: list[LaneWidth] = field(default_factory=list)
    heights: list[LaneHeight] = field(default_factory=list)
    road_marks: list[RoadMark] = field(default_factory=list)

    def width_at(self, s_local: float) -> LaneWidth | None:
        """Find the width polynomial at local s-offset."""
        if not self.widths:
            return None
        result = self.widths[0]
        for w in self.widths:
            if w.s_offset <= s_local:
                result = w
            else:
                break
        return result

    def height_at(self, s_local: float) -> LaneHeight | None:
        """Find the height attributes at local s-offset."""
        if not self.heights:
            return None
        result = self.heights[0]
        for h in self.heights:
            if h.s_offset <= s_local:
                result = h
            else:
                break
        return result


@dataclass
class LaneOffset:
    """Lane offset polynomial (shifts center lane laterally)."""

    s: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0


@dataclass
class LaneSection:
    """A lane section containing left, center, and right lanes."""

    s: float = 0.0
    left_lanes: list[Lane] = field(default_factory=list)
    center_lane: Lane = field(default_factory=Lane)
    right_lanes: list[Lane] = field(default_factory=list)

    @property
    def all_lanes(self) -> list[Lane]:
        """All lanes sorted by ID (left positive → center 0 → right negative)."""
        return sorted(
            self.left_lanes + [self.center_lane] + self.right_lanes,
            key=lambda l: l.id,
            reverse=True,
        )

    @property
    def min_lane_id(self) -> int:
        return min(l.id for l in self.right_lanes) if self.right_lanes else 0

    @property
    def max_lane_id(self) -> int:
        return max(l.id for l in self.left_lanes) if self.left_lanes else 0


@dataclass
class Lanes:
    """Container for lane offsets and lane sections of a road."""

    lane_offsets: list[LaneOffset] = field(default_factory=list)
    lane_sections: list[LaneSection] = field(default_factory=list)

    def lane_offset_at(self, s: float) -> LaneOffset | None:
        """Find the lane offset polynomial at s-coordinate."""
        if not self.lane_offsets:
            return None
        result = self.lane_offsets[0]
        for lo in self.lane_offsets:
            if lo.s <= s:
                result = lo
            else:
                break
        return result

    def lane_section_at(self, s: float) -> LaneSection | None:
        """Find the lane section at s-coordinate."""
        if not self.lane_sections:
            return None
        result = self.lane_sections[0]
        for ls in self.lane_sections:
            if ls.s <= s:
                result = ls
            else:
                break
        return result
