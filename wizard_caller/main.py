"""CLI entry point for the SHACL-driven SD Creation Wizard.

When enabled, parses SHACL shape constraints and interactively prompts
the user to fill in missing JSON-LD metadata fields.  When disabled,
simply copies the input JSON-LD to the output path unchanged.

Supports two backends (selected via ``-api-url``):

* **local** (default) — parse SHACL with rdflib (basic constraints)
* **api**   — delegate to the sd-creation-wizard-api for full SHACL
  support including ``sh:or``, ``sh:and``, ``sh:xone``
"""

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

from wizard_caller.shacl_wizard import run_wizard, run_wizard_api

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
    parser.add_argument(
        "-api-url",
        default=None,
        help=(
            "URL of the sd-creation-wizard-api (e.g. http://localhost:8080). "
            "Falls back to env var WIZARD_API_URL. "
            "If set, uses the API backend for full SHACL support (sh:or, etc.)"
        ),
    )
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

    api_url = args.api_url or os.environ.get("WIZARD_API_URL")

    if api_url:
        from wizard_caller.api_client import WizardAPIError, is_api_available

        if is_api_available(api_url):
            logger.info("Using Wizard API at %s", api_url)
            try:
                run_wizard_api(jsonld_path, shacl_path, output_path, api_url)
                return
            except WizardAPIError as exc:
                logger.warning("API call failed: %s — falling back to local mode", exc)
        else:
            logger.warning(
                "Wizard API at %s is not reachable — falling back to local mode",
                api_url,
            )

    run_wizard(jsonld_path, shacl_path, output_path)


if __name__ == "__main__":
    main()
