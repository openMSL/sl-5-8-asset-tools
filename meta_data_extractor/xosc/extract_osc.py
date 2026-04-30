"""OpenSCENARIO metadata extractor — schema-driven implementation.

Uses the engine module to decode the XSD and extract metadata via the
declarative mapping in ``meta_data_extractor/mappings/scenario.yaml``.

File reference discovery (LogicFile, catalogs, SceneGraphFile) remains as
explicit Python code since it involves filesystem resolution.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple

import logging

from ..engine.decoder import SchemaDecoder
from ..engine.engine import ExtractionEngine
from ..engine.mapping import MappingConfig
from ..gaiax import enrich_resource_description
from utils.ids import create_uuid
from utils.constants import (
    DID_ADRESS,
    ENVITED_URL,
    ENVITEDX_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    OSC_SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)

_MAPPING_FILE = Path(__file__).resolve().parents[1] / "mappings" / "scenario.yaml"
_decoder = SchemaDecoder()


# ═══════════════════════════════════════════════════════════════════════════════
# File reference discovery (filesystem-dependent, cannot be in YAML mapping)
# ═══════════════════════════════════════════════════════════════════════════════


def _discover_file_references(osc_path: Path) -> list[dict[str, str]]:
    """Discover file references in an OpenSCENARIO file.

    Scans for LogicFile, SceneGraphFile, CatalogLocations, and
    TrafficSignalController references.
    """
    references: list[dict[str, str]] = []
    sc = ET.parse(osc_path).getroot()

    # Extract parameter values for variable substitution
    variables: dict[str, str] = {}
    for param in sc.findall(".//ParameterDeclaration"):
        name = param.get("name", "")
        value = param.get("value", "")
        if name:
            variables[f"${name}"] = value

    def resolve_value(val: str) -> str:
        if "$" in val and val in variables:
            return variables[val]
        return val

    # LogicFile (HD-map reference)
    logic_file = sc.find(".//LogicFile")
    if logic_file is not None and "filepath" in logic_file.attrib:
        filepath = resolve_value(logic_file.attrib["filepath"])
        entry: dict[str, str] = {"type": "LogicFile", "path": filepath}
        resolved = (osc_path.parent / filepath).resolve()
        if not resolved.exists():
            resolved = (osc_path.parent / Path(filepath).name).resolve()
        if resolved.exists():
            try:
                entry["relativePath"] = str(resolved.relative_to(osc_path.parent))
            except ValueError:
                entry["relativePath"] = str(resolved)
        references.append(entry)

    # SceneGraphFile (3D environment model)
    scene_graph = sc.find(".//SceneGraphFile")
    if scene_graph is not None and "filepath" in scene_graph.attrib:
        sg_path = resolve_value(scene_graph.attrib["filepath"])
        if sg_path:
            entry = {"type": "SceneGraphFile", "path": sg_path}
            resolved = (osc_path.parent / sg_path).resolve()
            if resolved.exists():
                try:
                    entry["relativePath"] = str(resolved.relative_to(osc_path.parent))
                except ValueError:
                    entry["relativePath"] = str(resolved)
            references.append(entry)

    # TrafficSignalController
    for tsc in sc.findall(".//TrafficSignalController"):
        ref_el = tsc.find("Phase/TrafficSignalState")
        if ref_el is not None:
            references.append(
                {"type": "TrafficSignalController", "name": tsc.get("name", "")}
            )

    # CatalogLocations
    catalog_locations_el = sc.find(".//CatalogLocations")
    if catalog_locations_el is not None:
        for catalog in catalog_locations_el:
            dir_el = catalog.find("Directory")
            if dir_el is None:
                continue
            cat_path = dir_el.get("path", "")
            if not cat_path:
                continue
            location = (osc_path.parent / cat_path).resolve()
            if location.is_dir():
                for f in location.iterdir():
                    if f.suffix in (".osc", ".xosc"):
                        references.append(
                            {
                                "type": f"Catalog:{catalog.tag}",
                                "path": f.name,
                                "relativePath": str(f),
                            }
                        )
            elif location.is_file():
                references.append(
                    {
                        "type": f"Catalog:{catalog.tag}",
                        "path": cat_path,
                        "relativePath": str(location),
                    }
                )

    return references


def extract_meta_data(file: Path) -> Tuple[bool, dict]:
    """Extract metadata from an OpenSCENARIO file.

    Returns (success, metadata_dict) matching the expected pipeline format.
    """
    file = Path(file).resolve()
    logger.debug("Loading input file %s", file)

    try:
        data, decode_errors = _decoder.decode(file)
    except Exception:
        logger.exception("Cannot decode %s", file)
        return False, {}

    # Parse element tree for transforms that need raw XML access
    element_tree = ET.parse(file).getroot()

    try:
        mapping = MappingConfig.from_yaml(_MAPPING_FILE)
        engine = ExtractionEngine()
        extracted = engine.extract(
            data, mapping, context={"file_path": file, "element_tree": element_tree}
        )
    except Exception:
        logger.exception("Cannot extract metadata from %s", file)
        return False, {}

    # ── Assemble output structure ──────────────────────────────────────────
    meta_data_dict: dict = {}
    meta_data_dict["did"] = f"did:web:registry.gaia-x.eu:Scenario:{create_uuid()}"
    meta_data_dict["shacl_schema"] = get_schema_name()
    meta_data_dict["shacl_url"] = get_namespace()

    # Resource description
    resource_desc: dict = {}
    resource_desc["gx:name"] = file.stem
    description = extracted.pop("scenario:description", None)
    if description:
        resource_desc["gx:description"] = description
    else:
        resource_desc["gx:description"] = "OpenSCENARIO file"
    enrich_resource_description(resource_desc, file)
    meta_data_dict["scenario:hasResourceDescription"] = resource_desc

    # Domain specification
    domain: dict = {}

    # Format
    format_dict: dict = {}
    if "scenario:formatType" in extracted:
        format_dict["scenario:formatType"] = extracted.pop("scenario:formatType")
    if "scenario:version" in extracted:
        format_dict["scenario:version"] = extracted.pop("scenario:version")
    domain["scenario:hasFormat"] = format_dict

    # Content
    content_dict: dict = {}
    content_keys = (
        "scenario:abstractionLevel",
        "scenario:timeDate",
        "scenario:usedStandardFunctions",
        "scenario:customCommands",
        "scenario:sunAzimuth",
        "scenario:weatherSummary",
        "scenario:entityTypes",
        "scenario:countrySpecificSign",
        "scenario:countrySpecificTrafficParticipants",
    )
    for key in content_keys:
        if key in extracted:
            content_dict[key] = extracted.pop(key)
    domain["scenario:hasContent"] = content_dict

    # Quantity
    quantity_dict: dict = {}
    quantity_keys = (
        "scenario:numberTrafficObjects",
        "scenario:controllers",
    )
    for key in quantity_keys:
        if key in extracted:
            val = extracted.pop(key)
            quantity_dict[key] = str(val) if isinstance(val, int) else val
    domain["scenario:hasQuantity"] = quantity_dict

    domain["scenario:hasQuality"] = {}
    meta_data_dict["scenario:hasDomainSpecification"] = domain

    # Manifest
    meta_data_dict["scenario:hasManifest"] = {
        "manifest:hasAccessRole": "envited-x:isPublic",
        "manifest:hasCategory": "envited-x:isManifest",
        "manifest:hasFileMetadata": {
            "manifest:filePath": "../manifest.json",
            "manifest:mimeType": "application/ld+json",
        },
        "manifest:iri": f"{DID_ADRESS}{create_uuid()}",
        "skos:note": (
            "Ensure that manifest.json contains all required categories: "
            "simulationData, documentation, metadata, media."
        ),
        "sh:conformsTo": [
            f"https://w3id.org/ascs-ev/envited-x/envited-x/{ENVITEDX_SCHEMA_VERSION}/",
            f"https://w3id.org/ascs-ev/envited-x/manifest/{MANIFEST_SCHEMA_VERSION}/",
        ],
    }

    # File references (filesystem-dependent discovery)
    try:
        file_refs = _discover_file_references(file)
        if file_refs:
            meta_data_dict["scenario:fileReferences"] = file_refs
    except Exception:
        logger.warning("Could not discover file references in %s", file.name)

    # Pass through any remaining extracted fields
    for key, val in extracted.items():
        if key.startswith("scenario:"):
            meta_data_dict[key] = val

    logger.info("Extracted metadata from %s", file.name)
    return True, meta_data_dict


def get_description() -> str:
    return "extract OpenSCENARIO"


def get_name_lower() -> str:
    return get_schema_name().lower()


def get_schema_name() -> str:
    return "Scenario"


def get_namespace() -> str:
    return f"{ENVITED_URL}{get_name_lower()}/{OSC_SCHEMA_VERSION}"
