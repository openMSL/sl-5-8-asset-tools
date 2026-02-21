#import debugpy

# debugpy, listening on port 5678
#debugpy.listen(("0.0.0.0", 5678))
#print("Waiting for debugger to attach...")

#debugpy.wait_for_client()

#debugpy.breakpoint()


from datetime import datetime
from rdflib.namespace import SH
from rdflib import Graph, URIRef
from collections import defaultdict
from pathlib import Path
from typing import Any, Tuple, Union, Dict, List
from utils.rdf import get_prefixes, convert_graph_to_dict
from utils.http import get_url_for_download, download_shacl
from utils.json import write_json
from utils.constants import SHACL_NS, SHACL_FOLDER_NAME, GX_NS

import shutil
import json
import logging
import argparse
import operator

#logging.basicConfig(
#    level=logging.DEBUG,
#    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
#)

logger = logging.getLogger(__name__)

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
    check = check_min_max(shacl_data, f'{SH}qualifiedMinCount', 1, operator.ge)
    if check is None:
        check = check_min_max(shacl_data, f'{SH}minCount', 1, operator.ge)

    if check is None:
        return False
    return check


# check if can have more entries
# max count <= 1 or min count > 1 or min count 0
def is_list_property(shacl_data):
    test = get_value('minCount',shacl_data)
    if test is not None and test == '0':
        test = 0 
    check = check_min_max(shacl_data, f'{SH}qualifiedMaxCount', 1, operator.le)
    if check is None:
        check = check_min_max(shacl_data, f'{SH}maxCount', 1, operator.le)
    if check:
        return not check
    
    check = check_min_max(shacl_data, f'{SH}qualifiedMinCount', 1, operator.ge)
    if check is None:
        check = check_min_max(shacl_data, f'{SH}minCount', 1, operator.gt) or check_min_max(shacl_data, f'{SH}minCount', 0, operator.eq)

    if check is None:
        return False    

    return check


# get named value
def get_value(name, values):
    name_pre = '#' + name
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
            if k.endswith(f"{SHACL_NS}node") or k.endswith(f"{SHACL_NS}class"):
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
def get_value_type(key : str, shacl_values : dict) -> str:
    literal_constraints = [
        "datatype", "pattern", "in",
        "minLength", "maxLength",
        "length",
        "minInclusive", "maxInclusive",
        "minExclusive", "maxExclusive",
        "languageIn"
    ]
    value_key = (
        "@value"
        if any(get_value(name, shacl_values) for name in literal_constraints)
        else "@id"
    )    

    # set value_key
    if key == 'gx:license' and value_key != "@value":
        value_key = "@value" # no idea how to handle this via shacl values
    if key == 'manifest:hasAccessRole' and value_key != "@id":
        value_key = "@id"        
    if key == 'manifest:hasCategory' and value_key != "@id":
        value_key = "@id" 
    return value_key


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
def create_property(namespace : str, property_name : str, value, datatype: str, name: str, jsonLD_dict: dict, shacl_values : dict, level : int):
    
    key = create_namespace_name(namespace, property_name)
    value_key = get_value_type(key, shacl_values)
   
    if isinstance(value, list):
        if value_key == '@id':
            properties = []
            for list_value in value:
                properties.append({ value_key : list_value})
            jsonLD_dict[key] = properties
        else: 
            jsonLD_dict[key] = value
    else:
        if datatype:
            if datatype == 'string':
                jsonLD_dict[key] = value
            else: # literal
                dtype = f"xsd:{datatype}" if ":" not in datatype else datatype
                jsonLD_dict[key] = {
                    '@type' : dtype, 
                    value_key : value} # value
        elif name: # id-Property
            jsonLD_dict[key] = {
                '@type' : name, 
                value_key : value} # id       
        else:
            jsonLD_dict[key] = {value_key : value}
            class_value = get_value('class', shacl_values)
            if class_value:
                jsonLD_dict[key]['@type'] = f'{namespace}:{get_name_from_url(class_value)}'
       
    logger.debug(f'{" " * level * 3}add prop {key}')


