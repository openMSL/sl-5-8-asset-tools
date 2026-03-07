from pathlib import Path
from lxml import etree
from utils.subprocess import run_command

import argparse
import logging

DEBUG = False

logger = logging.getLogger(__name__)

ASAM_ODR_VERSION_URL: str = "http://www.asam.de/ODR/16/"


def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Calls the java tool from VCS https://github.com/virtualcitySYSTEMS/opendriveconverter to convert an OpenDRIVE file into a geojson.",
    )
    parser.add_argument("filename", help="filename of OpenDRIVE file")
    parser.add_argument("-out", required=True, help="geojson file")
    parser.add_argument(
        "-path",
        required=True,
        help="path to the temp folder for a temporary opendrive with customized header.",
    )
    args = parser.parse_args()

    xodr_file = Path(args.filename)
    if not xodr_file.is_absolute():
        xodr_file = xodr_file.resolve()
    if not xodr_file.exists():
        raise FileNotFoundError(f"json file {xodr_file} not exists")

    filename_out = Path(args.out)
    temp_path = Path(args.path)

    # fix header
    tree = etree.parse(xodr_file)
    root = tree.getroot()
    root.set("xmlns", ASAM_ODR_VERSION_URL)

    # write temp file
    new_temp_file = temp_path / "geojson"
    new_temp_file.mkdir(parents=True, exist_ok=True)
    new_temp_file = new_temp_file / xodr_file.name
    with open(new_temp_file, "wb") as f:
        tree.write(f, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    # call java script
    script_call = []
    script_call.append("java")
    script_call.append("-jar")
    if DEBUG:
        script_call.append(
            "E:/Data/Customer/GaiaX/GIT/provider-tools/asset_extraction/vcs-odr-converter-1.0.0.jar"
        )
    else:
        script_call.append("/app/java/vcs-odr-converter-1.0.0.jar")

    script_call.append(new_temp_file.as_posix())
    script_call.append(filename_out.parent.as_posix())

    # run
    run_command(cmd=script_call, name="vcs-odr-converter")


if __name__ == "__main__":
    main()
