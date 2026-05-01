"""Declarative mapping configuration.

Loads YAML mapping files that define how XSD paths map to SHACL ontology
properties. Each mapping entry specifies:

- ``path``: Dot-notation path into the decoded dict (supports ``[*]`` for arrays)
- ``value``: Static constant value
- ``transform``: Name of a registered transform function
- ``collector``: How to aggregate multiple matches (first, all, all_unique, count, sum, min, max)
- ``type``: Expected output type (string, float, int, bool)
- ``also_search``: Additional paths to merge results from
- ``filter``: Predicate to include/exclude matches
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class MappingRule:
    """A single property mapping rule."""

    property: str
    path: str | None = None
    value: Any = None
    transform: str | None = None
    collector: str = "first"
    type: str = "string"
    also_search: list[str] = field(default_factory=list)
    filter: dict[str, Any] | None = None
    format_str: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class MappingConfig:
    """Complete mapping configuration for one asset type."""

    schema_format: str
    source_xsd: str
    ontology_prefix: str
    rules: list[MappingRule]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> MappingConfig:
        """Load a mapping config from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        rules = []
        for prop, rule_def in raw.get("mappings", {}).items():
            if isinstance(rule_def, str):
                # Shorthand: just a path
                rules.append(MappingRule(property=prop, path=rule_def))
            elif isinstance(rule_def, dict):
                rules.append(
                    MappingRule(
                        property=prop,
                        path=rule_def.get("path"),
                        value=rule_def.get("value"),
                        transform=rule_def.get("transform"),
                        collector=rule_def.get("collector", "first"),
                        type=rule_def.get("type", "string"),
                        also_search=rule_def.get("also_search", []),
                        filter=rule_def.get("filter"),
                        format_str=rule_def.get("format"),
                        args=rule_def.get("args", {}),
                    )
                )
            else:
                logger.warning("Skipping invalid mapping rule for %s", prop)

        return cls(
            schema_format=raw.get("schema_format", ""),
            source_xsd=raw.get("source_xsd", ""),
            ontology_prefix=raw.get("ontology_prefix", ""),
            rules=rules,
            metadata=raw.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, data: dict) -> MappingConfig:
        """Create a MappingConfig from a plain dict (useful for testing)."""
        rules = []
        for prop, rule_def in data.get("mappings", {}).items():
            if isinstance(rule_def, str):
                rules.append(MappingRule(property=prop, path=rule_def))
            elif isinstance(rule_def, dict):
                rules.append(
                    MappingRule(
                        property=prop,
                        path=rule_def.get("path"),
                        value=rule_def.get("value"),
                        transform=rule_def.get("transform"),
                        collector=rule_def.get("collector", "first"),
                        type=rule_def.get("type", "string"),
                        also_search=rule_def.get("also_search", []),
                        filter=rule_def.get("filter"),
                        format_str=rule_def.get("format"),
                        args=rule_def.get("args", {}),
                    )
                )

        return cls(
            schema_format=data.get("schema_format", ""),
            source_xsd=data.get("source_xsd", ""),
            ontology_prefix=data.get("ontology_prefix", ""),
            rules=rules,
            metadata=data.get("metadata", {}),
        )
