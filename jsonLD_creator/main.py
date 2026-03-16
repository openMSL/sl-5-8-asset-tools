from rdflib.namespace import SH
from rdflib import Graph, URIRef
from collections import defaultdict
from pathlib import Path
from typing import Any, Tuple, Union, Dict, List
from utils.rdf import get_prefixes, convert_graph_to_dict
from utils.http import get_url_for_download, download_shacl
from utils.json import write_json
from utils.constants import SHACL_NS, SHACL_FOLDER_NAME, GX_NS, ENVITED_URL

import shutil
import json
import logging
import argparse
import operator

logger = logging.getLogger(__name__)
SHACL_CACHE_DIR = Path(__file__).resolve().parent.parent / SHACL_FOLDER_NAME


# global config value with all shacls, dicts and jsonLD output
class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            # initalize config
            cls._instance.SHACLS = {}
            cls._instance.JSON_OUT = {}
        return cls._instance


config = Config()


# check if value is greater/smaller then value
def check_min_max(shacl_data, name: str, compare_value: int, op):
    if name in shacl_data:
        value = int(shacl_data[name])
        return op(value, compare_value)

    return None


# check if min count >= 1
def is_required_property(shacl_data):
    check = check_min_max(shacl_data, f"{SH}qualifiedMinCount", 1, operator.ge)
    if check is None:
        check = check_min_max(shacl_data, f"{SH}minCount", 1, operator.ge)

    if check is None:
        return False
    return check


def is_list_property(shacl_data):
    """Return True if the property can have multiple values (i.e., should be represented as a list)."""

    # If maxCount/qualifiedMaxCount is explicitly 1, it's NOT a list
    qmax = get_value("qualifiedMaxCount", shacl_data)
    if qmax is not None:
        return int(qmax) != 1

    maxc = get_value("maxCount", shacl_data)
    if maxc is not None:
        return int(maxc) != 1

    # If no maxCount is defined, SHACL allows multiple values by default -> treat as list
    return True


# get named value
def get_value(name, values):
    name_pre = "#" + name
    for key, data in values.items():
        if str(key).endswith(name_pre):
            return data
    return None


def collect_nodes(shape: Any, visited: set | None = None) -> List[str]:
    """Recursively collect all values under sh:node and sh:class and expand referenced shapes."""
    if visited is None:
        visited = set()

    nodes: List[str] = []

    if isinstance(shape, dict):
        for k, v in shape.items():
            # SHACL-node / SHACL-class
            if k.endswith(f"{SHACL_NS}node"):
                if isinstance(v, str):
                    nodes.append(v)

                    # Try to resolve referenced NodeShape further (e.g., ContentOrOddSceneryShape -> sh:or -> ...)
                    if v not in visited:
                        visited.add(v)
                        ns, _ = get_namespace_name_from_url(v)
                        if ns:
                            sh = get_shacl_shape(ns, v)
                            if sh is not None:
                                nodes.extend(collect_nodes(sh, visited))

                else:
                    nodes.extend(collect_nodes(v, visited))

            # qualifiedValueShape contain nested Shapes
            elif k.endswith(f"{SHACL_NS}qualifiedValueShape"):
                nodes.extend(collect_nodes(v, visited))

            # sh:and / sh:or
            elif k.endswith(f"{SHACL_NS}and") or k.endswith(f"{SHACL_NS}or"):
                if isinstance(v, list):
                    for item in v:
                        nodes.extend(collect_nodes(item, visited))
                else:
                    nodes.extend(collect_nodes(v, visited))

            # property-Array
            elif k.endswith(f"{SHACL_NS}property"):
                if isinstance(v, list):
                    for prop in v:
                        nodes.extend(collect_nodes(prop, visited))
                else:
                    nodes.extend(collect_nodes(v, visited))

    elif isinstance(shape, list):
        for item in shape:
            nodes.extend(collect_nodes(item, visited))

    elif isinstance(shape, str):
        nodes.append(shape)

    return nodes


