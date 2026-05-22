"""OpenDRIVE root, header, and geo-reference dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from preview_3d.models.junction import Junction
from preview_3d.models.road import Road


@dataclass
class GeoReference:
    """Coordinate reference system from <geoReference> element."""

    proj4: str = ""
    epsg: str = ""


@dataclass
class Header:
    """OpenDRIVE file header."""

    rev_major: int = 0
    rev_minor: int = 0
    name: str = ""
    version: str = ""
    date: str = ""
    north: float = 0.0
    south: float = 0.0
    east: float = 0.0
    west: float = 0.0
    geo_reference: GeoReference = field(default_factory=GeoReference)


@dataclass
class OpenDRIVE:
    """Root OpenDRIVE data structure."""

    header: Header = field(default_factory=Header)
    roads: list[Road] = field(default_factory=list)
    junctions: list[Junction] = field(default_factory=list)
