from pathlib import Path
from geopy.geocoders import Nominatim
from pyproj import CRS, Transformer
from utils.json import write_json

import logging

logger = logging.getLogger(__name__)

# manual assignment of local country name (Germany) to alpha-2 -> OSM only receives local name, but for alpha 2 code you need the English name.
COUNTRY_NAME_TO_ALPHA2 = {
    "Deutschland": "DE",
    "Österreich": "AT",
    "Schweiz": "CH",
    "Italia": "IT",
    "España": "ES",
    "Portugal": "PT",
    "Nederland": "NL",
    "Belgique": "BE",
    "Danmark": "DK",
    "Sverige": "SE",
    "Norge": "NO",
    "Suomi": "FI",
    "Polska": "PL",
    "Česká republika": "CZ",
    "Magyarország": "HU",
    "Ελλάδα": "GR",
    "Türkiye": "TR",
    "United Kingdom": "GB",
    "Ireland": "IE",
    "United States": "US",
    "Canada": "CA",
    "México": "MX",
    "Brasil": "BR",
    "Argentina": "AR",
    "Chile": "CL",
    "Australia": "AU",
    "New Zealand": "NZ",
    "日本": "JP",
    "中国": "CN",
    "Россия": "RU",
    "भारत": "IN",
    "South Africa": "ZA",
    # Todo, add more
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
    geolocator = Nominatim(user_agent=custom_user_agent)
    # Reverse geocoding: find address based on coordinates
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    # Extract the desired information
    address = location.raw["address"]
    country_name = address.get("country", "")
    data_dict["georeference:country"] = replace_german_umlauts(
        str(
            address.get("country_code", COUNTRY_NAME_TO_ALPHA2.get(country_name, "DE"))
        ).upper()
    )
    data_dict["georeference:state"] = address.get(
        "ISO3166-2-lvl4", address.get("state", "")
    )
    # data_dict['postcode'] = address.get('postcode', '')
    data_dict["georeference:region"] = replace_german_umlauts(address.get("county", ""))
    data_dict["georeference:city"] = replace_german_umlauts(
        address.get("city", address.get("town", address.get("village", "")))
    )


# convert proj4 to epsg code
def proj4_to_epsg(proj4_string: str) -> int:
    # create a CRS-Object from Proj4-String
    crs = CRS.from_proj4(proj4_string)
    # get EPSG-Code
    epsg_code = crs.to_epsg()
    return epsg_code


# convert coordinates to LatLon using pyproj
def convert_to_LatLon(x: float, y: float, proj4: str) -> tuple[float, float]:
    transformer = Transformer.from_proj(proj4, "epsg:4326")  # WGS84
    lon, lat = transformer.transform(x, y)
    return lon, lat


# extract meta data from file
def extract(file: Path, output_file: Path) -> bool:
    file = file.expanduser()
    file = file.resolve()

    # check folder with extension
    extension = file.suffix.lstrip(".")
    format_path = Path(__file__).parent / f"{extension}"
    if not format_path.exists() or not format_path.is_dir():
        logger.error(
            f"Provided format path does not exist or is not a file: {format_path.absolute()}"
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
    module_name = "meta_data_extractor." + Path(files[0]).relative_to(
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
    except:
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
    except:
        logger.exception(f"Could not extract format {extract_module.get_description()}")
        return False

    write_json(output_file, meta_data)
    logger.info(f"write json to {output_file}")

    return True