#  Extracts the path and lists all target-node / class shapes, no matter how deeply they are nested.
def get_node_data(values: Dict[str, Any]) -> Tuple[str, List[str]]:
    path = get_value("path", values)
    node_list = collect_nodes(values)
    if node_list:
        return path, node_list
    else:
        return path, None


# detect value type (@value or @id) from shacl_values (Literal or IRI node)
def get_value_type(key: str, shacl_values: dict) -> str:
    literal_constraints = [
        "datatype",
        "pattern",
        "in",
        "minLength",
        "maxLength",
        "length",
        "minInclusive",
        "maxInclusive",
        "minExclusive",
        "maxExclusive",
        "languageIn",
    ]

    # Explicit: sh:nodeKind sh:IRI -> @id
    node_kind = get_value("nodeKind", shacl_values)
    if node_kind and str(node_kind).endswith("IRI"):
        return "@id"

    value_key = (
        "@value"
        if any(get_value(name, shacl_values) for name in literal_constraints)
        else "@id"
    )

    # set value_key
    if key == "gx:license" and value_key != "@value":
        value_key = "@value"  # no idea how to handle this via shacl values
    if key == "manifest:hasAccessRole" and value_key != "@id":
        value_key = "@id"
    if key == "manifest:hasCategory" and value_key != "@id":
        value_key = "@id"
    return value_key


def create_property_key(namespace: str, property_name: str) -> str:
    """Create a JSON-LD property key and remove ENVITED prefixes for leaf properties."""
    namespace_url = config.JSON_OUT["@context"].get(namespace)

    if namespace_url and ENVITED_URL in str(namespace_url):
        return property_name
    if namespace == "sh" and property_name == "conformsTo":  # special case
        return property_name

    return create_namespace_name(namespace, property_name)


# Comments in English as requested
INLINE_XSD_TYPES = {
    "string",
    "boolean",
    "decimal",
    "float",
    "double",
    "integer",
    "nonPositiveInteger",
    "negativeInteger",
    "long",
    "int",
    "short",
    "byte",
    "nonNegativeInteger",
    "unsignedLong",
    "unsignedInt",
    "unsignedShort",
    "unsignedByte",
    "positiveInteger",
    "anyURI",
}


# Comments in English as requested
def normalize_xsd_datatype(datatype: str) -> str:
    """Normalize datatype strings like 'xsd:float' or full XSD URIs to the local XSD name."""
    if datatype is None:
        return None

    dtype = str(datatype)

    if dtype.startswith("xsd:"):
        return dtype.split(":", 1)[1]

    xsd_prefix = "http://www.w3.org/2001/XMLSchema#"
    if dtype.startswith(xsd_prefix):
        return dtype[len(xsd_prefix) :]

    return dtype


# Comments in English as requested
def should_inline_literal(datatype: str) -> bool:
    """Return True if the datatype should be written as a plain JSON literal/string."""
    dtype = normalize_xsd_datatype(datatype)
    return dtype in INLINE_XSD_TYPES


