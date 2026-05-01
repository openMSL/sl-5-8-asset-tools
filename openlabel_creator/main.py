"""OpenLABEL creator — pipeline entry point.

Discovers OpenLABEL JSON companion files for scenario assets and
transforms them into JSON-LD conforming to openlabel:TagShape.

Usage as CLI:
    python -m openlabel_creator --input <openlabel.json> --output <openlabel.jsonld>

Usage from pipeline:
    from openlabel_creator.main import create_openlabel_jsonld
    result = create_openlabel_jsonld(input_json, output_path)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from utils.ids import create_uuid

from .transformer import load_openlabel_json, transform

logger = logging.getLogger(__name__)

DID_PREFIX = "did:web:registry.gaia-x.eu:Tag"


def create_openlabel_jsonld(
    input_file: Path,
    output_file: Path,
    tag_id: str | None = None,
) -> bool:
    """Transform an OpenLABEL JSON file into JSON-LD.

    Args:
        input_file: Path to the source OpenLABEL JSON.
        output_file: Path where the JSON-LD output will be written.
        tag_id: Optional @id for the output. Auto-generated if not provided.

    Returns:
        True on success, False on failure.
    """
    openlabel_data = load_openlabel_json(input_file)
    if openlabel_data is None:
        logger.error("Not a valid OpenLABEL file: %s", input_file)
        return False

    if tag_id is None:
        tag_id = f"{DID_PREFIX}:{create_uuid()}"

    try:
        jsonld = transform(openlabel_data, tag_id)
    except ValueError as e:
        logger.error("Transform failed for %s: %s", input_file, e)
        return False

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(jsonld, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info("Created OpenLABEL JSON-LD: %s", output_file)
    return True


def inject_into_scenario(openlabel_file: Path, scenario_file: Path) -> bool:
    """Inject openlabel tag into scenario JSON-LD's hasContent field.

    Converts scenario:hasContent from a single object to an array
    containing both the original content and the openlabel tag.
    """
    if not openlabel_file.exists() or not scenario_file.exists():
        return False

    with open(openlabel_file, "r", encoding="utf-8") as f:
        openlabel_data = json.load(f)

    with open(scenario_file, "r", encoding="utf-8") as f:
        scenario_data = json.load(f)

    domain_spec = scenario_data.get("scenario:hasDomainSpecification", {})
    current_content = domain_spec.get("scenario:hasContent")

    if current_content is None:
        domain_spec["scenario:hasContent"] = openlabel_data
    elif isinstance(current_content, list):
        current_content.append(openlabel_data)
    else:
        domain_spec["scenario:hasContent"] = [current_content, openlabel_data]

    with open(scenario_file, "w", encoding="utf-8") as f:
        json.dump(scenario_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info("Injected OpenLABEL tag into %s", scenario_file)
    return True


def find_companion_openlabel(scenario_file: Path) -> Path | None:
    """Find the OpenLABEL JSON companion for a scenario file.

    Looks for <stem>.json in the same directory as the .xosc file.
    """
    candidate = scenario_file.with_suffix(".json")
    if candidate.exists():
        # Verify it's actually OpenLABEL (not an input_manifest or other JSON)
        data = load_openlabel_json(candidate)
        if data is not None:
            return candidate
    return None


def main() -> int:
    """CLI entry point.

    Supports two calling conventions:
    1. Pipeline mode: positional .xosc file, auto-discovers companion .json
    2. Direct mode: --input <openlabel.json> explicitly
    """
    parser = argparse.ArgumentParser(description="Transform OpenLABEL JSON to JSON-LD")
    parser.add_argument(
        "filename",
        nargs="?",
        type=Path,
        help="Scenario file (.xosc) — companion .json is auto-discovered",
    )
    parser.add_argument(
        "--input", "-i", type=Path, help="Direct path to OpenLABEL JSON file"
    )
    parser.add_argument(
        "-out", "--output", "-o", required=True, type=Path, help="Output JSON-LD file"
    )
    parser.add_argument(
        "-inject",
        type=Path,
        help="Scenario JSON-LD file to inject the openlabel tag into",
    )
    parser.add_argument("--id", type=str, default=None, help="Override @id for output")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Determine input file
    input_file: Path | None = None
    if args.input:
        input_file = args.input
    elif args.filename:
        # Pipeline mode: find companion OpenLABEL JSON for .xosc
        companion = find_companion_openlabel(args.filename)
        if companion:
            input_file = companion
        else:
            logger.info("No OpenLABEL companion found for %s — skipping", args.filename)
            return 0
    else:
        logger.error("Provide either a positional filename or --input")
        return 1

    success = create_openlabel_jsonld(input_file, args.output, tag_id=args.id)
    if not success:
        return 1

    # Inject into scenario JSON-LD if requested
    if args.inject:
        inject_into_scenario(args.output, args.inject)

    return 0


if __name__ == "__main__":
    sys.exit(main())
