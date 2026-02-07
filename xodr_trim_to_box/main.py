from pathlib import Path
from lxml import etree

import logging
import argparse
import math
import sys

logger = logging.getLogger(__name__)

# helper class for 2d bounding box
class Box2D:
    xMin : float
    yMin : float
    xMax : float    
    yMax : float

    def __init__(self, 
                 xMin: float = sys.float_info.max, 
                 yMin: float = sys.float_info.max, 
                 xMax: float = -sys.float_info.max,                  
                 yMax: float = -sys.float_info.max) -> None:
        super().__init__()
        self.xMin = xMin
        self.yMin = yMin
        self.xMax = xMax        
        self.yMax = yMax

    # check intersection to box2
    def intersection(self, box2) -> bool:
        x_overlap = max(0, min(self.xMax, box2.xMax) - max(self.xMin, box2.xMin))
        y_overlap = max(0, min(self.yMax, box2.yMax) - max(self.yMin, box2.yMin))
        
        if x_overlap > 0 and y_overlap > 0:
            return True
        else:
            return False
    # expands the box with box_expand
    def expandByBox(self, box_expand):
        if box_expand.xMin < self.xMin:
            self.xMin = box_expand.xMin
        if box_expand.xMax > self.xMax:
            self.xMax = box_expand.xMax
        if box_expand.yMin < self.yMin:
            self.yMin = box_expand.yMin
        if box_expand.yMax > self.yMax:
            self.yMax = box_expand.yMax       

    # expands the box with position
    def expandByPos(self, x, y):
        if x < self.xMin:
            self.xMin = x
        if x > self.xMax:
            self.xMax = x

        if y < self.yMin:
            self.yMin = y
        if y > self.yMax:
            self.yMax = y            
    
    # expands the box with seam
    def expandBySeam(self, seam):
        self.xMin = self.xMin - seam
        self.xMax = self.xMax + seam
        self.yMin = self.yMin - seam
        self.yMax = self.yMax + seam


# calc end position from start pos, heading and length value
def calculate_end_position(start_x, start_y, heading, length):
    end_x = start_x + math.cos(heading) * length
    end_y = start_y + math.sin(heading) * length

    return end_x, end_y


# calc box for line segment
def calculate_bounding_box(x, y, hdg, length):

    endPos = calculate_end_position(x, y, hdg, length)
    box = Box2D()
    box.expandByPos(x, y)
    box.expandByPos(endPos[0], endPos[1])
    box.expandBySeam(10)
    return box

# calc box for road element
def getRoadBounding(road):
    geometries = road.findall(".//geometry")
    boxRoad = Box2D()
    for geometry in geometries:
        x = float(geometry.attrib['x'])
        y = float(geometry.attrib['y'])
        hdg = float(geometry.attrib['hdg'])
        length = float(geometry.attrib['length'])
        boxGeom = calculate_bounding_box(x, y, hdg, length)
        boxRoad.expandByBox(boxGeom)
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
            boxRoad = getRoadBounding(road)
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