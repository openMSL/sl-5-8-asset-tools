from pyproj import CRS, Transformer
from pathlib import Path

import xml.etree.ElementTree as ET
import simplekml
import argparse
import json
import math
import logging

logger = logging.getLogger(__name__)

class Vec2:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class BoundingBox:
    def __init__(self, xMin, yMin, xMax, yMax):
        self.xMin = xMin
        self.yMin = yMin
        self.xMax = xMax
        self.yMax = yMax


# function to parse the XML file and extract coordinates
def parse_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    georef = root.find('.//geoReference')
    proj4_str = None
    if georef is not None:
        proj4_str = georef.text.strip()
    
    offset_node = root.find('.//offset')
    offset = Vec2(0,0)
    if offset_node is not None:
        offset = Vec2(float(offset_node.attrib['x']), float(offset_node.attrib['y']))

    lines = []
    for line in root.findall('.//planView'):
        coordinates = []
        for point in line.findall('.//geometry'):
            x = float(point.attrib['x'])
            y = float(point.attrib['y'])
            hdg = float(point.attrib['hdg'])
            length = float(point.attrib['length'])
            coordinates.append((x, y, hdg, length))
        lines.append(coordinates)
    return proj4_str, offset, lines


def calculate_end_position(start_pos : Vec2, heading, length):
    end_x = start_pos.x + math.cos(heading) * length
    end_y = start_pos.y + math.sin(heading) * length
    return Vec2(end_x, end_y)


# function to reproject the coordinates
def reproject(lines, offset, transformer):
    transformed_lines = []
    for line in lines:
        transformed_coords = []
        count = len(line) - 1
        for x, y, hdg, length in line:
            pos_abs = Vec2(x + offset.x, y + offset.y)
            lon, lat = transformer.transform(pos_abs.x, pos_abs.y)
            transformed_coords.append((lon, lat))
            if count == 0:
                end_pos = calculate_end_position(pos_abs, hdg, length)
                lon, lat = transformer.transform(end_pos.x, end_pos.y)
                transformed_coords.append((lon, lat))
            count = count - 1
        transformed_lines.append(transformed_coords)
    return transformed_lines


# Function to create and write KML elements
def create_kml(elements: list, output_file: Path, isPolygon: bool):
    kml = simplekml.Kml()
    for element in elements:
        if isPolygon:
            datastring = kml.newpolygon(name="Box")
            datastring.outerboundaryis = element
        else:
            datastring = kml.newlinestring(name="Line")
            datastring.coords = element

    kml.save(output_file)


# Function to create and write a GeoJson elements
def create_geojson(elements: list, output_file: Path, isPolygon: bool):
    features = []
    for element in elements:
        if isPolygon:
            feature = {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [(lon, lat) for lon, lat in element]
            },
            "properties": {}
        }
        else:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [(lon, lat) for lon, lat in element]
                },
                "properties": {}
            }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # write GeoJSON
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)


# function to create bounding box from point list
def create_bounding_box(elements: list) -> BoundingBox :        
    x_coords = []
    y_coords = []
    for element in elements:
        for coord in element:
            x_coords.append(coord[0])
            y_coords.append(coord[1])

    box = BoundingBox
    box.xMin = min(x_coords)
    box.yMin = min(y_coords)
    box.xMax = max(x_coords)
    box.yMax = max(y_coords)

    return box


def main():
    parser = argparse.ArgumentParser(prog='main.py', description='creates routing files (as geojson or kml) on OpenDRIVE files.')   
    parser.add_argument('filename', help='filename of OpenDRIVE file.')
    parser.add_argument('-out', type=str,help='filename of exported geo file.')
    parser.add_argument('-box', type=str,help='filename for boundingbox geo file.')
    args = parser.parse_args()

    xodr_file = Path(args.filename)
    if not xodr_file.exists():
        logger.error(f'xodr file {xodr_file} not exists')
        exit(1)

    output_file = Path(args.out)
    if not output_file.parent.exists():
        output_file.parent.mkdir()

    extension = output_file.suffix

    # Parse the XML file and extract coordinates
    in_proj, offset, lines = parse_xml(xodr_file)
    if in_proj is None or lines is None:
        logger.error(f"no projection found!")    
        exit(0)

    # PROJ.4 projections
    #web_mecator = CRS.from_epsg(3857)
    web_mecator = CRS.from_proj4(in_proj)
    wgs84 = CRS.from_epsg(4326)
    transformer_proj_to_wgs84 = Transformer.from_crs(web_mecator, wgs84, always_xy=True)

    # Reproject the coordinates
    transformed_lines= reproject(lines, offset, transformer_proj_to_wgs84)

    output_file_box = args.box
    if output_file_box:
        box = create_bounding_box(transformed_lines)
        coordinates = []
        coordinates.append((box.xMin,box.yMin))
        coordinates.append((box.xMax,box.yMin))
        coordinates.append((box.xMax,box.yMax))
        coordinates.append((box.xMin,box.yMax))
        coordinates.append((box.xMin,box.yMin))
        boxes = []
        boxes.append(coordinates)
        if extension == "geojson":
            create_geojson(boxes, output_file_box, True)
        else:
            create_kml(boxes, output_file_box, True)

    # Create the KML line
    if extension == "geojson":
        create_geojson(transformed_lines, output_file, False)
    else:
        create_kml(transformed_lines, output_file, False)

    logger.info(f"KML file created: {output_file}")

if __name__ == '__main__':
    main()