"""Public API for schema-driven metadata extraction.

This is the main entry point for external callers. It provides a simple
function interface that hides the internal engine machinery.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lxml import etree

from .decoder import SchemaDecoder
from .engine import ExtractionEngine
from .mapping import MappingConfig

logger = logging.getLogger(__name__)

# Singleton decoder (caches compiled schemas)
_decoder = SchemaDecoder()

# Default mapping directory
_MAPPINGS_DIR = Path(__file__).resolve().parents[1] / "mappings"


def extract_metadata(
    file: Path,
    mapping: MappingConfig | Path | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract metadata from an XML file using schema-driven mapping.

    Args:
        file: Path to the XML file (.xosc or .xodr).
        mapping: Either a MappingConfig object, a path to a YAML mapping file,
                 or None to auto-select based on file extension.
        context: Optional extra context dict passed to transforms.

    Returns:
        Dict of extracted metadata keyed by ontology property names.

    Raises:
        ValueError: If no mapping can be determined for the file.
        FileNotFoundError: If the file or mapping YAML doesn't exist.
    """
    file = Path(file).resolve()
    if not file.exists():
        raise FileNotFoundError(f"File not found: {file}")

    # Resolve mapping config
    if mapping is None:
        mapping = _auto_mapping(file)
    elif isinstance(mapping, Path):
        mapping = MappingConfig.from_yaml(mapping)

    # Decode XML using XSD schema
    data = _decoder.decode_to_dict(file)

    # Build context
    ctx = {
        "file_path": file,
        "file_stem": file.stem,
        "element_tree": _parse_tree(file),
    }
    if context:
        ctx.update(context)

    # Run extraction engine
    engine = ExtractionEngine()
    return engine.extract(data, mapping, context=ctx)


def decode_xml(file: Path) -> dict[str, Any]:
    """Decode an XML file to a typed dict without applying any mapping.

    Useful for inspection, debugging, or custom processing.
    """
    return _decoder.decode_to_dict(file)


def _auto_mapping(file: Path) -> MappingConfig:
    """Auto-select mapping config based on file extension."""
    ext = file.suffix.lower()
    if ext == ".xosc":
        mapping_file = _MAPPINGS_DIR / "scenario.yaml"
    elif ext == ".xodr":
        mapping_file = _MAPPINGS_DIR / "hdmap.yaml"
    else:
        raise ValueError(
            f"Cannot auto-select mapping for extension '{ext}'. "
            f"Provide a mapping explicitly."
        )

    if not mapping_file.exists():
        raise FileNotFoundError(
            f"Auto-selected mapping file not found: {mapping_file}. "
            f"Create it or provide a mapping explicitly."
        )
    return MappingConfig.from_yaml(mapping_file)


def _parse_tree(file: Path) -> etree._Element:
    """Parse file into lxml element tree (for transforms needing raw XML)."""
    return etree.parse(str(file)).getroot()
