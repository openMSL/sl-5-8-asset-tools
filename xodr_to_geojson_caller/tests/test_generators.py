"""Tests for object, signal, and road mark generators."""

import pytest

from xodr_to_geojson_caller.generators.object import generate_object_geometries
from xodr_to_geojson_caller.generators.signal import generate_signal_points
from xodr_to_geojson_caller.generators.roadmark import generate_road_mark_points
from xodr_to_geojson_caller.models.geometry import Line
from xodr_to_geojson_caller.models.lane import Lane, LaneSection, LaneWidth, Lanes
from xodr_to_geojson_caller.models.object import (
    CornerRoad,
    ObjectRepeat,
    Outline,
    RoadObject,
)
from xodr_to_geojson_caller.models.road import ElevationProfile, Polynomial, Road
from xodr_to_geojson_caller.models.roadmark import RoadMark
from xodr_to_geojson_caller.models.signal import Signal


def _simple_road(**kwargs) -> Road:
    defaults = dict(
        id="1", name="Test", length=100.0, junction="-1",
        plan_view=[Line(s=0.0, x=0.0, y=0.0, hdg=0.0, length=100.0)],
        elevation_profile=ElevationProfile(
            elevations=[Polynomial(s=0.0, a=0.0, b=0.0, c=0.0, d=0.0)]
        ),
        lanes=Lanes(
            lane_sections=[
                LaneSection(
                    s=0.0,
                    center_lane=Lane(id=0, type="none"),
                    right_lanes=[
                        Lane(id=-1, type="driving",
                             widths=[LaneWidth(s_offset=0.0, a=3.5)],
                             road_marks=[RoadMark(s_offset=0.0, type="solid", width=0.15)]),
                    ],
                )
            ],
        ),
    )
    defaults.update(kwargs)
    return Road(**defaults)


class TestObjectGenerator:
    def test_simple_point_object(self):
        road = _simple_road(objects=[
            RoadObject(id="o1", s=10.0, t=5.0, z_offset=0.0),
        ])
        geoms = generate_object_geometries(road)
        assert len(geoms) == 1
        geom_type, coords, props = geoms[0]
        assert geom_type == "Point"
        assert props["id"] == "o1"

    def test_rectangular_object(self):
        road = _simple_road(objects=[
            RoadObject(id="o2", s=10.0, t=5.0, length=4.0, width=2.0),
        ])
        geoms = generate_object_geometries(road)
        assert len(geoms) == 1
        geom_type, coords, props = geoms[0]
        assert geom_type == "Polygon"

    def test_circular_object(self):
        road = _simple_road(objects=[
            RoadObject(id="o3", s=10.0, t=5.0, radius=2.0),
        ])
        geoms = generate_object_geometries(road)
        geom_type, _, _ = geoms[0]
        assert geom_type == "Point"

    def test_outline_object(self):
        road = _simple_road(objects=[
            RoadObject(
                id="o4", s=20.0, t=-6.0,
                outlines=[Outline(corner_road=[
                    CornerRoad(s=20.0, t=-5.0),
                    CornerRoad(s=25.0, t=-5.0),
                    CornerRoad(s=25.0, t=-7.5),
                    CornerRoad(s=20.0, t=-7.5),
                ])],
            ),
        ])
        geoms = generate_object_geometries(road)
        geom_type, coords, _ = geoms[0]
        assert geom_type == "Polygon"
        assert len(coords) >= 4


class TestSignalGenerator:
    def test_signal_point(self):
        road = _simple_road(signals=[
            Signal(id="s1", s=30.0, t=-4.0, z_offset=3.5, orientation="+"),
        ])
        points = generate_signal_points(road)
        assert len(points) == 1
        coords, props = points[0]
        assert props["id"] == "s1"
        assert len(coords) == 3  # x, y, z

    def test_signal_minus_orientation_flips_heading(self):
        road = _simple_road(signals=[
            Signal(id="s2", s=30.0, t=-4.0, z_offset=0.0, orientation="-"),
        ])
        points = generate_signal_points(road)
        _, props = points[0]
        import math
        assert abs(props["heading"]) > 0  # heading should be non-zero (flipped)


class TestRoadMarkGenerator:
    def test_generates_mark_points(self):
        road = _simple_road()
        ls = road.lanes.lane_sections[0]
        marks = generate_road_mark_points(road, ls, step=10.0)
        assert len(marks) > 0
