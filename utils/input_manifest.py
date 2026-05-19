"""Conversion utilities for input_manifest.json.

The input_manifest.json is a partial envited-x:Manifest in JSON-LD that
describes user-provided input files using the same vocabulary as the output
manifest_reference.json. This module converts the JSON-LD format into the
flat entry list used internally by the pipeline.

See EVES-003 §1b for the specification.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Category → type inference based on file extension.
# When input_manifest.json is used, the ad-hoc "type" field is absent.
# We derive it from the category and file extension using the same mapping
# that packager/main.py CATEGORIES dict defines.
_CATEGORY_TYPE_MAP = {
    "isSimulationData": {"default": "Asset"},
    "isDocumentation": {"default": "Document"},
    "isMedia": {
        "default": "Image",
        "png": "Image",
        "jpeg": "Image",
        "jpg": "Image",
        "mp4": "Video",
        "json": "3DPreview",
        "geojson": "Routing",
    },
    "isMetadata": {"default": "MetaData"},
    "isValidationReport": {"default": "Validation"},
    "isLicense": {"default": "License"},
    "isMiscellaneous": {"default": "Service"},
}


def is_input_manifest(data) -> bool:
    """Check whether the loaded JSON is a valid input_manifest.json (JSON-LD object)."""
    return isinstance(data, dict) and "@context" in data


def _strip_prefix(value: str) -> str:
    """Remove namespace prefix from an @id value.
    e.g. 'envited-x:isSimulationData' -> 'isSimulationData'
         'manifest:isPublic' -> 'isPublic'
    """
    if ":" in value and not value.startswith(("http://", "https://", "did:")):
        return value.split(":", 1)[1]
    return value


def _extract_id(node) -> str:
    """Extract the @id value from a node, handling both compact and expanded forms."""
    if isinstance(node, str):
        return _strip_prefix(node)
    if isinstance(node, dict):
        raw = node.get("@id", "")
        return _strip_prefix(raw)
    return ""


def _infer_type(category: str, extension: str) -> str:
    """Infer the 'type' field from category and file extension."""
    cat_map = _CATEGORY_TYPE_MAP.get(category, {})
    return cat_map.get(extension, cat_map.get("default", "Asset"))


def _link_to_entry(link: dict) -> dict:
    """Convert a single manifest:Link node to a pipeline entry dict."""
    category = _extract_id(
        link.get("hasCategory", link.get("manifest:hasCategory", ""))
    )
    file_meta = link.get("hasFileMetadata", link.get("manifest:hasFileMetadata", {}))

    file_path = file_meta.get("filePath", file_meta.get("manifest:filePath", ""))
    # Handle expanded JSON-LD @value form
    if isinstance(file_path, dict):
        file_path = file_path.get("@value", "")

    extension = Path(file_path).suffix.lstrip(".").lower() if file_path else ""
    entry_type = _infer_type(category, extension)

    entry = {
        "filename": file_path,
        "type": entry_type,
        "category": category,
    }
    return entry


def input_manifest_to_entries(data: dict) -> list:
    """Convert an input_manifest.json (JSON-LD) to a flat list of pipeline entry dicts.

    The @id of the manifest is attached as 'did' to the simulation data entry.
    """
    entries = []
    manifest_id = data.get("@id", "")

    # Process hasArtifacts
    artifacts = data.get("hasArtifacts", data.get("manifest:hasArtifacts", []))
    if not isinstance(artifacts, list):
        artifacts = [artifacts]

    for link in artifacts:
        entry = _link_to_entry(link)
        # Attach the manifest @id as DID to the simulation data entry
        if entry["category"] == "isSimulationData" and manifest_id:
            entry["did"] = manifest_id
        entries.append(entry)

    # Process hasLicense
    license_link = data.get("hasLicense", data.get("manifest:hasLicense"))
    if license_link:
        entry = _link_to_entry(license_link)
        entries.append(entry)

    return entries


def load_input_file(json_path: Path) -> list:
    """Load an input_manifest.json and return a flat list of pipeline entry dicts."""
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not is_input_manifest(data):
        raise ValueError(
            f"Unrecognized input format in {json_path}. "
            "Expected a JSON-LD object (input_manifest.json) with an @context field."
        )

    logger.info("Loading input_manifest.json (JSON-LD)")
    return input_manifest_to_entries(data)


def load_referenced_artifacts(json_path: Path) -> list | None:
    """Extract hasReferencedArtifacts from an input_manifest.json.

    Returns the raw JSON-LD array of referenced artifact links,
    or None if the manifest has no references.
    """
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not is_input_manifest(data):
        return None

    refs = data.get(
        "hasReferencedArtifacts", data.get("manifest:hasReferencedArtifacts")
    )
    if refs is None:
        return None
    if not isinstance(refs, list):
        refs = [refs]
    return refs if refs else None
