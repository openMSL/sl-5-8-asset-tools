"""SHACL vocabulary extraction for LLM prompt construction.

Reads SHACL shape files and extracts:
- sh:in enumerations (valid values per property)
- sh:datatype constraints (numeric/string types)
- sh:name/sh:description (human-readable field documentation)

This enables building LLM prompts dynamically from the ontology,
following the pattern from ontology-based-nl-search/packages/ontology.
"""

import logging
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace

logger = logging.getLogger(__name__)

SH = Namespace("http://www.w3.org/ns/shacl#")

ENUM_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?path ?name ?description ?value WHERE {
    ?shape sh:property ?prop .
    ?prop sh:path ?path .
    OPTIONAL { ?prop sh:name ?name }
    OPTIONAL { ?prop sh:description ?description }
    ?prop sh:in ?list .
    ?list rdf:rest*/rdf:first ?value .
}
ORDER BY ?path ?value
"""

PROPERTY_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?path ?name ?description ?datatype ?minCount WHERE {
    ?shape sh:property ?prop .
    ?prop sh:path ?path .
    OPTIONAL { ?prop sh:name ?name }
    OPTIONAL { ?prop sh:description ?description }
    OPTIONAL { ?prop sh:datatype ?datatype }
    OPTIONAL { ?prop sh:minCount ?minCount }
    FILTER NOT EXISTS { ?prop sh:in ?list }
}
ORDER BY ?path
"""


def extract_vocabulary(shacl_path: Path) -> dict[str, Any]:
    """Extract vocabulary from a SHACL shape file.

    Returns a dict with:
        enums: {property_name: {values: [...], name: ..., description: ...}}
        properties: {property_name: {type: ..., name: ..., description: ..., required: bool}}
    """
    g = Graph()
    g.parse(str(shacl_path), format="turtle")

    vocab: dict[str, Any] = {"enums": {}, "properties": {}}

    for row in g.query(ENUM_QUERY):
        prop = _local_name(str(row.path))
        if prop not in vocab["enums"]:
            vocab["enums"][prop] = {
                "values": [],
                "name": str(row.name) if row.name else prop,
                "description": str(row.description) if row.description else "",
            }
        vocab["enums"][prop]["values"].append(str(row.value))

    for row in g.query(PROPERTY_QUERY):
        prop = _local_name(str(row.path))
        if prop.startswith("has") or prop.startswith("ndb"):
            continue
        dt = _local_name(str(row.datatype)) if row.datatype else "string"
        required = bool(row.minCount and int(row.minCount) > 0)
        vocab["properties"][prop] = {
            "type": dt,
            "name": str(row.name) if row.name else prop,
            "description": str(row.description) if row.description else "",
            "required": required,
        }

    logger.info(
        "Extracted vocabulary: %d enums, %d properties from %s",
        len(vocab["enums"]),
        len(vocab["properties"]),
        shacl_path.name,
    )
    return vocab


def _local_name(uri: str) -> str:
    """Extract local name from a URI."""
    for sep in ("#", "/"):
        if sep in uri:
            return uri.rsplit(sep, 1)[-1]
    return uri
