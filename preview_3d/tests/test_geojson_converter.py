"""Tests for GeoJSON converter."""

import json
import textwrap

import pytest

from preview_3d.converter.geojson import (
    CONVERTERS,
    convert_all,
    convert_junctions,
    convert_lane_break_lines,
    convert_lane_sections,
    convert_lanes,
    convert_objects,
    convert_reference_lines,
    convert_road_marks,
    convert_roads,
    convert_signals,
)
from preview_3d.parser.xodr_parser import parse_opendrive_string

XODR = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenDRIVE>
        <header revMajor="1" revMinor="6" name="Test">
            <geoReference><![CDATA[]]></geoReference>
        </header>
        <road id="1" name="Main" length="50.0" junction="-1">
            <planView>
                <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="50.0">
                    <line/>
                </geometry>
            </planView>
            <elevationProfile>
                <elevation s="0.0" a="0.0" b="0.0" c="0.0" d="0.0"/>
            </elevationProfile>
            <lanes>
                <laneSection s="0.0">
                    <left>
                        <lane id="1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                            <roadMark sOffset="0.0" type="solid" width="0.15"/>
                        </lane>
                    </left>
                    <center>
                        <lane id="0" type="none" level="false"/>
                    </center>
                    <right>
                        <lane id="-1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                        </lane>
                    </right>
                </laneSection>
            </lanes>
            <objects>
                <object id="o1" s="10.0" t="5.0" zOffset="0.0" hdg="0.0"
                        length="0.0" width="0.0" height="0.0" orientation="+"
                        type="pole" name="Pole" validLength="0.0"/>
            </objects>
            <signals>
                <signal id="s1" s="20.0" t="-4.0" zOffset="3.0"
                        hOffset="0.0" orientation="+" type="274" subtype="50"
                        dynamic="no" country="DEU" name="Speed" value="50.0"/>
            </signals>
        </road>
    </OpenDRIVE>
""")


@pytest.fixture
def odr():
    return parse_opendrive_string(XODR)


class TestConvertReferenceLines:
    def test_produces_feature_collection(self, odr):
        fc = convert_reference_lines(odr, step=10.0)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1

    def test_feature_is_linestring(self, odr):
        fc = convert_reference_lines(odr, step=10.0)
        feat = fc["features"][0]
        assert feat["geometry"]["type"] == "LineString"
        assert feat["properties"]["roadId"] == "1"


class TestConvertLanes:
    def test_produces_lane_polygons(self, odr):
        fc = convert_lanes(odr, step=10.0)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2  # left + right

    def test_lane_polygon_structure(self, odr):
        fc = convert_lanes(odr, step=10.0)
        feat = fc["features"][0]
        assert feat["geometry"]["type"] == "Polygon"
        assert "laneId" in feat["properties"]
        assert "roadId" in feat["properties"]


class TestConvertRoads:
    def test_produces_road_polygon(self, odr):
        fc = convert_roads(odr, step=10.0)
        assert len(fc["features"]) == 1
        assert fc["features"][0]["geometry"]["type"] == "Polygon"


class TestConvertLaneSections:
    def test_produces_section_polygons(self, odr):
        fc = convert_lane_sections(odr, step=10.0)
        assert len(fc["features"]) == 1


class TestConvertBreakLines:
    def test_produces_line_features(self, odr):
        fc = convert_lane_break_lines(odr, step=10.0)
        assert len(fc["features"]) >= 2  # at least center + one boundary
        for feat in fc["features"]:
            assert feat["geometry"]["type"] == "LineString"


class TestConvertObjects:
    def test_produces_object_features(self, odr):
        fc = convert_objects(odr)
        assert len(fc["features"]) == 1
        assert fc["features"][0]["geometry"]["type"] == "Point"
        assert fc["features"][0]["properties"]["id"] == "o1"


class TestConvertSignals:
    def test_produces_signal_features(self, odr):
        fc = convert_signals(odr)
        assert len(fc["features"]) == 1
        assert fc["features"][0]["geometry"]["type"] == "Point"
        assert fc["features"][0]["properties"]["id"] == "s1"


class TestConvertRoadMarks:
    def test_produces_mark_features(self, odr):
        fc = convert_road_marks(odr, step=10.0)
        assert len(fc["features"]) >= 1
        for feat in fc["features"]:
            assert feat["geometry"]["type"] == "Polygon"


class TestConvertJunctions:
    def test_empty_junctions(self, odr):
        fc = convert_junctions(odr)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 0


MULTI_SECTION_XODR = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenDRIVE>
        <header revMajor="1" revMinor="6" name="Test">
            <geoReference><![CDATA[]]></geoReference>
        </header>
        <road id="1" name="MultiSection" length="100.0" junction="-1">
            <planView>
                <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="100.0">
                    <line/>
                </geometry>
            </planView>
            <lanes>
                <laneSection s="0.0">
                    <left>
                        <lane id="1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                        </lane>
                    </left>
                    <center><lane id="0" type="none" level="false"/></center>
                    <right>
                        <lane id="-1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                        </lane>
                    </right>
                </laneSection>
                <laneSection s="50.0">
                    <left>
                        <lane id="1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                        </lane>
                    </left>
                    <center><lane id="0" type="none" level="false"/></center>
                    <right>
                        <lane id="-1" type="driving" level="false">
                            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
                        </lane>
                    </right>
                </laneSection>
            </lanes>
        </road>
    </OpenDRIVE>
""")


