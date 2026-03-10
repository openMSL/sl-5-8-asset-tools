"""OpenDRIVE to GeoJSON converter.

Converts OpenDRIVE (.xodr) files into GeoJSON format, producing separate
FeatureCollections for reference lines, lanes, roads, lane sections,
objects, signals, road markings, and junctions.

This is a pure-Python re-implementation of the VCS opendriveconverter
(https://github.com/virtualcitySYSTEMS/opendriveconverter).
"""

from pathlib import Path

import argparse
import logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        prog="xodr_to_geojson_caller",
        description="Convert an OpenDRIVE (.xodr) file into GeoJSON files.",
    )
    parser.add_argument("filename", help="path to the OpenDRIVE (.xodr) input file")
    parser.add_argument("-out", required=True, help="output directory for GeoJSON files")
    parser.add_argument(
        "-path",
        required=False,
        default=None,
        help="(unused, kept for backward compatibility with pipeline)",
    )
    parser.add_argument(
        "-step",
        type=float,
        default=0.2,
        help="discretisation step size in meters (default: 0.2)",
    )
    args = parser.parse_args()

    xodr_file = Path(args.filename)
    if not xodr_file.is_absolute():
        xodr_file = xodr_file.resolve()
    if not xodr_file.exists():
        raise FileNotFoundError(f"OpenDRIVE file not found: {xodr_file}")

    output_dir = Path(args.out)
    if output_dir.suffix == ".geojson" or output_dir.suffix == ".json":
        # If -out points to a file, use its parent as output dir
        output_dir = output_dir.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Parsing %s", xodr_file)
    from xodr_to_geojson_caller.parser.xodr_parser import parse_opendrive

    odr = parse_opendrive(xodr_file)
    logger.info(
        "Parsed %d road(s), %d junction(s)",
        len(odr.roads),
        len(odr.junctions),
    )

    from xodr_to_geojson_caller.converter.geojson import convert_all

    convert_all(odr, output_dir=output_dir, step=args.step)
    logger.info("Done. Output written to %s", output_dir)


if __name__ == "__main__":
    main()
