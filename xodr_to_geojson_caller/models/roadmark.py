"""Road marking dataclasses and constants."""

from __future__ import annotations

from dataclasses import dataclass


# Road mark type constants
SOLID = "solid"
BROKEN = "broken"
SOLID_SOLID = "solid solid"
SOLID_BROKEN = "solid broken"
BROKEN_SOLID = "broken solid"
BROKEN_BROKEN = "broken broken"
EDGE = "edge"
GRASS = "grass"
CURB = "curb"
NONE = "none"
CUSTOM = "custom"
BOTTS_DOTS = "botts dots"


@dataclass
class RoadMark:
    """Road marking on a lane boundary."""

    s_offset: float = 0.0
    type: str = NONE
    weight: str = ""
    color: str = "standard"
    width: float = 0.0
    lane_change: str = ""
    material: str = ""
    height: float = 0.0
