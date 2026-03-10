"""Object geometry generator."""

from __future__ import annotations

import math

from xodr_to_geojson_caller.geometry.elevation import get_elevation
from xodr_to_geojson_caller.geometry.handlers import sth2xyz
from xodr_to_geojson_caller.models.road import Road

Coord3D = tuple[float, float, float]
# Each result is (geom_type, coordinates, properties)
ObjectGeometry = tuple[str, list[Coord3D] | Coord3D, dict]


def _elev_params(road: Road, s: float) -> dict:
    elev = road.elevation_at(s)
    if elev is None:
        return dict(elev_a=0.0, elev_b=0.0, elev_c=0.0, elev_d=0.0, elev_s=0.0)
    return dict(elev_a=elev.a, elev_b=elev.b, elev_c=elev.c, elev_d=elev.d, elev_s=elev.s)


def _obj_props(obj) -> dict:
    return {
        "id": obj.id, "name": obj.name, "type": obj.type,
        "s": obj.s, "t": obj.t, "heading": obj.hdg,
        "zOffset": obj.z_offset,
    }


def generate_object_geometries(road: Road) -> list[ObjectGeometry]:
    """Generate geometry for all objects on a road."""
    results: list[ObjectGeometry] = []

    for obj in road.objects:
        props = _obj_props(obj)
        geom = road.geometry_at(obj.s)
        ep = _elev_params(road, obj.s)
        h = get_elevation(s=obj.s, t=obj.t, **ep) + obj.z_offset

        if obj.outlines:
            # Complex outlines
            for outline in obj.outlines:
                coords: list[Coord3D] = []
                if outline.corner_road:
                    for cr in outline.corner_road:
                        g = road.geometry_at(cr.s)
                        h_cr = get_elevation(s=cr.s, t=cr.t, **_elev_params(road, cr.s)) + cr.dz
                        x, y, z = sth2xyz(g, s=cr.s, t=cr.t, h=h_cr)
                        coords.append((x, y, z))
                elif outline.corner_local:
                    for cl in outline.corner_local:
                        g = road.geometry_at(obj.s)
                        h_cl = get_elevation(s=obj.s, t=obj.t, **ep) + cl.z
                        x, y, z = sth2xyz(g, s=obj.s + cl.u, t=obj.t + cl.v, h=h_cl)
                        coords.append((x, y, z))
                if coords:
                    coords.append(coords[0])  # close ring
                    results.append(("Polygon", coords, props))

        elif obj.length > 0.0 and obj.width > 0.0 and obj.radius == 0.0:
            # Rectangular object
            half_l = obj.length / 2.0
            half_w = obj.width / 2.0
            corners = [
                (obj.s - half_l, obj.t - half_w),
                (obj.s + half_l, obj.t - half_w),
                (obj.s + half_l, obj.t + half_w),
                (obj.s - half_l, obj.t + half_w),
            ]
            coords = []
            for cs, ct in corners:
                g = road.geometry_at(cs)
                h_c = get_elevation(s=cs, t=ct, **_elev_params(road, cs)) + obj.z_offset
                x, y, z = sth2xyz(g, s=cs, t=ct, h=h_c)
                coords.append((x, y, z))
            coords.append(coords[0])
            results.append(("Polygon", coords, props))

        else:
            # Point object (including circular — radius stored as property)
            x, y, z = sth2xyz(geom, s=obj.s, t=obj.t, h=h)
            if obj.radius > 0.0:
                props["radius"] = obj.radius
            results.append(("Point", (x, y, z), props))

    return results
