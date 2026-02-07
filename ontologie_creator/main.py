# download current table into this script folder 
# https://ascs2008.sharepoint.com/:x:/r/sites/team/_layouts/15/Doc.aspx?sourcedoc=%7B29F2C96B-A33B-44B9-92E3-0F513A0ED58B%7D&file=Metadata.xlsx&action=default&mobileredirect=true

from rdflib import Graph, Literal, Namespace, BNode
from rdflib.namespace import XSD, OWL, RDF, RDFS, SH, SKOS, DCTERMS
from utils.constants import GAIAX_CORE_NS, GAIAX_TRUST_NS, SHACL_NS

import pandas as pd
import argparse
import logging
import os
import utils.constants 

logger = logging.getLogger(__name__)

# data string to data type
DATA_TYPE_MAP = {
    'string': {'type' : XSD.string},
    'boolean': {'type' : XSD.boolean},
    'date': {'type' : XSD.dateTime},
    'link': {'type' : "Link"},
    'url': {'type' : XSD.anyURI},
    'coordinate': {'type' : 'Coordinate2D'},
    'range': {'type' : 'Range2D'},
    'boundingbox': {'type' : 'BoundingBox'}, # not yet supported
    'float': {'type' : XSD.float},
    'unsigned': {'type' : XSD.unsignedInt},
    'date': {'type' : XSD.dateTime},
    'angle': {'type' : XSD.float},
    'int': {'type' : XSD.int},
    'integer': {'type' : XSD.int},
    'country' : {'type' : XSD.string, 'pattern' : '^[a-zA-Z]{2}'},
    'state' : {'type' : XSD.string, 'pattern' : '^[a-zA-Z]{2}-(?:[a-zA-Z]{1,3}|[0-9]{1,3})$'},
    'link_type' : {'type' : XSD.string, 'values' : ["Image", "Video", "Document", "Routing", 'Model']},
    'hdmap_road_type' : {'type' : XSD.string, 'values' : ["Bicycle", 'LowSpeed', 'Motorway', 'Pedestrian', 'Rural', 'TownArterial', 'TownCollector', 'TownExpressway', 'TownLocal', 'TownPlayStreet', 'TownPrivate', 'Town', 'Unknown']},
    'hdmap_lane_type' : {'type' : XSD.string, 'values' : ["biking", "border", "connectingRamp", "curb", "driving", "entry", "exit", "median", "none", "offRamp", "onRamp", "parking", "restricted", "shoulder", "slipLane", "stop", "walking"]},
    'hdmap_object_type' : {'type' : XSD.string, 'values' : ["barrier", "bike", "building", "bus", "car", "crosswalk", "gantry", "motorbike"]},
    'hdmap_type' : {'type' : XSD.string, 'values' : ["ASAM OpenDRIVE", "Lanelet2", "road2sim", "Road5", "roadXML", "Shape"]},
    'hdmap_traffic_dir_type' : {'type' : XSD.string, 'values' : ["left-hand", "right-hand"]},
    'surfacemodel_type' : {'type' : XSD.string, 'values' : ["ASAM OpenCRG", "DLM"]},
    'scenario_type' : {'type' : XSD.string, 'values' : ["ASAM OpenSCENARIO XML", "ASAM OpenSCENARIO DSL"]},
    'scenario_participant_type' : {'type' : XSD.string, 'values' : ["car", "truck", "pedestrian"]},
    'model_type' : {'type' : XSD.string, 'values' : ["Unreal DataSmith", "Autodesk FBX", "OpenSceneGraph" , "GLTF"]},
    'model_detaillevel_type' : {'type' : XSD.string, 'values' : ["High", "Medium", "Low"]},
    'geo_height_type' : {'type' : XSD.string, 'values' : ["Ellipsodial height", "Orthometric height"]}
}   

# use only this rows for import
USE_ROW_NAME = {
    'category' : str, 
    'subtype' : str, 
    'attribute_name' : str, 
    'attribute_description' : str, 
    'frequency' : str, 
    'data_type' : str, 
    'unit' : str,
    'example' : str
}

# used data_type_node
used_data_type_nodes = set()

