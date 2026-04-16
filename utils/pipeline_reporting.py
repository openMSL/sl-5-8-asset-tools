from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import logging
import os
import re
import xml.etree.ElementTree as ET

from utils.log_config import extract_warning_lines, normalize_output_line
from utils.subprocess import CommandError, CommandResult

logger = logging.getLogger(__name__)


STAGE_LABELS = {
    "config_meta_data_extractor.json": "Extract metadata",
    "config_extractor_json_syntax_validator_omb.json": "Check extracted metadata JSON syntax",
    "config_asset_jsonLD_creator.json": "Create extracted metadata JSON-LD",
    "config_3dmodel_jsonLD_creator.json": "Create 3D model JSON-LD",
    "config_shacl_combiner.json": "Build SHACL bundle",
    "config_wizard_caller.json": "Populate metadata",
    "config_jsonLD_validator_omb.json": "Validate metadata",
    "config_quality_checker_asam_xodr.json": "Run ASAM OpenDRIVE checks",
    "config_quality_checker_asam_xosc.json": "Run ASAM OpenSCENARIO checks",
    "config_quality_checker_openmsl_xodr.json": "Run OpenMSL OpenDRIVE checks",
    "config_xodr_routing_creator.json": "Generate routing GeoJSON",
    "config_vcs_odr-converter.json": "Generate detailed preview GeoJSON",
    "config_asset_reducer.json": "Create reduced simulation asset",
    "config_structure_creator.json": "Build asset structure",
    "config_structure_json_syntax_validator_omb.json": "Check structure JSON syntax",
    "config_structure_jsonLD_creator.json": "Create final manifest JSON-LD",
    "config_structure_jsonLD_validator_omb.json": "Validate final manifest",
}


@dataclass
class StageSummary:
    status: str = "ok"
    message: str = ""
    details: list[str] = field(default_factory=list)


class PipelineReporter:
    def __init__(
        self,
        *,
        pipeline_name: str,
        total_stages: int,
        input_file: Path,
        output_dir: Path,
        project_root: Path,
    ) -> None:
        self.pipeline_name = pipeline_name
        self.total_stages = total_stages
        self.input_file = input_file
        self.output_dir = output_dir
        self.project_root = project_root
        self.warning_count = 0

    def start_pipeline(self) -> None:
        logger.info("%s pipeline: %d stage(s)", self.pipeline_name, self.total_stages)
        logger.info("Input:  %s", _display_path(self.input_file, self.project_root))
        logger.info("Output: %s", _display_path(self.output_dir, self.project_root))

    def start_stage(self, index: int, label: str) -> None:
        logger.info("%s START %s", _stage_prefix(index, self.total_stages), label)

    def finish_stage(
        self, index: int, label: str, duration_seconds: float, summary: StageSummary
    ) -> None:
        status = summary.status.lower()
        if status == "warn":
            self.warning_count += 1
            log = logger.warning
            tag = "WARN "
        elif status == "fail":
            log = logger.error
            tag = "FAIL "
        else:
            log = logger.info
            tag = "OK   "

        message = summary.message or "completed"
        log(
            "%s %s %s (%.1fs) - %s",
            _stage_prefix(index, self.total_stages),
            tag,
            label,
            duration_seconds,
            message,
        )

        for detail in summary.details:
            log("              %s", detail)

    def finish_pipeline(self, duration_seconds: float) -> None:
        if self.warning_count:
            logger.warning(
                "[DONE ] %s pipeline complete (%.1fs, %d warning stage%s)",
                self.pipeline_name,
                duration_seconds,
                self.warning_count,
                "" if self.warning_count == 1 else "s",
            )
            return

        logger.info(
            "[DONE ] %s pipeline complete (%.1fs)",
            self.pipeline_name,
            duration_seconds,
        )


def get_pipeline_name(asset_file: Path) -> str:
    extension = asset_file.suffix.lower()
    if extension == ".xodr":
        return "OpenDRIVE"
    if extension == ".xosc":
        return "OpenSCENARIO"
    return "Asset"


def get_stage_label(script_config: dict, source_filename: str = "") -> str:
    if source_filename in STAGE_LABELS:
        return STAGE_LABELS[source_filename]

    raw_name = script_config.get("name", "Pipeline stage")
    return raw_name.replace("_", " ").strip()


