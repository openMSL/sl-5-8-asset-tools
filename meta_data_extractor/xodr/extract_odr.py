from sympy import symbols, solveset
from lxml import etree
from pathlib import Path
from datetime import datetime
from typing import Tuple
from ..extractor import get_adress_from_osm, proj4_to_epsg, convert_to_LatLon
from utils.utils import create_uuid

import logging

logger = logging.getLogger(__name__)

ENVITEDX_URL: str = 'https://ontologies.envited-x.net'
ODR_SCHEMA_VERSION = 'v4'

# convert container to str
def container_in_str(data: any) -> str:
    string = ''
    for value in data:
        if value is not None:
            string = string + f' {value}'
    return string

# convert data and time to str
def convert_date_time(date_string : str, supported_syntax : list[str]) -> str:
    for syntax in supported_syntax:
        try:
            date = datetime.strptime(date_string, syntax)
            return date.isoformat()
        except ValueError:
            continue
    return None



#######################################################################################################################
def get_meta_data(file_path: str, default_value: str) -> dict:

    root = etree.parse(file_path).getroot()

    unknown_unit = "unknown unit"

    # get data used several times
    data = dict()
    content_dict = dict()
    format_dict = dict()
    quantity_dict = dict()

    # read xml and extract header data
    data['header'] = root.find('.//header').attrib if check_data(root, ".//header") else None
    if check_data(root,".//header//geoReference"):
        data['header']['geoReference'] = root.find('.//header//geoReference').text

    # read xml and extract all elevation data
    data['elevation'] = [elevation.attrib for elevation in root.findall('.//elevation')]

    # read xml and extract object data
    data['object'] = [obj.attrib for obj in root.findall('.//object')] if check_data(root, ".//object") else None

    # readable meta data
    # read xml and search for CRG and read the element file         # TODO Testing
    data_links = container_in_str(set([crg.attrib['file'] for crg in root.findall('.//CRG')])) if check_data(root, ".//CRG","file") else ''# default_value
    #if data_links:
    #    meta_data_dict['data_link'] = {}

    # read xml and search for speed and the element max --> then sort by max and create a set --> set == unique values
    speedlimit_range = sorted(set((max.attrib['max'] for max in root.findall('.//speed')))) if check_data(root, ".//speed","max") else [0, 50]
    speedlimit_range_dict = {}
    speedlimit_range_dict['hdmap:min'] = float(speedlimit_range[0])
    speedlimit_range_dict['hdmap:max'] = float(speedlimit_range[-1])
    quantity_dict['hdmap:speedLimit'] = speedlimit_range_dict

    # read xml and check if lane and its element type exists --> take all information of lane type and make them unique
    lane_types = set([lane.attrib['type'] for lane in root.findall('.//lane')]) if check_data(root, ".//lane","type") else None
    if lane_types:
        content_dict['hdmap:laneTypes'] = list(sorted(lane_types))

    # read xml and check if road and its element type exists --> take all information of road type and make them unique 
    road_types = set([road_type.attrib['type'] for road_type in root.findall('./road/type')]) if check_data(root,"./road/type","type") else None
    if road_types:
        content_dict['hdmap:roadTypes'] = list(sorted(road_types))

    # create a unique list of object type if it exists
    objects = set([obj['type'] for obj in data['object']]) if check_data(root, ".//object", "type") else None
    if objects:
        content_dict['hdmap:levelOfDetail'] = list(objects)

    # search for revMajor and revMinor and create the format_version string
    format_dict['hdmap:version'] = str(data['header']['revMajor']) + '.' + str(data['header']['revMinor']) if check_data(root, ".//header", "revMajor", "revMinor") else default_value
    format_dict['hdmap:formatType'] = 'ASAM OpenDRIVE'

    # read xml and create a list with all lengths
    list_of_lengths = [float(road.attrib['length']) for road in root.findall('.//road')] if check_data(root,".//road","length") else default_value

    # search for needed information
    #meta_data_dict['vendor_name'] = data['header']['vendor'] if check_data(root, ".//header","vendor") else default_value
    # convert to datetime object
    hasDataResource_dict = dict()
    #general_data_dict = dict()

    
    # parse string of georeference
    # set all values to default
    geo_reference = None
    if 'header' in data and 'geoReference' in data['header']:
        geo_reference = data['header']['geoReference']

    if geo_reference:
        geodetic_ref_system_dict = dict()
        geo_data = geo_reference.split(' ')

        # go through the string and parse data if available
        local_data_dict = dict()
        local_data_dict['projection_type'] = ''
        for information in geo_data:
            if information.startswith("+proj="):
                local_data_dict['projection_type'] = local_data_dict['projection_type'] + (information.split("+proj=")[1])
            elif information.startswith("+grids="):
                geodetic_ref_system_dict['georeference:heightSystem'] = information.split("+grids=")[1]
            elif information.startswith("+datum="):
                local_data_dict['geodetic_datum'] = information.split("+datum=")[1]
            elif information.startswith("+units="):
                local_data_dict['geodetic_unit'] = information.split("+units=")[1]
            #elif information.startswith("+lat_0="):
            #    lat = information.split("+lat_0=")[1]
            #elif information.startswith("+lon_0="):
            #    lon = information.split("+lon_0=")[1]

        epsg_code = proj4_to_epsg(geo_reference)
        if epsg_code:
            geodetic_ref_system_dict['georeference:coordinateSystem'] = epsg_code
        else:
            geodetic_ref_system_dict['georeference:coordinateSystemName'] = local_data_dict['projection_type']

    ###################################################################################################################
    # calculated meta data

    # read xml and count the amount of junctions/intersection
    quantity_dict['hdmap:numberIntersections'] = len(root.findall('.//junction')) if check_data(root,".//junction") else 0

    # read xml and count the amount of outlines
    quantity_dict['hdmap:numberOutlines'] = len(root.findall('.//outline')) if check_data(root, ".//outline") else 0

    # add all lengths /1000 -->from meters to kilometers
    quantity_dict['hdmap:length'] = float(sum(list_of_lengths) / 1000) if len(list_of_lengths) else 0.0
    #meta_data_dict['length_unit'] = 'km'

    # call function get_elevation_range with elevation data
    quantity_dict['hdmap:elevationRange'] = float(get_elevation_range(root, data['elevation'], list_of_lengths))
    #meta_data_dict['elevation_range_unit'] = 'm'

    # count the amount of objects
    quantity_dict['hdmap:numberObjects'] = len(data['object']) if data['object'] is not None else 0

    # check if object has the element subtype and count the amount of subtype == trafficLight
    quantity_dict['hdmap:numberTrafficLights'] = len([obj for obj in data['object'] if obj['subtype'] == 'trafficLight']) if check_data(root, './/object','subtype') else 0

    # check if object has the element subtype and count the amount of subtype == trafficSign
    quantity_dict['hdmap:numberTrafficSigns'] = len([obj for obj in data['object'] if obj['subtype'] == 'trafficSign']) if check_data(root, './/object','subtype') else 0

    ###################################################################################################################
    # constant meta data

    # if it is a xodr file it describes road network    
    hasDataResource_dict['gx:name'] = file_path.name.replace('.xodr', '')
    hasDataResource_dict['gx:description'] = "road network"

    # bounding
    georeference_dict = dict()
    if geo_reference:
        projection_location_dict = dict()
        georeference_dict['georeference:hasProjectLocation'] = projection_location_dict
        bounding_dict = dict()
        bounding_dict['xMin'] = float(root.find('.//header').attrib['west']) if check_data(root, ".//header", "west") else unknown_unit
        bounding_dict['xMax'] = float(root.find('.//header').attrib['east']) if check_data(root, ".//header", "east") else unknown_unit
        bounding_dict['yMin'] = float(root.find('.//header').attrib['south']) if check_data(root, ".//header", "south") else unknown_unit
        bounding_dict['yMax'] = float(root.find('.//header').attrib['north']) if check_data(root, ".//header", "north") else unknown_unit    
        bounding_dict['yMin'], bounding_dict['xMin'] = convert_to_LatLon(bounding_dict['xMin'], bounding_dict['yMin'], geo_reference)
        bounding_dict['yMax'], bounding_dict['xMax'] = convert_to_LatLon(bounding_dict['xMax'], bounding_dict['yMax'], geo_reference)
        bounding_data_dict = dict()
        bounding_data_dict['georeference:xMin'] = str(bounding_dict['xMin'])
        bounding_data_dict['georeference:yMin'] = str(bounding_dict['yMin'])
        bounding_data_dict['georeference:xMax'] = str(bounding_dict['xMax'])
        bounding_data_dict['georeference:yMax'] = str(bounding_dict['yMax'])
        projection_location_dict['georeference:hasBoundingBox'] = bounding_data_dict

        # get 0,0 point in unit and convert to lat lon
        lat, lon = convert_to_LatLon(0.0, 0.0, geo_reference)
        origin_dict = dict()
        origin_dict['georeference:lat'] = str(lat)
        origin_dict['georeference:lon'] = str(lon)
        geodetic_ref_system_dict['georeference:hasOrigin'] = origin_dict

        # get country, state, town from OSM
        center_lon = (bounding_dict['xMin'] + bounding_dict['xMax']) * 0.5
        center_lat = (bounding_dict['yMin'] + bounding_dict['yMax']) * 0.5
        get_adress_from_osm(projection_location_dict, center_lat, center_lon)
        viewpoint_dict = dict()
        viewpoint_dict['georeference:lat'] = str(center_lat)
        viewpoint_dict['georeference:lon'] = str(center_lon)
        geodetic_ref_system_dict['georeference:hasViewPoint'] = viewpoint_dict  
        georeference_dict['georeference:hasGeodeticReferenceSystem'] = geodetic_ref_system_dict

    ###################################################################################################################
    # unfinished meta data
    
    #meta_data_dict['range_of_modeling'] = 0.0 #"Wie ermittelt man das?"
    # TODO get from traffic rule
    #content_dict['hdmap:trafficDirection'] = ""
    #content_dict['hdmap:levelOfDetail'] = ""
    #projection_location_dict['georeference:relationOrArea'] = ""
    #projection_location_dict['georeference:relationOrArea'] = ""
    
    
    meta_data_dict = dict()
    meta_data_dict['did'] = 'did:web:registry.gaia-x.eu:HdMap:' + create_uuid()
    meta_data_dict['shacl_type'] = f'{get_schema_name().lower()}::{get_namespace()}#{get_schema_name()}Shape'
    meta_data_dict[f'{get_schema_name().lower()}:hasDataResource'] = hasDataResource_dict    

    try:        
        supported_date_syntax = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",  # 2023-01-09T14:51:51
        ]
        meta_data_dict['recordingTime'] = convert_date_time(data['header']['date'], supported_date_syntax) if check_data(root,".//header","date") else default_value
    except:
        logger.error('cannot extract date')    

    hasDataResourceExtension_dict = dict()
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasFormat'] = format_dict
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasContent'] = content_dict
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasQuantity'] = quantity_dict
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasQuality'] = {}
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasDataSource'] = {}
    hasDataResourceExtension_dict[f'{get_schema_name().lower()}:hasGeoreference'] = georeference_dict    
    meta_data_dict[f'{get_schema_name().lower()}:hasDataResourceExtension'] = hasDataResourceExtension_dict

    hasManifest_dict = dict() # TODO
    hasManifest_dict['manifest:hasAccessRole'] = 'envited-x:isPublic'
    hasManifest_dict['manifest:hasCategory'] = 'envited-x:isManifest'
    hasManifest_dict['manifest:hasFileMetadata'] = { # TODO
        "manifest:filename": "manifest_reference.json",
        "manifest:filePath": "./manifest_reference.json",
        "manifest:mimeType": "application/ld+json"
    }
    hasManifest_dict['manifest:iri'] = 'did:web:registry.gaia-x.eu:Manifest:uuid'
    hasManifest_dict['skos:note'] = 'Ensure that manifest_reference.json contains all required categories: simulationData, documentation, metadata, media.'
    hasManifest_dict['sh:conformsTo'] = [
        "https://ontologies.envited-x.net/envited-x/v2/ontology#",
        "https://ontologies.envited-x.net/manifest/v5/ontology#"
    ]
    meta_data_dict[f'{get_schema_name().lower()}:hasManifest'] = hasManifest_dict

    return meta_data_dict


