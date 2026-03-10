"""Road object dataclasses: Object, Outline, Repeat, Bridge, Tunnel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CornerRoad:
    """Outline corner in road coordinates (s, t, dz)."""

    s: float = 0.0
    t: float = 0.0
    dz: float = 0.0
    height: float = 0.0


@dataclass
class CornerLocal:
    """Outline corner in local coordinates (u, v, z)."""

    u: float = 0.0
    v: float = 0.0
    z: float = 0.0
    height: float = 0.0


@dataclass
class Outline:
    """Object outline (cornerRoad or cornerLocal specification)."""

    corner_road: list[CornerRoad] = field(default_factory=list)
    corner_local: list[CornerLocal] = field(default_factory=list)


@dataclass
class ObjectRepeat:
    """Repeated/continuous object along s-coordinate."""

    s: float = 0.0
    length: float = 0.0
    distance: float = 0.0
    t_start: float = 0.0
    t_end: float = 0.0
    width_start: float = 0.0
    width_end: float = 0.0
    z_offset_start: float = 0.0
    z_offset_end: float = 0.0


@dataclass
class RoadObject:
    """An object on or beside the road (parking, building, barrier, etc.)."""

    id: str = ""
    name: str = ""
    type: str = ""
    s: float = 0.0
    t: float = 0.0
    z_offset: float = 0.0
    hdg: float = 0.0
    length: float = 0.0
    width: float = 0.0
    radius: float = 0.0
    height: float = 0.0
    orientation: str = ""
    valid_length: float = 0.0
    subtype: str = ""
    outlines: list[Outline] = field(default_factory=list)
    repeats: list[ObjectRepeat] = field(default_factory=list)
