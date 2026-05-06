"""SHACL-driven CLI wizard for enriching JSON-LD metadata.

Parses a combined SHACL Turtle file to discover required and optional
properties, compares against an existing JSON-LD instance, and prompts
the user to fill in any missing values interactively.

Supports two backends:

* **local** — parse SHACL with rdflib (basic constraints only)
* **api**   — delegate to the sd-creation-wizard TypeScript API which handles
  conditional SHACL constructs (``sh:or``, ``sh:and``, ``sh:xone``)
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
    """Run the interactive CLI wizard using local SHACL parsing.

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
    print("  SD Creation Wizard  (CLI — local mode)")
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


# ── API-backed enrichment ───────────────────────────────────────────


def _prompt_api_property(
    constraint: dict, current: str | None = None
) -> str | tuple[str, str] | None:
    """Prompt the user for a single property based on API shape constraints.

    Returns:
        A string value for simple properties, a ``(prop_key, value)`` tuple
        when an ``sh:or`` branch carries its own path, or *current* unchanged.
    """
    required = (constraint.get("minCount") or 0) >= 1
    tag = "\033[91m*\033[0m" if required else " "
    name = constraint.get("name", constraint.get("path", {}).get("value", "?"))

    desc_map = constraint.get("description") or {}
    desc = desc_map.get("en", "")

    print(f"\n  {tag} {name}", end="")
    if desc:
        print(f"  —  {desc}", end="")
    print()

    if current is not None:
        print(f"    Current: \033[92m{current}\033[0m")

    # sh:or — let user pick which branch
    or_options = constraint.get("or")
    if or_options and isinstance(or_options, list):
        print("    This property allows alternative types:")
        for i, opt in enumerate(or_options, 1):
            opt_path = opt.get("path", {})
            opt_name = opt.get("name") or (
                f"{opt_path.get('prefix', '')}:{opt_path.get('value', '')}"
                if opt_path.get("value")
                else f"Option {i}"
            )
            print(f"    {i}) {opt_name}")
        raw = input(f"    Select [1–{len(or_options)}] (Enter to skip): ").strip()
        if not raw:
            return current
        if raw.isdigit() and 1 <= int(raw) <= len(or_options):
            selected = or_options[int(raw) - 1]
            result = _prompt_api_property(selected, current)
            # If the selected branch has its own path, return (key, value)
            # so the caller knows which JSON-LD key to use.
            branch_path = selected.get("path") or {}
            if branch_path.get("value"):
                branch_key = (
                    f"{branch_path['prefix']}:{branch_path['value']}"
                    if branch_path.get("prefix")
                    else branch_path["value"]
                )
                val = result[1] if isinstance(result, tuple) else result
                return (branch_key, val)
            return result
        print("    Invalid selection — keeping current value.")
        return current

    # sh:in — enumeration
    in_options = constraint.get("in") or []
    if in_options:
        for i, opt in enumerate(in_options, 1):
            val = opt.get("value", str(opt)) if isinstance(opt, dict) else str(opt)
            marker = " \033[92m←\033[0m" if val == current else ""
            print(f"    {i}) {val}{marker}")
        raw = input(f"    Select [1–{len(in_options)}]: ").strip()
        if not raw:
            return current
        if raw.isdigit() and 1 <= int(raw) <= len(in_options):
            opt = in_options[int(raw) - 1]
            return opt.get("value", str(opt)) if isinstance(opt, dict) else str(opt)
        print("    Invalid selection — keeping current value.")
        return current

    # Typed input
    dt = constraint.get("datatype") or {}
    type_label = dt.get("value", "text") if isinstance(dt, dict) else "text"
    hint = " (Enter to keep)" if current is not None else ""
    raw = input(f"    [{type_label}]{hint}: ").strip()

    if not raw:
        return current
    return raw