#######################################################################################################################


# function to check if the path is in xml file and if the element is in the certain path
def check_data(root, path: str, *elements) -> bool:
    try:
        # finding the first instance of the path. if no instance is found 'None' is returned
        entries = root.find(path)

        # if the path is not existing
        if entries is None:
            return False

        # as elements is a vararg iterate through it
        if len(elements) != 0:
            # go through every element and try to reach it
            for element in elements:
                entries.attrib[element]  # as we only want to reach it we don't need to store it
        return True

    # if xpath is not in current xml file there will be a key error
    except KeyError:
        return False

    # if one of the elements is not in current xml path at the certain xpath there will be a value error
    except ValueError:
        return False

    # if the entry doesn't have the elements there will be a attribute error
    except AttributeError:
        return False


#######################################################################################################################


# function to get all functions and differentiation of the elevations
def get_elevation_functions(a, b, c, d, s):
    # declare x as a variable
    x = symbols('x')

    # build the function as described in opendrive --> elev(ds) = a + b*ds + c*ds² + d*ds³
    # link: https://releases.asam.net/OpenDRIVE/1.6.0/ASAM_OpenDRIVE_BS_V1-6-0.html#_methods_of_elevation
    expression = a + b * x + c * x**2 + d * x**3

    # derive the function by hand
    differentiation = b + 2 * c * x + 3 * d * x**2

    return [s, expression, differentiation]


