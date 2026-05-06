"""CLI entry point for the SHACL-driven SD Creation Wizard.

When enabled, opens the browser-based wizard UI pre-filled with
auto-extracted metadata. The user enriches the form and clicks Export.
The pipeline pauses until the user completes the wizard.

When disabled, simply copies the input JSON-LD to the output path unchanged.

Supports two backends (selected via ``-api-url``):

* **browser** (default when API available) — opens wizard UI, waits for export
* **local** (fallback) — CLI-based SHACL wizard with rdflib
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
            "URL of the sd-creation-wizard API (e.g. http://localhost:3007). "
            "Falls back to env var WIZARD_API_URL. "
            "If set, uses the browser-based wizard for interactive editing."
        ),
    )
    parser.add_argument(
        "-frontend-url",
        default=None,
        help=(
            "URL of the wizard frontend (e.g. http://localhost:4200). "
            "Falls back to env var WIZARD_FRONTEND_URL."
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

    # Environment variable WIZARD_ENABLED=true overrides the config's -enable flag.
    # This allows: WIZARD=true make generate opendrive
    env_enabled = os.environ.get("WIZARD_ENABLED", "").strip().lower() == "true"
    config_enabled = args.enable.strip().lower() == "true"

    if not (config_enabled or env_enabled):
        shutil.copy2(jsonld_path, output_path)
        logger.info("Wizard disabled — copied %s → %s", jsonld_path, output_path)
        return

    api_url = (
        args.api_url or os.environ.get("WIZARD_API_URL") or "http://localhost:3007"
    )
    frontend_url = args.frontend_url or os.environ.get("WIZARD_FRONTEND_URL")

    from wizard_caller.api_client import (
        WizardAPIError,
        ensure_wizard_running,
        open_wizard_browser,
    )

    resolved_url = ensure_wizard_running(api_url)
    if resolved_url:
        logger.info("Wizard API ready at %s — opening browser wizard", resolved_url)
        try:
            success = open_wizard_browser(
                api_url=resolved_url,
                frontend_url=frontend_url,
                shacl_path=shacl_path,
                jsonld_path=jsonld_path,
                output_path=output_path,
            )
            if success:
                logger.info("Wizard export complete → %s", output_path)
                return
            else:
                logger.warning("Wizard timed out — falling back to local mode")
        except WizardAPIError as exc:
            logger.warning(
                "Browser wizard failed: %s — falling back to local mode", exc
            )
    else:
        logger.warning("Could not start wizard — falling back to local CLI mode")

    run_wizard(jsonld_path, shacl_path, output_path)


if __name__ == "__main__":
    main()