JUNCTION_XODR = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenDRIVE>
        <header revMajor="1" revMinor="6" name="Test">
            <geoReference><![CDATA[]]></geoReference>
        </header>
        <road id="1" name="Incoming" length="50.0" junction="-1">
            <planView>
                <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="50.0">
                    <line/>
                </geometry>
            </planView>
            <lanes>
                <laneSection s="0.0">
                    <center><lane id="0" type="none"/></center>
                    <right>
                        <lane id="-1" type="driving">
                            <width sOffset="0.0" a="3.5"/>
                        </lane>
                    </right>
                </laneSection>
            </lanes>
        </road>
        <road id="2" name="Connecting" length="30.0" junction="100">
            <planView>
                <geometry s="0.0" x="50.0" y="0.0" hdg="0.0" length="30.0">
                    <line/>
                </geometry>
            </planView>
            <lanes>
                <laneSection s="0.0">
                    <center><lane id="0" type="none"/></center>
                    <right>
                        <lane id="-1" type="driving">
                            <width sOffset="0.0" a="3.5"/>
                        </lane>
                    </right>
                </laneSection>
            </lanes>
        </road>
        <junction id="100" name="Junc1">
            <connection id="1" incomingRoad="1" connectingRoad="2" contactPoint="start">
                <laneLink from="-1" to="-1"/>
            </connection>
        </junction>
    </OpenDRIVE>
""")


class TestConvertRoadsMultiSection:
    """Regression: convert_roads must merge all lane sections."""

    def test_multi_section_polygon_spans_full_road(self):
        odr = parse_opendrive_string(MULTI_SECTION_XODR)
        fc = convert_roads(odr, step=10.0)
        assert len(fc["features"]) == 1
        coords = fc["features"][0]["geometry"]["coordinates"][0]
        xs = [c[0] for c in coords]
        assert min(xs) == pytest.approx(0.0, abs=1.0)
        assert max(xs) == pytest.approx(100.0, abs=1.0)

    def test_multi_section_polygon_is_closed(self):
        odr = parse_opendrive_string(MULTI_SECTION_XODR)
        fc = convert_roads(odr, step=10.0)
        ring = fc["features"][0]["geometry"]["coordinates"][0]
        assert ring[0] == ring[-1]


class TestConvertJunctionsGeometry:
    """Junctions with connecting roads should produce MultiPolygon features."""

    def test_junction_produces_multipolygon(self):
        odr = parse_opendrive_string(JUNCTION_XODR)
        fc = convert_junctions(odr, step=10.0)
        assert len(fc["features"]) == 1
        feat = fc["features"][0]
        assert feat["geometry"]["type"] == "MultiPolygon"
        assert feat["properties"]["junctionId"] == "100"

    def test_junction_coordinates_not_empty(self):
        odr = parse_opendrive_string(JUNCTION_XODR)
        fc = convert_junctions(odr, step=10.0)
        coords = fc["features"][0]["geometry"]["coordinates"]
        assert len(coords) > 0


# -- convert_all options -------------------------------------------------------


class TestConvertAllConverterSelection:
    """Test that convert_all respects the converters parameter."""

    def test_all_converters_by_default(self, odr, tmp_path):
        convert_all(odr, output_dir=tmp_path, step=10.0)
        produced = {p.name for p in tmp_path.iterdir()}
        assert produced == set(CONVERTERS.keys())

    def test_subset_converters(self, odr, tmp_path):
        convert_all(
            odr,
            output_dir=tmp_path,
            step=10.0,
            converters=["refLine.json", "roads.json"],
        )
        produced = {p.name for p in tmp_path.iterdir()}
        assert produced == {"refLine.json", "roads.json"}

    def test_unknown_converter_ignored(self, odr, tmp_path):
        convert_all(
            odr,
            output_dir=tmp_path,
            step=10.0,
            converters=["refLine.json", "nonexistent.json"],
        )
        produced = {p.name for p in tmp_path.iterdir()}
        assert produced == {"refLine.json"}

    def test_empty_converter_list_produces_nothing(self, odr, tmp_path):
        convert_all(odr, output_dir=tmp_path, step=10.0, converters=[])
        produced = list(tmp_path.iterdir())
        assert produced == []


class TestConvertAllCompact:
    """Test compact JSON output mode."""

    def test_compact_produces_single_line_json(self, odr, tmp_path):
        convert_all(
            odr,
            output_dir=tmp_path,
            step=10.0,
            converters=["refLine.json"],
            compact=True,
        )
        content = (tmp_path / "refLine.json").read_text(encoding="utf-8")
        # Compact JSON has no indentation — the entire file is one line
        assert "\n" not in content.strip()

    def test_non_compact_produces_indented_json(self, odr, tmp_path):
        convert_all(
            odr,
            output_dir=tmp_path,
            step=10.0,
            converters=["refLine.json"],
            compact=False,
        )
        content = (tmp_path / "refLine.json").read_text(encoding="utf-8")
        assert "\n" in content

    def test_compact_is_valid_json(self, odr, tmp_path):
        convert_all(
            odr,
            output_dir=tmp_path,
            step=10.0,
            converters=["refLine.json"],
            compact=True,
        )
        content = (tmp_path / "refLine.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["type"] == "FeatureCollection"
