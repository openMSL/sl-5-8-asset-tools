"""Signal point geometry generator."""

from __future__ import annotations

import math

from xodr_to_geojson_caller.geometry.elevation import get_elevation
from xodr_to_geojson_caller.geometry.handlers import calc_heading, sth2xyz
from xodr_to_geojson_caller.models.road import Road

Coord3D = tuple[float, float, float]
SignalResult = tuple[Coord3D, dict]


def generate_signal_points(road: Road) -> list[SignalResult]:
    """Generate point coordinates and properties for all signals on a road."""
    results: list[SignalResult] = []

    for signal in road.signals:
        geom = road.geometry_at(signal.s)
        elev = road.elevation_at(signal.s)

        h = signal.z_offset
        if elev is not None:
            h += get_elevation(
                s=signal.s,
                t=signal.t,
                elev_a=elev.a,
                elev_b=elev.b,
                elev_c=elev.c,
                elev_d=elev.d,
                elev_s=elev.s,
            )

        x, y, z = sth2xyz(geom, s=signal.s, t=signal.t, h=h)

        # Compute heading
        hdg = calc_heading(geom, signal.s)
        if signal.orientation == "-":
            hdg += math.pi
        hdg += signal.hdg

        props = {
            "id": signal.id,
            "name": signal.name,
            "type": signal.type,
            "subtype": signal.subtype,
            "s": signal.s,
            "heading": hdg,
            "zOffset": signal.z_offset,
            "orientation": signal.orientation,
            "dynamic": signal.dynamic,
            "value": signal.value,
            "country": signal.country,
        }

        results.append(((x, y, z), props))

    return results
