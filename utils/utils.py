from pathlib import Path
from urllib.parse import urlparse
from rdflib import Graph
from rdflib.namespace import SH, RDF
from rdflib import Graph, URIRef, BNode
from rdflib.collection import Collection
from typing import Optional

import re
import json
import requests
import logging
import uuid

logger = logging.getLogger(__name__)

ENVITEDX_URL = 'https://ontologies.envited-x.net'
GAIAX_GITHUB_RAW_URL = "https://raw.githubusercontent.com/GAIA-X4PLC-AAD/ontology-management-base"
SHACLE_FOLDER_NAME = 'shacles' 


# get filename, if url download file first and get local filename
def download_or_get_file(filename : Path, out_path: Path) -> Path:

    if is_url(filename):
        filename = Path(download_file(normalize_url(str(filename)), out_path, filename.name))

    filename = filename.resolve()
    return filename

# download file to out_path
def download_file(url_path : str, out_path: Path, filename: str)-> Path:
    url_path = github_to_raw(url_path)
    with requests.get(url_path, stream=True, timeout=30) as r:
        r.raise_for_status()  # Raise an error for HTTP 4xx/5xx
        if not out_path.exists():
            out_path.mkdir()
        filepath = out_path / filename
        with filepath.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
        return filepath

# download shacl from url if not in local shacles folder
def download_shacle(url_path : str, shacle_name: str) -> Path:
    filename = f'{shacle_name}_shacl.ttl'   
    local_filepath = Path(f'{SHACLE_FOLDER_NAME}/{filename}')

    if not local_filepath.exists():
        # get file from github
        url = f'{url_path}{filename}' if str(url_path).startswith(ENVITEDX_URL) else url_path
        response = requests.get(url)
        if not response:
            logger.error(f'No shacl files found in url: {url}')
            exit(1)

        if not Path(SHACLE_FOLDER_NAME).exists():
            Path(SHACLE_FOLDER_NAME).mkdir()
        with open(local_filepath, 'wb') as file:
            file.write(response.content) 

    return local_filepath


# replace url with raw.githubusercontent.com
def get_url_for_download(url: str) -> str:
    
    is_gaiax_ontology = True if str(url).startswith(ENVITEDX_URL) else False
    if is_gaiax_ontology:
        # Break the old URL into components
        parsed = urlparse(url)
        # Split the path into individual segments (empty parts are removed)
        segments = [seg for seg in parsed.path.split("/") if seg]
        
        if segments:
            name = segments[0]
            # Create the new URL: new server, /main/, then the extracted name
            new_url = f"{GAIAX_GITHUB_RAW_URL}/main/{name}/{name}_shacl.ttl"
            return new_url
    else:
        # If no path segments were found, return the new server
        return url.replace('#', '.ttl')
    

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

# create unique id
def create_uuid() -> str:
    random_uuid = uuid.uuid4()   # e.g. 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
    return str(random_uuid)

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

def is_url(path: Path):
    url = url_from_path(path)
    parsed = urlparse(url)
    # A URL usually has a scheme (e.g. “http”, “https”) and a “netloc” (e.g. “www.example.com”)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)

def url_from_path(path: Path) -> str:
    s = path.as_posix()
    # from 'http:/example.com' to 'http://example.com'
    s = re.sub(
        r'^(?P<scheme>https?):/+',
        lambda m: f"{m.group('scheme')}://",
        s,
        flags=re.IGNORECASE
    )
    return s

# Convert GitHub blob URL to raw URL; pass through raw URLs unchanged
def github_to_raw(url: str) -> str:
    url = url.strip()
    p = urlparse(url)

    # Already raw
    if p.netloc == "raw.githubusercontent.com":
        return url

    if p.netloc != "github.com":
        return url  # Not GitHub; leave as-is

    parts = [x for x in p.path.split("/") if x]
    # Expect: org, repo, "blob", ref, ...path
    if len(parts) >= 5 and parts[2] == "blob":
        org, repo, ref = parts[0], parts[1], parts[3]
        file_path = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{file_path}"

    return url

# Normalize a URL that accidentally contains backslashes or wrong number of slashes
def normalize_url(u: str) -> str:
    u = u.strip().replace("\\", "/")  # Fix Windows separators
    # Ensure scheme has exactly '://'
    u = re.sub(r"^(https?):/+", r"\1://", u)
    return u