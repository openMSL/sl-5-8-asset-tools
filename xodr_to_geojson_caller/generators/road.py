"""Road & lane geometry generator.

Discretises the reference line, computes lane boundary points via width
accumulation, and constructs lane/road polygons as coordinate lists.
"""

from __future__ import annotations

from xodr_to_geojson_caller.generators._utils import (
    get_elev_params,
    get_lane_offset_value,
    get_super_params,
)
from xodr_to_geojson_caller.geometry.curves import calc_polynom_value
from xodr_to_geojson_caller.geometry.discretisation import generate_s_runner
from xodr_to_geojson_caller.geometry.elevation import get_elevation, get_projected_width
from xodr_to_geojson_caller.geometry.handlers import sth2xyz
from xodr_to_geojson_caller.models.lane import LaneSection
from xodr_to_geojson_caller.models.road import Road

Coord3D = tuple[float, float, float]


def generate_center_line(road: Road, step: float = 0.2) -> list[Coord3D]:
    """Generate the reference line (center lane) as a list of 3D points."""
    s_positions = generate_s_runner(length=road.length, step=step)
    points: list[Coord3D] = []

    for s in s_positions:
        geom = road.geometry_at(s)
        elev = road.elevation_at(s)
        h = 0.0
        if elev is not None:
            h = get_elevation(
                s=s,
                t=0.0,
                elev_a=elev.a,
                elev_b=elev.b,
                elev_c=elev.c,
                elev_d=elev.d,
                elev_s=elev.s,
            )
        x, y, z = sth2xyz(geom, s=s, t=0.0, h=h)
        points.append((x, y, z))

    return points


def generate_lane_ground_points(
    road: Road,
    lane_section: LaneSection,
    step: float = 0.2,
    ls_length: float | None = None,
) -> dict[int, list[Coord3D]]:
    """Compute lane boundary points for all lanes in a lane section.

    Returns a dict mapping lane boundary ID → list of 3D points.
    Boundary ID corresponds to the lane whose outer edge it represents:
    - ID 0: center lane (reference line + lane offset)
    - ID 1, 2, ...: left lane boundaries
    - ID -1, -2, ...: right lane boundaries
    """
    if ls_length is None:
        # Find next lane section to determine length
        idx = road.lanes.lane_sections.index(lane_section)
        if idx + 1 < len(road.lanes.lane_sections):
            ls_length = road.lanes.lane_sections[idx + 1].s - lane_section.s
        else:
            ls_length = road.length - lane_section.s

    s_start = lane_section.s
    s_positions = generate_s_runner(length=ls_length, step=step, start=0.0)

    # Collect all lane IDs we need boundaries for
    all_ids = sorted(
        [l.id for l in lane_section.right_lanes]
        + [0]
        + [l.id for l in lane_section.left_lanes]
    )
    points: dict[int, list[Coord3D]] = {lid: [] for lid in all_ids}

    for s_local in s_positions:
        s_global = s_start + s_local
        geom = road.geometry_at(s_global)
        elev_params = get_elev_params(road, s_global)
        super_params = get_super_params(road, s_global)
        offset = get_lane_offset_value(road, s_global)

        # Center lane boundary (ID 0)
        t_center = offset
        pw_center = get_projected_width(t_center, s=s_global, **super_params)
        h_center = get_elevation(s=s_global, t=t_center, **elev_params, **super_params)
        x, y, z = sth2xyz(geom, s=s_global, t=pw_center, h=h_center)
        points[0].append((x, y, z))

        # Right lanes (negative IDs, accumulate width in negative t direction)
        t_accum = offset
        for lane in sorted(lane_section.right_lanes, key=lambda l: l.id, reverse=True):
            w = lane.width_at(s_local)
            if w is not None:
                ds_w = s_local - w.s_offset
                width = calc_polynom_value(w.a, w.b, w.c, w.d, ds=ds_w)
            else:
                width = 0.0
            t_accum -= width
            pw = get_projected_width(
                t_accum, s=s_global, level=lane.level, **super_params
            )
            h = get_elevation(
                s=s_global, t=t_accum, level=lane.level, **elev_params, **super_params
            )
            x, y, z = sth2xyz(geom, s=s_global, t=pw, h=h)
            points[lane.id].append((x, y, z))

        # Left lanes (positive IDs, accumulate width in positive t direction)
        t_accum = offset
        for lane in sorted(lane_section.left_lanes, key=lambda l: l.id):
            w = lane.width_at(s_local)
            if w is not None:
                ds_w = s_local - w.s_offset
                width = calc_polynom_value(w.a, w.b, w.c, w.d, ds=ds_w)
            else:
                width = 0.0
            t_accum += width
            pw = get_projected_width(
                t_accum, s=s_global, level=lane.level, **super_params
            )
            h = get_elevation(
                s=s_global, t=t_accum, level=lane.level, **elev_params, **super_params
            )
            x, y, z = sth2xyz(geom, s=s_global, t=pw, h=h)
            points[lane.id].append((x, y, z))

    return points


def generate_lane_polygons(
    lane_section: LaneSection,
    boundary_points: dict[int, list[Coord3D]],
) -> list[tuple[int, list[Coord3D]]]:
    """Build closed polygon rings for each lane from boundary points.

    Returns list of (lane_id, polygon_coords) tuples.
    """
    polygons: list[tuple[int, list[Coord3D]]] = []

    # Right lanes: boundary between ID i and ID (i-1)
    right_ids = sorted([l.id for l in lane_section.right_lanes], reverse=True)
    for lane_id in right_ids:
        inner_id = lane_id + 1 if lane_id + 1 in boundary_points else 0
        if inner_id not in boundary_points or lane_id not in boundary_points:
            continue
        inner = boundary_points[inner_id]
        outer = boundary_points[lane_id]
        ring = list(inner) + list(reversed(outer))
        ring.append(ring[0])
        polygons.append((lane_id, ring))

    # Left lanes: boundary between ID i and ID (i+1)
    left_ids = sorted([l.id for l in lane_section.left_lanes])
    for lane_id in left_ids:
        inner_id = lane_id - 1 if lane_id - 1 in boundary_points else 0
        if inner_id not in boundary_points or lane_id not in boundary_points:
            continue
        inner = boundary_points[inner_id]
        outer = boundary_points[lane_id]
        ring = list(inner) + list(reversed(outer))
        ring.append(ring[0])
        polygons.append((lane_id, ring))

    return polygons


def generate_road_polygon(
    lane_section: LaneSection,
    boundary_points: dict[int, list[Coord3D]],
) -> list[Coord3D]:
    """Build the overall road polygon from outermost lane boundaries."""
    all_ids = sorted(boundary_points.keys())
    if len(all_ids) < 2:
        return []

    outermost_left = max(all_ids)
    outermost_right = min(all_ids)

    left_boundary = boundary_points[outermost_left]
    right_boundary = boundary_points[outermost_right]

    ring = list(left_boundary) + list(reversed(right_boundary))
    ring.append(ring[0])
    return ring
