from pathlib import Path
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Nominatim
from pyproj import CRS, Transformer
from utils.json import write_json

import logging

logger = logging.getLogger(__name__)

FORMAT_ALIASES = {
    "3dmodel": "3dModel",
}

CONVERT_GERMAN_UMLAUT = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "ß": "ss",
}


# replace German umlauts with non-umlaut equivalents
def replace_german_umlauts(text: str) -> str:

    for umlaut, replacement in CONVERT_GERMAN_UMLAUT.items():
        text = text.replace(umlaut, replacement)

    return text


# get adress from OSM geolocator
def get_adress_from_osm(data_dict, latitude, longitude):
    # custom User-Agent
    custom_user_agent = "GaiaX_ODR_Extractor/1.0"
    # Initialize Nominatim geocoder
    geolocator = Nominatim(user_agent=custom_user_agent, timeout=10)
    try:
        location = geolocator.reverse((latitude, longitude), exactly_one=True)
    except GeocoderServiceError as exc:
        logger.warning(
            "Could not reverse geocode latitude=%s longitude=%s: %s",
            latitude,
            longitude,
            exc,
        )
        return False

    if location is None or not isinstance(getattr(location, "raw", None), dict):
        logger.warning(
            "Reverse geocoding returned no address for latitude=%s longitude=%s",
            latitude,
            longitude,
        )
        return False

    address = location.raw.get("address")
    if not isinstance(address, dict):
        logger.warning(
            "Reverse geocoding returned no structured address for latitude=%s longitude=%s",
            latitude,
            longitude,
        )
        return False

    # Nominatim always provides country_code (ISO 3166-1 alpha-2, lowercase).
    # We uppercase it and omit the field when absent (e.g. ocean coordinates).
    country_code = address.get("country_code", "").upper()
    if country_code:
        data_dict["georeference:country"] = country_code

    # Nominatim returns ISO 3166-2 codes at varying admin levels depending on
    # the country.  Try the most common levels (4, 3, 6) before falling back to
    # the free-text "state" field.  City-states like Singapore may not have any
    # subdivision at all — in that case we simply omit the optional field so
    # SHACL validation does not fail on an empty string.
    state = (
        address.get("ISO3166-2-lvl4")
        or address.get("ISO3166-2-lvl3")
        or address.get("ISO3166-2-lvl6")
        or address.get("state", "")
    )
    if state:
        data_dict["georeference:state"] = state

    region = replace_german_umlauts(address.get("county", ""))
    if region:
        data_dict["georeference:region"] = region

    city = replace_german_umlauts(
        address.get("city", address.get("town", address.get("village", "")))
    )
    if city:
        data_dict["georeference:city"] = city
    return True


# convert proj4 to epsg code
def proj4_to_epsg(proj4_string: str) -> int:
    # create a CRS-Object from Proj4-String
    crs = CRS.from_proj4(proj4_string)
    # get EPSG-Code
    epsg_code = crs.to_epsg()
    return epsg_code


# convert coordinates to LatLon using pyproj
def convert_to_LatLon(x: float, y: float, proj4: str) -> tuple[float, float]:
    source_crs = CRS.from_proj4(proj4)
    transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lat, lon


def get_format_name(file: Path, format_hint: str | None = None) -> str:
    if format_hint:
        return FORMAT_ALIASES.get(format_hint, format_hint)
    return file.suffix.lstrip(".")


# extract meta data from file
def extract(file: Path, output_file: Path, format_hint: str | None = None) -> bool:
    file = file.expanduser()
    file = file.resolve()

    # check folder with extension
    format_name = get_format_name(file, format_hint)
    format_path = Path(__file__).parent / format_name
    if not format_path.exists() or not format_path.is_dir():
        logger.error(
            "Provided format path does not exist or is not a directory: %s",
            format_path.absolute(),
        )
        return False

    # import python script from subfolder
    files = [
        extrator_file
        for extrator_file in format_path.iterdir()
        if extrator_file.name.endswith(".py")
        and extrator_file.name != "__init__.py"
        and extrator_file.name.startswith("extract_")
    ]
    if len(files) == 0:
        return False
    module_name = "metadata_extractor." + Path(files[0]).relative_to(
        Path(__file__).parent
    ).as_posix().replace("/", ".").replace(".py", "")
    required_functions = [
        "extract_meta_data",
        "get_description",
        "get_schema_name",
        "get_namespace",
    ]
    logger.debug(f"Loading extractor {{{module_name}}}")
    try:
        extract_module = __import__(module_name, fromlist=required_functions)
    except Exception:
        logger.exception(f"Could not load extract file from module {module_name}")
        return False

    # check required functions
    missing_function = False
    for function in required_functions:
        if not hasattr(extract_module, function):
            logger.error(f"{module_name} has no requried function {function}")
            missing_function = True
            break
    if missing_function:
        return False

    # call extract and get filled attributes
    try:
        valid, meta_data = extract_module.extract_meta_data(file)
        if valid is False:
            return valid
    except Exception:
        logger.exception(f"Could not extract format {extract_module.get_description()}")
        return False

    write_json(output_file, meta_data)
    logger.info(f"write json to {output_file}")

    return True