# from 'https://ontologies.envited-x.net/manifest/v5/ontology#hasManifestReference'
# compare with registered prefixes, e.g  @prefix manifest: <https://ontologies.envited-x.net/manifest/v5/ontology#>
# to manifest, hasManifestReference
def get_namespace_name_from_url(url: str) -> Tuple[str, str]:
    # serach in own prefixes
    prefixes = config.JSON_OUT['@context']
    for ns_key, uri_ref in prefixes.items():
        prefix = str(uri_ref)
        if url.startswith(prefix):
            shape_name = url[len(prefix):]
            return ns_key, shape_name
        
    # try in other shacls
    for key, value in config.SHACLS.items():
        for ns_key, uri_ref in value['prefixes'].items():
            prefix = str(uri_ref)
            if url.startswith(prefix):
                shape_name = url[len(prefix):]
                return ns_key, shape_name
    return None, None


# from hdmap:Quantity 
# to hdmap, Quantity
def get_namespace(namespace_and_name):
    parts = namespace_and_name.split('::')
    if len(parts) != 2:
        raise ValueError(f'{namespace_and_name} not valid!')
    return parts[0], parts[1]

def get_name_from_url(url):
    parts = url.split('#')
    if len(parts) == 2:
        return parts[1]
    
    return None
    

def create_namespace_name(namespace : str, shapename : str) -> str:
    return f'{namespace}:{shapename}'

# create node like
# "hdmap:hasQuantity": {
#       "@type": "hdmap:Quantity",
def create_node(namespace : str, shapename : str, type: str, lsonLD: Union[Dict,List], is_list : bool, level : int) -> dict:
    node = {}
    node['@type'] = type

    key = create_namespace_name(namespace, shapename)

    if is_list:
        lsonLD.append(node)
    else:
        lsonLD[key] = node

    logger.debug(f'{" " * level * 3}add node {key}')
    return node


# get shacl shema
def get_shacl_shema(namespace : str) -> dict:
    if namespace in config.SHACLS:
        return config.SHACLS[namespace]
    return None


# get shape from shacl data
def get_shacl_shape(namespace : str, shapename : str) -> list:
    shacl_graph_data = get_shacl_shema(namespace)
    if shacl_graph_data:
        if shapename in shacl_graph_data['dict']:
            return shacl_graph_data['dict'][shapename]
    
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

# register key + value to json ld
def register_key(key : str, values : dict, meta_data: dict, nodes : list, namespace: str, shapename: str, path: str, is_required: bool, lsonLD_dict: dict, level : int):

    if key in meta_data:

        if nodes is None:
            # register as property
            namespace_sub, name_subtype = get_namespace_name_from_url(path)
            type_url = get_value("datatype", values)
            if type_url:
                namespace_type, type = get_namespace_name_from_url(type_url)
                create_property(namespace, shapename, meta_data[key], type, None, lsonLD_dict, values, level)
                del meta_data[key]
            else:
                name_url = get_value("name", values)
                name = get_name_from_url(name_url) if name_url else None
                property_name = create_namespace_name(namespace, name) if name is not None else None
                type = (
                    "manifest:AccessRole" if shapename == "hasAccessRole"
                    else "manifest:Category" if shapename == "hasCategory"
                    else None
                )
                create_property(namespace, shapename, meta_data[key], type, property_name, lsonLD_dict, values, level)
                del meta_data[key]
        else:
            # --- NEW: for hdmap:hasManifest add richer shapes for mapping ---
            if key == "hdmap:hasManifest":
                nodes = _inject_manifest_mapping_candidates(nodes)

            created_node = None
            for node in nodes:
                if key not in meta_data:
                    continue # already filled

                ulr = node if isinstance(node, str) else list(node)[0]
                namespace_sub, type = get_namespace_name_from_url(ulr)
                shape_value_sub = get_shacl_shape(namespace_sub, str(ulr))
                if shape_value_sub is None:
                    continue
                
                if created_node is None:
                    used_namespace, name_subtype = get_namespace_name_from_url(path)
                    type_without_shape = type.replace('Shape', '')
                    if shapename == "hasManifest":
                        # Prefer manifest:Link if the prefix exists, fallback to envited-x:Link
                        if "manifest" in config.JSON_OUT["@context"]:
                            type_str = "manifest:Link"
                        else:
                            type_str = "envited-x:Link"
                    else:
                        type_str = create_namespace_name(namespace_sub, type_without_shape)
                    #type_str = create_namespace_name(namespace_sub, 'Link' if shapename == 'hasManifest' else type_without_shape) # HACK to support "@type": "manifest:Link",
                    created_node = create_node(used_namespace, shapename, type_str, lsonLD_dict, False, level)
                # only subnodes / properties of further nodes are registered

                # go deeper
                nodes_sub = list(node.values())[0] if isinstance(node, dict) else None
                lsonLD_node = created_node

                process_node(shape_value_sub, meta_data[key], nodes_sub, lsonLD_node, level + 1)
                # remove data if empty
                if not meta_data[key]:
                    del meta_data[key]

    elif is_required:
        # TODO write empty node
        test = 0

