import argparse
import logging

from utils.geometry import Vec2D, Box2D
from utils.xodr import parse_planview

logger = logging.getLogger(__name__)


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
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="calculates the bounding box of the road data in the OpenDRIVE and outputs the lat/lon box as a print.",
    )
    parser.add_argument("filename", help="OpenDRIVE filename")
    args = parser.parse_args()

    xodr_file = args.filename
    if not xodr_file.exists():
        raise FileNotFoundError(f"{xodr_file} not found")

    # Parse the XML file and extract coordinates
    projection, offset, lines = parse_planview(xodr_file)

    if lines is None:
        raise ValueError(f"no line data found!")

    # calculate box from coordinates
    bounding_box = calcBox(lines, offset)

    # print box
    logger.info(
        f"box : {bounding_box.x_min}, {bounding_box.x_max} - {bounding_box.y_min}, {bounding_box.y_max}"
    )


if __name__ == "__main__":
    main()
