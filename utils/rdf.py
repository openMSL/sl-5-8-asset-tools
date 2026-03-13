from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any, Dict
from rdflib import Graph, BNode
from rdflib.namespace import SH, RDF
from rdflib.collection import Collection
from utils.constants import ENVITED_URL

import logging

logger = logging.getLogger(__name__)
SL58_ROOT = Path(__file__).resolve().parent.parent
OMB_ROOT = SL58_ROOT / "submodules" / "ontology-management-base"


@lru_cache(maxsize=1)
def _get_omb_resolver() -> Any:
    """Return the OMB registry resolver for the nested ontology submodule."""

    if not (OMB_ROOT / "artifacts" / "catalog-v001.xml").exists():
        raise RuntimeError(
            "ontology-management-base artifacts are missing. "
            "Run `make setup` to initialize the required submodule dependencies."
        )

    try:
        registry_module = import_module("src.tools.utils.registry_resolver")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ontology-management-base Python package is unavailable. "
            "Run `make setup` so sl-5-8 can reuse OMB's graph loading logic."
        ) from exc

    RegistryResolver = getattr(registry_module, "RegistryResolver")
    return RegistryResolver(OMB_ROOT)


@lru_cache(maxsize=1)
def _get_omb_context_url_map() -> dict[str, Path]:
    """Build the local context URL map from OMB's catalogs."""

    resolver = _get_omb_resolver()

    try:
        context_module = import_module("src.tools.utils.context_resolver")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ontology-management-base context resolver is unavailable. "
            "Run `make setup` so sl-5-8 can reuse OMB's offline JSON-LD loading."
        ) from exc

    build_context_url_map = getattr(context_module, "build_context_url_map")
    context_url_map = build_context_url_map(resolver, OMB_ROOT)
    if not context_url_map:
        raise RuntimeError(
            f"No OMB context mappings were discovered under {OMB_ROOT!s}."
        )
    return context_url_map


def _load_jsonld_file_with_omb(jsonld_file: Path) -> Graph:
    """Load JSON-LD via OMB so local contexts are inlined before parsing."""

    graph_loader_module = import_module("src.tools.utils.graph_loader")
    load_jsonld_files = getattr(graph_loader_module, "load_jsonld_files")

    context_url_map = _get_omb_context_url_map()
    data_graph, _ = load_jsonld_files(
        [jsonld_file],
        SL58_ROOT,
        store="default",
        context_url_map=context_url_map,
    )
    return data_graph


def _load_shacl_files_with_omb(data_graph: Graph) -> list[Path]:
    """Resolve SHACL files from OMB's registry based on rdf:type usage."""

    resolver = _get_omb_resolver()

    try:
        schema_module = import_module("src.tools.validators.shacl.schema_discovery")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ontology-management-base schema discovery is unavailable. "
            "Run `make setup` so sl-5-8 can reuse OMB's catalog-based SHACL logic."
        ) from exc

    discover_required_schemas = getattr(schema_module, "discover_required_schemas")
    extract_rdf_types = getattr(schema_module, "extract_rdf_types")
    rdf_types = extract_rdf_types(data_graph)
    _, shacl_paths, unresolved_types = discover_required_schemas(rdf_types, resolver)

    if unresolved_types:
        logger.debug(
            "OMB could not resolve SHACL domains for types: %s",
            ", ".join(sorted(unresolved_types)),
        )

    if not shacl_paths:
        raise RuntimeError(
            "OMB schema discovery returned no SHACL files for the given JSON-LD graph."
        )

    return [resolver.to_absolute(path) for path in shacl_paths]


def get_prefixes(graph: Graph) -> Dict[str, str]:
    """Extract prefixes from an RDF graph."""

    prefixes = {
        prefix: str(namespace)
        for prefix, namespace in graph.namespace_manager.namespaces()
        if str(namespace).startswith(ENVITED_URL)
    }
    return prefixes


def load_jsonld_file(jsonld_file: Path) -> Graph:
    """Load JSON-LD into an RDF graph, preferring OMB's offline loader."""

    if not jsonld_file.exists():
        raise FileNotFoundError(f"JsonLD files not found: {jsonld_file}")

    logger.info(f"adding jsonld file to data graph: {jsonld_file}.")
    return _load_jsonld_file_with_omb(jsonld_file)


def load_shacl_files(shacl_files: list) -> Graph:
    """load shacl as rdf graph"""

    shacl_graph = Graph()
    for shacl_file in shacl_files:
        shacl_graph.parse(shacl_file, format="turtle")
    return shacl_graph


def get_shacl_from_json_graph(data_graph: Graph) -> Graph:
    """Load the SHACL graphs for a JSON-LD graph via OMB schema discovery."""

    shacl_files = _load_shacl_files_with_omb(data_graph)
    shacl_graph = load_shacl_files(shacl_files)
    return shacl_graph


def resolve_value(graph: Graph, value: Any) -> Any:
    """Resolve a value; expand blank nodes and RDF lists recursively."""
    if isinstance(value, BNode):
        # Detect RDF list via rdf:first
        if (value, RDF.first, None) in graph:
            items = list(Collection(graph, value))
            return [resolve_value(graph, it) for it in items]
        return convert_bnode_to_dict(graph, value)

    # For URIs or literals, return as string
    return str(value)


def convert_bnode_to_dict(graph: Graph, bnode: BNode) -> Dict[str, Any]:
    """Convert a blank node recursively to dict."""
    result: Dict[str, Any] = {}
    for pred, obj in graph.predicate_objects(bnode):
        result[str(pred)] = resolve_value(graph, obj)
    return result


def convert_graph_to_dict(graph: Graph, search_node_shape: bool) -> Dict[str, Any]:
    """convert rdf graph to dict, resolve blank nodes"""

    graph_dict = {}
    type_to_search = SH.NodeShape if search_node_shape else SH.NodeKind

    for node_shape in graph.subjects(RDF.type, type_to_search):
        prop_list = []

        # Collect shape-level constraints (e.g., sh:or, sh:message) in a single dict
        shape_level: Dict[str, Any] = {}
        for pred, obj in graph.predicate_objects(node_shape):
            if pred in (RDF.type, SH.property):
                continue
            shape_level[str(pred)] = resolve_value(graph, obj)

        # Collect property shapes (your existing behavior)
        for prop in graph.objects(node_shape, SH.property):
            values_dict = {}
            for detail, value in graph.predicate_objects(prop):
                values_dict[str(detail)] = resolve_value(graph, value)
            prop_list.append(values_dict)

        # Keep the original output type: List[Dict]
        # Add shape-level dict only if it exists (and especially helpful for shapes with no sh:property)
        if shape_level:
            prop_list.insert(0, shape_level)

        graph_dict[str(node_shape)] = prop_list

    return graph_dict
