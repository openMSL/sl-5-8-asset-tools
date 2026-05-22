"""Object geometry generator."""

from __future__ import annotations

import logging
import math

from preview_3d.generators._utils import get_elev_params
from preview_3d.geometry.elevation import get_elevation
from preview_3d.geometry.handlers import sth2xyz
from preview_3d.models.road import Road

logger = logging.getLogger(__name__)

Coord3D = tuple[float, float, float]
# Each result is (geom_type, coordinates, properties)
ObjectGeometry = tuple[str, list[Coord3D] | Coord3D, dict]


def _obj_props(obj) -> dict:
    return {
        "id": obj.id,
        "name": obj.name,
        "type": obj.type,
        "s": obj.s,
        "t": obj.t,
        "heading": obj.hdg,
        "zOffset": obj.z_offset,
    }


def generate_object_geometries(road: Road) -> list[ObjectGeometry]:
    """Generate geometry for all objects on a road."""
    results: list[ObjectGeometry] = []

    for obj in road.objects:
        if obj.repeats:
            logger.debug(
                "Object '%s' has %d repeat element(s) which are not yet supported",
                obj.id,
                len(obj.repeats),
            )

        props = _obj_props(obj)
        geom = road.geometry_at(obj.s)
        ep = get_elev_params(road, obj.s)
        h = get_elevation(s=obj.s, t=obj.t, **ep) + obj.z_offset

        if obj.outlines:
            # Complex outlines
            for outline in obj.outlines:
                coords: list[Coord3D] = []
                if outline.corner_road:
                    for cr in outline.corner_road:
                        g = road.geometry_at(cr.s)
                        h_cr = (
                            get_elevation(s=cr.s, t=cr.t, **get_elev_params(road, cr.s))
                            + cr.dz
                        )
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
            # Rectangular object rotated by obj.hdg
            half_l = obj.length / 2.0
            half_w = obj.width / 2.0
            cos_h = math.cos(obj.hdg)
            sin_h = math.sin(obj.hdg)
            local_corners = [
                (-half_l, -half_w),
                (+half_l, -half_w),
                (+half_l, +half_w),
                (-half_l, +half_w),
            ]
            corners = [
                (obj.s + du * cos_h - dv * sin_h, obj.t + du * sin_h + dv * cos_h)
                for du, dv in local_corners
            ]
            coords = []
            for cs, ct in corners:
                g = road.geometry_at(cs)
                h_c = (
                    get_elevation(s=cs, t=ct, **get_elev_params(road, cs))
                    + obj.z_offset
                )
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