# check special chars in string
def check_special_chars(string : str) -> bool:
    special_chars = [" ", "/", "..."]
    for char in special_chars:
        if char in string:
            logger.error(f'attribute name {string} has unsuported chars!')
            return True
    return False

# convert str to camel case forma
def to_camel_case(s : str) -> str:
    words = s.split()
    if not words:
        return s
    # lower case for first word
    camel_case_string = words[0].lower()
    # upper case for first letter of following words
    for word in words[1:]:
        camel_case_string += word.capitalize()
    return camel_case_string

# check if utf16-le is used for string encoding
def is_utf16_le(string: str) -> bool:
    try:
        string.encode('utf-16le')
        return True
    except UnicodeEncodeError:
        logger.exception(f'string {string} has utf16 chars!')
        return False

# add to attributes
def addData(category : str, subcategory : str, data_name : str, data : dict, attributes : dict):
    if category not in attributes:
        attributes[category] = {}
    if subcategory not in attributes[category]:
        attributes[category][subcategory] = {}
    if data_name not in attributes[category][subcategory]:
        attributes[category][subcategory][data_name] = {}
    attributes[category][subcategory][data_name] = data

# read excel file
def read_from_excel(filename: str) ->dict:
    
    # read excel file
    df = pd.read_excel(filename, header=0, usecols=USE_ROW_NAME)

    #convert all values to str
    for c in df.columns.values:
        df[c] = df[c].astype(str)
    
    category = None
    subtype = None
    attributes = {}
    
    # loop rows and read attributes
    for r in df.itertuples():        
        if r.category != 'nan':
            category = r.category
            categorie_data = {
                'contributor' : r.attribute_name,
                'description' : r.attribute_description,
                'version' : r.example,
            }
            attributes[category] = {}
            attributes[category]["categorie_data"] = (categorie_data)
        else:            
            if r.subtype != 'nan':
                subtype = r.subtype         
            if r.attribute_name != 'nan':                
                data = {
                    'name' : r.attribute_name,
                    'description' : r.attribute_description,
                    'frequency' : r.frequency.lower() ,
                    'data_type' : r.data_type.lower()   ,
                    'unit' : r.unit.lower(),
                    'example' : r.example
                }
                addData(category, subtype, r.attribute_name, data, attributes)    

    attributes = dict(sorted(attributes.items()))

    # fix/convert values
    for cat, cat_data in attributes.items():
        is_utf16_le(cat)  
        if check_special_chars(cat):
            logger.exception(f'category {cat} has unsuported chars!')

        for sub_cat, sub_cat_data in cat_data.items():
            if sub_cat == "categorie_data":
                continue

            is_utf16_le(sub_cat)  
            if check_special_chars(sub_cat):
                logger.exception(f'sub category {sub_cat} has unsuported chars!')

            for attrib, attrib_data in sub_cat_data.items():
                is_utf16_le(attrib)
                if check_special_chars(attrib):
                    logger.exception(f'attrib {attrib} has unsuported chars!')                
        
                # convert datatype str in xsd type
                """
                if attrib_data['data_type'] in dataTypeMap:
                    attrib_data['data_type'] = dataTypeMap[attrib_data['data_type']]
                elif attrib_data['data_type'] == "nan":
                    attrib_data['data_type'] = dataTypeMap['string']
                else:
                    logger.error(f"unsupported datatype: {attrib_data['data_type']} for {attrib}")
                """

                # convert frequency str to min max
                if attrib_data['frequency'] == "1" or attrib_data['frequency'] == "1.0":
                    attrib_data['frequency_min'] = 1
                    attrib_data['frequency_max'] = 1
                elif attrib_data['frequency'] == "0-n":
                    attrib_data['frequency_min'] = 0
                elif attrib_data['frequency'] == "1-n":
                    attrib_data['frequency_min'] = 1
                elif attrib_data['frequency'] == "0-1":
                    attrib_data['frequency_min'] = 0
                    attrib_data['frequency_max'] = 1  
                elif attrib_data['frequency'] == "nan":      
                    attrib_data['frequency_min'] = 0
                else:
                    logger.info(type(attrib_data['frequency']))
                    logger.error(f"unsupported frequency: {attrib_data['frequency']} for {attrib}")

                # fix unit
                if attrib_data['unit'] == 'nan' or attrib_data['unit'] == '-':
                    attrib_data['unit'] = ''    
    return attributes

