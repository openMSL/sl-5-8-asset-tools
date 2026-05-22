"""Shared utility functions for geometry generators."""

from __future__ import annotations

from preview_3d.geometry.curves import calc_polynom_value
from preview_3d.models.road import Road


def get_elev_params(road: Road, s: float) -> dict:
    """Extract elevation polynomial params for get_elevation calls."""
    elev = road.elevation_at(s)
    if elev is None:
        return dict(elev_a=0.0, elev_b=0.0, elev_c=0.0, elev_d=0.0, elev_s=0.0)
    return dict(
        elev_a=elev.a, elev_b=elev.b, elev_c=elev.c, elev_d=elev.d, elev_s=elev.s
    )


def get_super_params(road: Road, s: float) -> dict:
    """Extract superelevation polynomial params."""
    se = road.superelevation_at(s)
    if se is None:
        return {}
    return dict(super_a=se.a, super_b=se.b, super_c=se.c, super_d=se.d, super_s=se.s)


def get_lane_offset_value(road: Road, s: float) -> float:
    """Get the lane offset (lateral shift of center lane) at s."""
    lo = road.lanes.lane_offset_at(s)
    if lo is None:
        return 0.0
    ds = s - lo.s
    return calc_polynom_value(lo.a, lo.b, lo.c, lo.d, ds=ds)
