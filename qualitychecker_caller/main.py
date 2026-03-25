import argparse
import logging
import re
import sys
import tempfile
from pathlib import Path

from lxml import etree

from utils.log_config import is_debug_logging, setup_logging
from utils.subprocess import CommandError, run_command

setup_logging(logging.DEBUG if is_debug_logging() else logging.INFO)
logger = logging.getLogger(__name__)


def _generate_text_report(xqar_file: Path, report_file: Path) -> None:
    """Convert an XQAR result file to a human-readable text report.

    Uses the Python qc_baselib.Result API (from asam-qc-baselib) to generate
    human-readable text reports.  See asam-ev/qc-framework#115.
    """
    from qc_baselib import Result

    result = Result()
    result.load_from_file(str(xqar_file))

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 102 + "\n")
        f.write("Text Report Module - Pooled Results\n")
        f.write("=" * 102 + "\n")

        for bundle in result.get_checker_bundle_results():
            f.write(f"\n    CheckerBundle: {bundle.name}\n")
            f.write(f"    Build date: {bundle.build_date}\n")
            f.write(f"    Build version: {bundle.version}\n")
            f.write(f"    Description: {bundle.description}\n")
            f.write(f"    Summary: {bundle.summary}\n")
            if bundle.params:
                f.write("    Parameters:\n")
                for param in bundle.params:
                    f.write(f"    {param.name} = {param.value}\n")

            f.write("    " + "=" * 20 + "\n")
            f.write("    Checkers:\n")
            f.write("    " + "=" * 20 + "\n")

            for checker in bundle.checkers:
                f.write(f"\n        Checker:        {checker.checker_id}\n")
                f.write(f"        Description:    {checker.description}\n")
                f.write(f"        Status:    {checker.status or ''}\n")
                f.write(f"        Summary:        {checker.summary}\n")

                f.write("        " + "=" * 20 + "\n")
                f.write("        Issues:\n")
                f.write("        " + "=" * 20 + "\n")
                for issue in checker.issues:
                    f.write(f"            Issue:              {issue.issue_id}\n")
                    f.write(f"            Description:        {issue.description}\n")
                    f.write(f"            Level:              {issue.level}\n")

                if checker.addressed_rule:
                    f.write("        " + "=" * 20 + "\n")
                    f.write("        Addressed rules:\n")
                    f.write("        " + "=" * 20 + "\n")
                    for rule in checker.addressed_rule:
                        f.write(f"            Addressed Rule:     {rule.rule_uid}\n")

                if checker.metadata:
                    f.write("        " + "=" * 20 + "\n")
                    f.write("        Metadata:\n")
                    f.write("        " + "=" * 20 + "\n")
                    for meta in checker.metadata:
                        f.write(f"            Metadata:        {meta.key}\n")
                        f.write(f"            Value:        {meta.value}\n")
                        f.write(f"            Description:        {meta.description}\n")


# update config file and replace input, output file and bundle name
def update_config_file(
    template_file: Path,
    checkerbundle_name: str,
    input_file: Path,
    result_file: Path,
    config_file: Path,
) -> Path:
    # Parse the XML file
    logger.debug("Using template %s", template_file)
    tree = etree.parse(template_file)
    root = tree.getroot()

    # Find the Param element 'application' in 'CheckerBundle' and update its value attribute
    for param in root.xpath("//*[local-name()='CheckerBundle']"):
        param.set("application", checkerbundle_name)

    # Find the Param element 'InputFile' and update its value attribute
    for param in root.findall(".//Param[@name='InputFile']"):
        param.set("value", input_file.as_posix())

    # Find the Param element 'resultFile' and update its value attribute
    for param in root.findall(".//Param[@name='resultFile']"):
        param.set("value", result_file.as_posix())

    # Write the updated XML to the output file
    tree.write(config_file, encoding="utf-8", pretty_print=True, xml_declaration=True)
    logger.debug("Created configuration file %s", config_file)

    return config_file