# create ontology
def create_onotology(cat, cat_data, output_path, link_repro):
    namespace_GaiaX_Core = Namespace(GAIAX_CORE_NS)
    namespace_GaiaX_Trust = Namespace(GAIAX_TRUST_NS)
 
    cat_lowercase = cat.lower()

    ontology = Graph()
    ontology_name = f'{cat_lowercase}_ontology'

    # prefixes (others are added automatically!!)
    ontology.bind('gax-core', namespace_GaiaX_Core)
    ontology.bind('gax-trust-framework', namespace_GaiaX_Trust)        
    cat_namespace = Namespace(f"{link_repro}{cat_lowercase}/")
    ontology.bind(f'{cat_lowercase}', cat_namespace)

    # ontology and contributer
    node = cat_namespace['']
    ontology.add((node, RDF.type, OWL.Ontology))
    ontology.add((node, DCTERMS.contributor, Literal(f"{cat_data['categorie_data']['contributor']}")))
    ontology.add((node, RDFS.label, Literal(f'ontology definition for {cat}', lang='en')))
    ontology.add((node, OWL.versionInfo, Literal(f"{cat_data['categorie_data']['version']}", datatype=XSD.float)))

    # category class
    node_cat = cat_namespace[f'{cat}']
    ontology.add((node_cat, RDF.type, OWL.Class))
    ontology.add((node_cat, RDFS.subClassOf, namespace_GaiaX_Core.Resource))
    ontology.add((node_cat, RDFS.label, Literal(f'class definition for {cat}')))
    ontology.add((node_cat, RDFS.comment, Literal(f"{cat_data['categorie_data']['description']}", lang="en")))

    # write ontology
    file = output_path + ontology_name + '.ttl'
    with open(file, 'w') as f:
        f.write(ontology.serialize(format='turtle'))
        f.close()
        logger.info(f'write {ontology_name}')

# handle data type
def handle_data_type(root, propierty, cat_namespace, attrib_data):
    data_type = attrib_data['data_type']
    if data_type in DATA_TYPE_MAP:
        type_data = DATA_TYPE_MAP[data_type]        
        data_type_str = type_data['type']
        if '#' in data_type_str:
            root.add((propierty, SH.datatype, type_data['type']))
        else:
            data_type_ns = cat_namespace[f'{data_type_str}Shape']
            root.add((propierty, SH.node, data_type_ns))
            used_data_type_nodes.add(data_type)

        if 'pattern' in type_data:
            root.add((propierty, SH.pattern, Literal(type_data['pattern'])))

        if 'values' in type_data:
            namespace_Shacl = Namespace(SHACL_NS)
            type_data['values'].sort() # alpha numeric order ist imported
            in_constraint = root.resource(propierty)
            values = "(" + " ".join("'" + value + "'" for value in type_data['values']) + ")"
            in_constraint.add(namespace_Shacl.in_, Literal(values))
    else:
        logger.error(f"unsupported datatype: {data_type} for {attrib_data['name']}")

# create property for the shape
def create_property(root, shape, cat_namespace, attrib_data, order):    
    propierty = BNode()
    root.add((shape, SH.property, propierty))

    handle_data_type(root, propierty, cat_namespace, attrib_data)

    root.add((propierty, SH.path, cat_namespace[f"{attrib_data['name']}"]))

    if 'frequency_min' in attrib_data and attrib_data['frequency_min'] != 1:
        root.add((propierty, SH.minCount, Literal(int(attrib_data['frequency_min']))))
    if 'frequency_max' in attrib_data:
        root.add((propierty, SH.maxCount, Literal(int(attrib_data['frequency_max']))))
    if 'frequency_max' not in attrib_data and 'frequency_min' not in attrib_data:
        #root.add((propierty, SH.minCount, Literal(1)))
        root.add((propierty, SH.maxCount, Literal(1)))

    if 'example' in attrib_data:
        root.add((propierty, SKOS.example, Literal(attrib_data['example'])))        
    
    message_str = f"Validation of {attrib_data['name']} failed!"
    root.add((propierty, SH.message, Literal(message_str, lang='en')))          
    root.add((propierty, SH.name, Literal(attrib_data['name'], lang='en')))    

    if 'description' in attrib_data:
        root.add((propierty, SH.description, Literal(attrib_data['description'], lang='en')))

    root.add((propierty, SH.order,  Literal(int(order))))    