# register list of key + value to json ld
def register_list(key : str, values : dict, meta_data: dict, nodes : list, namespace: str, shapename: str, path: str, is_required: bool, lsonLD_dict: dict, level : int):
    if key in meta_data:
        if not isinstance(meta_data[key], list):
            raise ValueError(f'meta_data of {key} should be a list!')

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
                        type_without_shape = type.replace('Shape', '')
                        type_str = create_namespace_name(namespace_sub, type_without_shape)
                        created_node = create_node(namespace_sub, shapename, type_str, created_nodes, True, level)
                    # only subnodes / properties of further nodes are registered

                    # go deeper
                    process_node(shape_value_sub, sub_meta_data, None, created_node, level + 1)   
            else:
                # register as property
                register_key(key, values, meta_data, None, namespace, shapename, path, is_required, lsonLD_dict, level) 

        if key in meta_data and all(not elem for elem in meta_data[key]):   
            del meta_data[key]

        if created_nodes:
            lsonLD_dict[key] = created_nodes

    elif is_required:
        # TODO write empty node
        test = 0        

# process node with all props and sub nodes
def process_node(shape_value: list, meta_data: Union[Dict, List], nodes_in: list, lsonLD_dict: dict, level : int):
    if not isinstance(shape_value, list):
        raise ValueError('shape_value should be a list!')
    
    handle_node =[]
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
            matching_uri = next((uri for uri in nodes_in if str(uri) == node_value), None)
            if matching_uri is not None:
                nodes = nodes_in

        is_required = is_required_property(values)
        is_list = is_list_property(values)
        if is_list:
            if not key in handle_node: # register key only one time : e.g hasArtifacts exist for multiple types via sh:hasValue envited-x:isSimulationData
                register_list(key, values, meta_data, nodes, namespace, shapename, path, is_required, lsonLD_dict, level)
                handle_node.append(key)
        else:
            register_key(key, values, meta_data, nodes, namespace, shapename, path, is_required, lsonLD_dict, level)


# get prefix from url
def get_prefix_for_url(url : str, graph : Graph) -> str:
    for prefix, namespace in graph.namespace_manager.namespaces():
        # check if uri starts with namespace
        if url.startswith(str(namespace)):
            return prefix
    return None


# from https://ontologies.envited-x.net/envited-x/v2/ontology#isMedia
# to https://ontologies.envited-x.net/envited-x/v2/ontology#
def get_url_from_namespace(value: str) -> str:
    if "#" in value:
        url = value.rsplit('#', 1)[0] + '#'
    else: 
        url = value.split('#')[0].rsplit('/', 1)[0] + '/'
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