def summarize_stage_success(
    script_config: dict,
    cmd: list[str],
    result: CommandResult,
    *,
    project_root: Path,
    source_filename: str = "",
) -> StageSummary:

    if source_filename in {
        "config_extractor_json_syntax_validator_omb.json",
        "config_structure_json_syntax_validator_omb.json",
    }:
        return _summarize_omb_syntax_check(cmd, result, project_root)

    if source_filename in {
        "config_jsonLD_validator_omb.json",
        "config_structure_jsonLD_validator_omb.json",
    }:
        return _summarize_omb_validation(result, source_filename=source_filename)

    if source_filename in {
        "config_quality_checker_asam_xodr.json",
        "config_quality_checker_asam_xosc.json",
        "config_quality_checker_openmsl_xodr.json",
    }:
        return _summarize_quality_checker(cmd, project_root)

    if source_filename == "config_vcs_odr-converter.json":
        return _summarize_geojson_converter(result.stderr)

    if source_filename == "config_shacl_combiner.json":
        return _summarize_shacl_combiner(result.stderr, project_root)

    return _summarize_output_targets(cmd, project_root)


def summarize_stage_failure(
    script_config: dict,
    cmd: list[str],
    exc: CommandError,
    *,
    project_root: Path,
    source_filename: str = "",
) -> StageSummary:
    details: list[str] = []

    if source_filename in {
        "config_quality_checker_asam_xodr.json",
        "config_quality_checker_asam_xosc.json",
        "config_quality_checker_openmsl_xodr.json",
    }:
        xqar_path = _get_option_value(cmd, "-out")
        if xqar_path:
            report_path = str(Path(xqar_path).with_suffix("")) + "_QCReport.txt"
            details.append(f"Report: {_display_path(report_path, project_root)}")

    if source_filename in {
        "config_extractor_json_syntax_validator_omb.json",
        "config_structure_json_syntax_validator_omb.json",
    }:
        details.extend(_extract_syntax_failure_details(exc))
        return StageSummary(
            status="fail",
            message="JSON syntax check failed",
            details=details[:3],
        )

    if source_filename in {
        "config_jsonLD_validator_omb.json",
        "config_structure_jsonLD_validator_omb.json",
    }:
        details.extend(
            _extract_validation_failure_details(
                exc,
                source_filename=source_filename,
            )
        )
        return StageSummary(
            status="fail",
            message=_validation_failure_message(exc),
            details=details[:3],
        )

    detail = _best_error_detail(exc)
    return StageSummary(status="fail", message=detail, details=details)


def _summarize_output_targets(cmd: list[str], project_root: Path) -> StageSummary:
    outputs = []
    for option in ("-out", "-box"):
        output_value = _get_option_value(cmd, option)
        if output_value:
            outputs.append(_display_path(output_value, project_root))

    if not outputs:
        return StageSummary(message="completed")

    if len(outputs) == 1:
        return StageSummary(message=f"wrote {outputs[0]}")

    joined = ", ".join(outputs[:-1]) + f" and {outputs[-1]}"
    return StageSummary(message=f"wrote {joined}")


def _summarize_shacl_combiner(stderr: str, project_root: Path) -> StageSummary:
    for raw_line in stderr.splitlines():
        line = normalize_output_line(raw_line)
        match = re.search(r"\bwrite\s+(.+)$", line, re.IGNORECASE)
        if match:
            return StageSummary(
                message=f"wrote {_display_path(match.group(1).strip(), project_root)}"
            )

    return StageSummary(message="wrote SHACL bundle")


def _summarize_omb_validation(
    result: CommandResult, *, source_filename: str
) -> StageSummary:
    warning_lines = _filter_validation_warning_lines(
        extract_warning_lines(result.stderr),
        source_filename=source_filename,
    )
    warning_details = [_condense_validation_warning(line) for line in warning_lines[:3]]

    data_match = re.search(
        r"Found\s+(\d+)\s+top-level file\(s\)\s+to validate", result.stdout
    )
    file_count = int(data_match.group(1)) if data_match else None

    message = "SHACL validation passed"
    if file_count is not None:
        noun = "file" if file_count == 1 else "files"
        message += f" for {file_count} {noun}"

    if warning_lines:
        noun = "warning" if len(warning_lines) == 1 else "warnings"
        message += f" with {len(warning_lines)} {noun}"

    return StageSummary(
        status="warn" if warning_lines else "ok",
        message=message,
        details=warning_details,
    )


