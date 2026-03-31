"""Tests for OpenSCENARIO file-reference extraction."""

import json
import textwrap
from pathlib import Path

import pytest


XOSC_WITH_REFS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenSCENARIO>
      <FileHeader revMajor="1" revMinor="3" date="2026-01-01" author="test"
                  description="test scenario"/>
      <ParameterDeclarations/>
      <CatalogLocations>
        <VehicleCatalog>
          <Directory path="Catalogs/Vehicles"/>
        </VehicleCatalog>
      </CatalogLocations>
      <RoadNetwork>
        <LogicFile filepath="map/road.xodr"/>
        <SceneGraphFile filepath="models/scene.gltf"/>
      </RoadNetwork>
      <Entities>
        <ScenarioObject name="Ego">
          <Vehicle name="EgoCar" vehicleCategory="car">
            <BoundingBox><Center x="1.4" y="0.0" z="0.7"/>
              <Dimensions width="1.8" height="1.4" length="4.5"/>
            </BoundingBox>
            <Axles>
              <FrontAxle maxSteering="0.5" wheelDiameter="0.6"
                         trackWidth="1.6" positionX="3.1" positionZ="0.3"/>
              <RearAxle maxSteering="0" wheelDiameter="0.6"
                        trackWidth="1.6" positionX="0" positionZ="0.3"/>
            </Axles>
            <Performance maxSpeed="69.4" maxAcceleration="10" maxDeceleration="10"/>
          </Vehicle>
        </ScenarioObject>
      </Entities>
      <Storyboard>
        <Init><Actions/></Init>
        <StopTrigger/>
      </Storyboard>
    </OpenSCENARIO>
""")

XOSC_NO_REFS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <OpenSCENARIO>
      <FileHeader revMajor="1" revMinor="3" date="2026-01-01" author="test"
                  description="bare scenario"/>
      <ParameterDeclarations/>
      <RoadNetwork/>
      <Entities/>
      <Storyboard>
        <Init><Actions/></Init>
        <StopTrigger/>
      </Storyboard>
    </OpenSCENARIO>
""")


@pytest.fixture
def xosc_with_refs(tmp_path):
    """Create a minimal XOSC file with LogicFile, SceneGraphFile, and catalog refs."""
    xosc_file = tmp_path / "test.xosc"
    xosc_file.write_text(XOSC_WITH_REFS, encoding="utf-8")

    # Create the referenced map so the extractor can resolve it
    map_dir = tmp_path / "map"
    map_dir.mkdir()
    (map_dir / "road.xodr").write_text("<OpenDRIVE/>", encoding="utf-8")

    # Create the scene graph file
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "scene.gltf").write_text("{}", encoding="utf-8")

    # Create a catalog directory with one file
    cat_dir = tmp_path / "Catalogs" / "Vehicles"
    cat_dir.mkdir(parents=True)
    (cat_dir / "car.xosc").write_text(
        '<?xml version="1.0"?><OpenSCENARIO><Catalog name="VehicleCatalog"/></OpenSCENARIO>',
        encoding="utf-8",
    )
    return xosc_file


@pytest.fixture
def xosc_no_refs(tmp_path):
    """Create a bare XOSC file with no file references."""
    xosc_file = tmp_path / "bare.xosc"
    xosc_file.write_text(XOSC_NO_REFS, encoding="utf-8")
    return xosc_file


class TestLoadOpenscenarioFileReferences:
    """Verify file reference extraction from OpenSCENARIO files."""

    def test_logic_file_reference(self, xosc_with_refs):
        from meta_data_extractor.xosc.extract_osc import load_openscenario_file

        osc = load_openscenario_file(xosc_with_refs)
        logic_refs = [r for r in osc.file_references if r["type"] == "LogicFile"]
        assert len(logic_refs) == 1
        assert logic_refs[0]["path"] == "map/road.xodr"
        assert "relativePath" in logic_refs[0]

    def test_scene_graph_reference(self, xosc_with_refs):
        from meta_data_extractor.xosc.extract_osc import load_openscenario_file

        osc = load_openscenario_file(xosc_with_refs)
        sg_refs = [r for r in osc.file_references if r["type"] == "SceneGraphFile"]
        assert len(sg_refs) == 1
        assert sg_refs[0]["path"] == "models/scene.gltf"

    def test_catalog_reference(self, xosc_with_refs):
        from meta_data_extractor.xosc.extract_osc import load_openscenario_file

        osc = load_openscenario_file(xosc_with_refs)
        cat_refs = [r for r in osc.file_references if r["type"].startswith("Catalog:")]
        assert len(cat_refs) >= 1
        assert any("car.xosc" in r.get("path", "") for r in cat_refs)

    def test_no_refs_when_absent(self, xosc_no_refs):
        from meta_data_extractor.xosc.extract_osc import load_openscenario_file

        osc = load_openscenario_file(xosc_no_refs)
        assert osc.file_references == []

    def test_map_location_set(self, xosc_with_refs):
        from meta_data_extractor.xosc.extract_osc import load_openscenario_file

        osc = load_openscenario_file(xosc_with_refs)
        assert osc.map_location is not None
        assert osc.map_location.name == "road.xodr"


class TestRefsFromExtractor:
    """Test _refs_from_extractor helper in asset_extraction."""

    def test_builds_refs_from_file_references(self, tmp_path):
        from asset_extraction.main import _refs_from_extractor

        extractor_data = {
            "scenario:fileReferences": [
                {
                    "type": "LogicFile",
                    "path": "map/road.xodr",
                    "relativePath": "map/road.xodr",
                },
                {
                    "type": "SceneGraphFile",
                    "path": "models/scene.gltf",
                    "relativePath": "models/scene.gltf",
                },
            ]
        }
        extractor_json = tmp_path / "test_extractor.json"
        extractor_json.write_text(json.dumps(extractor_data), encoding="utf-8")

        refs = _refs_from_extractor(extractor_json)
        assert len(refs) == 2
        assert refs[0]["hasCategory"]["@id"] == "envited-x:isSimulationData"
        assert refs[0]["hasFileMetadata"]["filePath"] == "map/road.xodr"
        assert refs[0]["hasFileMetadata"]["mimeType"] == "application/xml"
        assert refs[1]["hasFileMetadata"]["filePath"] == "models/scene.gltf"
        assert refs[1]["hasFileMetadata"]["mimeType"] == "model/gltf+json"

    def test_returns_empty_when_no_references(self, tmp_path):
        from asset_extraction.main import _refs_from_extractor

        extractor_json = tmp_path / "empty_extractor.json"
        extractor_json.write_text("{}", encoding="utf-8")

        refs = _refs_from_extractor(extractor_json)
        assert refs == []

    def test_returns_empty_on_missing_file(self, tmp_path):
        from asset_extraction.main import _refs_from_extractor

        refs = _refs_from_extractor(tmp_path / "nonexistent.json")
        assert refs == []