# use shacls and extracted data to create json ld dict
def process_graph(schema_namespace, schema_name, meta_data):
    config.JSON_OUT = defaultdict(list)
    # get shacl for asset
    if schema_namespace.lower() in config.SHACLS:        

        shacl_graph_data = config.SHACLS[schema_namespace.lower()]

        config.JSON_OUT['@context'] = shacl_graph_data['prefixes']
        
        # add did
        if 'did' in meta_data:
            config.JSON_OUT['@id'] = meta_data['did']
            del meta_data['did']
        else:
            raise ValueError(f'did not found in extraced data!')

        # add type
        config.JSON_OUT['@type'] = create_namespace_name(schema_namespace.lower(), schema_namespace)

        # get first element of main shacl        
        shape_value = get_shacl_shape(schema_namespace.lower(), f'{schema_name}/{schema_namespace}Shape')
        if not shape_value:
            raise ValueError(f'did not found {schema_name} in shacl {schema_namespace}!')

        process_node(shape_value, meta_data, None, config.JSON_OUT, 0)

        if meta_data:
            hasOnlyRecordingTime = True if len(meta_data) == 1 and 'recordingTime' in meta_data else False
            if not hasOnlyRecordingTime:
                logger.warning("non-transferring values:")
                logger.warning(json.dumps(meta_data, indent=4, ensure_ascii=False))

    else:
        logger.error(f'Cannot find ontology {schema_namespace}')


# create shacl data structure and register
def register_shacl(url_path : str, shacl_name: str, shacls):

    local_file_path = download_shacl(url_path, shacl_name)

    try:
        if local_file_path:
            graph = Graph()
            graph = graph.parse(local_file_path, format='turtle')
            
            graph_data = {}
            graph_data['graph'] = graph
            graph_data['dict'] = convert_graph_to_dict(graph, not str(url_path).startswith("http://www.w3.org/ns"))        
            graph_data['prefixes'] = getPrefixes(graph)

            shacls[shacl_name] = graph_data
    except:
        raise FileNotFoundError(f'cannot read turtle file: {local_file_path}')


def main():
    # parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='creates a jsonLD from an attribute table of the meta data extractors')
    parser.add_argument('filename', type=str,help='filename of json attribute table.')
    parser.add_argument('-ontology', type=str,help='githup path to ontologies')
    parser.add_argument('-out', type=str, help='output filname for json LD file.')
    parser.add_argument('-removeShacl', action="store_true", help='remove the downloaded folder shacl first')
    args = parser.parse_args()

    # read attribute data
    claim_path = Path(args.filename)
    claim_path = claim_path.resolve()
    if not claim_path.exists():
        raise FileNotFoundError(f'Could not find file {claim_path}')
    with open(claim_path, 'r', encoding='utf-8') as file:
        claim_data = json.load(file)

    # download shacl file    
    if args.removeShacl:
        shacl_folder = Path(SHACL_FOLDER_NAME)
        if shacl_folder.exists():
            shutil.rmtree(shacl_folder)
    shacl_namespace = claim_data['shacl_schema']
    shacl_url = claim_data['shacl_url'] 
    del claim_data['shacl_schema']
    del claim_data['shacl_url']

    ontology_path = args.ontology + '/'
    ontology_path = ontology_path.format(schema=shacl_namespace)
    shacl_definitions = {}
    new_url_path = get_url_for_download(ontology_path)
    register_shacl(new_url_path, shacl_namespace.lower(), shacl_definitions)

    # get gaiaX/envited prefixes
    shacl_data = shacl_definitions[shacl_namespace.lower()]
    prefixes = get_prefixes(shacl_data['graph'])
    # add special prefixes
    prefixes["sh"] = SHACL_NS

    # and download additional shacls
    for key, value in prefixes.items():
        if key not in shacl_definitions:
            new_url_path = get_url_for_download(value)
            register_shacl(new_url_path, key, shacl_definitions)
    config.SHACLS = shacl_definitions
    
    # fill data in shacl structure
    try:
        process_graph(shacl_namespace, shacl_url, claim_data)
    except:
        raise Exception(f'Could not convert to json')
        
    # write claims as json id to output    
    output_path = Path(args.out)
    config.JSON_OUT['@context']["gx"] = GX_NS
    write_json(output_path, config.JSON_OUT, indentValue= 2)
    logger.info(f'write json ld to {output_path}')


if __name__ == '__main__':
    main()