def _summarize_omb_syntax_check(
    cmd: list[str], result: CommandResult, project_root: Path
) -> StageSummary:
    warning_lines = extract_warning_lines(result.stderr)
    syntax_matches = re.findall(r"Syntax OK:\s+(.+)", result.stdout)
    input_path = _get_option_value(cmd, "--data-paths")

    message = "JSON syntax passed"
    if syntax_matches:
        noun = "file" if len(syntax_matches) == 1 else "files"
        message += f" for {len(syntax_matches)} {noun}"

    details = []
    if input_path:
        details.append(f"File: {_display_path(input_path, project_root)}")
    elif len(syntax_matches) == 1:
        details.append(f"File: {normalize_output_line(syntax_matches[0].strip())}")

    for line in warning_lines[:2]:
        details.append(normalize_output_line(line))

    if warning_lines:
        noun = "warning" if len(warning_lines) == 1 else "warnings"
        message += f" with {len(warning_lines)} {noun}"

    return StageSummary(
        status="warn" if warning_lines else "ok",
        message=message,
        details=details,
    )


def _summarize_quality_checker(cmd: list[str], project_root: Path) -> StageSummary:
    xqar_path = _get_option_value(cmd, "-out")
    if not xqar_path:
        return StageSummary(message="quality checks completed")

    result_file = Path(xqar_path)
    if not result_file.exists():
        return StageSummary(
            status="warn",
            message="quality checks completed with missing XQAR summary",
            details=[f"Expected result: {_display_path(result_file, project_root)}"],
        )

    try:
        tree = ET.parse(result_file)
    except ET.ParseError:
        return StageSummary(
            status="warn",
            message="quality checks completed with malformed XQAR",
            details=[f"Expected result: {_display_path(result_file, project_root)}"],
        )
    bundle = tree.find(".//CheckerBundle")
    summary = bundle.get("summary", "").strip() if bundle is not None else ""
    compact = _compact_bundle_summary(summary)

    detail_path = str(result_file.with_suffix("")) + "_QCReport.txt"
    details = [f"Report: {_display_path(detail_path, project_root)}"]

    # Detect internal checker errors (e.g. upstream checker bugs) and surface
    # them as warnings so the pipeline continues but the user is informed.
    # See https://github.com/openMSL/sl-5-8-asset-tools/issues/19.
    error_checkers = [
        c.get("checkerId", "unknown")
        for c in tree.findall(".//Checker[@status='error']")
    ]
    if error_checkers:
        details.append(
            f"Internal errors in: {', '.join(error_checkers[:3])}"
            + (f" (+{len(error_checkers) - 3} more)" if len(error_checkers) > 3 else "")
        )
        return StageSummary(
            status="warn",
            message=compact or "quality checks completed",
            details=details,
        )

    return StageSummary(message=compact or "quality checks completed", details=details)


def _summarize_geojson_converter(stderr: str) -> StageSummary:
    feature_counts = []
    for raw_line in stderr.splitlines():
        line = normalize_output_line(raw_line)
        match = re.search(r"Wrote\s+.+\((\d+)\s+features?\)", line)
        if match:
            feature_counts.append(int(match.group(1)))

    if not feature_counts:
        return StageSummary(message="generated preview GeoJSON")

    file_count = len(feature_counts)
    total_features = sum(feature_counts)
    return StageSummary(
        message=(
            f"wrote {file_count} preview layer"
            f"{'' if file_count == 1 else 's'} ({total_features} total features)"
        )
    )


def _compact_bundle_summary(summary: str) -> str:
    if not summary:
        return "quality checks completed"

    counts = []
    patterns = (
        (r"(\d+)\s+checker\(s\)\s+(?:are\s+)?executed", "executed"),
        (r"(\d+)\s+checker\(s\)\s+(?:are\s+)?completed", "completed"),
        (r"(\d+)\s+checker\(s\)\s+(?:are\s+)?skipped", "skipped"),
        (
            r"(\d+)\s+checker\(s\)\s+(?:have\s+)?internal error",
            "internal errors",
        ),
        (
            r"(\d+)\s+checker\(s\)\s+do not contain status",
            "missing status",
        ),
    )
    for pattern, label in patterns:
        match = re.search(pattern, summary)
        if not match:
            continue
        value = int(match.group(1))
        if value == 0 and label in {"internal errors", "missing status"}:
            continue
        counts.append(f"{value} {label}")

    if counts:
        return ", ".join(counts)

    return normalize_output_line(summary)


