from pathlib import Path
from lxml import etree

import logging
import argparse
from utils.geometry import Vec2D, Box2D

logger = logging.getLogger(__name__)


# calc box for line segment
def calculate_bounding_box(pos : Vec2D, hdg, length):

    box = Box2D()
    box.expand_by_pos(pos)
    endPos = pos.end_position(hdg, length)
    box.expand_by_pos(endPos)
    box.expand_by_seam(10)
    return box

# calc box for road element
def get_road_bounding(road):
    geometries = road.findall(".//geometry")
    boxRoad = Box2D()
    for geometry in geometries:
        pos = Vec2D(float(geometry.attrib['x']), float(geometry.attrib['y']))
        hdg = float(geometry.attrib['hdg'])
        length = float(geometry.attrib['length'])
        boxGeom = calculate_bounding_box(pos, hdg, length)
        boxRoad.expand_by_box(boxGeom)
    return boxRoad  

# replace box data in xodr file
def reduceXODR(box, file_in, file_out):

    root = etree._Element()

    # read file and convert to tree structure    
    logger.info(f"read file {file_in.stem}")
    try:
        tree = etree.parse(file_in)
        root = tree.getroot()
    except etree.ParseError as err:
        logger.error(f'cant load {file_in.stem}: {err.msg}')
        return False
    
    junctions = {}
    roads = root.findall(".//road")
    for road in roads:
        junctionID = road.attrib["junction"]
        if junctionID == "-1": # only non junction road
            # get links
            linkIDs = []
            link = road.find("link")
            if link is not None:
                for child in link:
                    linkIDs.append(child.attrib["elementId"])
            
            # check inside / outside
            boxRoad = get_road_bounding(road)
            container = "inside"
            if boxRoad.intersection(box) == False:
                container = "outside"
            
            # register
            for id in linkIDs:
                if id not in junctions:
                    junctions[id] = {"inside": [], "outside": [], "internal": []}
                junctions[id][container].append(road)
        else: # register internal road
            if junctionID not in junctions:
                junctions[junctionID] = {"inside": [], "outside": [], "internal": []}
            junctions[junctionID]["internal"].append(road)

    # loop junctions
    for key, value in junctions.items():
        if not value["inside"]: # all incomming road of this junctions are outside -> remove junction            
            # get junction
            for junction in root.findall("junction"):
                if junction.get("id") == key:
                    root.remove(junction) # remove junction
                    for internal_road in value["internal"]: # remove internal roads
                        root.remove(internal_road)
                    for road in value["outside"]:
                        link = road.find("link")
                        if link is not None:
                            for child in link:
                                if child.attrib["elementId"] == key:
                                    link.remove(child)
                                    break
                            
                            if not len(link): # is empty
                                root.remove(road)

    tree.write(file_out)


def main():
    # parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='removes the streets and intersections that are not in the specified bounding box and writes them out with *_reduce.xodr.')   
    parser.add_argument('filename', help='OpenDRIVE filename')
    parser.add_argument("--bbox", type=float, nargs=4, required=True,
                        metavar=("x_min", "y_min", "x_max", "y_max"),
                        help="bounding box as 4 values: x_min, y_min, x_max, y_max")
    args = parser.parse_args()
    
    # get box
    x_min, y_min, x_max, y_max = args.bbox
    box = Box2D(x_min, y_min, x_max, y_max)

    # get file
    file_in = Path(args.filename)
    file_out = file_in.with_stem(file_in.stem + "_reduced")

    # reduce
    reduceXODR(box, file_in, file_out)
    
if __name__ == '__main__':
    main()    
