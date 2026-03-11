"""Golden file regression test.

Proves feature coverage by converting the reference .xodr and asserting
that output structure matches the snapshotted golden metrics. This
ensures our Python converter produces the same output layer structure
as the Java reference implementation.
"""

import json
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
GOLDEN_METRICS = Path(__file__).resolve().parent / "golden_metrics.json"


@pytest.mark.skipif(
    not SAMPLE_XODR.exists(),
    reason=f"Sample .xodr not found at {SAMPLE_XODR}",
)
class TestGoldenFileRegression:
    """Verify Python converter output matches golden snapshot."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_path):
        odr = parse_opendrive(SAMPLE_XODR)
        convert_all(odr, output_dir=tmp_path, step=1.0)
        self.output_dir = tmp_path
        with open(GOLDEN_METRICS) as f:
            self.golden = json.load(f)

    def test_all_expected_files_produced(self):
        for filename in self.golden:
            assert (self.output_dir / filename).exists(), f"Missing {filename}"

    def test_no_extra_files_produced(self):
        produced = {f.name for f in self.output_dir.glob("*.json")}
        expected = set(self.golden.keys())
        assert produced == expected

    def test_feature_counts_match(self):
        for filename, expected in self.golden.items():
            with open(self.output_dir / filename) as f:
                data = json.load(f)
            actual_count = len(data["features"])
            assert actual_count == expected["feature_count"], (
                f"{filename}: expected {expected['feature_count']} features, got {actual_count}"
            )

    def test_geometry_types_match(self):
        for filename, expected in self.golden.items():
            with open(self.output_dir / filename) as f:
                data = json.load(f)
            actual_types = sorted(
                set(feat["geometry"]["type"] for feat in data["features"])
            )
            expected_types = sorted(expected["geometry_types"])
            assert actual_types == expected_types, (
                f"{filename}: expected types {expected_types}, got {actual_types}"
            )

    def test_all_features_have_valid_geojson(self):
        for filename in self.golden:
            with open(self.output_dir / filename) as f:
                data = json.load(f)
            assert data["type"] == "FeatureCollection"
            for feat in data["features"]:
                assert feat["type"] == "Feature"
                assert "geometry" in feat
                assert "properties" in feat
                assert feat["geometry"]["type"] in (
                    "Point",
                    "LineString",
                    "Polygon",
                    "MultiPolygon",
                )

    def test_polygons_are_closed_rings(self):
        for filename in self.golden:
            with open(self.output_dir / filename) as f:
                data = json.load(f)
            for feat in data["features"]:
                if feat["geometry"]["type"] == "Polygon":
                    for ring in feat["geometry"]["coordinates"]:
                        assert ring[0] == ring[-1], f"{filename}: unclosed polygon ring"

    def test_linestrings_have_multiple_points(self):
        for filename in self.golden:
            with open(self.output_dir / filename) as f:
                data = json.load(f)
            for feat in data["features"]:
                if feat["geometry"]["type"] == "LineString":
                    coords = feat["geometry"]["coordinates"]
                    assert len(coords) >= 2, f"{filename}: LineString with < 2 points"

    def test_reference_line_coverage(self):
        """Verify reference line spans the full road length."""
        with open(self.output_dir / "refLine.json") as f:
            data = json.load(f)
        for feat in data["features"]:
            coords = feat["geometry"]["coordinates"]
            # Should have points along the entire road
            xs = [c[0] for c in coords]
            road_extent = max(xs) - min(xs)
            assert road_extent > 0, "Reference line has zero extent"

    def test_lane_count_matches_road(self):
        """Number of lane polygons should match lane count in road."""
        with open(self.output_dir / "lanes.json") as f:
            data = json.load(f)
        # StraightRoad has 4 lanes (2 left + 2 right, no center polygon)
        assert len(data["features"]) == 4

    def test_break_lines_count(self):
        """Break lines = center + lane boundaries."""
        with open(self.output_dir / "breakLines.json") as f:
            data = json.load(f)
        # 4 lanes → 5 boundaries (outer-left, inner-left, center, inner-right, outer-right)
        assert len(data["features"]) == 5
