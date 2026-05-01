"""Schema-driven metadata extraction engine.

This module replaces hand-written lxml find()/findall() extraction code with a
declarative approach:

1. **SchemaDecoder** — Loads XSD schemas and decodes XML files into typed Python
   dicts using the ``xmlschema`` library.
2. **MappingConfig** — Declarative YAML configuration that maps XSD paths to
   SHACL ontology properties.
3. **ExtractionEngine** — Traverses the decoded dict according to the mapping
   config, applying collectors and transforms to produce the metadata dict.
4. **Transforms** — A registry of named transform functions for logic too complex
   to express as a simple path (e.g. weather classification).

Usage::

    from meta_data_extractor.engine import extract_metadata
    from pathlib import Path

    metadata = extract_metadata(Path("scenario.xosc"))
"""

from .api import extract_metadata
from .decoder import SchemaDecoder
from .engine import ExtractionEngine
from .mapping import MappingConfig

__all__ = [
    "extract_metadata",
    "ExtractionEngine",
    "MappingConfig",
    "SchemaDecoder",
]