# create property like
# "hdmap:elevationRange": {
#       "@value": "5.6",
#       "@type": "xsd:float"
#  },
# or
#  "manifest:hasAccessRole": {
#      "@type": "manifest:AccessRole",
#      "@id": "envited-x:isPublic"
# }
def create_property(
    namespace: str,
    property_name: str,
    value,
    datatype,
    name,
    jsonLD_dict: dict,
    shacl_values: dict,
    level: int,
):
    """
    Create a JSON-LD property.
    Inline standard XSD scalar/string/URI values as plain JSON values.
    Keep typed objects only where they are semantically needed.
    """
    key = create_property_key(namespace, property_name)
    full_key = create_namespace_name(namespace, property_name)
    value_key = get_value_type(full_key, shacl_values)

    # Resolve class type from SHACL if not explicitly provided
    if not name:
        name = class_types_from_shacl(shacl_values)

    assigned_type = name[0] if isinstance(name, list) and len(name) > 0 else name

    # Handle lists
    if isinstance(value, list):
        if value_key == "@id":
            # Keep typed IRI objects only if a class is required
            if assigned_type:
                jsonLD_dict[key] = [
                    {"@type": assigned_type, "@id": list_value} for list_value in value
                ]
            else:
                jsonLD_dict[key] = value
        else:
            # Lists of literals can stay as plain JSON values
            jsonLD_dict[key] = value

        logger.debug(f"{' ' * level * 3}add prop {key}")
        return

    # Handle single values
    if datatype:
        dtype_local = normalize_xsd_datatype(datatype)

        # Inline standard XSD literals such as string, float, integer, boolean, anyURI
        if should_inline_literal(dtype_local):
            jsonLD_dict[key] = value
        else:
            dtype = f"xsd:{dtype_local}" if ":" not in str(datatype) else str(datatype)
            jsonLD_dict[key] = {"@type": dtype, value_key: value}

    elif value_key == "@id":
        # Keep typed IRI objects only if a class is required
        if assigned_type:
            jsonLD_dict[key] = {"@type": assigned_type, "@id": value}
        else:
            jsonLD_dict[key] = value

    else:
        jsonLD_dict[key] = value

    logger.debug(f"{' ' * level * 3}add prop {key}")


# from 'https://ontologies.envited-x.net/manifest/v5/ontology#hasManifestReference'
# compare with registered prefixes, e.g  @prefix manifest: <https://ontologies.envited-x.net/manifest/v5/ontology#>
# to manifest, hasManifestReference
def get_namespace_name_from_url(url: str) -> Tuple[str, str]:
    # serach in own prefixes
    prefixes = config.JSON_OUT["@context"]
    for ns_key, uri_ref in prefixes.items():
        prefix = str(uri_ref)
        if url.startswith(prefix):
            shape_name = url[len(prefix) :]
            return ns_key, shape_name

    # try in other shacls
    for key, value in config.SHACLS.items():
        for ns_key, uri_ref in value["prefixes"].items():
            prefix = str(uri_ref)
            if url.startswith(prefix):
                shape_name = url[len(prefix) :]
                return ns_key, shape_name
    return None, None


# from hdmap:Quantity
# to hdmap, Quantity
def get_namespace(namespace_and_name):
    parts = namespace_and_name.split("::")
    if len(parts) != 2:
        raise ValueError(f"{namespace_and_name} not valid!")
    return parts[0], parts[1]


def get_name_from_url(url):
    parts = url.split("#")
    if len(parts) == 2:
        return parts[1]

    return None


def create_namespace_name(namespace: str, shapename: str) -> str:
    return f"{namespace}:{shapename}"


# create node like
# "hdmap:hasQuantity": {
#       "@type": "hdmap:Quantity",
def create_node(
    namespace: str,
    shapename: str,
    type: str,
    lsonLD: Union[Dict, List],
    is_list: bool,
    level: int,
) -> dict:
    node = {}
    node["@type"] = type

    key = create_namespace_name(namespace, shapename)

    if is_list:
        lsonLD.append(node)
    else:
        lsonLD[key] = node

    logger.debug(f"{' ' * level * 3}add node {key}")
    return node


# get shacl shema
def get_shacl_shema(namespace: str) -> dict:
    if namespace in config.SHACLS:
        return config.SHACLS[namespace]
    return None


# get shape from shacl data
def get_shacl_shape(namespace: str, shapename: str) -> list:
    shacl_graph_data = get_shacl_shema(namespace)
    if shacl_graph_data:
        if shapename in shacl_graph_data["dict"]:
            return shacl_graph_data["dict"][shapename]

    return None


# --- Add this helper near register_key (e.g., above it) ---
def _inject_manifest_mapping_candidates(nodes: list | None) -> list:
    """Add richer Link shapes for mapping hasManifest fields (even if not required by the sh:or)."""
    if nodes is None:
        nodes = []
    # Ensure list
    if not isinstance(nodes, list):
        nodes = list(nodes)

    # These URIs exist in your loaded SHACL set (manifest + envited-x)
    extra = [
        "https://w3id.org/ascs-ev/envited-x/manifest/v5/LinkShape",
        "https://w3id.org/ascs-ev/envited-x/envited-x/v3/ExtendedLinkShape",
    ]

    # Avoid duplicates
    for uri in extra:
        if uri not in nodes:
            nodes.append(uri)

    return nodes