def _enrich_from_api(
    json_data: dict,
    shapes: list[dict],
    matched: dict[str, str],
    prefix_list: list[dict],
) -> bool:
    """Walk the API shape model and prompt for missing/empty values.

    Returns True if json_data was modified.
    """
    modified = False

    for shape in shapes:
        shape_name = shape.get("schema", "")
        constraints = shape.get("constraints") or []
        if not constraints:
            continue

        print(f"\n{'─' * 56}")
        print(f"  {shape_name}")
        print(f"{'─' * 56}")

        for constraint in constraints:
            # sh:or at the constraint level (no path on wrapper itself)
            # — the branches carry their own paths.
            or_options = constraint.get("or")
            if (
                or_options
                and isinstance(or_options, list)
                and not constraint.get("path")
            ):
                new_val = _prompt_api_property(constraint, None)
                if isinstance(new_val, tuple):
                    branch_key, branch_val = new_val
                    if branch_val is not None:
                        json_data[branch_key] = branch_val
                        modified = True
                continue

            path_info = constraint.get("path") or {}
            prefix = path_info.get("prefix", "")
            value = path_info.get("value", "")
            if not value:
                continue

            # Build the full property key used in the JSON-LD
            prop_key = f"{prefix}:{value}" if prefix else value

            # Children → nested shape (recurse when data available)
            children_ref = constraint.get("children")
            if children_ref:
                # Find the nested shape
                nested = next(
                    (s for s in shapes if s.get("schema") == children_ref), None
                )
                if nested and isinstance(json_data.get(prop_key), dict):
                    sub = _enrich_from_api(
                        json_data[prop_key], [nested], matched, prefix_list
                    )
                    modified = modified or sub
                continue

            # Leaf property — check matched value and prompt
            # Build possible URI keys for the matched map
            ns_url = ""
            for p in prefix_list:
                if p.get("alias") == prefix:
                    ns_url = p.get("url", "")
                    break
            full_uri = f"{ns_url}{value}" if ns_url else prop_key

            current = matched.get(full_uri) or json_data.get(prop_key)
            if isinstance(current, dict):
                current = current.get("@value", current.get("value"))

            new_val = _prompt_api_property(constraint, current)

            # _prompt_api_property may return (key, value) for sh:or branches
            if isinstance(new_val, tuple):
                branch_key, branch_val = new_val
                if branch_val is not None and branch_val != current:
                    json_data[branch_key] = branch_val
                    modified = True
            elif new_val is not None and new_val != current:
                json_data[prop_key] = new_val
                modified = True

    return modified


def run_wizard_api(
    jsonld_path: Path,
    shacl_path: Path,
    output_path: Path,
    api_url: str,
) -> bool:
    """Run the wizard using the sd-creation-wizard TypeScript API backend.

    The API resolves conditional SHACL constructs (sh:or, sh:and, etc.)
    that the local parser cannot handle.

    Returns True if the JSON-LD was modified.
    """
    from wizard_caller.api_client import convert_and_prefill

    result = convert_and_prefill(api_url, shacl_path, jsonld_path)

    shacl_model = result.get("shaclModel", {})
    matched = result.get("matchedSubjects", {})
    shapes = shacl_model.get("shapes", [])
    prefix_list = shacl_model.get("prefixList", [])

    with open(jsonld_path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n{'=' * 60}")
    print("  SD Creation Wizard  (CLI — API mode)")
    print(f"{'=' * 60}")
    print(f"  JSON-LD  : {jsonld_path.name}")
    print(f"  SHACL    : {shacl_path.name}")
    print(f"  API      : {api_url}")
    print(f"  Shapes   : {len(shapes)} resolved")
    print(f"  Prefilled: {len(matched)} value(s)")
    print(f"  \033[91m*\033[0m = required field")

    modified = _enrich_from_api(data, shapes, matched, prefix_list)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if modified:
        print(f"\n\033[92m[OK]\033[0m Enhanced JSON-LD written to {output_path}")
    else:
        print(f"\n[OK] No changes — JSON-LD copied to {output_path}")

    return modified
