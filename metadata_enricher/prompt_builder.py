"""Prompt builder for metadata enrichment.

Builds a system prompt from SHACL vocabulary (following the
ontology-based-nl-search pattern) that instructs the LLM to fill
empty metadata fields based on asset analysis signals.
"""

from typing import Any

PREAMBLE = """\
# Metadata Enrichment Agent — Simulation Asset

You are a metadata enrichment agent for ENVITED-X simulation assets.
You receive analysis signals extracted from a simulation asset file
and must fill missing metadata fields.

## Rules
1. Only fill fields you can determine with HIGH CONFIDENCE from the signals
2. Use EXACTLY the valid values listed below for enum fields
3. For string fields, provide concise, factual descriptions
4. For fields you cannot determine, set the value to null
5. Call `submit_metadata` with your filled fields
"""


def build_prompt(
    vocabulary: dict[str, Any],
    domain: str,
    missing_fields: list[str],
) -> str:
    """Build LLM system prompt from SHACL vocabulary and missing fields.

    Args:
        vocabulary: Output from vocabulary.extract_vocabulary()
        domain: "hdmap" or "scenario"
        missing_fields: List of field names that need filling
    """
    sections = [PREAMBLE]

    sections.append(f"\n## Domain: {domain}\n")

    # Enum tables
    enum_fields = [f for f in missing_fields if f in vocabulary["enums"]]
    if enum_fields:
        sections.append("### Enumeration Fields (use ONLY listed values)\n")
        sections.append("| Field | Valid Values |")
        sections.append("| ----- | ----------- |")
        for field in sorted(enum_fields):
            info = vocabulary["enums"][field]
            vals = ", ".join(f"`{v}`" for v in info["values"])
            desc = f" — {info['description'][:60]}" if info["description"] else ""
            sections.append(f"| `{field}`{desc} | {vals} |")

    # Non-enum fields
    prop_fields = [
        f
        for f in missing_fields
        if f not in vocabulary["enums"] and f in vocabulary["properties"]
    ]
    if prop_fields:
        sections.append("\n### Data Fields\n")
        sections.append("| Field | Type | Description |")
        sections.append("| ----- | ---- | ----------- |")
        for field in sorted(prop_fields):
            info = vocabulary["properties"][field]
            sections.append(
                f"| `{field}` | {info['type']} | {info['description'][:80]} |"
            )

    sections.append("\n### Guidelines\n")
    sections.append(
        "- `scenarioCategory`: infer from maneuver names, action types, and scenario description"
    )
    sections.append("- `sourceType`: infer from author metadata and file provenance")
    sections.append(
        "- `criticalityFactors`: infer from entity interactions, weather, speeds"
    )
    sections.append(
        "- `country`: infer from geo coordinates, author affiliation, or traffic rules"
    )
    sections.append("- `trafficDirection`: infer from road rule attribute (RHT/LHT)")
    sections.append("- `aim`: derive from scenario name and description")
    sections.append(
        "- `movementDescription`: summarize the types of motion/actions in the scenario"
    )

    return "\n".join(sections)


def build_tool_schema(
    vocabulary: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    """Build the submit_metadata tool schema from vocabulary.

    Returns a JSON Schema compatible dict for the tool's input.
    """
    properties: dict[str, Any] = {}

    for field in missing_fields:
        if field in vocabulary["enums"]:
            info = vocabulary["enums"][field]
            properties[field] = {
                "type": ["string", "array", "null"],
                "description": info.get("description", field),
                "enum": info["values"] + [None],
            }
        elif field in vocabulary["properties"]:
            info = vocabulary["properties"][field]
            json_type = _xsd_to_json_type(info["type"])
            properties[field] = {
                "type": [json_type, "null"],
                "description": info.get("description", field),
            }
        else:
            properties[field] = {
                "type": ["string", "null"],
                "description": field,
            }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


def _xsd_to_json_type(xsd_type: str) -> str:
    """Convert XSD datatype to JSON Schema type."""
    mapping = {
        "string": "string",
        "integer": "integer",
        "float": "number",
        "double": "number",
        "dateTime": "string",
        "boolean": "boolean",
    }
    return mapping.get(xsd_type, "string")
