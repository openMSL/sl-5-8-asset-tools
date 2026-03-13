from pathlib import Path
from utils.rdf import load_jsonld_file, get_shacl_from_json_graph

import argparse
import logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        prog="main.py", description="combine shalce file for jsonLD to one file"
    )
    parser.add_argument("filename", type=str, help="json LD filename")
    parser.add_argument(
        "-out", type=str, required=True, help="output path for combined shacl file"
    )
    args = parser.parse_args()

    # load json
    json_LD_file = Path(args.filename)
    data_graph = load_jsonld_file(json_LD_file)

    # load shacls
    shacl_graph = get_shacl_from_json_graph(data_graph)

    output_path = Path(args.out)
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    file = output_path / Path(json_LD_file.stem + ".ttl")
    with open(file, "w", encoding="utf-8") as f:
        f.write(shacl_graph.serialize(format="turtle"))
        f.close()
        logger.info(f"write {file}")


if __name__ == "__main__":
    main()
