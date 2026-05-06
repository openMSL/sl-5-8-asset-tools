"""Tests for the OpenLABEL JSON → JSON-LD transformer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlabel_creator.tag_categories import (
    BEHAVIOUR_TAGS,
    ODD_TAGS,
    ROAD_USER_TAGS,
    VALUE_PROPERTIES,
    categorize_tag,
)
from openlabel_creator.transformer import (
    _build_admin_tag,
    _extract_value,
    _literal_value,
    load_context,
    load_openlabel_json,
    transform,
)
from openlabel_creator.main import (
    create_openlabel_jsonld,
    find_companion_openlabel,
    inject_into_scenario,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tag categorization
# ═══════════════════════════════════════════════════════════════════════════════


class TestTagCategories:
    def test_motion_tags_are_behaviour(self):
        assert categorize_tag("MotionDrive") == "Behaviour"
        assert categorize_tag("MotionCutIn") == "Behaviour"
        assert categorize_tag("MotionDecelerate") == "Behaviour"

    def test_vehicle_tags_are_road_user(self):
        assert categorize_tag("VehicleCar") == "RoadUser"
        assert categorize_tag("HumanPedestrian") == "RoadUser"
        assert categorize_tag("RoadUserVehicle") == "RoadUser"

    def test_odd_tags(self):
        assert categorize_tag("LaneSpecificationLaneCount") == "Odd"
        assert categorize_tag("WeatherRain") == "Odd"
        assert categorize_tag("DrivableAreaType") == "Odd"

    def test_unknown_tag_returns_none(self):
        assert categorize_tag("CompletelyUnknownTag") is None

    def test_no_overlap_between_categories(self):
        assert BEHAVIOUR_TAGS.isdisjoint(ROAD_USER_TAGS)
        assert BEHAVIOUR_TAGS.isdisjoint(ODD_TAGS)
        assert ROAD_USER_TAGS.isdisjoint(ODD_TAGS)


# ═══════════════════════════════════════════════════════════════════════════════
# Transformer core
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransformer:
    def test_minimal_valid_input(self):
        data = {
            "openlabel": {
                "metadata": {"Name": "test"},
                "tags": {"0": {"type": "MotionDrive", "ontology_uid": "0"}},
            }
        }
        result = transform(data, "did:web:test:Tag:123")
        assert result["@type"] == "openlabel:Tag"
        assert result["@id"] == "did:web:test:Tag:123"
        assert "openlabel:Behaviour" in result
        assert result["openlabel:Behaviour"]["openlabel:MotionDrive"] is True

    def test_missing_openlabel_key_raises(self):
        with pytest.raises(ValueError, match="openlabel"):
            transform({"not_openlabel": {}}, "did:web:test:Tag:1")

    def test_vehicle_car_maps_to_road_user(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {"0": {"type": "VehicleCar", "ontology_uid": "0"}},
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        assert "openlabel:RoadUser" in result
        ru = result["openlabel:RoadUser"]
        assert ru["@type"] == "RoadUser"
        assert ru["openlabel:RoadUserVehicle"] == {"@id": "openlabel:VehicleCar"}

    def test_lane_count_with_value(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {
                        "type": "LaneSpecificationLaneCount",
                        "ontology_uid": "0",
                        "tag_data": {"num": [{"type": "value", "val": 3}]},
                    }
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        odd = result["openlabel:Odd"]
        assert odd["openlabel:LaneSpecificationLaneCount"] is True
        assert odd["openlabel:laneSpecificationLaneCountValue"] == {
            "@type": "xsd:integer",
            "@value": "3",
        }

    def test_range_value(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {
                        "type": "MotionDecelerate",
                        "ontology_uid": "0",
                        "tag_data": {
                            "vec": {"type": "range", "val": ["18", "10"]},
                            "property": "motionDecelerateValue",
                        },
                    }
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        beh = result["openlabel:Behaviour"]
        assert beh["openlabel:MotionDecelerate"] is True
        assert beh["openlabel:motionDecelerateValue"] == {
            "@type": "schema:QuantitativeValue",
            "schema:minValue": "10.0",
            "schema:maxValue": "18.0",
        }

    def test_admin_tag_from_metadata(self):
        data = {
            "openlabel": {
                "metadata": {
                    "Name": "Test Scenario",
                    "Description": "A test",
                    "ScenarioId": "SCEN-123",
                    "CreateDate": "2026-01-01T00:00:00",
                    "Creator": "TestOrg",
                    "OpenXAvailability": {"Osc": True, "Odr": True},
                },
                "tags": {},
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        admin = result["openlabel:AdminTag"]
        assert admin["@type"] == "AdminTag"
        assert admin["openlabel:scenarioName"] == {
            "@type": "xsd:string",
            "@value": "Test Scenario",
        }
        assert admin["openlabel:scenarioDescription"] == {
            "@type": "xsd:string",
            "@value": "A test",
        }
        assert "openlabel:scenarioDefinitionLanguageURI" in admin

    def test_empty_tags_still_produces_valid_structure(self):
        data = {"openlabel": {"metadata": {"Name": "empty"}, "tags": {}}}
        result = transform(data, "did:web:test:Tag:1")
        assert result["@type"] == "openlabel:Tag"
        assert "openlabel:AdminTag" in result
        # No Behaviour/RoadUser/Odd sections when no tags
        assert "openlabel:Behaviour" not in result
        assert "openlabel:RoadUser" not in result
        assert "openlabel:Odd" not in result

    def test_multiple_tags_same_section(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {"type": "MotionDrive", "ontology_uid": "0"},
                    "1": {"type": "MotionCutOut", "ontology_uid": "0"},
                    "2": {"type": "MotionLaneChangeRight", "ontology_uid": "0"},
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        beh = result["openlabel:Behaviour"]
        assert beh["openlabel:MotionDrive"] is True
        assert beh["openlabel:MotionCutOut"] is True
        assert beh["openlabel:MotionLaneChangeRight"] is True

    def test_enum_tags_accumulate_into_arrays(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {
                        "type": "DrivableAreaEdge",
                        "ontology_uid": "0",
                        "tag_data": {"val": "EdgeShoulderPavedOrGravel"},
                    },
                    "1": {
                        "type": "DrivableAreaEdge",
                        "ontology_uid": "0",
                        "tag_data": {"val": "EdgeBarrier"},
                    },
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        odd = result["openlabel:Odd"]
        edges = odd["openlabel:DrivableAreaEdge"]
        assert isinstance(edges, list)
        assert len(edges) == 2
        assert {"@id": "openlabel:EdgeShoulderPavedOrGravel"} in edges
        assert {"@id": "openlabel:EdgeBarrier"} in edges

    def test_non_numeric_value_handled_gracefully(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {
                        "type": "LaneSpecificationLaneCount",
                        "ontology_uid": "0",
                        "tag_data": {"num": [{"type": "value", "val": "not_a_number"}]},
                    }
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        odd = result["openlabel:Odd"]
        assert odd["openlabel:LaneSpecificationLaneCount"] is True
        assert "openlabel:laneSpecificationLaneCountValue" not in odd

    def test_non_dict_tag_data_handled_gracefully(self):
        data = {
            "openlabel": {
                "metadata": {},
                "tags": {
                    "0": {
                        "type": "MotionDrive",
                        "ontology_uid": "0",
                        "tag_data": "not a dict",
                    }
                },
            }
        }
        result = transform(data, "did:web:test:Tag:1")
        beh = result["openlabel:Behaviour"]
        assert beh["openlabel:MotionDrive"] is True

    def test_context_is_well_formed(self):
        data = {"openlabel": {"metadata": {}, "tags": {}}}
        result = transform(data, "did:web:test:Tag:1")
        ctx = result["@context"]
        assert isinstance(ctx, list)
        assert ctx[0] == "https://openlabel.asam.net/V1-0-0/ontologies/"
        assert isinstance(ctx[1], dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Value extraction
# ═══════════════════════════════════════════════════════════════════════════════


class TestValueExtraction:
    def test_range_vec(self):
        result = _extract_value(
            "MotionDecelerate", {"vec": {"type": "range", "val": ["5", "15"]}}
        )
        assert result["@type"] == "schema:QuantitativeValue"
        assert result["schema:minValue"] == "5.0"
        assert result["schema:maxValue"] == "15.0"

    def test_num_list(self):
        result = _extract_value(
            "LaneSpecificationLaneCount", {"num": [{"type": "value", "val": 3}]}
        )
        assert result == {"@type": "xsd:integer", "@value": "3"}

    def test_decimal_value(self):
        result = _extract_value("WeatherRain", {"val": "5.2"})
        assert result == {"@type": "xsd:decimal", "@value": "5.2"}

    def test_empty_tag_data(self):
        result = _extract_value("MotionDrive", {})
        assert result is None

    def test_single_value_range(self):
        result = _extract_value(
            "MotionDrive", {"vec": {"type": "range", "val": ["10"]}}
        )
        assert result["@type"] == "schema:QuantitativeValue"
        assert result["schema:minValue"] == "10.0"
        assert result["schema:maxValue"] == "10.0"

    def test_non_numeric_range_returns_none(self):
        result = _extract_value(
            "MotionDrive", {"vec": {"type": "range", "val": ["abc", "def"]}}
        )
        assert result is None

    def test_non_dict_tag_data_returns_none(self):
        result = _extract_value("MotionDrive", "not a dict")
        assert result is None

    def test_empty_string_val_returns_none(self):
        result = _extract_value("WeatherRain", {"val": ""})
        assert result is None

    def test_whitespace_string_val_returns_none(self):
        result = _extract_value("WeatherRain", {"val": "   "})
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# File loading
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileLoading:
    def test_load_valid_openlabel(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(
            json.dumps({"openlabel": {"metadata": {}, "tags": {}}}), encoding="utf-8"
        )
        result = load_openlabel_json(f)
        assert result is not None
        assert "openlabel" in result

    def test_load_non_openlabel_json(self, tmp_path):
        f = tmp_path / "other.json"
        f.write_text(json.dumps({"@context": [], "type": "Manifest"}), encoding="utf-8")
        assert load_openlabel_json(f) is None

    def test_load_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{{", encoding="utf-8")
        assert load_openlabel_json(f) is None

    def test_load_missing_file(self, tmp_path):
        assert load_openlabel_json(tmp_path / "nope.json") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    def test_create_openlabel_jsonld(self, tmp_path):
        src = tmp_path / "scenario.json"
        src.write_text(
            json.dumps(
                {
                    "openlabel": {
                        "metadata": {"Name": "test"},
                        "tags": {"0": {"type": "MotionDrive", "ontology_uid": "0"}},
                    }
                }
            ),
            encoding="utf-8",
        )
        out = tmp_path / "output" / "openlabel.jsonld"
        assert create_openlabel_jsonld(src, out) is True
        assert out.exists()

        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["@type"] == "openlabel:Tag"

    def test_create_fails_for_non_openlabel(self, tmp_path):
        src = tmp_path / "manifest.json"
        src.write_text(json.dumps({"@context": []}), encoding="utf-8")
        out = tmp_path / "out.jsonld"
        assert create_openlabel_jsonld(src, out) is False

    def test_find_companion_openlabel(self, tmp_path):
        # Create scenario + companion
        xosc = tmp_path / "test.xosc"
        xosc.write_text("<OpenSCENARIO/>", encoding="utf-8")
        companion = tmp_path / "test.json"
        companion.write_text(
            json.dumps({"openlabel": {"metadata": {}, "tags": {}}}), encoding="utf-8"
        )
        assert find_companion_openlabel(xosc) == companion

    def test_find_companion_ignores_non_openlabel(self, tmp_path):
        xosc = tmp_path / "test.xosc"
        xosc.write_text("<OpenSCENARIO/>", encoding="utf-8")
        other = tmp_path / "test.json"
        other.write_text(json.dumps({"@context": []}), encoding="utf-8")
        assert find_companion_openlabel(xosc) is None

    def test_find_companion_none_when_missing(self, tmp_path):
        xosc = tmp_path / "test.xosc"
        xosc.write_text("<OpenSCENARIO/>", encoding="utf-8")
        assert find_companion_openlabel(xosc) is None

    def test_inject_merges_context_to_top_level(self, tmp_path):
        """Verify inject_into_scenario merges @context to top level."""
        openlabel = tmp_path / "openlabel.json"
        openlabel.write_text(
            json.dumps(
                {
                    "@context": [
                        "https://openlabel.asam.net/V1-0-0/ontologies/",
                        {"openlabel": "https://openlabel.asam.net/V1-0-0/ontologies/"},
                    ],
                    "@type": "openlabel:Tag",
                    "@id": "did:web:test:Tag:1",
                    "openlabel:Behaviour": {"@type": "Behaviour"},
                }
            ),
            encoding="utf-8",
        )
        scenario = tmp_path / "scenario.json"
        scenario.write_text(
            json.dumps(
                {
                    "@context": [
                        "https://example.org/scenario/",
                        {"xsd": "http://www.w3.org/2001/XMLSchema#"},
                    ],
                    "scenario:hasDomainSpecification": {
                        "scenario:hasContent": {"@type": "scenario:Content"},
                    },
                }
            ),
            encoding="utf-8",
        )
        assert inject_into_scenario(openlabel, scenario) is True

        result = json.loads(scenario.read_text(encoding="utf-8"))
        # Nested @context should NOT exist
        content = result["scenario:hasDomainSpecification"]["scenario:hasContent"]
        assert isinstance(content, list)
        assert "@context" not in content[1]
        # Top-level should have openlabel URL merged
        ctx_urls = [e for e in result["@context"] if isinstance(e, str)]
        assert "https://openlabel.asam.net/V1-0-0/ontologies/" in ctx_urls
        # Openlabel data still intact
        assert content[1]["@type"] == "openlabel:Tag"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: real IKA files
# ═══════════════════════════════════════════════════════════════════════════════


IKA_OPENLABEL_FILES = (
    list(Path("examples/IKA").rglob("*/scenario/input/*.json"))
    if Path("examples/IKA").exists()
    else []
)

# Filter to actual OpenLABEL files (exclude input_manifest.json etc.)
IKA_OPENLABEL_FILES = [
    f
    for f in IKA_OPENLABEL_FILES
    if f.name != "input_manifest.json" and "openlabel" not in f.stem.lower()
]


@pytest.mark.skipif(not IKA_OPENLABEL_FILES, reason="No IKA examples available")
class TestIKAIntegration:
    @pytest.mark.parametrize(
        "openlabel_file", IKA_OPENLABEL_FILES, ids=lambda f: f.name
    )
    def test_transform_produces_valid_structure(self, openlabel_file):
        data = load_openlabel_json(openlabel_file)
        if data is None:
            pytest.skip(f"{openlabel_file.name} is not OpenLABEL")
        result = transform(data, f"did:web:test:Tag:{openlabel_file.stem}")

        # Must have required fields
        assert result["@type"] == "openlabel:Tag"
        assert "@context" in result
        assert "@id" in result

        # Must have at least one section
        has_section = any(
            k in result
            for k in (
                "openlabel:AdminTag",
                "openlabel:Behaviour",
                "openlabel:RoadUser",
                "openlabel:Odd",
            )
        )
        assert has_section, f"No sections produced for {openlabel_file.name}"
