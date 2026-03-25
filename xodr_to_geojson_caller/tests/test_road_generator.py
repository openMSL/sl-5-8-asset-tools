"""Tests for road & lane geometry generators."""

import math
import textwrap

import pytest

from xodr_to_geojson_caller.generators.road import (
    generate_center_line,
    generate_lane_ground_points,
    generate_lane_polygons,
    generate_road_polygon,
)
from xodr_to_geojson_caller.models.geometry import Line
from xodr_to_geojson_caller.models.lane import Lane, LaneSection, LaneWidth, Lanes
from xodr_to_geojson_caller.models.road import ElevationProfile, Polynomial, Road


def _simple_road() -> Road:
    """A straight 100m road with one 3.5m lane on each side."""
    return Road(
        id="1",
        name="Test",
        length=100.0,
        junction="-1",
        plan_view=[Line(s=0.0, x=0.0, y=0.0, hdg=0.0, length=100.0)],
        elevation_profile=ElevationProfile(
            elevations=[Polynomial(s=0.0, a=0.0, b=0.0, c=0.0, d=0.0)]
        ),
        lanes=Lanes(
            lane_sections=[
                LaneSection(
                    s=0.0,
                    left_lanes=[
                        Lane(
                            id=1,
                            type="driving",
                            widths=[LaneWidth(s_offset=0.0, a=3.5)],
                        ),
                    ],
                    center_lane=Lane(id=0, type="none"),
                    right_lanes=[
                        Lane(
                            id=-1,
                            type="driving",
                            widths=[LaneWidth(s_offset=0.0, a=3.5)],
                        ),
                    ],
                )
            ],
        ),
    )


class TestGenerateCenterLine:
    def test_returns_points(self):
        road = _simple_road()
        points = generate_center_line(road, step=10.0)
        assert len(points) > 2
        # First point at origin
        assert points[0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)
        # Last point at (100, 0, 0)
        assert points[-1] == pytest.approx((100.0, 0.0, 0.0), abs=1e-6)

    def test_points_progress_along_x(self):
        road = _simple_road()
        points = generate_center_line(road, step=10.0)
        x_coords = [p[0] for p in points]
        assert x_coords == sorted(x_coords)


class TestGenerateLaneGroundPoints:
    def test_returns_dict_with_lane_ids(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=10.0)
        # Should have keys for all lane boundaries: -1, 0, 1
        assert 0 in points
        assert 1 in points
        assert -1 in points

    def test_center_lane_at_origin(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=50.0)
        # Center lane (id=0) boundary at t=0 → y≈0
        for p in points[0]:
            assert p[1] == pytest.approx(0.0, abs=1e-6)

    def test_right_lane_negative_y(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=50.0)
        # Right lane boundary (id=-1) at t=-3.5
        for p in points[-1]:
            assert p[1] == pytest.approx(-3.5, abs=0.1)

    def test_left_lane_positive_y(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=50.0)
        for p in points[1]:
            assert p[1] == pytest.approx(3.5, abs=0.1)


class TestGenerateLanePolygons:
    def test_returns_polygons(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=10.0)
        polygons = generate_lane_polygons(ls, points)
        # One polygon per non-center lane: left(1) + right(-1) = 2
        assert len(polygons) == 2

    def test_polygon_is_closed_ring(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=10.0)
        polygons = generate_lane_polygons(ls, points)
        for lane_id, coords in polygons:
            assert coords[0] == coords[-1]

    def test_polygon_has_properties(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=10.0)
        polygons = generate_lane_polygons(ls, points)
        lane_ids = [lid for lid, _ in polygons]
        assert 1 in lane_ids
        assert -1 in lane_ids


class TestGenerateRoadPolygon:
    def test_returns_closed_ring(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        points = generate_lane_ground_points(road, ls, step=10.0)
        polygon = generate_road_polygon(ls, points)
        assert polygon[0] == polygon[-1]
        assert len(polygon) > 4


class TestEmptyPlanView:
    """Road with no geometry should raise ValueError on geometry_at."""

    def test_geometry_at_raises_on_empty_planview(self):
        road = Road(id="empty", name="Empty", length=10.0)
        with pytest.raises(ValueError, match="empty planView"):
            road.geometry_at(0.0)
