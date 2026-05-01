"""Extraction engine: traverses decoded XML dicts using mapping rules.

The engine takes a decoded dict (from SchemaDecoder) and a MappingConfig,
then resolves each rule to produce the final metadata dict.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .mapping import MappingConfig, MappingRule
from .transforms import get_transform

logger = logging.getLogger(__name__)


class ExtractionEngine:
    """Traverses decoded XML dicts using declarative mapping rules."""

    def extract(
        self,
        data: dict[str, Any],
        config: MappingConfig,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute all mapping rules against the decoded data.

        Args:
            data: Decoded XML dict from SchemaDecoder.
            config: Mapping configuration with rules.
            context: Optional extra context passed to transforms (e.g., file path,
                     element tree for transforms that need raw lxml access).

        Returns:
            Flat dict of {ontology_property: extracted_value} for non-None results.
        """
        context = context or {}
        result: dict[str, Any] = {}

        for rule in config.rules:
            try:
                value = self._execute_rule(data, rule, context)
                if value is not None and value != "" and value != []:
                    result[rule.property] = value
            except Exception:
                logger.exception("Failed to extract %s", rule.property)

        return result

    def _execute_rule(
        self,
        data: dict[str, Any],
        rule: MappingRule,
        context: dict[str, Any],
    ) -> Any:
        """Execute a single mapping rule."""
        # Static constant value
        if rule.value is not None:
            return self._cast(rule.value, rule.type)

        # Transform-only rule (no path)
        if rule.transform and not rule.path:
            transform_fn = get_transform(rule.transform)
            return transform_fn(data, **rule.args, **context)

        # Path-based extraction
        if rule.path:
            values = self._resolve_path(data, rule.path)

            # Also search additional paths
            for extra_path in rule.also_search:
                extra_values = self._resolve_path(data, extra_path)
                values.extend(extra_values)

            # Apply filter if specified
            if rule.filter:
                values = self._apply_filter(values, rule.filter)

            # Apply transform if specified
            if rule.transform:
                transform_fn = get_transform(rule.transform)
                return transform_fn(values, **rule.args, **context)

            # Apply collector
            collected = self._collect(values, rule.collector)

            # Apply format string if specified
            if rule.format_str and collected is not None:
                try:
                    return rule.format_str.format(value=collected)
                except (KeyError, IndexError):
                    return str(collected)

            # Cast to target type
            return self._cast(collected, rule.type)

        return None

    def _resolve_path(self, data: Any, path: str) -> list[Any]:
        """Resolve a dot-notation path into a list of matched values.

        Supports:
            - ``FileHeader.@revMajor`` — nested dict access, @ for attributes
            - ``Entities.ScenarioObject[*].Vehicle`` — array wildcard
            - ``road[*].@length`` — attribute on array items
            - ``Weather`` — direct key access at current level
        """
        parts = _split_path(path)
        return self._walk(data, parts)

    def _walk(self, node: Any, parts: list[str]) -> list[Any]:
        """Recursively walk the path parts, collecting values."""
        if not parts:
            if node is None:
                return []
            return [node]

        head, *tail = parts

        # Array wildcard: "Element[*]"
        if head.endswith("[*]"):
            key = head[:-3]
            child = self._get_child(node, key)
            if child is None:
                return []
            # Normalize to list
            items = child if isinstance(child, list) else [child]
            results = []
            for item in items:
                results.extend(self._walk(item, tail))
            return results

        # Regular key access
        child = self._get_child(node, head)
        if child is None:
            return []
        return self._walk(child, tail)

    @staticmethod
    def _get_child(node: Any, key: str) -> Any:
        """Get a child from a dict node. Handles @ prefix for attributes."""
        if not isinstance(node, dict):
            return None
        # xmlschema uses @attr for attributes
        if key.startswith("@"):
            return node.get(key)
        return node.get(key)

    @staticmethod
    def _apply_filter(values: list[Any], filter_spec: dict) -> list[Any]:
        """Filter values based on a predicate specification.

        Supported filters:
            - {"attribute": "subtype", "equals": "trafficLight"}
            - {"attribute": "country", "not_equals": "OpenDRIVE"}
        """
        attribute = filter_spec.get("attribute", "")
        equals = filter_spec.get("equals")
        not_equals = filter_spec.get("not_equals")

        result = []
        for v in values:
            if not isinstance(v, dict):
                continue
            attr_val = v.get(f"@{attribute}")
            if equals is not None and attr_val == equals:
                result.append(v)
            elif not_equals is not None and attr_val != not_equals:
                result.append(v)
            elif equals is None and not_equals is None:
                result.append(v)
        return result

    @staticmethod
    def _collect(values: list[Any], collector: str) -> Any:
        """Aggregate a list of values according to the collector strategy."""
        if not values:
            # count should return 0 for empty results, not None
            if collector == "count":
                return 0
            return None

        if collector == "first":
            return values[0]

        if collector == "all":
            # Flatten and comma-join
            flat = []
            for v in values:
                if isinstance(v, (list, tuple)):
                    flat.extend(str(x) for x in v)
                else:
                    flat.append(str(v))
            return ", ".join(flat)

        if collector == "all_unique":
            flat = set()
            for v in values:
                if isinstance(v, (list, tuple)):
                    flat.update(str(x) for x in v)
                else:
                    flat.add(str(v))
            return ", ".join(sorted(flat))

        if collector == "count":
            return len(values)

        if collector == "sum":
            return sum(float(v) for v in values if v is not None)

        if collector == "min":
            numeric = [float(v) for v in values if v is not None]
            return min(numeric) if numeric else None

        if collector == "max":
            numeric = [float(v) for v in values if v is not None]
            return max(numeric) if numeric else None

        if collector == "join_lines":
            return "\n".join(str(v) for v in values)

        logger.warning("Unknown collector '%s', using 'first'", collector)
        return values[0] if values else None

    @staticmethod
    def _cast(value: Any, target_type: str) -> Any:
        """Cast a value to the specified target type."""
        if value is None:
            return None

        try:
            if target_type == "string":
                return str(value)
            if target_type == "float":
                return float(value)
            if target_type == "int":
                return int(float(value))
            if target_type == "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            if target_type == "raw":
                return value
        except (ValueError, TypeError):
            logger.debug("Cannot cast %r to %s", value, target_type)
            return None

        return value


# ═══════════════════════════════════════════════════════════════════════════════
# Path parsing utilities
# ═══════════════════════════════════════════════════════════════════════════════

_PATH_SPLITTER = re.compile(r"(?<!\[)\.")


def _split_path(path: str) -> list[str]:
    """Split a dot-notation path respecting array brackets.

    "Entities.ScenarioObject[*].Vehicle.@vehicleCategory"
    → ["Entities", "ScenarioObject[*]", "Vehicle", "@vehicleCategory"]
    """
    return _PATH_SPLITTER.split(path)