def _condense_validation_warning(line: str) -> str:
    lowered = line.lower()
    if "unresolved iri" in lowered:
        detail = line
        match = re.search(
            r"unresolved iri(?:\s*\(continuing validation\))?:\s*(.+)$",
            line,
            re.IGNORECASE,
        )
        if match:
            detail = match.group(1).strip()
        return f"Unresolved IRI: {detail}"
    return line


def _best_error_detail(exc: CommandError) -> str:
    for text in (exc.stderr, exc.stdout):
        if not text:
            continue
        for raw_line in text.splitlines():
            line = normalize_output_line(raw_line)
            if not line:
                continue
            if line.startswith("Traceback"):
                continue
            return line
    return str(exc)


def _validation_failure_message(exc: CommandError) -> str:
    combined = "\n".join(text for text in (exc.stdout, exc.stderr) if text)
    if "Validation FAILED" in combined:
        return "SHACL validation failed"
    return _best_error_detail(exc)


def _extract_validation_failure_details(
    exc: CommandError, *, source_filename: str
) -> list[str]:
    details: list[str] = []

    for raw_line in _filter_validation_warning_lines(
        extract_warning_lines(exc.stderr),
        source_filename=source_filename,
    ):
        details.append(_condense_validation_warning(raw_line))

    combined = "\n".join(text for text in (exc.stdout, exc.stderr) if text)
    property_match = re.search(r"Property:\s+(\S+)", combined)
    if property_match:
        details.append(
            f"First failing property: {_compact_validation_property(property_match.group(1))}"
        )

    error_match = re.search(r"Error:\s+(.+)", combined)
    if error_match:
        compact_error = _compact_validation_error(error_match.group(1).strip())
        if compact_error:
            details.append(compact_error)

    return details


def _filter_validation_warning_lines(
    warning_lines: list[str], *, source_filename: str
) -> list[str]:
    if source_filename != "config_jsonLD_validator_omb.json":
        return warning_lines

    filtered = []
    for line in warning_lines:
        if re.search(
            r"unresolved iri.*did:web:registry\.gaia-x\.eu:Manifest:[0-9a-fA-F-]{36}",
            line,
            re.IGNORECASE,
        ):
            continue
        filtered.append(line)
    return filtered


def _extract_syntax_failure_details(exc: CommandError) -> list[str]:
    details: list[str] = []

    for raw_line in extract_warning_lines(exc.stderr):
        details.append(normalize_output_line(raw_line))

    combined = "\n".join(text for text in (exc.stdout, exc.stderr) if text)
    syntax_match = re.search(r"Syntax ERROR:\s+(.+)", combined)
    if syntax_match:
        details.append(syntax_match.group(1).strip())
        return details

    error_match = re.search(r"Error:\s+(.+)", combined)
    if error_match:
        details.append(error_match.group(1).strip())
        return details

    fallback = _best_error_detail(exc)
    if fallback and fallback not in details:
        details.append(fallback)

    return details


def _compact_validation_property(value: str) -> str:
    return value.replace("https://w3id.org/gaia-x/development#", "gx:")


def _compact_validation_error(value: str) -> str | None:
    if value.startswith("Less than 1 values on"):
        return "Missing required value"
    if value.startswith("More than 1 values on"):
        return "Too many values provided"
    if value:
        return value[:160].rstrip()
    return None


def _get_option_value(cmd: list[str], option_name: str) -> str | None:
    for index, value in enumerate(cmd[:-1]):
        if value == option_name:
            return str(cmd[index + 1])
    return None


def _display_path(path_like: str | Path, project_root: Path) -> str:
    path = Path(path_like)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    try:
        return str(resolved.relative_to(project_root)).replace("/", os.sep)
    except ValueError:
        return str(path).replace("/", os.sep)


def _stage_prefix(index: int, total: int) -> str:
    return f"[{index:02d}/{total:02d}]"