# create config file
def create_config_file(
    config_file_name: Path,
    checkerbundle_name: str,
    input_file: Path,
    result_file: Path,
    config_file: Path,
) -> Path:
    script_folder = Path(__file__).parent
    templates_folder = script_folder / "templates"
    template_file = templates_folder / config_file_name

    if not template_file.exists():
        raise FileNotFoundError(f"template file not exist {template_file}")

    return update_config_file(
        template_file,
        checkerbundle_name,
        input_file,
        result_file,
        config_file,
    )


def get_internal_checker_errors(result_file: Path) -> list[str]:
    """Return QC checker errors recorded in the generated XQAR result."""

    if not result_file.exists():
        raise FileNotFoundError(f"quality checker result file not found: {result_file}")

    tree = etree.parse(str(result_file))
    bundle = tree.find(".//CheckerBundle")

    errors = []
    for checker in tree.findall(".//Checker[@status='error']"):
        checker_id = checker.get("checkerId", "unknown-checker")
        summary = checker.get("summary", "internal checker error")
        errors.append(f"{checker_id}: {summary}")

    if errors:
        return errors

    if bundle is not None:
        summary = bundle.get("summary", "")
        match = re.search(r"(\d+)\s+checker\(s\)\s+have internal error", summary)
        if match and int(match.group(1)) > 0:
            return [summary]

    return []


def get_checker_bundle_summary(result_file: Path) -> str | None:
    if not result_file.exists():
        return None

    tree = etree.parse(str(result_file))
    bundle = tree.find(".//CheckerBundle")
    return bundle.get("summary", "").strip() if bundle is not None else None


def fail_on_internal_checker_errors(
    app_name: str, result_file: Path, text_report: Path | None = None
) -> None:
    """Stop the pipeline when the QC tool completed with internal checker errors."""

    errors = get_internal_checker_errors(result_file)
    if not errors:
        return

    details = "; ".join(errors[:3])
    if len(errors) > 3:
        details += f"; ... ({len(errors)} total)"

    report_hint = f" See {text_report} for details." if text_report else ""
    raise SystemExit(
        f"{app_name} reported internal checker errors: {details}{report_hint}"
    )


def main():
    # parse arguments
    parser = argparse.ArgumentParser(
        prog="main.py", description="setup and run quality checker"
    )
    parser.add_argument("filename", type=str, help="ASAM OpenX file, e.g. xodr, xosc")
    parser.add_argument("-out", type=str, required=True, help="output result file")
    parser.add_argument(
        "-config",
        type=str,
        required=True,
        help="name of config file in subfolder templates",
    )
    parser.add_argument(
        "-app", type=str, required=True, help="name of quality checker application"
    )
    parser.add_argument(
        "-checkerbundle", type=str, required=True, help="name of checkerbundle"
    )
    args = parser.parse_args()

    input_file = Path(args.filename).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"input file {input_file} not exists")

    # create config file from templates with input_file replacement
    output_file = Path(args.out).resolve()
    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True, exist_ok=True)

    config_file_name = Path(args.config)
    if not config_file_name:
        raise ValueError(f"missing config file {config_file_name}")

    bundle_name = args.checkerbundle
    if not bundle_name:
        raise ValueError(f"bundle name not valid {bundle_name}")

    with tempfile.NamedTemporaryFile(
        prefix=f"{output_file.stem}_",
        suffix="_qc_config.xml",
        dir=output_file.parent,
        delete=False,
    ) as temp_config:
        config_file = Path(temp_config.name)

    app_name = args.app
    if not app_name:
        raise ValueError(f"app name not valid {app_name}")

    try:
        config_file = create_config_file(
            config_file_name, bundle_name, input_file, output_file, config_file
        )

        script_call = [app_name, "-c", config_file.as_posix()]
        run_command(cmd=script_call, name=app_name)

        text_report_path = Path(f"{output_file.with_suffix('')}_QCReport.txt")
        _generate_text_report(output_file, text_report_path)

        fail_on_internal_checker_errors(app_name, output_file, text_report_path)
        summary = get_checker_bundle_summary(output_file)
        if summary:
            logger.info("%s: %s", app_name, summary)
    except CommandError as exc:
        if is_debug_logging():
            logger.debug("Full error details:", exc_info=exc)
        raise SystemExit(str(exc)) from None
    finally:
        if config_file.exists():
            config_file.unlink()


if __name__ == "__main__":
    main()
