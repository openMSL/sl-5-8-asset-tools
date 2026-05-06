"""OpenLABEL JSON → JSON-LD transformer.

Converts raw OpenLABEL JSON (as produced by scenario annotation tools)
into JSON-LD conforming to the openlabel:TagShape SHACL schema.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .tag_categories import (
    BEHAVIOUR_TAGS,
    ENUM_TAGS,
    ODD_TAGS,
    ROAD_USER_ANIMAL_TYPES,
    ROAD_USER_HUMAN_TYPES,
    ROAD_USER_VEHICLE_TYPES,
    VALUE_PROPERTIES,
    categorize_tag,
)

logger = logging.getLogger(__name__)

OPENLABEL_CONTEXT_URL = "https://openlabel.asam.net/V1-0-0/ontologies/"
OPENLABEL_PREFIX = "openlabel:"

_OMB_CONTEXT_PATH = (
    Path(__file__).resolve().parents[1]
    / "submodules"
    / "ontology-management-base"
    / "artifacts"
    / "openlabel"
    / "openlabel.context.jsonld"
)


def load_context() -> list[Any]:
    """Load the JSON-LD @context from the OMB submodule."""
    if _OMB_CONTEXT_PATH.exists():
        with open(_OMB_CONTEXT_PATH, encoding="utf-8") as f:
            ctx_doc = json.load(f)
        return [OPENLABEL_CONTEXT_URL, ctx_doc.get("@context", {})]

    # Fallback: minimal context if OMB not available
    return [
        OPENLABEL_CONTEXT_URL,
        {
            "openlabel": OPENLABEL_CONTEXT_URL,
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "schema": "http://schema.org/",
        },
    ]


def transform(openlabel_json: dict, tag_id: str) -> dict:
    """Transform an OpenLABEL JSON dict into a JSON-LD document.

    Args:
        openlabel_json: Parsed OpenLABEL JSON (root object with "openlabel" key).
        tag_id: The @id URI for the output document
                (e.g. "did:web:registry.gaia-x.eu:Tag:<uuid>").

    Returns:
        JSON-LD dict conforming to openlabel:TagShape.

    Raises:
        ValueError: If the input is not valid OpenLABEL JSON.
    """
    openlabel = openlabel_json.get("openlabel")
    if not openlabel or not isinstance(openlabel, dict):
        raise ValueError("Input JSON must contain an 'openlabel' root key")

    metadata = openlabel.get("metadata", {})
    tags = openlabel.get("tags", {})

    # Build output structure
    result: dict[str, Any] = {
        "@context": load_context(),
        "@id": tag_id,
        "@type": "openlabel:Tag",
    }

    # AdminTag from metadata
    admin_tag = _build_admin_tag(metadata)
    if admin_tag:
        result["openlabel:AdminTag"] = admin_tag

    # Categorize and build sections from tags
    behaviour: dict[str, Any] = {}
    road_user: dict[str, Any] = {}
    odd: dict[str, Any] = {}

    for _tag_id, tag in tags.items():
        if not isinstance(tag, dict):
            continue
        tag_type = tag.get("type", "")
        tag_data = tag.get("tag_data", {})

        _apply_tag(tag_type, tag_data, behaviour, road_user, odd)

    if behaviour:
        behaviour["@type"] = "Behaviour"
        result["openlabel:Behaviour"] = behaviour
    if road_user:
        road_user["@type"] = "RoadUser"
        result["openlabel:RoadUser"] = road_user
    if odd:
        odd["@type"] = "Odd"
        result["openlabel:Odd"] = odd

    return result


def _build_admin_tag(metadata: dict) -> dict[str, Any] | None:
    """Build the AdminTag section from OpenLABEL metadata."""
    admin: dict[str, Any] = {"@type": "AdminTag"}

    field_map = {
        "Name": "openlabel:scenarioName",
        "Description": "openlabel:scenarioDescription",
        "ScenarioId": "openlabel:scenarioUniqueReference",
        "CreateDate": "openlabel:scenarioCreatedDate",
        "ModifyDate": "openlabel:scenarioVersion",
        "Creator": "openlabel:ownerName",
    }

    for src_key, dst_key in field_map.items():
        value = metadata.get(src_key)
        if value and isinstance(value, str):
            admin[dst_key] = _literal_value(value)

    # scenarioDefinitionLanguageURI from OpenXAvailability
    openx = metadata.get("OpenXAvailability", {})
    if openx.get("Osc"):
        admin["openlabel:scenarioDefinitionLanguageURI"] = _literal_value(
            "https://www.asam.net/standards/detail/openscenario/"
        )

    # Only return if we have content beyond @type
    if len(admin) > 1:
        return admin
    return None


def _apply_tag(
    tag_type: str,
    tag_data: dict,
    behaviour: dict,
    road_user: dict,
    odd: dict,
) -> None:
    """Apply a single tag to the appropriate section."""
    if not isinstance(tag_data, dict):
        tag_data = {}

    # Handle road user entity types (VehicleCar → RoadUserVehicle: {@id: ...})
    for types_set, prop in (
        (ROAD_USER_VEHICLE_TYPES, "RoadUserVehicle"),
        (ROAD_USER_HUMAN_TYPES, "RoadUserHuman"),
        (ROAD_USER_ANIMAL_TYPES, "RoadUserAnimal"),
    ):
        if tag_type in types_set:
            key = f"{OPENLABEL_PREFIX}{prop}"
            new_val = {"@id": f"{OPENLABEL_PREFIX}{tag_type}"}
            if key in road_user:
                logger.warning("Overwriting %s: %s → %s", key, road_user[key], new_val)
            road_user[key] = new_val
            return

    # Determine target section
    section = categorize_tag(tag_type)
    if section is None:
        logger.debug("Unknown tag type '%s', skipping", tag_type)
        return

    target = {"Behaviour": behaviour, "RoadUser": road_user, "Odd": odd}[section]

    # Tags in ENUM_TAGS use @id reference (may accumulate into arrays)
    if tag_type in ENUM_TAGS:
        enum_value = tag_data.get("val") if tag_data else None
        if enum_value:
            _append_or_set(
                target,
                f"{OPENLABEL_PREFIX}{tag_type}",
                {"@id": f"{OPENLABEL_PREFIX}{enum_value}"},
            )
        else:
            target[f"{OPENLABEL_PREFIX}{tag_type}"] = True
        return

    # Boolean tags (presence = true)
    target[f"{OPENLABEL_PREFIX}{tag_type}"] = True

    # If there's associated numeric value data, add the value property
    value_prop = VALUE_PROPERTIES.get(tag_type)
    if value_prop and tag_data:
        typed_value = _extract_value(tag_type, tag_data)
        if typed_value is not None:
            target[f"{OPENLABEL_PREFIX}{value_prop}"] = typed_value


def _append_or_set(target: dict, key: str, value: Any) -> None:
    """Set a key or accumulate into an array if it already exists."""
    existing = target.get(key)
    if existing is None:
        target[key] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        target[key] = [existing, value]


def _extract_value(tag_type: str, tag_data: dict) -> Any:
    """Extract a typed value from tag_data.

    Handles multiple formats:
    - {"vec": {"type": "range", "val": [min, max]}} → QuantitativeValue
    - {"num": [{"type": "value", "val": N}]} → typed scalar
    - {"val": "N"} → typed scalar
    """
    if not isinstance(tag_data, dict):
        return None

    # Range values → schema:QuantitativeValue
    vec = tag_data.get("vec")
    if isinstance(vec, dict) and vec.get("type") == "range":
        vals = vec.get("val", [])
        try:
            floats = [float(v) for v in vals]
        except (ValueError, TypeError):
            logger.warning("Non-numeric range values in %s: %s", tag_type, vals)
            return None
        if len(floats) >= 2:
            return {
                "@type": "schema:QuantitativeValue",
                "schema:minValue": str(min(floats)),
                "schema:maxValue": str(max(floats)),
            }
        if len(floats) == 1:
            return {
                "@type": "schema:QuantitativeValue",
                "schema:minValue": str(floats[0]),
                "schema:maxValue": str(floats[0]),
            }

    # Numeric list values
    num = tag_data.get("num")
    if isinstance(num, list) and num:
        first = num[0]
        if isinstance(first, dict):
            val = first.get("val")
            if val is not None:
                return _typed_scalar(tag_type, val)
        elif isinstance(first, (int, float)):
            return _typed_scalar(tag_type, first)

    # Direct value
    val = tag_data.get("val")
    if val is not None:
        return _typed_scalar(tag_type, val)

    return None


def _typed_scalar(tag_type: str, value: Any) -> dict[str, str] | None:
    """Wrap a scalar value with XSD type annotation.

    XSD types are chosen to match SHACL sh:datatype constraints per property.
    Returns None if the value cannot be converted or is empty.
    """
    if isinstance(value, str) and not value.strip():
        return None

    xsd_type = _XSD_TYPE_MAP.get(tag_type, "xsd:decimal")
    try:
        if "integer" in xsd_type or "Integer" in xsd_type:
            return {"@type": xsd_type, "@value": str(int(float(value)))}
        return {"@type": xsd_type, "@value": str(value)}
    except (ValueError, TypeError):
        logger.warning("Cannot convert value '%s' for %s", value, tag_type)
        return None


# Per-property XSD type mapping (matching SHACL sh:datatype constraints)
_XSD_TYPE_MAP: dict[str, str] = {
    "LaneSpecificationLaneCount": "xsd:integer",
    "SubjectVehicleSpeed": "xsd:nonNegativeInteger",
    "TrafficAgentDensity": "xsd:nonNegativeInteger",
    "TrafficFlowRate": "xsd:nonNegativeInteger",
    "TrafficVolume": "xsd:nonNegativeInteger",
}


def _literal_value(value: str) -> dict[str, str]:
    """Wrap a string as an xsd:string typed value."""
    return {"@type": "xsd:string", "@value": value}


def load_openlabel_json(file_path: Path) -> dict | None:
    """Load and validate basic structure of an OpenLABEL JSON file.

    Returns the parsed dict or None if the file is not valid OpenLABEL.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("Cannot parse %s as JSON", file_path)
        return None

    if not isinstance(data, dict) or "openlabel" not in data:
        return None

    return data