def _extend_shape_with_additional_nodes(
    shape_value: list[dict], additional_nodes: list[str]
) -> list[dict]:
    merged_shape = list(shape_value)
    for node in additional_nodes:
        namespace_sub, _ = get_namespace_name_from_url(node)
        if not namespace_sub:
            continue

        additional_shape = get_shacl_shape(namespace_sub, node)
        if additional_shape:
            merged_shape.extend(additional_shape)

    return merge_property_constraints(merged_shape)


def class_types_from_shacl(shacl_values: dict) -> Union[str, None]:
    """
    Extracts the expected rdf:class from the SHACL property definition.
    Used to populate the @type field for IRI references.
    """
    class_iri = get_value("class", shacl_values)
    if class_iri:
        ns, name = get_namespace_name_from_url(class_iri)
        return create_namespace_name(ns, name)
    return None


def node_uri(node: Any) -> str:
    """Extract the URI from a node candidate (str or dict wrapper)."""
    if isinstance(node, dict):
        return list(node.keys())[0]
    return str(node)


def node_shape_priority(node: Any) -> int:
    """Higher value = process earlier. Prefer rich shapes like manifest:LinkShape."""
    u = node_uri(node)

    if u.endswith("/LinkShape") or u.endswith("LinkShape"):
        return 100
    if u.endswith("ManifestLinkReferenceShape"):
        return 80
    if u.endswith("ExtendedLinkShape"):
        return 10
    return 50


def score_shape_match(shape_properties: list, data_dict: dict) -> int:
    """
    Calculates how well a SHACL shape matches the provided data.
    Counts the number of keys in the data that are defined as properties in the shape.
    """
    if not isinstance(data_dict, dict):
        return 0

    score = 0
    data_keys = set(data_dict.keys())

    for prop in shape_properties:
        path = get_value("path", prop)
        if path:
            ns, ln = get_namespace_name_from_url(path)
            # Create the key as it appears in the source JSON (e.g., "gx:name")
            prop_key = create_namespace_name(ns, ln)
            if prop_key in data_keys:
                score += 1
    return score


def register_key(
    key: str,
    values: dict,
    meta_data: dict,
    nodes: list,
    namespace: str,
    shapename: str,
    path: str,
    is_required: bool,
    jsonLD_dict: dict,
    level: int,
):
    """
    Registers a key and processes its content based on SHACL shapes.
    Includes logic to select the best matching shape for 'sh:or' constraints.
    """
    if key in meta_data:
        if nodes is None:
            # Handle leaf properties (literals or simple IRIs)
            namespace_sub, name_subtype = get_namespace_name_from_url(path)
            type_url = get_value("datatype", values)

            if type_url:
                namespace_type, dt = get_namespace_name_from_url(type_url)
                create_property(
                    namespace,
                    shapename,
                    meta_data[key],
                    dt,
                    None,
                    jsonLD_dict,
                    values,
                    level,
                )
            else:
                # Get class hints from sh:class if available
                type_hints = class_types_from_shacl(values)
                create_property(
                    namespace,
                    shapename,
                    meta_data[key],
                    None,
                    type_hints,
                    jsonLD_dict,
                    values,
                    level,
                )

            del meta_data[key]
        else:
            # Handle nested objects (Nodes)
            if key == "hdmap:hasManifest":
                nodes = _inject_manifest_mapping_candidates(nodes)

            best_node = None
            max_score = -1

            # Evaluate all possible shapes to find the best match for the input data
            for node in nodes:
                uri = node if isinstance(node, str) else list(node)[0]
                ns_sub, type_name = get_namespace_name_from_url(uri)
                shape_val = get_shacl_shape(ns_sub, str(uri))

                if shape_val:
                    # Score based on property match
                    match_score = score_shape_match(shape_val, meta_data[key])
                    # Secondary priority based on configuration
                    priority = node_shape_priority(uri)

                    # Combined score (higher match count wins, then priority)
                    final_score = (match_score * 1000) + priority

                    if final_score > max_score:
                        max_score = final_score
                        best_node = (uri, ns_sub, type_name, shape_val)

            if best_node:
                uri, ns_sub, type_name, shape_val = best_node
                used_ns, _ = get_namespace_name_from_url(path)

                if key.endswith(":hasResourceDescription"):
                    shape_val = _extend_shape_with_additional_nodes(
                        shape_val,
                        [f"{GX_NS}VirtualResourceShape"],
                    )

                # Determine the LD-type string (e.g., manifest:Link or hdmap:ResourceDescription)
                type_without_shape = type_name.replace("Shape", "")
                # Special handling for Link typing
                if "Link" in type_name:
                    type_str = (
                        "manifest:Link"
                        if "manifest" in config.JSON_OUT["@context"]
                        else "envited-x:Link"
                    )
                else:
                    type_str = create_namespace_name(ns_sub, type_without_shape)

                created_node = create_node(
                    used_ns, shapename, type_str, jsonLD_dict, False, level
                )
                # Recursively process the nested structure
                process_node(shape_val, meta_data[key], None, created_node, level + 1)

                if not meta_data[key]:
                    del meta_data[key]

    elif is_required:
        pass  # empty required nodes are omitted for now


