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

# Threshold (bytes) above which the step size is auto-scaled to keep
# conversion time and output size reasonable.
_AUTO_STEP_FILE_SIZE_THRESHOLD = 20 * 1024 * 1024  # 20 MB
_AUTO_STEP_LARGE_FILE = 2.0  # meters


def main():
    from preview_3d.converter.geojson import CONVERTERS

    available = list(CONVERTERS.keys())

    parser = argparse.ArgumentParser(
        prog="preview_3d",
        description="Convert an OpenDRIVE (.xodr) file into GeoJSON files.",
    )
    parser.add_argument("filename", help="path to the OpenDRIVE (.xodr) input file")
    parser.add_argument(
        "-out", required=True, help="output directory for GeoJSON files"
    )
    parser.add_argument(
        "-path",
        required=False,
        default=None,
        help="(unused, kept for backward compatibility with pipeline)",
    )
    parser.add_argument(
        "-step",
        type=float,
        default=None,
        help="discretisation step size in meters (default: 0.2, auto-scaled for large files)",
    )
    parser.add_argument(
        "-converters",
        nargs="*",
        default=None,
        metavar="NAME",
        help=f"converters to run (default: all). Available: {', '.join(available)}",
    )
    parser.add_argument(
        "-compact",
        action="store_true",
        default=False,
        help="write compact JSON without indentation to reduce file size",
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

    # Auto-scale step size for large files to avoid excessive runtime / output.
    # Only auto-scale when the user did not explicitly provide -step.
    user_set_step = args.step is not None
    step = args.step if user_set_step else 0.2
    file_size = xodr_file.stat().st_size
    if (
        not user_set_step
        and file_size > _AUTO_STEP_FILE_SIZE_THRESHOLD
        and step < _AUTO_STEP_LARGE_FILE
    ):
        logger.info(
            "Large file detected (%.1f MB) — auto-scaling step from %.2f m to %.1f m",
            file_size / (1024 * 1024),
            step,
            _AUTO_STEP_LARGE_FILE,
        )
        step = _AUTO_STEP_LARGE_FILE

    logger.info("Parsing %s", xodr_file)
    from preview_3d.parser.xodr_parser import parse_opendrive

    odr = parse_opendrive(xodr_file)
    logger.info(
        "Parsed %d road(s), %d junction(s)",
        len(odr.roads),
        len(odr.junctions),
    )

    from preview_3d.converter.geojson import convert_all

    convert_all(
        odr,
        output_dir=output_dir,
        step=step,
        converters=args.converters,
        compact=args.compact,
    )
    logger.info("Done. Output written to %s", output_dir)


if __name__ == "__main__":
    main()
