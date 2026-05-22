"""Road marking geometry generator."""

from __future__ import annotations

from preview_3d.generators._utils import get_lane_offset_value
from preview_3d.geometry.curves import calc_polynom_value
from preview_3d.geometry.discretisation import generate_s_runner
from preview_3d.geometry.elevation import get_elevation
from preview_3d.geometry.handlers import sth2xyz
from preview_3d.models.lane import LaneSection
from preview_3d.models.road import Road
from preview_3d.models.roadmark import NONE

Coord3D = tuple[float, float, float]
DEFAULT_MARK_WIDTH = 0.06  # 6cm default road mark width

# (mark_type, lane_id, inner_points, outer_points)
MarkSegment = tuple[str, int, list[Coord3D], list[Coord3D]]


def generate_road_mark_points(
    road: Road,
    lane_section: LaneSection,
    step: float = 0.2,
    ls_length: float | None = None,
) -> list[MarkSegment]:
    """Generate road marking geometry segments for a lane section.

    Returns list of (mark_type, lane_id, inner_coords, outer_coords) tuples,
    each representing a continuous segment of road marking.
    """
    if ls_length is None:
        idx = road.lanes.lane_sections.index(lane_section)
        if idx + 1 < len(road.lanes.lane_sections):
            ls_length = road.lanes.lane_sections[idx + 1].s - lane_section.s
        else:
            ls_length = road.length - lane_section.s

    s_start = lane_section.s
    s_positions = generate_s_runner(length=ls_length, step=step, start=0.0)
    results: list[MarkSegment] = []

    # Collect all lanes that have road marks
    all_lanes = (
        [(0, lane_section.center_lane)]
        + [(l.id, l) for l in lane_section.right_lanes]
        + [(l.id, l) for l in lane_section.left_lanes]
    )

    for lane_id, lane in all_lanes:
        if not lane.road_marks:
            continue

        # Compute the accumulated width to this lane's boundary
        # (needed to position road marks at the lane edge)
        for rm in lane.road_marks:
            if rm.type == NONE:
                continue

            mark_width = rm.width / 2.0 if rm.width > 0.0 else DEFAULT_MARK_WIDTH

            inner_pts: list[Coord3D] = []
            outer_pts: list[Coord3D] = []

            for s_local in s_positions:
                if s_local < rm.s_offset:
                    continue

                s_global = s_start + s_local
                geom = road.geometry_at(s_global)
                elev = road.elevation_at(s_global)
                ep = {}
                if elev is not None:
                    ep = dict(
                        elev_a=elev.a,
                        elev_b=elev.b,
                        elev_c=elev.c,
                        elev_d=elev.d,
                        elev_s=elev.s,
                    )

                # Compute t-offset to this lane boundary
                t = _lane_boundary_t(lane_section, lane_id, s_local, road, s_global)
                h = get_elevation(s=s_global, t=t, **ep) if ep else 0.0

                # Inner and outer edges of the road mark
                x_in, y_in, z_in = sth2xyz(geom, s=s_global, t=t - mark_width, h=h)
                x_out, y_out, z_out = sth2xyz(geom, s=s_global, t=t + mark_width, h=h)
                inner_pts.append((x_in, y_in, z_in))
                outer_pts.append((x_out, y_out, z_out))

            if inner_pts:
                results.append((rm.type, lane_id, inner_pts, outer_pts))

    return results


def _lane_boundary_t(
    ls: LaneSection, lane_id: int, s_local: float, road: Road, s_global: float
) -> float:
    """Compute the t-coordinate of a lane boundary."""
    offset = get_lane_offset_value(road, s_global)

    if lane_id == 0:
        return offset

    if lane_id < 0:
        t = offset
        for lane in sorted(ls.right_lanes, key=lambda l: l.id, reverse=True):
            w = lane.width_at(s_local)
            if w is not None:
                ds_w = s_local - w.s_offset
                t -= calc_polynom_value(w.a, w.b, w.c, w.d, ds=ds_w)
            if lane.id == lane_id:
                break
        return t

    t = offset
    for lane in sorted(ls.left_lanes, key=lambda l: l.id):
        w = lane.width_at(s_local)
        if w is not None:
            ds_w = s_local - w.s_offset
            t += calc_polynom_value(w.a, w.b, w.c, w.d, ds=ds_w)
        if lane.id == lane_id:
            break
    return t
