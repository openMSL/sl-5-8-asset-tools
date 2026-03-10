"""Tests for OpenDRIVE XML parser."""

import textwrap

import pytest

from xodr_to_geojson_caller.parser.xodr_parser import parse_opendrive_string


MINIMAL_XODR = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenDRIVE>
        <header revMajor="1" revMinor="6" name="TestRoad" version="1.0"
                date="2024-01-01" north="100" south="0" east="200" west="0">
            <geoReference><![CDATA[+proj=utm +zone=32 +datum=WGS84]]></geoReference>
        </header>
        <road id="1" name="MainStreet" length="100.0" junction="-1">
            <planView>
                <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="50.0">
                    <line/>
                </geometry>
                <geometry s="50.0" x="50.0" y="0.0" hdg="0.0" length="50.0">
                    <arc curvature="0.01"/>
                </geometry>
            </planView>
            <elevationProfile>
                <elevation s="0.0" a="10.0" b="0.01" c="0.0" d="0.0"/>
            </elevationProfile>
            <lateralProfile>
                <superelevation s="0.0" a="0.05" b="0.0" c="0.0" d="0.0"/>
            </lateralProfile>
            <lanes>
                <laneOffset s="0.0" a="0.0" b="0.0" c="0.0" d="0.0"/>
                <laneSection s="0.0">
                    <left>
                        <lane id="1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                            <roadMark sOffset="0.0" type="solid" color="white" width="0.15"/>
                        </lane>
                    </left>
                    <center>
                        <lane id="0" type="none" level="false">
                            <roadMark sOffset="0.0" type="solid" color="yellow" width="0.1"/>
                        </lane>
                    </center>
                    <right>
                        <lane id="-1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                            <height sOffset="0.0" inner="0.0" outer="0.02"/>
                            <roadMark sOffset="0.0" type="broken" color="white" width="0.15"/>
                        </lane>
                    </right>
                </laneSection>
            </lanes>
            <objects>
                <object id="obj1" name="Barrier" type="barrier" s="10.0" t="5.0"
                        zOffset="0.0" hdg="0.0" length="2.0" width="0.5" height="1.0"
                        orientation="+" validLength="0.0">
                    <repeat s="10.0" length="30.0" distance="5.0"
                            tStart="5.0" tEnd="5.0"
                            widthStart="0.5" widthEnd="0.5"
                            zOffsetStart="0.0" zOffsetEnd="0.0"/>
                </object>
                <object id="obj2" name="Parking" type="parkingSpace" s="20.0" t="-6.0"
                        zOffset="0.0" hdg="0.0" length="5.0" width="2.5" height="0.0"
                        orientation="+" validLength="0.0">
                    <outlines>
                        <outline>
                            <cornerRoad s="20.0" t="-5.0" dz="0.0" height="0.0"/>
                            <cornerRoad s="25.0" t="-5.0" dz="0.0" height="0.0"/>
                            <cornerRoad s="25.0" t="-7.5" dz="0.0" height="0.0"/>
                            <cornerRoad s="20.0" t="-7.5" dz="0.0" height="0.0"/>
                        </outline>
                    </outlines>
                </object>
            </objects>
            <signals>
                <signal id="sig1" name="SpeedLimit" type="274" subtype="50"
                        s="30.0" t="-4.0" zOffset="3.5" hOffset="0.0"
                        orientation="+" dynamic="no" country="DEU" value="50.0"/>
            </signals>
        </road>
        <junction id="100" name="Junction1">
            <connection id="1" incomingRoad="1" connectingRoad="2" contactPoint="start">
                <laneLink from="-1" to="-1"/>
            </connection>
        </junction>
    </OpenDRIVE>
""")


class TestParserHeader:
    def test_header_attributes(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert odr.header.rev_major == 1
        assert odr.header.rev_minor == 6
        assert odr.header.name == "TestRoad"

    def test_geo_reference(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert "+proj=utm" in odr.header.geo_reference.proj4


class TestParserRoads:
    def test_road_count(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads) == 1

    def test_road_attributes(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        road = odr.roads[0]
        assert road.id == "1"
        assert road.name == "MainStreet"
        assert road.length == pytest.approx(100.0)
        assert road.junction == "-1"


class TestParserPlanView:
    def test_geometry_count(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads[0].plan_view) == 2

    def test_line_geometry(self):
        from xodr_to_geojson_caller.models.geometry import Line

        odr = parse_opendrive_string(MINIMAL_XODR)
        geom = odr.roads[0].plan_view[0]
        assert isinstance(geom, Line)
        assert geom.s == 0.0
        assert geom.length == 50.0

    def test_arc_geometry(self):
        from xodr_to_geojson_caller.models.geometry import Arc

        odr = parse_opendrive_string(MINIMAL_XODR)
        geom = odr.roads[0].plan_view[1]
        assert isinstance(geom, Arc)
        assert geom.curvature == pytest.approx(0.01)


class TestParserElevation:
    def test_elevation_parsed(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        elevs = odr.roads[0].elevation_profile.elevations
        assert len(elevs) == 1
        assert elevs[0].a == pytest.approx(10.0)
        assert elevs[0].b == pytest.approx(0.01)

    def test_superelevation_parsed(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        supers = odr.roads[0].lateral_profile.super_elevations
        assert len(supers) == 1
        assert supers[0].a == pytest.approx(0.05)


class TestParserLanes:
    def test_lane_sections(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads[0].lanes.lane_sections) == 1

    def test_lane_counts(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        ls = odr.roads[0].lanes.lane_sections[0]
        assert len(ls.left_lanes) == 1
        assert ls.center_lane.id == 0
        assert len(ls.right_lanes) == 1

    def test_lane_width(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        ls = odr.roads[0].lanes.lane_sections[0]
        left_lane = ls.left_lanes[0]
        assert left_lane.widths[0].a == pytest.approx(3.5)

    def test_lane_height(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        ls = odr.roads[0].lanes.lane_sections[0]
        right_lane = ls.right_lanes[0]
        assert len(right_lane.heights) == 1
        assert right_lane.heights[0].outer == pytest.approx(0.02)

    def test_road_marks(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        ls = odr.roads[0].lanes.lane_sections[0]
        assert ls.center_lane.road_marks[0].type == "solid"
        assert ls.right_lanes[0].road_marks[0].type == "broken"

    def test_lane_offset(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads[0].lanes.lane_offsets) == 1


class TestParserObjects:
    def test_object_count(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads[0].objects) == 2

    def test_object_with_repeat(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        obj = odr.roads[0].objects[0]
        assert obj.id == "obj1"
        assert len(obj.repeats) == 1
        assert obj.repeats[0].distance == pytest.approx(5.0)

    def test_object_with_outline(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        obj = odr.roads[0].objects[1]
        assert len(obj.outlines) == 1
        assert len(obj.outlines[0].corner_road) == 4


class TestParserSignals:
    def test_signal_parsed(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.roads[0].signals) == 1
        sig = odr.roads[0].signals[0]
        assert sig.id == "sig1"
        assert sig.s == pytest.approx(30.0)
        assert sig.z_offset == pytest.approx(3.5)


class TestParserJunctions:
    def test_junction_parsed(self):
        odr = parse_opendrive_string(MINIMAL_XODR)
        assert len(odr.junctions) == 1
        junc = odr.junctions[0]
        assert junc.id == "100"
        assert len(junc.connections) == 1
        assert junc.connections[0].incoming_road == "1"
        assert len(junc.connections[0].lane_links) == 1
