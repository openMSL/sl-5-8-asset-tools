import xml.etree.ElementTree as ET
import argparse
import math
import logging

from utils.geometry import Vec2D, Box2D

logger = logging.getLogger(__name__)

# parse the XML file and extract proj4_str, offset and coordinates
def parse_xml(file_path : str) ->tuple[str, Vec2D, list]:
    tree = ET.parse(file_path)
    root = tree.getroot()

    georef = root.find('.//geoReference')
    if georef is not None:
        proj4_str = georef.text.strip()
    
    offset_node = root.find('.//offset')
    offset = Vec2D(0,0)
    if offset_node is not None:
        offset = Vec2D(float(offset_node.attrib['x']), float(offset_node.attrib['y']))

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

# calc box from line data
def calcBox(lines: list, offset: Vec2D) -> Box2D:
    bounding_box = Box2D()
    for line in lines:
        count = len(line) - 1
        for x, y, hdg, length in line:
            pos_abs = Vec2D(x + offset.x, y + offset.y)
            bounding_box = bounding_box.expand_by_pos(pos_abs)
            if count == 0:
                end_pos = pos_abs.end_position(hdg, length)
                bounding_box = bounding_box.expand_by_pos(end_pos)
            count = count - 1
    return bounding_box


def main():
    #  parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='calculates the bounding box of the road data in the OpenDRIVE and outputs the lat/lon box as a print.')   
    parser.add_argument('filename', help='OpenDRIVE filename')
    args = parser.parse_args()

    xodr_file = args.filename
    if not xodr_file.exists():        
        logger.error(f'{xodr_file} not found')
        exit(1)
    
    # Parse the XML file and extract coordinates
    in_proj, offset, lines = parse_xml(xodr_file)
    
    if in_proj is None or lines is None:
        logger.error(f"no projection found!")    
        exit(1)

    # calculate box from coordinates
    bounding_box = calcBox(lines, offset)
    
    # print box
    logger.info(f"box : {bounding_box.x_min}, {bounding_box.x_max} - {bounding_box.y_min}, {bounding_box.y_max}")


if __name__ == '__main__':
    main()