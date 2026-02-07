from pathlib import Path
from urllib.parse import urlparse
from rdflib import Graph
from rdflib.namespace import SH, RDF
from rdflib import Graph, URIRef, BNode
from rdflib.collection import Collection
from typing import Optional

from utils.http import download_shacle, get_url_for_download

import re
import json
import requests
import logging

logger = logging.getLogger(__name__)

ENVITEDX_URL = 'https://ontologies.envited-x.net' 

# get all envited x prefixes    
def get_prefixes(shacl_graph: Graph) -> dict[str, str]:
    prefixes = {
        prefix: str(namespace) 
        for prefix, namespace in shacl_graph.namespace_manager.namespaces() 
        if str(namespace).startswith(ENVITEDX_URL)
    }   
    return prefixes 


# load shacl as rdf graph
def load_shacl_files(shacl_files) ->Graph:
    shacl_graph = Graph()
    for shacl_file in shacl_files:
        shacl_graph.parse(shacl_file, format='turtle')
    return shacl_graph

# load json ld and add to rdf graph
def load_jsonld_file(jsonld_file : Path):

    if not jsonld_file.exists():
        logger.error(f'JsonLD files not found: {jsonld_file}')
        exit(1)  

    data_graph = Graph()
    logger.info(f'adding jsonld file to data graph: {jsonld_file}.')
    with open(jsonld_file) as f:
        data = json.load(f)
    data_graph.parse(data=json.dumps(data), format='json-ld')
    return data_graph

# load all shacls for jsonld and return as one graph
def get_shacle_from_json_graph(data_graph : Graph, prefixes_to_add : Optional[dict] = None) ->Graph:
    prefixes = get_prefixes(data_graph)
    if prefixes_to_add:
        prefixes.update(prefixes_to_add)

    shacl_files = []
    for key, value in prefixes.items():
        new_url_path = get_url_for_download(value)
        shacl_files.append(download_shacle(new_url_path, key))
    shacl_graph = load_shacl_files(shacl_files)    
    return shacl_graph

#    Recursive function to “resolve” a value.
#    If it is a blank node, it is checked whether it is an RDF list.
#    Otherwise, an attempt is made to convert the blank node into a dict.
def resolve_value(graph, value):
    if isinstance(value, BNode):
        # Check whether it is an RDF list
        if (value, RDF.first, None) in graph:
            try:
                items = list(Collection(graph, value))
                return [resolve_value(graph, it) for it in items]
            except Exception as e:
                # Fallback: recursive conversion of the BNode into a dict
                return convert_bnode_to_dict(graph, value)
        else:
            # If not as a list, then try to convert the BNode into a dict.
            return convert_bnode_to_dict(graph, value)
    else:
        # For URIs or literals, simply return as a string
        return str(value)


# convert blank node recursive to dict
def convert_bnode_to_dict(graph, bnode):
    result = {}
    for pred, obj in graph.predicate_objects(bnode):
        result[str(pred)] = resolve_value(graph, obj)
    return result


# convert rdf graph to dict, resolve blank nodes
def convert_graph_to_dict(graph, search_node_shape: bool):
    graph_dict = {}
    type_to_search = SH.NodeShape if search_node_shape else SH.NodeKind
    for node_shape in graph.subjects(RDF.type, type_to_search):

        prop_list = []
        for prop in graph.objects(node_shape, SH.property):    

            values_dict = {}
            for detail, value in graph.predicate_objects(prop):
                values_dict[str(detail)] = resolve_value(graph, value)

            prop_list.append(values_dict)
        graph_dict[str(node_shape)] = prop_list

    return graph_dict