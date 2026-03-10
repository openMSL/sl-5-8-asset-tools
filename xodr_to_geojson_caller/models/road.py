"""Road-level dataclasses: Road, PlanView, ElevationProfile, LateralProfile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from xodr_to_geojson_caller.models.geometry import Geometry
from xodr_to_geojson_caller.models.lane import Lanes
from xodr_to_geojson_caller.models.object import RoadObject
from xodr_to_geojson_caller.models.signal import Signal


@dataclass
class Polynomial:
    """Generic cubic polynomial with s-offset: f(ds) = a + b*ds + c*ds² + d*ds³."""

    s: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0


@dataclass
class ElevationProfile:
    """Elevation profile as ordered list of elevation polynomials."""

    elevations: list[Polynomial] = field(default_factory=list)


@dataclass
class LateralProfile:
    """Superelevation and shape profiles."""

    super_elevations: list[Polynomial] = field(default_factory=list)
    shapes: list[tuple[float, list[Polynomial]]] = field(default_factory=list)


@dataclass
class Road:
    """An OpenDRIVE road element."""

    id: str = ""
    name: str = ""
    length: float = 0.0
    junction: str = "-1"
    plan_view: list[Geometry] = field(default_factory=list)
    elevation_profile: ElevationProfile = field(default_factory=ElevationProfile)
    lateral_profile: LateralProfile = field(default_factory=LateralProfile)
    lanes: Lanes = field(default_factory=Lanes)
    objects: list[RoadObject] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)

    def geometry_at(self, s: float) -> Geometry:
        """Find the geometry segment containing s-coordinate."""
        result = self.plan_view[0]
        for geom in self.plan_view:
            if geom.s <= s:
                result = geom
            else:
                break
        return result

    def elevation_at(self, s: float) -> Polynomial | None:
        """Find the elevation polynomial at s-coordinate."""
        if not self.elevation_profile.elevations:
            return None
        result = self.elevation_profile.elevations[0]
        for elev in self.elevation_profile.elevations:
            if elev.s <= s:
                result = elev
            else:
                break
        return result

    def superelevation_at(self, s: float) -> Polynomial | None:
        """Find the superelevation polynomial at s-coordinate."""
        if not self.lateral_profile.super_elevations:
            return None
        result = self.lateral_profile.super_elevations[0]
        for se in self.lateral_profile.super_elevations:
            if se.s <= s:
                result = se
            else:
                break
        return result