# register list of key + value to json ld
def register_list(
    key: str,
    values: dict,
    meta_data: dict,
    nodes: list,
    namespace: str,
    shapename: str,
    path: str,
    is_required: bool,
    lsonLD_dict: dict,
    level: int,
):

    if key in meta_data:
        # Normalize single objects to a list of one element
        if not isinstance(meta_data[key], list):
            meta_data[key] = [meta_data[key]]

        created_nodes = []
        for sub_meta_data in meta_data[key]:
            created_node = None
            if nodes:
                for node in nodes:
                    namespace_sub, type = get_namespace_name_from_url(node)
                    shape_value_sub = get_shacl_shape(namespace_sub, str(node))
                    if shape_value_sub is None:
                        continue

                    if created_node is None:
                        type_without_shape = type.replace("Shape", "")
                        type_str = create_namespace_name(
                            namespace_sub, type_without_shape
                        )
                        created_node = create_node(
                            namespace_sub,
                            shapename,
                            type_str,
                            created_nodes,
                            True,
                            level,
                        )
                    # only subnodes / properties of further nodes are registered
                    # Go deeper
                    process_node(
                        shape_value_sub, sub_meta_data, None, created_node, level + 1
                    )
            else:
                # Register as property (list of literals case)
                register_key(
                    key,
                    values,
                    meta_data,
                    None,
                    namespace,
                    shapename,
                    path,
                    is_required,
                    lsonLD_dict,
                    level,
                )

        if key in meta_data and all(not elem for elem in meta_data[key]):
            del meta_data[key]

        if created_nodes:
            lsonLD_dict[key] = created_nodes

    elif is_required:
        pass  # empty required nodes are omitted for now


