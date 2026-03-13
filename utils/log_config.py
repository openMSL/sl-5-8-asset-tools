import logging
import os
import re

from colorlog import ColoredFormatter

LOG_MODE_ENV = "SL58_LOG_MODE"


def get_log_mode() -> str:
    mode = os.environ.get(LOG_MODE_ENV, "concise").strip().lower()
    if mode in {"debug", "verbose", "full"}:
        return "debug"
    return "concise"


def is_debug_logging() -> bool:
    return get_log_mode() == "debug"


def normalize_output_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    stripped = re.sub(
        r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*[^-]+\s*-\s*",
        "",
        stripped,
    )
    stripped = re.sub(r"^=== .*? ===\s*", "", stripped)
    return stripped.strip()


def extract_warning_lines(text: str | None) -> list[str]:
    if not text:
        return []

    warnings = []
    for raw_line in text.splitlines():
        line = normalize_output_line(raw_line)
        if not line:
            continue
        if "warning" not in line.lower():
            continue
        if line.upper().startswith("WARNING:"):
            line = "Warning: " + line.split(":", 1)[1].strip()
        warnings.append(line)
    return warnings


def extract_error_summary(stderr: str | None, stdout: str | None) -> str | None:
    for text in (stderr, stdout):
        if not text:
            continue
        for raw_line in text.splitlines():
            line = normalize_output_line(raw_line)
            if not line:
                continue
            if line.startswith("Traceback"):
                continue
            return line
    return None


def setup_logging(level=logging.DEBUG):
    """
    # Set up root logger with colored output.
    # - Uses colorlog.ColoredFormatter for automatic color mapping.
    # - Attaches one StreamHandler to the root logger.
    # - Subsequent calls are idempotent.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    # Create console handler with colored formatter
    handler = logging.StreamHandler()
    concise_format = "%(log_color)s%(levelname)-7s%(reset)s %(message)s"
    debug_format = "%(log_color)s%(levelname)-7s%(reset)s %(name)s: %(message)s"
    handler.setFormatter(
        ColoredFormatter(
            debug_format if is_debug_logging() else concise_format,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
                "EXCEPTION": "white, bg_red",
            },
        )
    )

    root.setLevel(level)
    root.addHandler(handler)


def handle_output(result, name):
    rc = result.returncode
    root = logging.getLogger()

    if is_debug_logging():
        if rc != 0:
            root.error("Command %s exited with return code %d", name, rc)
            if result.stdout:
                root.debug("=== %s stdout ===\n%s", name, result.stdout.rstrip())
            if result.stderr:
                root.error("=== %s stderr ===\n%s", name, result.stderr.rstrip())
            return

        if result.stderr:
            for line in result.stderr.splitlines():
                if not line.strip():
                    continue
                if "warning" in line.lower():
                    root.warning("=== %s stderr warning === %s", name, line)
                else:
                    root.info("=== %s stderr === %s", name, line)

        if result.stdout:
            root.info("=== %s stdout ===\n%s", name, result.stdout.rstrip())
        return

    if rc != 0:
        detail = extract_error_summary(result.stderr, result.stdout)
        if detail:
            root.error("%s failed: %s", name, detail)
        else:
            root.error("%s failed with return code %d", name, rc)
        return

    for line in extract_warning_lines(result.stderr):
        root.warning("%s: %s", name, line)
