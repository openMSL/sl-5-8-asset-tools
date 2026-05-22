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

OPENLABEL_CONTEXT_URL = "https://w3id.org/ascs-ev/envited-x/openlabel/v2/"

_OMB_CONTEXT_PATH = (
    Path(__file__).resolve().parents[1]
    / "submodules"
    / "ontology-management-base"
    / "artifacts"
    / "openlabel-v2"
    / "openlabel-v2.context.jsonld"
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
            "openlabel_v2": OPENLABEL_CONTEXT_URL,
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "schema": "https://schema.org/",
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
        "@type": "Tag",
    }

    # AdminTag from metadata
    admin_tag = _build_admin_tag(metadata)
    if admin_tag:
        result["AdminTag"] = admin_tag

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
        result["Behaviour"] = behaviour
    if road_user:
        road_user["@type"] = "RoadUser"
        result["RoadUser"] = road_user
    if odd:
        odd["@type"] = "Odd"
        result["Odd"] = odd

    return result


def _build_admin_tag(metadata: dict) -> dict[str, Any] | None:
    """Build the AdminTag section from OpenLABEL metadata."""
    admin: dict[str, Any] = {"@type": "AdminTag"}

    field_map = {
        "Name": "scenarioName",
        "Description": "scenarioDescription",
        "ScenarioId": "scenarioUniqueReference",
        "CreateDate": "scenarioCreatedDate",
        "ModifyDate": "scenarioVersion",
        "Creator": "ownerName",
    }

    for src_key, dst_key in field_map.items():
        value = metadata.get(src_key)
        if value and isinstance(value, str):
            admin[dst_key] = value

    # scenarioDefinitionLanguageURI from OpenXAvailability
    openx = metadata.get("OpenXAvailability", {})
    if openx.get("Osc"):
        admin["scenarioDefinitionLanguageURI"] = (
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

    # Handle road user entity types (VehicleCar → RoadUserVehicle: "VehicleCar")
    for types_set, prop in (
        (ROAD_USER_VEHICLE_TYPES, "RoadUserVehicle"),
        (ROAD_USER_HUMAN_TYPES, "RoadUserHuman"),
        (ROAD_USER_ANIMAL_TYPES, "RoadUserAnimal"),
    ):
        if tag_type in types_set:
            key = prop
            new_val = tag_type
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

    # Tags in ENUM_TAGS use bare enum values (may accumulate into arrays)
    if tag_type in ENUM_TAGS:
        enum_value = tag_data.get("val") if tag_data else None
        if enum_value:
            _append_or_set(target, tag_type, enum_value)
        else:
            target[tag_type] = True
        return

    # Boolean tags (presence = true)
    target[tag_type] = True

    # If there's associated numeric value data, add the value property
    value_prop = VALUE_PROPERTIES.get(tag_type)
    if value_prop and tag_data:
        typed_value = _extract_value(tag_type, tag_data)
        if typed_value is not None:
            target[value_prop] = typed_value


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
                "minValue": str(min(floats)),
                "maxValue": str(max(floats)),
            }
        if len(floats) == 1:
            return {
                "@type": "schema:QuantitativeValue",
                "minValue": str(floats[0]),
                "maxValue": str(floats[0]),
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


def _typed_scalar(tag_type: str, value: Any) -> str | int | float | None:
    """Convert a scalar value to the appropriate Python type.

    Types are chosen to match SHACL sh:datatype constraints per property.
    Returns None if the value cannot be converted or is empty.
    """
    if isinstance(value, str) and not value.strip():
        return None

    try:
        if tag_type in _INTEGER_TAGS:
            return int(float(value))
        return str(value)
    except (ValueError, TypeError):
        logger.warning("Cannot convert value '%s' for %s", value, tag_type)
        return None


# Tags whose value properties expect integer types in SHACL
_INTEGER_TAGS: frozenset[str] = frozenset(
    {
        "LaneSpecificationLaneCount",
        "SubjectVehicleSpeed",
        "TrafficAgentDensity",
        "TrafficFlowRate",
        "TrafficVolume",
    }
)


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