# Comments in English as requested
def merge_property_constraints(shape_value: list[dict]) -> list[dict]:
    """Merge multiple SHACL property constraints that share the same sh:path into one dict."""
    by_path: dict[str, dict] = {}

    for prop in shape_value:
        path = get_value("path", prop)
        if path is None:
            continue

        if path not in by_path:
            by_path[path] = dict(prop)
            continue

        merged = by_path[path]

        # Merge minCount/maxCount: keep the most restrictive when present
        for k in ["minCount", "maxCount", "qualifiedMaxCount", "qualifiedMinCount"]:
            v_new = (
                get_value(k.replace("Count", ""), prop)
                if False
                else prop.get(f"{SHACL_NS}{k}") or prop.get(k)
            )  # keep simple if your keys are full URIs
            v_old = merged.get(f"{SHACL_NS}{k}") or merged.get(k)

            # Prefer defined values; for minCount take max, for maxCount take min
            if v_new is None:
                continue
            if v_old is None:
                merged[f"{SHACL_NS}{k}"] = v_new
            else:
                try:
                    if k.endswith("minCount"):
                        merged[f"{SHACL_NS}{k}"] = str(max(int(v_old), int(v_new)))
                    elif k.endswith("maxCount"):
                        merged[f"{SHACL_NS}{k}"] = str(min(int(v_old), int(v_new)))
                    else:
                        merged[f"{SHACL_NS}{k}"] = v_old
                except Exception:
                    merged[f"{SHACL_NS}{k}"] = v_old

        # Merge sh:class: keep the more specific one if you can, otherwise keep both
        # Easiest safe behavior: if there are two, store as list (AND semantics)
        cls_old = merged.get(str(SH["class"]))
        cls_new = prop.get(str(SH["class"]))
        if cls_new:
            if not cls_old:
                merged[str(SH["class"])] = cls_new
            else:
                # Normalize to list
                if not isinstance(cls_old, list):
                    cls_old = [cls_old]
                if cls_new not in cls_old:
                    cls_old.append(cls_new)
                merged[str(SH["class"])] = cls_old

    return list(by_path.values())


# process node with all props and sub nodes
def process_node(
    shape_value: list,
    meta_data: Union[Dict, List],
    nodes_in: list,
    lsonLD_dict: dict,
    level: int,
):
    if not isinstance(shape_value, list):
        raise ValueError("shape_value should be a list!")

    # Merge duplicate constraints that share the same sh:path (e.g., hasCategory, iri)
    shape_value = merge_property_constraints(shape_value)

    handle_node = []
    for values in shape_value:
        path_data = get_value("path", values)
        # Skip shape-level constraints that do not represent a property (no sh:path)
        if path_data is None:
            continue

        path, nodes = get_node_data(values)
        namespace, shapename = get_namespace_name_from_url(path)
        key = create_namespace_name(namespace, shapename)

        # if node value in node in -> use nodes_in
        if nodes_in is not None:
            node_value = get_value("node", values)
            matching_uri = next(
                (uri for uri in nodes_in if str(uri) == node_value), None
            )
            if matching_uri is not None:
                nodes = nodes_in

        is_required = is_required_property(values)
        is_list = is_list_property(values)
        # If the input value is NOT a list, serialize it as a single value
        # even if SHACL allows multiple values (maxCount missing).
        if key in meta_data and not isinstance(meta_data[key], list):
            is_list = False

        if is_list:
            if (
                not key in handle_node
            ):  # register key only one time : e.g hasArtifacts exist for multiple types via sh:hasValue envited-x:isSimulationData
                register_list(
                    key,
                    values,
                    meta_data,
                    nodes,
                    namespace,
                    shapename,
                    path,
                    is_required,
                    lsonLD_dict,
                    level,
                )
                handle_node.append(key)
        else:
            register_key(
                key,
                values,
                meta_data,
                nodes,
                namespace,
                shapename,
                path,
                is_required,
                lsonLD_dict,
                level,
            )


# get prefix from url
def get_prefix_for_url(url: str, graph: Graph) -> str:
    for prefix, namespace in graph.namespace_manager.namespaces():
        # check if uri starts with namespace
        if url.startswith(str(namespace)):
            return prefix
    return None


# from https://ontologies.envited-x.net/envited-x/v2/ontology#isMedia
# to https://ontologies.envited-x.net/envited-x/v2/ontology#
def get_url_from_namespace(value: str) -> str:
    if "#" in value:
        url = value.rsplit("#", 1)[0] + "#"
    else:
        url = value.split("#")[0].rsplit("/", 1)[0] + "/"
    return url