#######################################################################################################################
# function to get the max and min value of the certain section of the function
def get_elevation_min_max(start, end, expr, diff):
    # declare x as a variable
    x = symbols('x')
    # use start as x to get the value of the front border
    start_value = expr.subs(x, 0)
    # use end as x to get the value of the back border
    end_value = expr.subs(x, end-start)
    # get the potential min and max value
    candidates = []
    # if diff is 0 do not search for results as 0 = 0
    if diff != 0:
        solveset(diff)
    candidate_value = []
    if len(candidates) != 0:
        for candidate in candidates:

            # check if the candidate is between the front and back border
            if 0 <= candidate <= end-start:
                # if so --> use candidate as x and get the value
                candidate_value.append(expr.subs({x: candidate}))

        if len(candidate_value) != 0:
            # get of all candidates the minimum
            min_candidate = min(candidate_value)
            # get of all candidates the maximum
            max_candidate = max(candidate_value)

            # return the min and max value of candidate, front and back border
            return [min(start_value, end_value, min_candidate), max(start_value, end_value, max_candidate)]
        else:
            # if there are any candidates valid --> get the min and max from front and back border
            return [min(start_value, end_value), max(start_value, end_value)]
    else:
        # if there are no candidates then just take the min and max from front and back border
        return [min(start_value, end_value), max(start_value, end_value)]