# create shape for bounding box
def create_BoundingBoxShape(root, cat_namespace):
    box_shape = cat_namespace[f'BoundingBoxShape']
    root.add((box_shape, RDF.type, SH.NodeShape))
    cat_ns = cat_namespace[f'BoundingBox']
    root.add((box_shape, SH.targetClass, cat_ns)) 

    attrib_data = {'name' : 'xMin', 'data_type' : 'float'}
    create_property(root, box_shape, cat_namespace, attrib_data, 0)
    attrib_data = {'name' : 'yMin', 'data_type' : 'float'}
    create_property(root, box_shape, cat_namespace, attrib_data, 1)
    attrib_data = {'name' : 'xMax', 'data_type' : 'float'}
    create_property(root, box_shape, cat_namespace, attrib_data, 2)
    attrib_data = {'name' : 'yMax', 'data_type' : 'float'}
    create_property(root, box_shape, cat_namespace, attrib_data, 3)

# crate shape for coordiante 2d
def create_Coordinate2DShape(root, cat_namespace):
    coordinate_shape = cat_namespace[f'Coordinate2DShape']
    root.add((coordinate_shape, RDF.type, SH.NodeShape))
    cat_ns = cat_namespace[f'Coordinate2D']
    root.add((coordinate_shape, SH.targetClass, cat_ns)) 

    attrib_data = {'name' : 'x', 'data_type' : 'float'}
    create_property(root, coordinate_shape, cat_namespace, attrib_data, 0)
    attrib_data = {'name' : 'y', 'data_type' : 'float'}
    create_property(root, coordinate_shape, cat_namespace, attrib_data, 1)

# create shape for range 2d
def create_Range2DShape(root, cat_namespace):
    range_shape = cat_namespace[f'Range2DShape']
    root.add((range_shape, RDF.type, SH.NodeShape))
    cat_ns = cat_namespace[f'Range2D']
    root.add((range_shape, SH.targetClass, cat_ns)) 

    attrib_data = {'name' : 'min', 'data_type' : 'float'}
    create_property(root, range_shape, cat_namespace, attrib_data, 0)
    attrib_data = {'name' : 'max', 'data_type' : 'float'}
    create_property(root, range_shape, cat_namespace, attrib_data, 0)   

# create shape for link
def create_LinkShape(root, cat_namespace):
    link_shape = cat_namespace[f'LinkShape']
    root.add((link_shape, RDF.type, SH.NodeShape))
    cat_ns = cat_namespace[f'Link']
    root.add((link_shape, SH.targetClass, cat_ns)) 

    attrib_data = {'name' : 'url', 'data_type' : 'url'}
    create_property(root, link_shape, cat_namespace, attrib_data, 0)
    attrib_data = {'name' : 'type', 'data_type' : 'link_type'}
    create_property(root, link_shape, cat_namespace, attrib_data, 1)
    #attrib_data = {'name' : 'data', 'data_type' : 'string', 'frequency_min' : 0}
    #create_property(root, link_shape, cat_namespace, attrib_data)

# create data structure
def create_data_structure(root, cat_namespace):

    for used_type in used_data_type_nodes:
        if used_type == "boundingbox":
            create_BoundingBoxShape(root, cat_namespace)
        elif used_type == "coordinate":            
            create_Coordinate2DShape(root, cat_namespace)
        elif used_type == "range":
            create_Range2DShape(root, cat_namespace)
        elif used_type == "link":
            create_LinkShape(root, cat_namespace)
        else:
            logger.error(f'data node not implmented: {used_type}')  