# get prefixes
def getPrefixes(shacl_graph: Graph) -> dict:
    # collect mamespace prefix
    used_namespaces = set()
    for s, p, o in shacl_graph:
        #  check if subject, predicat, object is uri
        if isinstance(s, URIRef):
            used_namespaces.add(get_url_from_namespace(s))
        if isinstance(p, URIRef):
            used_namespaces.add(get_url_from_namespace(p))
        if isinstance(o, URIRef):
            used_namespaces.add(get_url_from_namespace(o))

    prefixes = dict()
    for prefix, namespace in shacl_graph.namespace_manager.namespaces():
        uriStr = str(namespace)
        if uriStr in used_namespaces:
            prefix_str = get_prefix_for_url(namespace, shacl_graph)
            prefixes[prefix_str] = namespace
    return prefixes


def is_supported_shacl_namespace(url: str) -> bool:
    namespace = str(url)
    return namespace.startswith(ENVITED_URL) or namespace.startswith(GX_NS)


def register_shacl_dependencies(
    root_key: str, shacl_definitions: dict, extra_prefixes: dict | None = None
) -> None:
    pending_keys = [root_key]

    while pending_keys:
        current_key = pending_keys.pop(0)
        graph_data = shacl_definitions.get(current_key)
        if graph_data is None:
            continue

        prefixes = getPrefixes(graph_data["graph"])
        if current_key == root_key and extra_prefixes:
            prefixes.update(extra_prefixes)

        for key, value in prefixes.items():
            if key in shacl_definitions:
                continue
            if not is_supported_shacl_namespace(value):
                continue

            register_shacl(get_url_for_download(value), key, shacl_definitions)
            pending_keys.append(key)


# use shacls and extracted data to create json ld dict
def process_graph(schema_namespace, schema_name, meta_data):
    config.JSON_OUT = defaultdict(list)
    # get shacl for asset
    if schema_namespace.lower() in config.SHACLS:
        shacl_graph_data = config.SHACLS[schema_namespace.lower()]

        config.JSON_OUT["@context"] = shacl_graph_data["prefixes"]

        # add did
        if "did" in meta_data:
            config.JSON_OUT["@id"] = meta_data["did"]
            del meta_data["did"]
        else:
            raise ValueError(f"did not found in extraced data!")

        # add type
        config.JSON_OUT["@type"] = create_namespace_name(
            schema_namespace.lower(), schema_namespace
        )

        # get first element of main shacl
        shape_value = get_shacl_shape(
            schema_namespace.lower(), f"{schema_name}/{schema_namespace}Shape"
        )
        if not shape_value:
            raise ValueError(
                f"did not found {schema_name} in shacl {schema_namespace}!"
            )

        process_node(shape_value, meta_data, None, config.JSON_OUT, 0)

        if meta_data:
            hasOnlyRecordingTime = (
                True if len(meta_data) == 1 and "recordingTime" in meta_data else False
            )
            if not hasOnlyRecordingTime:
                logger.warning("non-transferring values:")
                logger.warning(json.dumps(meta_data, indent=4, ensure_ascii=False))

    else:
        logger.error(f"Cannot find ontology {schema_namespace}")


# create shacl data structure and register
def register_shacl(url_path: str, shacl_name: str, shacls):

    local_file_path = download_shacl(url_path, shacl_name)

    try:
        if local_file_path:
            graph = Graph()
            graph = graph.parse(local_file_path, format="turtle")

            graph_data = {}
            graph_data["graph"] = graph
            graph_data["dict"] = convert_graph_to_dict(
                graph, not str(url_path).startswith("http://www.w3.org/ns")
            )
            graph_data["prefixes"] = getPrefixes(graph)

            shacls[shacl_name] = graph_data
    except Exception as exc:
        raise RuntimeError(f"cannot read turtle file: {local_file_path}") from exc


def convert_context_for_output(context: dict) -> list:
    """Convert prefix map to JSON-LD context list."""

    direct_urls = []
    other_prefixes = {}
    seen_urls = set()

    for prefix, url in context.items():
        url = str(url)

        # Put ENVITED contexts directly into the list
        if ENVITED_URL in url:
            if url not in seen_urls:
                direct_urls.append(url)
                seen_urls.add(url)
        else:
            other_prefixes[prefix] = url

    # Append remaining prefixes as one mapping block
    if other_prefixes:
        direct_urls.append(other_prefixes)

    return direct_urls


