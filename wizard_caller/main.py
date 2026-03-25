"""CLI entry point for the SHACL-driven SD Creation Wizard.

When enabled, parses SHACL shape constraints and interactively prompts
the user to fill in missing JSON-LD metadata fields.  When disabled,
simply copies the input JSON-LD to the output path unchanged.
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from wizard_caller.shacl_wizard import run_wizard

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        prog="wizard_caller",
        description="CLI wizard for enriching JSON-LD with SHACL-guided prompts",
    )
    parser.add_argument("filename", help="Input JSON-LD file")
    parser.add_argument("-shacl", required=True, help="Combined SHACL Turtle file")
    parser.add_argument(
        "-enable",
        required=True,
        help="'true' to run interactive wizard, 'false' to copy unchanged",
    )
    parser.add_argument("-out", required=True, help="Output JSON-LD file path")
    args = parser.parse_args()

    jsonld_path = Path(args.filename)
    shacl_path = Path(args.shacl)
    output_path = Path(args.out)

    if not jsonld_path.exists():
        sys.exit(f"Error: JSON-LD file not found: {jsonld_path}")
    if not shacl_path.exists():
        sys.exit(f"Error: SHACL file not found: {shacl_path}")

    if args.enable.strip().lower() != "true":
        shutil.copy2(jsonld_path, output_path)
        logger.info("Wizard disabled — copied %s → %s", jsonld_path, output_path)
        return

    run_wizard(jsonld_path, shacl_path, output_path)


if __name__ == "__main__":
    main()
