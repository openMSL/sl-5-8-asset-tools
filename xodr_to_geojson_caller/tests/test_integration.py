"""Integration test: end-to-end parsing and conversion of sample .xodr file."""

import json
import os
from pathlib import Path

import pytest

from xodr_to_geojson_caller.converter.geojson import convert_all
from xodr_to_geojson_caller.parser.xodr_parser import parse_opendrive

SAMPLE_XODR = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "OpenDRIVE"
    / "StraightRoad_NCAP_Roadmarks.xodr"
)


@pytest.mark.skipif(
    not SAMPLE_XODR.exists(),
    reason=f"Sample .xodr not found at {SAMPLE_XODR}",
)
class TestIntegration:
    def test_parse_sample_file(self):
        odr = parse_opendrive(SAMPLE_XODR)
        assert len(odr.roads) > 0
        assert odr.roads[0].plan_view  # Has geometry

    def test_convert_all_writes_files(self, tmp_path):
        odr = parse_opendrive(SAMPLE_XODR)
        convert_all(odr, output_dir=tmp_path, step=1.0)

        expected_files = [
            "refLine.json",
            "breakLines.json",
            "roads.json",
            "lanes.json",
            "laneSections.json",
            "objects.json",
            "signals.json",
            "roadMarks.json",
            "junctions.json",
        ]
        for fname in expected_files:
            fpath = tmp_path / fname
            assert fpath.exists(), f"{fname} not generated"
            with open(fpath) as f:
                data = json.load(f)
            assert data["type"] == "FeatureCollection"

    def test_reference_line_has_coordinates(self, tmp_path):
        odr = parse_opendrive(SAMPLE_XODR)
        convert_all(odr, output_dir=tmp_path, step=1.0)

        with open(tmp_path / "refLine.json") as f:
            data = json.load(f)

        assert len(data["features"]) > 0
        coords = data["features"][0]["geometry"]["coordinates"]
        assert len(coords) > 2  # More than start and end

    def test_lanes_have_polygons(self, tmp_path):
        odr = parse_opendrive(SAMPLE_XODR)
        convert_all(odr, output_dir=tmp_path, step=1.0)

        with open(tmp_path / "lanes.json") as f:
            data = json.load(f)

        for feat in data["features"]:
            assert feat["geometry"]["type"] == "Polygon"
            ring = feat["geometry"]["coordinates"][0]
            # Polygon ring must be closed
            assert ring[0] == ring[-1]