def strip_envited_prefixes_from_keys(data: Any, context: dict) -> Any:
    """Remove prefixes from keys when the prefix namespace is an ENVITED URL."""

    removable_prefixes = {
        prefix for prefix, url in context.items() if ENVITED_URL in str(url)
    }

    def transform(node: Any) -> Any:
        if isinstance(node, dict):
            result = {}

            for key, value in node.items():
                # Keep JSON-LD keywords unchanged
                if isinstance(key, str) and key.startswith("@"):
                    result[key] = value
                    continue

                new_key = key
                if isinstance(key, str) and ":" in key:
                    prefix, local_name = key.split(":", 1)

                    # Remove only ENVITED prefixes from property keys
                    if prefix in removable_prefixes:
                        new_key = local_name

                # Transform nested values recursively
                transformed_value = transform(value)

                # Detect collisions after prefix removal
                if new_key in result and new_key != key:
                    raise ValueError(
                        f"Key collision while stripping prefixes: '{key}' -> '{new_key}'"
                    )

                result[new_key] = transformed_value

            return result

        if isinstance(node, list):
            return [transform(item) for item in node]

        return node

    return transform(data)


def main():
    # parse arguments
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="creates a jsonLD from an attribute table of the meta data extractors",
    )
    parser.add_argument("filename", type=str, help="filename of json attribute table.")
    parser.add_argument(
        "-ontology", type=str, required=True, help="githup path to ontologies"
    )
    parser.add_argument(
        "-out", type=str, required=True, help="output filname for json LD file."
    )
    parser.add_argument(
        "-removeShacl",
        action="store_true",
        help="remove the downloaded folder shacl first",
    )
    args = parser.parse_args()

    # read attribute data
    claim_path = Path(args.filename)
    claim_path = claim_path.resolve()
    if not claim_path.exists():
        raise FileNotFoundError(f"Could not find file {claim_path}")
    with open(claim_path, "r", encoding="utf-8") as file:
        claim_data = json.load(file)

    # download shacl file
    if args.removeShacl:
        shacl_folder = SHACL_CACHE_DIR
        if shacl_folder.exists():
            shutil.rmtree(shacl_folder)
    config.SHACLS = {}
    config.JSON_OUT = {}
    shacl_namespace = claim_data["shacl_schema"]
    shacl_url = claim_data["shacl_url"]
    del claim_data["shacl_schema"]
    del claim_data["shacl_url"]

    ontology_path = args.ontology + "/"
    ontology_path = ontology_path.format(schema=shacl_namespace.lower())
    shacl_definitions = {}
    new_url_path = get_url_for_download(ontology_path)
    register_shacl(new_url_path, shacl_namespace.lower(), shacl_definitions)

    # get gaiaX/envited prefixes
    shacl_data = shacl_definitions[shacl_namespace.lower()]
    prefixes = getPrefixes(shacl_data["graph"])
    # add special prefixes
    prefixes["sh"] = SHACL_NS

    # and download additional shacls
    register_shacl_dependencies(
        shacl_namespace.lower(),
        shacl_definitions,
        extra_prefixes={"sh": SHACL_NS},
    )
    config.SHACLS = shacl_definitions

    # fill data in shacl structure
    try:
        process_graph(shacl_namespace, shacl_url, claim_data)
    except Exception as exc:
        raise RuntimeError("Could not convert to json") from exc

    # write claims as json id to output
    output_path = Path(args.out)

    # convert json output with reduced namespaces
    config.JSON_OUT["@context"]["gx"] = GX_NS
    # Convert @context to the final output format
    config.JSON_OUT["@context"] = convert_context_for_output(
        config.JSON_OUT["@context"]
    )

    write_json(output_path, config.JSON_OUT, indentValue=2)
    logger.info(f"write json ld to {output_path}")


if __name__ == "__main__":
    main()