#######################################################################################################################
# function to shorten the code in main
def get_elevation_range(root, elevations, list_of_lengths):
    result_min = 0.0
    result_max = 0.0

    # check if xml file has elevation and those elements
    if check_data(root, ".//elevation", "a", "b", "c", "d", "s"):

        all_functions = []
        # go through every elevation and get their functions
        for elevation in elevations:
            all_functions.append(
                get_elevation_functions(float(elevation['a']), float(elevation['b']), float(elevation['c']),
                                        float(elevation['d']), float(elevation['s'])))

        road_counter = 0

        # go through every function and calculate their min and max
        for ind, function in enumerate(all_functions):
            start = function[0]

            # get length --> to know the end
            length = len(all_functions)
            # get the function
            expr = function[1]
            # get the differentiation
            diff = function[2]

            # to get the end of the current elevation --> take the start of the following
            # if current is last elevation or following elevation restarted in 0 --> take the current length of road
            if ind + 1 == length or all_functions[ind + 1][0] == 0:
                end = list_of_lengths[road_counter]
                road_counter += 1
            else:
                end = all_functions[ind + 1][0]

            # call function to gen min and max
            min_val, max_val = get_elevation_min_max(start, end, expr, diff)

            if result_min == 0.0 and result_max == 0.0:
                result_min = min_val
                result_max = max_val
            else:
                # get current min and max and compare them with min and max in result_data
                result_min = min(result_min, min_val)
                result_max = max(result_max, max_val)

    return result_max - result_min


#######################################################################################################################
# open asset file, parse xml and extract meta data
def extract_meta_data(file: Path) ->Tuple[bool, dict]:
    # read file
    logger.debug(f'Loading input file {file.absolute()}')
    try: 
        with open(file, 'r') as f:
            _ = f.read()
    except:
        logger.exception(f'Cannot read file {file.absolute()}')
        return False
    
    # parse xml
    try: 
        root = etree.parse(str(file), etree.XMLParser(dtd_validation=False))
    except:
        logger.exception(f'Cannot parse XML from file {file.absolute()}')
        return False
    
    # ask in file dialog for file with given file extension -->close program if interrupted
    try:
        attributes = get_meta_data(file, "Unknown")
    except:
        logger.exception(f'Cannot extract from file {file.absolute()}')
        return False
    
    logger.info(f'Extract from file {file}')
    return True, attributes
    

def get_description() -> str:
    return 'extract OpenDRIVE'


def get_schema_name() -> str:
    return 'HdMap'

def get_namespace() -> str:
    return f'{ENVITEDX_URL}/{get_schema_name().lower()}/{ODR_SCHEMA_VERSION}/ontology'
