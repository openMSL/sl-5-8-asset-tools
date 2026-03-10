"""Junction dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JunctionLaneLink:
    """Lane link within a junction connection."""

    from_lane: int = 0
    to_lane: int = 0


@dataclass
class JunctionConnection:
    """Connection between roads within a junction."""

    id: str = ""
    incoming_road: str = ""
    connecting_road: str = ""
    contact_point: str = ""
    lane_links: list[JunctionLaneLink] = field(default_factory=list)


@dataclass
class Junction:
    """A junction connecting multiple roads."""

    id: str = ""
    name: str = ""
    connections: list[JunctionConnection] = field(default_factory=list)
