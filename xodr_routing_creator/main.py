from pyproj import CRS, Transformer
from pathlib import Path
from utils.xodr import parse_planview
from utils.json import write_json

import xml.etree.ElementTree as ET
import simplekml
import argparse
import logging

from utils.geometry import Vec2D, Box2D

logger = logging.getLogger(__name__)

# transform coordiante with or without transformer
def transform_coord(pos_abs : Vec2D, transformer : Transformer) -> tuple[float, float]:
    if transformer is not None:
        lon, lat = transformer.transform(pos_abs.x, pos_abs.y)
    else :
        lon = pos_abs.x
        lat = pos_abs.y
    return lon, lat

# reproject the coordinates
def reproject(lines : list, offset : Vec2D, transformer : Transformer) -> list : 
    transformed_lines = []
    for line in lines:
        transformed_coords = []
        count = len(line) - 1
        for x, y, hdg, length in line:
            pos_abs = Vec2D(x + offset.x, y + offset.y)
            lon, lat = transform_coord(pos_abs, transformer)
            transformed_coords.append((lon, lat))
            if count == 0:
                end_pos = pos_abs.end_position(hdg, length)
                lon, lat = transform_coord(end_pos, transformer)
                transformed_coords.append((lon, lat))
            count = count - 1
        transformed_lines.append(transformed_coords)
    return transformed_lines


# create and write data as KML elements
def create_kml(elements: list, output_file: Path, isPolygon: bool):
    kml = simplekml.Kml()
    for element in elements:
        if isPolygon:
            datastring = kml.newpolygon(name="Box")
            datastring.outerboundaryis = element
        else:
            datastring = kml.newlinestring(name="Line")
            datastring.coords = element

    # write KML
    kml.save(output_file)


# create and write data as GeoJson elements
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
    write_json(output_file, geojson, indentValue=2)


# create bounding box from point list
def create_bounding_box(elements: list) -> Box2D:
    # Create bounding box from nested list of coordinates.
    coords = []
    for element in elements:
        for coord in element:
            coords.append((coord[0], coord[1]))
    return Box2D.from_points(coords)


def main():
    parser = argparse.ArgumentParser(prog='main.py', description='creates routing files (as geojson or kml) on OpenDRIVE files.')   
    parser.add_argument('filename', help='filename of OpenDRIVE file.')
    parser.add_argument('-out', type=str,help='filename of exported geo file.')
    parser.add_argument('-box', type=str,help='filename for boundingbox geo file.')
    args = parser.parse_args()

    xodr_file = Path(args.filename)
    if not xodr_file.exists():
        raise FileNotFoundError(f'xodr file {xodr_file} not exists')

    output_file = Path(args.out)
    if not output_file.parent.exists():
        output_file.parent.mkdir()

    extension = output_file.suffix

    # Parse the XML file and extract coordinates
    projection, offset, lines = parse_planview(xodr_file)
    if lines is None:
        raise ValueError(f"no line data found!")    

    if projection is not None:
        # create projection transform
        web_mecator = CRS.from_proj4(projection)
        wgs84 = CRS.from_epsg(4326)
        transformer_proj_to_wgs84 = Transformer.from_crs(web_mecator, wgs84, always_xy=True)

        # Reproject the coordinates
        transformed_lines = reproject(lines, offset, transformer_proj_to_wgs84)
    else :
        transformed_lines = reproject(lines, offset, None)

    # crate and write bounding box
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

    # write line data 
    if extension == "geojson":
        create_geojson(transformed_lines, output_file, False)
    else:
        create_kml(transformed_lines, output_file, False)

    logger.info(f"KML file created: {output_file}")

if __name__ == '__main__':
    main()