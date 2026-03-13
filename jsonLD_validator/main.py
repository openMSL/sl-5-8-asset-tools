from pathlib import Path

import argparse
import logging
import sys

from utils.log_config import is_debug_logging, setup_logging
from utils.subprocess import CommandError, run_command

setup_logging(logging.DEBUG if is_debug_logging() else logging.INFO)
logger = logging.getLogger(__name__)
SL58_ROOT = Path(__file__).resolve().parent.parent
OMB_ARTIFACTS = Path("submodules") / "ontology-management-base" / "artifacts"


def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Deprecated compatibility wrapper for the ontology-management-base "
            "validation suite."
        ),
    )
    parser.add_argument("filename", type=str, help="json LD filename")
    parser.add_argument(
        "-closed",
        action="store_true",
        help="deprecated legacy option; no longer supported",
    )
    args = parser.parse_args()

    json_LD_file = Path(args.filename)
    if args.closed:
        raise SystemExit(
            "The deprecated `-closed` option is no longer supported. "
            "Use `python -m src.tools.validators.validation_suite` directly "
            "if you need custom validation behavior."
        )

    try:
        run_command(
            [
                sys.executable,
                "-m",
                "src.tools.validators.validation_suite",
                "--run",
                "check-data-conformance",
                "--data-paths",
                str(json_LD_file.resolve()),
                "--artifacts",
                str(OMB_ARTIFACTS),
            ],
            name="jsonLD validator from ontology-management-base",
            cwd=SL58_ROOT,
        )
    except CommandError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
