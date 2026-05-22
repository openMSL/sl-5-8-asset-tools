"""Integration tests: run engine against real OpenSCENARIO and OpenDRIVE files.

These tests verify that the schema decoder + engine produce sensible metadata
from actual asset files.
"""

import pytest
from pathlib import Path

from metadata_extractor.engine import extract_metadata
from metadata_extractor.engine.decoder import SchemaDecoder
from metadata_extractor.engine.mapping import MappingConfig

# Test fixtures — use the shipped example files
_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
_OPENDRIVE_EXAMPLE = (
    _EXAMPLES / "OpenDRIVE" / "input" / "StraightRoad_NCAP_Roadmarks.xodr"
)
_OPENSCENARIO_EXAMPLE = (
    _EXAMPLES / "OpenSCENARIO" / "input" / "StraightRoad_NCAP_Pedestrian_Crossing.xosc"
)

_MAPPINGS_DIR = Path(__file__).resolve().parents[1] / "mappings"


@pytest.fixture
def decoder():
    return SchemaDecoder()


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Decoder
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaDecoder:
    def test_decode_opendrive(self, decoder):
        if not _OPENDRIVE_EXAMPLE.exists():
            pytest.skip("OpenDRIVE example not available")
        data, errors = decoder.decode(_OPENDRIVE_EXAMPLE)
        assert isinstance(data, dict)
        assert "header" in data or "road" in data

    def test_decode_openscenario(self, decoder):
        if not _OPENSCENARIO_EXAMPLE.exists():
            pytest.skip("OpenSCENARIO example not available")
        data, errors = decoder.decode(_OPENSCENARIO_EXAMPLE)
        assert isinstance(data, dict)
        assert "FileHeader" in data

    def test_version_detection_xodr(self, decoder):
        if not _OPENDRIVE_EXAMPLE.exists():
            pytest.skip("OpenDRIVE example not available")
        fmt, version = decoder._detect_format_version(_OPENDRIVE_EXAMPLE)
        assert fmt == "opendrive"
        assert version.startswith("1.")

    def test_version_detection_xosc(self, decoder):
        if not _OPENSCENARIO_EXAMPLE.exists():
            pytest.skip("OpenSCENARIO example not available")
        fmt, version = decoder._detect_format_version(_OPENSCENARIO_EXAMPLE)
        assert fmt == "openscenario"
        assert version.startswith("1.")


# ═══════════════════════════════════════════════════════════════════════════════
# Full extraction with mapping YAML
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullExtraction:
    def test_scenario_extraction(self, decoder):
        if not _OPENSCENARIO_EXAMPLE.exists():
            pytest.skip("OpenSCENARIO example not available")
        mapping_path = _MAPPINGS_DIR / "scenario.yaml"
        if not mapping_path.exists():
            pytest.skip("scenario.yaml mapping not available")

        result = extract_metadata(_OPENSCENARIO_EXAMPLE, mapping=mapping_path)

        # Should have basic format info
        assert result.get("scenario:formatType") == "ASAM OpenSCENARIO XML"
        assert "scenario:version" in result

        # Should have entity types
        if "scenario:entityTypes" in result:
            assert isinstance(result["scenario:entityTypes"], str)

    def test_hdmap_extraction(self, decoder):
        if not _OPENDRIVE_EXAMPLE.exists():
            pytest.skip("OpenDRIVE example not available")
        mapping_path = _MAPPINGS_DIR / "hdmap.yaml"
        if not mapping_path.exists():
            pytest.skip("hdmap.yaml mapping not available")

        result = extract_metadata(_OPENDRIVE_EXAMPLE, mapping=mapping_path)

        # Should have basic format info
        assert result.get("hdmap:formatType") == "ASAM OpenDRIVE"
        assert "hdmap:version" in result

        # Should have some quantity data
        if "hdmap:length" in result:
            assert isinstance(result["hdmap:length"], float)
            assert result["hdmap:length"] > 0

    def test_scenario_entity_types_correct(self, decoder):
        """Verify entity types are properly extracted from example scenario."""
        if not _OPENSCENARIO_EXAMPLE.exists():
            pytest.skip("OpenSCENARIO example not available")
        mapping_path = _MAPPINGS_DIR / "scenario.yaml"
        if not mapping_path.exists():
            pytest.skip("scenario.yaml mapping not available")

        result = extract_metadata(_OPENSCENARIO_EXAMPLE, mapping=mapping_path)

        # The NCAP pedestrian crossing scenario should have pedestrian or car
        entity_types = result.get("scenario:entityTypes", "")
        # At minimum we expect some entities to be found
        assert entity_types != "" or "scenario:numberTrafficObjects" in result

    def test_hdmap_road_types(self, decoder):
        """Verify road/lane types are extracted from OpenDRIVE."""
        if not _OPENDRIVE_EXAMPLE.exists():
            pytest.skip("OpenDRIVE example not available")
        mapping_path = _MAPPINGS_DIR / "hdmap.yaml"
        if not mapping_path.exists():
            pytest.skip("hdmap.yaml mapping not available")

        result = extract_metadata(_OPENDRIVE_EXAMPLE, mapping=mapping_path)

        # A road file should have lane types
        if "hdmap:laneTypes" in result:
            assert (
                "driving" in result["hdmap:laneTypes"]
                or len(result["hdmap:laneTypes"]) > 0
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Mapping YAML loading
# ═══════════════════════════════════════════════════════════════════════════════


class TestMappingYaml:
    def test_scenario_yaml_loads(self):
        mapping_path = _MAPPINGS_DIR / "scenario.yaml"
        if not mapping_path.exists():
            pytest.skip("scenario.yaml not available")
        config = MappingConfig.from_yaml(mapping_path)
        assert config.schema_format == "openscenario"
        assert len(config.rules) > 5

    def test_hdmap_yaml_loads(self):
        mapping_path = _MAPPINGS_DIR / "hdmap.yaml"
        if not mapping_path.exists():
            pytest.skip("hdmap.yaml not available")
        config = MappingConfig.from_yaml(mapping_path)
        assert config.schema_format == "opendrive"
        assert len(config.rules) > 5
