import xml.etree.ElementTree as ET
import argparse
import math
import logging

logger = logging.getLogger(__name__)

class Vec2:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Box:
    def __init__(self, x_min, y_min, x_max, y_max):
        self.x_min = x_min
        self.y_min = y_min   
        self.x_max = x_max
        self.y_max = y_max       

# parse the XML file and extract proj4_str, offset and coordinates
def parse_xml(file_path : str) ->tuple[str, Vec2, list]:
    tree = ET.parse(file_path)
    root = tree.getroot()

    georef = root.find('.//geoReference')
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

# calc end position from start pos, heading and length value
def calculate_end_position(start_pos : Vec2, heading: float, length: float) -> Vec2:
    end_x = start_pos.x + math.cos(heading) * length
    end_y = start_pos.y + math.sin(heading) * length
    return Vec2(end_x, end_y)

# init box with invalid values
def initialize_bounding_box():
    return Box(float('inf'), float('inf'), float('-inf'), float('-inf'))

# enhance box with new position
def update_bounding_box(bounding_box : Box, point: Vec2) -> Box:    
    bounding_box.x_min = min(bounding_box.x_min, point.x)
    bounding_box.x_max = max(bounding_box.x_max, point.x)
    bounding_box.y_min = min(bounding_box.y_min, point.y)
    bounding_box.y_max = max(bounding_box.y_max, point.y)
    return bounding_box

# calc box from line data
def calcBox(lines: list, offset: Vec2) -> Box:
    bounding_box = initialize_bounding_box()
    for line in lines:
        count = len(line) - 1
        for x, y, hdg, length in line:
            pos_abs = Vec2(x + offset.x, y + offset.y)
            bounding_box = update_bounding_box(bounding_box, pos_abs)
            if count == 0:
                end_pos = calculate_end_position(pos_abs, hdg, length)
                bounding_box = update_bounding_box(bounding_box, end_pos)
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