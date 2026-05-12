"""OpenDRIVE metadata extractor — schema-driven implementation.

Uses the engine module to decode the XSD and extract metadata via the
declarative mapping in ``meta_data_extractor/mappings/hdmap.yaml``.

Filesystem-dependent operations (georeference conversion, license detection)
remain as explicit Python code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import logging
from datetime import datetime

from ..engine.decoder import SchemaDecoder
from ..engine.engine import ExtractionEngine
from ..engine.mapping import MappingConfig
from ..extractor import get_adress_from_osm, proj4_to_epsg, convert_to_LatLon
from ..gaiax import enrich_resource_description
from utils.ids import create_uuid
from utils.constants import (
    DID_ADRESS,
    ENVITED_URL,
    ENVITEDX_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    ODR_SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)

_MAPPING_FILE = Path(__file__).resolve().parents[1] / "mappings" / "hdmap.yaml"
_decoder = SchemaDecoder()

_SUPPORTED_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%Y-%m-%dT%H:%M:%S",
]


def _parse_date(date_string: str) -> str | None:
    """Parse a date string into ISO format, or return None if unrecognized."""
    for fmt in _SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(date_string, fmt).isoformat()
        except ValueError:
            continue
    return None


def _strip_missing_geoidgrids(proj4: str) -> str:
    """Remove '+geoidgrids=...' if referenced grid files are unavailable."""
    import os

    tokens = proj4.split()
    idx = next((i for i, t in enumerate(tokens) if t.startswith("+geoidgrids=")), None)
    if idx is None:
        return proj4

    value = tokens[idx].split("=", 1)[1].strip()
    if not value:
        del tokens[idx]
        return " ".join(tokens)

    # Check if grid files exist
    from pyproj.datadir import get_data_dir

    search_dirs = [Path.cwd()]
    for var in ("PROJ_DATA", "PROJ_LIB"):
        val = os.environ.get(var, "")
        if val:
            search_dirs.extend(Path(p) for p in val.split(os.pathsep) if p.strip())
    try:
        data_dir = get_data_dir()
        if data_dir:
            search_dirs.append(Path(data_dir))
    except Exception:
        pass

    grids = [g.strip() for g in value.split(",") if g.strip()]
    for g in grids:
        found = any((d / g).exists() for d in search_dirs)
        if not found:
            del tokens[idx]
            return " ".join(tokens)
    return proj4


def _build_georeference(data: dict) -> dict | None:
    """Build georeference dict from decoded header data with coordinate conversion."""
    header = data.get("header")
    if not isinstance(header, dict):
        return None

    geo_ref_text = header.get("geoReference")
    if not geo_ref_text or not isinstance(geo_ref_text, str):
        return None

    geo_ref_cleaned = _strip_missing_geoidgrids(geo_ref_text)
    georeference_dict: dict = {}
    geodetic_dict: dict = {}

    # Parse PROJ string for coordinate system
    epsg_code = None
    try:
        epsg_code = proj4_to_epsg(geo_ref_cleaned)
    except Exception:
        pass

    if epsg_code:
        geodetic_dict["georeference:coordinateSystem"] = epsg_code
    else:
        # Extract projection type from PROJ string
        for token in geo_ref_text.split():
            if token.startswith("+proj="):
                geodetic_dict["georeference:coordinateSystemName"] = token.split("=")[1]
                break

    # Bounding box from header attributes
    projection_location_dict: dict = {}
    west = header.get("@west", header.get("west"))
    east = header.get("@east", header.get("east"))
    south = header.get("@south", header.get("south"))
    north = header.get("@north", header.get("north"))

    if all(v is not None for v in (west, east, south, north)):
        try:
            x_min, y_min = float(west), float(south)
            x_max, y_max = float(east), float(north)
            lat_min, lon_min = convert_to_LatLon(x_min, y_min, geo_ref_cleaned)
            lat_max, lon_max = convert_to_LatLon(x_max, y_max, geo_ref_cleaned)
            projection_location_dict["georeference:hasBoundingBox"] = {
                "georeference:xMin": f"{lon_min:.8f}",
                "georeference:yMin": f"{lat_min:.8f}",
                "georeference:xMax": f"{lon_max:.8f}",
                "georeference:yMax": f"{lat_max:.8f}",
            }

            # Origin (0,0 in local coords)
            lat_origin, lon_origin = convert_to_LatLon(0.0, 0.0, geo_ref_cleaned)
            geodetic_dict["georeference:hasOrigin"] = {
                "georeference:lat": f"{lat_origin:.8f}",
                "georeference:lon": f"{lon_origin:.8f}",
            }

            # View point (center of bbox)
            center_lat = (lat_min + lat_max) * 0.5
            center_lon = (lon_min + lon_max) * 0.5
            get_adress_from_osm(projection_location_dict, center_lat, center_lon)
            geodetic_dict["georeference:hasViewPoint"] = {
                "georeference:lat": f"{center_lat:.8f}",
                "georeference:lon": f"{center_lon:.8f}",
            }
        except Exception:
            logger.warning("Could not convert georeference coordinates")

    if projection_location_dict:
        georeference_dict["georeference:hasProjectLocation"] = projection_location_dict
    if geodetic_dict:
        georeference_dict["georeference:hasGeodeticReferenceSystem"] = geodetic_dict

    return georeference_dict if georeference_dict else None


def extract_meta_data(file: Path) -> Tuple[bool, dict]:
    """Extract metadata from an OpenDRIVE file.

    Returns (success, metadata_dict) matching the expected pipeline format.
    """
    file = Path(file).resolve()
    logger.debug("Loading input file %s", file)

    try:
        # Decode XML using XSD schema
        data, decode_errors = _decoder.decode(file)
    except Exception:
        logger.exception("Cannot decode %s", file)
        return False, {}

    try:
        # Load mapping and run extraction engine
        mapping = MappingConfig.from_yaml(_MAPPING_FILE)
        engine = ExtractionEngine()
        extracted = engine.extract(data, mapping, context={"file_path": file})
    except Exception:
        logger.exception("Cannot extract metadata from %s", file)
        return False, {}

    # ── Assemble output structure ──────────────────────────────────────────
    meta_data_dict: dict = {}
    meta_data_dict["did"] = f"did:web:registry.gaia-x.eu:HdMap:{create_uuid()}"
    meta_data_dict["shacl_schema"] = get_schema_name()
    meta_data_dict["shacl_url"] = get_namespace()

    # Resource description
    resource_desc: dict = {}
    resource_desc["schema:name"] = file.stem
    resource_desc["schema:description"] = "road network"
    enrich_resource_description(resource_desc, file)
    meta_data_dict["hdmap:hasResourceDescription"] = resource_desc

    # Recording time from header
    header = data.get("header", {})
    if isinstance(header, dict):
        date_str = header.get("@date")
        if date_str:
            meta_data_dict["recordingTime"] = _parse_date(date_str)
        else:
            meta_data_dict["recordingTime"] = "Unknown"

    # Domain specification
    domain: dict = {}

    # Format
    format_dict: dict = {}
    if "hdmap:formatType" in extracted:
        format_dict["hdmap:formatType"] = extracted.pop("hdmap:formatType")
    if "hdmap:version" in extracted:
        format_dict["hdmap:version"] = extracted.pop("hdmap:version")
    domain["hdmap:hasFormat"] = format_dict

    # Content
    content_dict: dict = {}
    for key in ("hdmap:roadTypes", "hdmap:laneTypes", "hdmap:levelOfDetail"):
        if key in extracted:
            val = extracted.pop(key)
            content_dict[key] = val.split(", ") if isinstance(val, str) else val
    domain["hdmap:hasContent"] = content_dict

    # Quantity
    quantity_dict: dict = {}
    for key in (
        "hdmap:length",
        "hdmap:numberIntersections",
        "hdmap:numberOutlines",
        "hdmap:numberObjects",
        "hdmap:numberTrafficLights",
        "hdmap:numberTrafficSigns",
        "hdmap:elevationRange",
    ):
        if key in extracted:
            quantity_dict[key] = extracted.pop(key)

    # Speed limit (special structure: min/max)
    if "hdmap:speedLimit" in extracted:
        speed_str = extracted.pop("hdmap:speedLimit")
        if isinstance(speed_str, str) and speed_str:
            speeds = sorted(round(float(s), 2) for s in speed_str.split(", ") if s)
            quantity_dict["hdmap:speedLimit"] = {
                "hdmap:min": speeds[0] if speeds else 0.0,
                "hdmap:max": speeds[-1] if speeds else 50.0,
            }
        else:
            quantity_dict["hdmap:speedLimit"] = {"hdmap:min": 0.0, "hdmap:max": 50.0}
    else:
        quantity_dict["hdmap:speedLimit"] = {"hdmap:min": 0.0, "hdmap:max": 50.0}

    domain["hdmap:hasQuantity"] = quantity_dict
    domain["hdmap:hasQuality"] = {}
    domain["hdmap:hasDataSource"] = {}

    # Georeference
    geo = _build_georeference(data)
    if geo:
        domain["hdmap:hasGeoreference"] = geo

    meta_data_dict["hdmap:hasDomainSpecification"] = domain

    # Manifest
    meta_data_dict["hdmap:hasManifest"] = {
        "manifest:hasAccessRole": "envited-x:isPublic",
        "manifest:hasCategory": "envited-x:isManifest",
        "manifest:hasFileMetadata": {
            "manifest:filePath": "../manifest.json",
            "manifest:mimeType": "application/ld+json",
        },
        "manifest:iri": f"{DID_ADRESS}{create_uuid()}",
        "skos:note": (
            "Ensure that manifest.json contains all required categories: "
            "simulationData, documentation, metadata, media."
        ),
        "sh:conformsTo": [
            f"https://w3id.org/ascs-ev/envited-x/envited-x/{ENVITEDX_SCHEMA_VERSION}/",
            f"https://w3id.org/ascs-ev/envited-x/manifest/{MANIFEST_SCHEMA_VERSION}/",
        ],
    }

    logger.info("Extracted metadata from %s", file.name)
    return True, meta_data_dict


def get_description() -> str:
    return "extract OpenDRIVE"


def get_schema_name() -> str:
    return "HdMap"


def get_namespace() -> str:
    return f"{ENVITED_URL}{get_schema_name().lower()}/{ODR_SCHEMA_VERSION}"
