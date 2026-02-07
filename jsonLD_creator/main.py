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
from utils.http import get_url_for_download, download_shacle
import shutil
import json
import logging
import argparse
import operator

logger = logging.getLogger(__name__)

# global values
SHACL_URL = 'http://www.w3.org/ns/shacl#'
GX_URL = 'https://registry.lab.gaia-x.eu/development/api/trusted-shape-registry/v1/shapes/jsonld/trustframework#'
ENVITEDX_NAME = 'envited-x'
GAIAX_URL = "https://raw.githubusercontent.com/GAIA-X4PLC-AAD/ontology-management-base"


# global config value with all shacles, dicts and jsonLD output
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


def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")
    
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

# Recursively collect all values under the keys 'node' and 'class' and all nested lists/dicts under 'and', 'or' and 'qualifiedValueShape'
def collect_nodes(shape: Any) -> List[str]:
    
    nodes = []
    if isinstance(shape, dict):
        for k, v in shape.items():
            # SHACL-node / SHACL-class
            if k.endswith(f"{SHACL_URL}node"):
                if isinstance(v, str):
                    nodes.append(v)
                else:
                    nodes.extend(collect_nodes(v))

            # qualifiedValueShape enthält verschachtelte Shapes
            elif k.endswith(f"{SHACL_URL}qualifiedValueShape"):
                nodes.extend(collect_nodes(v))

            # sh:and / sh:or
            elif k.endswith(f"{SHACL_URL}and") or k.endswith(f"{SHACL_URL}or"):
                if isinstance(v, list):
                    for item in v:
                        nodes.extend(collect_nodes(item))

            # property-Array: dort können wiederum qualifiedValueShape o.ä. stehen
            elif k.endswith(f"{SHACL_URL}property"):
                if isinstance(v, list):
                    for prop in v:
                        nodes.extend(collect_nodes(prop))

    elif isinstance(shape, list):
        for item in shape:
            nodes.extend(collect_nodes(item))
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
    # debug
    if key == 'manifest:filename':
        test = 0

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
                jsonLD_dict[key] = {
                    '@type' : f'xsd:{datatype}', 
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


# from 'https://ontologies.envited-x.net/manifest/v4/ontology#hasManifestReference'
# compare with registered prefixes, e.g  @prefix manifest: <https://ontologies.envited-x.net/manifest/v4/ontology#>
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
        logger.error(f'{namespace_and_name} not valid!')
        exit(1)
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

    # debug
    if key == 'hdmap:hasManifest':
        test = 0

    if is_list:
        lsonLD.append(node)
    else:
        lsonLD[key] = node

    logger.debug(f'{" " * level * 3}add node {key}')
    return node


# get shacle shema
def get_shacle_shema(namespace : str) -> dict:
    if namespace in config.SHACLS:
        return config.SHACLS[namespace]
    return None


# get shape from shacle data
def get_shacle_shape(namespace : str, shapename : str) -> list:
    shacl_graph_data = get_shacle_shema(namespace)
    if shacl_graph_data:
        if shapename in shacl_graph_data['dict']:
            return shacl_graph_data['dict'][shapename]
    
    return None

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
                create_property(namespace, shapename, meta_data[key], None, property_name, lsonLD_dict, values, level)
                del meta_data[key]
        else:
            created_node = None
            for node in nodes:
                if key not in meta_data:
                    continue # already filled
                ulr = node if isinstance(node, str) else list(node)[0]
                namespace_sub, type = get_namespace_name_from_url(ulr)
                shape_value_sub = get_shacle_shape(namespace_sub, str(ulr))
                if shape_value_sub is None:
                    continue
                
                if created_node is None:
                    used_namespace, name_subtype = get_namespace_name_from_url(path)
                    type_without_shape = type.replace('Shape', '')
                    type_str = create_namespace_name(namespace_sub, 'Link' if shapename == 'hasManifest' else type_without_shape) # HACK to support "@type": "manifest:Link",
                    created_node = create_node(used_namespace, shapename, type_str, lsonLD_dict, False, level)
                # only subnodes / properties of further nodes are registered

                # go deeper
                nodes_sub = list(node.values())[0] if isinstance(node, dict) else None
                lsonLD_node = created_node

                process_node(shape_value_sub, meta_data[key], nodes_sub, lsonLD_node, level + 1)
                if not meta_data[key]:
                    del meta_data[key]

    elif is_required:
        # TODO write empty node
        test = 0

# register list of key + value to json ld
def register_list(key : str, values : dict, meta_data: dict, nodes : list, namespace: str, shapename: str, path: str, is_required: bool, lsonLD_dict: dict, level : int):
    if key in meta_data:
        if not isinstance(meta_data[key], list):
            logger.error(f'meta_data of {key} should be list!')
            exit(1)

        created_nodes = []
        for sub_meta_data in meta_data[key]:
            created_node = None
            if nodes:
                for node in nodes:
                    namespace_sub, type = get_namespace_name_from_url(node)
                    shape_value_sub = get_shacle_shape(namespace_sub, str(node))
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
        logger.error(f'shape_value should be a list!')
        exit(1)
    
    handle_node =[]
    for values in shape_value:
        path_data = get_value("path", values)     
        if path_data == 'https://ontologies.envited-x.net/manifest/v5/ontology#hasArtifacts':
            test = 0
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
    if schema_namespace in config.SHACLS:        

        shacl_graph_data = config.SHACLS[schema_namespace]

        config.JSON_OUT['@context'] = shacl_graph_data['prefixes']
        
        # add did
        if 'did' in meta_data:
            config.JSON_OUT['@id'] = meta_data['did']
            del meta_data['did']
        else:
            logger.error(f'did not found in extraced data!')
            exit(1)

        # add type
        name = get_name_from_url(schema_name)
        name = name.replace('Shape', '')
        shacle_namespace = 'manifest' if schema_namespace == ENVITEDX_NAME and name != 'Manifest' else schema_namespace
        config.JSON_OUT['@type'] = create_namespace_name(shacle_namespace, name)

        # get first element of main shacle        
        shape_value = get_shacle_shape(schema_namespace, schema_name)
        if not shape_value:
            logger.error(f'did not found {schema_name} in shacl {schema_namespace}!')
            exit(1)

        process_node(shape_value, meta_data, None, config.JSON_OUT, 0)

        if meta_data:
            hasOnlyRecordingTime = True if len(meta_data) == 1 and 'recordingTime' in meta_data else False
            if not hasOnlyRecordingTime:
                logger.warning("non-transferring values:")
                logger.warning(json.dumps(meta_data, indent=4, ensure_ascii=False))

        # TODO: hmm, we get valdation errors for manifest if we have envited-x prefix
        if ENVITEDX_NAME in config.JSON_OUT['@context']:
            del config.JSON_OUT['@context'][ENVITEDX_NAME]  
        # remove unused rfd prefix
        if 'rdf' in config.JSON_OUT['@context']:
            del config.JSON_OUT['@context']['rdf']        
    else:
        logger.error(f'Cannot find ontology {schema_namespace}')


# create shacl data structure and register
def register_shacle(url_path : str, shacle_name: str, shacls):

    local_file_path = download_shacle(url_path, shacle_name)

    try:
        if local_file_path:
            graph = Graph()
            graph.parse(local_file_path, format='turtle')
            
            is_gaiax_ontology = True if str(url_path).startswith(GAIAX_URL) else False

            graph_data = {}
            graph_data['graph'] = graph
            graph_data['dict'] = convert_graph_to_dict(graph, is_gaiax_ontology)        
            graph_data['prefixes'] = getPrefixes(graph)

            # DEBUG write as json
            debug_json_file = local_file_path.with_suffix(".json")
            with open(debug_json_file, 'w') as f:
                json.dump(graph_data['dict'], f, indent=2, default=datetime_handler)

            shacls[shacle_name] = graph_data
    except:
        logger.exception(f'cannot read turtle file: {local_file_path}')
        exit(1)


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
        logger.exception(f'Could not find file {claim_path}')
        exit(1)
    with open(claim_path, 'r', encoding='utf-8') as file:
        claim_data = json.load(file)

    # download shacle file    
    if args.removeShacl:
        shacl_folder = Path('shacles')
        if shacl_folder.exists():
            shutil.rmtree(shacl_folder)
    shacle_namespace, shacle_name = get_namespace(claim_data['shacl_type'])    
    del claim_data['shacl_type']

    ontology_path = args.ontology + '/'
    ontology_path = ontology_path.format(schema=shacle_namespace)
    shacl_definitions = {}
    url_path = f'{ontology_path}{shacle_namespace}/'
    new_url_path = get_url_for_download(url_path)
    register_shacle(new_url_path, shacle_namespace, shacl_definitions)

    # get gaiaX/envited prefixes
    shacl_data = shacl_definitions[shacle_namespace]
    prefixes = get_prefixes(shacl_data['graph'])
    # add special prefixes
    prefixes["sh"] = SHACL_URL
    prefixes["gx"] = GX_URL

    # and download additional shacles
    for key, value in prefixes.items():
        if key not in shacl_definitions:
            new_url_path = get_url_for_download(value)
            register_shacle(new_url_path, key, shacl_definitions)
    config.SHACLS = shacl_definitions
    
    # fill data in shacle structure
    try:
        process_graph(shacle_namespace, shacle_name, claim_data)
    except:
        logger.exception(f'Could not convert to json')
        exit(1)
        
    # write claims as json id to output    
    output_path = Path(args.out)
    with open(output_path, 'w') as f:
        json.dump(config.JSON_OUT, f, indent=2, default=datetime_handler)
        logger.info(f'write json ld to {output_path}')


if __name__ == '__main__':
    main()