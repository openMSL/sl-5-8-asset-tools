"""SHACL-driven CLI wizard for enriching JSON-LD metadata.

Parses a combined SHACL Turtle file to discover required and optional
properties, compares against an existing JSON-LD instance, and prompts
the user to fill in any missing values interactively.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.collection import Collection
from rdflib.namespace import RDF, XSD

SH = Namespace("http://www.w3.org/ns/shacl#")

logger = logging.getLogger(__name__)

# ── SHACL Parsing ────────────────────────────────────────────────────


def _local(uri) -> str:
    """Extract the local name from a URI (part after last # or /)."""
    s = str(uri)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _int_or_none(val):
    return int(val) if val is not None else None


def _extract_property(g: Graph, node) -> dict | None:
    """Extract constraints from a single SHACL property shape."""
    path = g.value(node, SH.path)
    if not path:
        return None

    prop = {
        "path_uri": str(path),
        "path_local": _local(path),
        "name": str(g.value(node, SH.name) or _local(path)),
        "description": str(g.value(node, SH.description) or ""),
        "min_count": int(g.value(node, SH.minCount) or 0),
        "max_count": _int_or_none(g.value(node, SH.maxCount)),
        "datatype": str(g.value(node, SH.datatype))
        if g.value(node, SH.datatype)
        else None,
        "node_shape": str(g.value(node, SH.node)) if g.value(node, SH.node) else None,
        "order": int(g.value(node, SH.order) or 999),
        "enum": None,
        "message": str(g.value(node, SH.message) or ""),
    }

    in_node = g.value(node, SH["in"])
    if in_node:
        prop["enum"] = [str(v) for v in Collection(g, in_node)]

    return prop


def parse_shapes(shacl_path: Path) -> tuple[dict, dict, dict]:
    """Parse a SHACL Turtle file.

    Returns:
        by_target:  {target_class_uri: shape_info}
        by_shape:   {shape_uri: shape_info}
        prefix_map: {prefix: namespace_uri}
    """
    g = Graph()
    g.parse(str(shacl_path), format="turtle")

    prefix_map = {str(p): str(ns) for p, ns in g.namespaces()}
    by_target: dict[str, dict] = {}
    by_shape: dict[str, dict] = {}

    for shape in g.subjects(RDF.type, SH.NodeShape):
        target = g.value(shape, SH.targetClass)
        props = []
        for pnode in g.objects(shape, SH.property):
            prop = _extract_property(g, pnode)
            if prop:
                props.append(prop)
        props.sort(key=lambda p: p["order"])

        info = {
            "shape_uri": str(shape),
            "target_class": str(target) if target else None,
            "properties": props,
        }
        by_shape[str(shape)] = info
        if target:
            by_target[str(target)] = info

    return by_target, by_shape, prefix_map


# ── JSON-LD Key Resolution ──────────────────────────────────────────


def find_key(json_obj: dict, path_uri: str, prefix_map: dict) -> str | None:
    """Find the JSON-LD key matching a SHACL property path URI.

    Tries: exact URI → prefixed name → local name.
    """
    if path_uri in json_obj:
        return path_uri

    for prefix, ns in prefix_map.items():
        if path_uri.startswith(ns):
            prefixed = f"{prefix}:{path_uri[len(ns) :]}"
            if prefixed in json_obj:
                return prefixed

    local = _local(path_uri)
    if local in json_obj:
        return local

    return None


def insert_key(json_obj: dict, path_uri: str, prefix_map: dict) -> str:
    """Determine the best key to use when inserting a new property.

    Matches the style of existing keys in the same object.
    """
    has_prefixed = any(":" in k and not k.startswith("@") for k in json_obj)

    if has_prefixed:
        for prefix, ns in prefix_map.items():
            if path_uri.startswith(ns):
                return f"{prefix}:{path_uri[len(ns) :]}"

    return _local(path_uri)


# ── Datatype Helpers ─────────────────────────────────────────────────

_TYPE_INFO: dict[str, tuple[str, type]] = {
    str(XSD.string): ("text", str),
    str(XSD.float): ("float", float),
    str(XSD.double): ("float", float),
    str(XSD.decimal): ("float", float),
    str(XSD.integer): ("integer", int),
    str(XSD.int): ("integer", int),
    str(XSD.nonNegativeInteger): ("non-negative integer", int),
    str(XSD.boolean): ("true/false", lambda v: v.strip().lower() == "true"),
}


# ── Interactive Prompting ────────────────────────────────────────────


def prompt_value(prop: dict, current=None):
    """Prompt the user for a single property value.

    Returns the new value, or the current value if the user skips.
    """
    required = prop["min_count"] >= 1
    tag = "\033[91m*\033[0m" if required else " "

    print(f"\n  {tag} {prop['name']}", end="")
    if prop["description"]:
        print(f"  —  {prop['description']}", end="")
    print()

    if current is not None:
        print(f"    Current: \033[92m{current}\033[0m")

    if prop.get("enum"):
        for i, opt in enumerate(prop["enum"], 1):
            marker = " \033[92m←\033[0m" if opt == current else ""
            print(f"    {i}) {opt}{marker}")
        raw = input("    Select [1–{}]: ".format(len(prop["enum"]))).strip()
        if not raw:
            return current
        if raw.isdigit() and 1 <= int(raw) <= len(prop["enum"]):
            return prop["enum"][int(raw) - 1]
        print("    Invalid selection — keeping current value.")
        return current

    type_label, converter = _TYPE_INFO.get(prop.get("datatype", ""), ("text", str))
    hint = f" (Enter to keep)" if current is not None else ""
    raw = input(f"    [{type_label}]{hint}: ").strip()

    if not raw:
        return current

    try:
        return converter(raw)
    except (ValueError, TypeError):
        print(f"    Invalid {type_label} — keeping current value.")
        return current


# ── JSON-LD Enrichment ──────────────────────────────────────────────


def enrich(
    json_data: dict,
    by_target: dict,
    by_shape: dict,
    prefix_map: dict,
    depth: int = 0,
) -> bool:
    """Walk a JSON-LD node, prompt for missing properties. Returns True if modified."""
    type_val = json_data.get("@type")
    if not type_val:
        return False

    type_uri = _expand(type_val, prefix_map)
    shape = by_target.get(type_uri)
    if not shape:
        for uri, s in by_target.items():
            if _local(uri) == _local(type_uri):
                shape = s
                break
    if not shape:
        return False

    indent = "  " * depth
    print(f"\n{indent}{'─' * (56 - depth * 2)}")
    print(f"{indent}  {_local(type_uri)}")
    print(f"{indent}{'─' * (56 - depth * 2)}")

    modified = False

    for prop in shape["properties"]:
        key = find_key(json_data, prop["path_uri"], prefix_map)

        # Nested shape — recurse
        if prop.get("node_shape"):
            if key and isinstance(json_data.get(key), dict):
                sub = enrich(json_data[key], by_target, by_shape, prefix_map, depth + 1)
                modified = modified or sub
            elif prop["min_count"] >= 1 and not key:
                nested_shape = by_shape.get(prop["node_shape"])
                if nested_shape and nested_shape.get("target_class"):
                    new_key = insert_key(json_data, prop["path_uri"], prefix_map)
                    tc = nested_shape["target_class"]
                    tc_short = _compact(tc, prefix_map)
                    json_data[new_key] = {"@type": tc_short}
                    sub = enrich(
                        json_data[new_key], by_target, by_shape, prefix_map, depth + 1
                    )
                    modified = True
            continue

        # Leaf property
        current = json_data.get(key) if key else None
        new_val = prompt_value(prop, current)

        if new_val is not None and new_val != current:
            write_key = key or insert_key(json_data, prop["path_uri"], prefix_map)
            json_data[write_key] = new_val
            modified = True

    return modified


def _expand(val: str, prefix_map: dict) -> str:
    """Expand a prefixed name to a full URI."""
    if ":" in val and not val.startswith("http"):
        prefix, local = val.split(":", 1)
        ns = prefix_map.get(prefix)
        if ns:
            return ns + local
    return val


def _compact(uri: str, prefix_map: dict) -> str:
    """Compact a full URI to a prefixed name."""
    for prefix, ns in prefix_map.items():
        if uri.startswith(ns) and prefix:
            return f"{prefix}:{uri[len(ns) :]}"
    return uri


# ── Public API ───────────────────────────────────────────────────────


def run_wizard(jsonld_path: Path, shacl_path: Path, output_path: Path) -> bool:
    """Run the interactive CLI wizard.

    Returns True if the JSON-LD was modified.
    """
    by_target, by_shape, prefix_map = parse_shapes(shacl_path)

    with open(jsonld_path, encoding="utf-8") as f:
        data = json.load(f)

    # Merge JSON-LD @context prefix definitions into our prefix map
    for ctx in data.get("@context", []):
        if isinstance(ctx, dict):
            for k, v in ctx.items():
                if not k.startswith("@") and isinstance(v, str):
                    if v.endswith("/") or v.endswith("#"):
                        prefix_map[k] = v

    print(f"\n{'=' * 60}")
    print("  SD Creation Wizard  (CLI)")
    print(f"{'=' * 60}")
    print(f"  JSON-LD : {jsonld_path.name}")
    print(f"  SHACL   : {shacl_path.name}")
    print(f"  Shapes  : {len(by_target)} discovered")
    print(f"  \033[91m*\033[0m = required field")

    modified = enrich(data, by_target, by_shape, prefix_map)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if modified:
        print(f"\n\033[92m[OK]\033[0m Enhanced JSON-LD written to {output_path}")
    else:
        print(f"\n[OK] No changes — JSON-LD copied to {output_path}")

    return modified