# crate shacle
def create_shacl(cat, cat_data, output_path, link_repro):
    
    cat_lowercase = cat.lower()
    
    shacl = Graph()
    shacl_name = f'{cat}_shacl'

    # add ontology prefix
    cat_namespace = Namespace(f"{link_repro}{cat_lowercase}/")
    shacl.bind(cat_lowercase, cat_namespace)

    # shape node for category
    cat_shape = cat_namespace[f'{cat}Shape']
    shacl.add((cat_shape, RDF.type, SH.NodeShape))

    # add poperty with link to sub classes
    order_cat = 0
    for sub_cat, sub_cat_data in cat_data.items():
        if sub_cat == "categorie_data":
            continue

        cat_prop = BNode()
        shacl.add((cat_shape, SH.property, cat_prop))
        sub_cat_ns = cat_namespace[f'{to_camel_case(sub_cat)}']
        sub_cat_shape_ns = cat_namespace[f'{sub_cat}Shape']
        shacl.add((cat_prop, SH.minCount, Literal(int(1))))
        shacl.add((cat_prop, SH.maxCount, Literal(int(1))))
        shacl.add((cat_prop, SH.path, sub_cat_ns))
        shacl.add((cat_prop, SH.node, sub_cat_shape_ns))
        shacl.add((cat_prop, SH.order,  Literal(int(order_cat))))   
        order_cat = order_cat + 1

    cat_ns = cat_namespace[f'{cat}']
    shacl.add((cat_shape, SH.targetClass, cat_ns))        

    # add sub classes with properties
    for sub_cat, sub_cat_data in cat_data.items():
        if sub_cat == "categorie_data":
            continue

        sub_cat_shape = cat_namespace[f'{sub_cat}Shape']
        shacl.add((sub_cat_shape, RDF.type, SH.NodeShape))

        # add properties
        order_property = 0
        for attrib, attrib_data in sub_cat_data.items():
            create_property(shacl, sub_cat_shape, cat_namespace, attrib_data, order_property)
            order_property = order_property + 1

        sub_cat_ns = cat_namespace[f'{sub_cat}']
        shacl.add((sub_cat_shape, SH.targetClass, sub_cat_ns)) 
        
    # add used data structs
    create_data_structure(shacl, cat_namespace)
    used_data_type_nodes.clear()

    # write shacle       
    file = output_path + shacl_name + '.ttl'
    with open(file, 'w') as f:
        f.write(shacl.serialize(format='turtle'))
        f.close()
        logger.info(f'write {shacl_name}')
        
# fix shacl ->  replace "sh:in_" with "sh:in"   
def fix_shacle(cat, output_path):
    shacl_name = f'{cat}_shacl'
    file_name = output_path + shacl_name + '.ttl'    
    with open(file_name, 'r') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        # check if line contain "sh:in_"
        if "sh:in_" in line:
            # replace "sh:in_" with "sh:in" , remove outer inverted commas , replace ' with "
            modified_line = line.replace('sh:in_', 'sh:in').replace('"', '')
            modified_line = modified_line.replace('\'', '"')
            lines[i] = modified_line

    with open(file_name, 'w') as file:
        file.writelines(lines)


def main():
    # parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='ontology and shacle files are generated from an excel table')
    parser.add_argument('-table', type=str,default='Metadata.xlsx', help='Path to Excel Table.')
    parser.add_argument('-out', '--out', type=str, default='ontologies/', help='Path to exported ontology and shacle files.')    
    parser.add_argument('-url', '--url', type=str, default='https://github.com/GAIA-X4PLC-AAD/map-and-scenario-data/tools/ontologie_creator/ontologies/', help='URL for the ontologies.')

    args = parser.parse_args()

    table_file = args.table
    if not os.path.isfile(table_file):
        logger.error(f'table file {table_file} not exists')
        exit(1)
    attributes = read_from_excel(table_file)

    #  write turtle files (ontologie and shacle)        
    if not os.path.exists(args.out):
        os.makedirs(args.out)     
  
    # for each category
    for cat, cat_data in attributes.items():
        # fill ontology
        create_onotology(cat, cat_data, args.out, args.url)

        # fill shacle
        create_shacl(cat, cat_data, args.out, args.url)

        #fix sh.in in shacle
        fix_shacle(cat, args.out)

if __name__ == '__main__':
    main()
