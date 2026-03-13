"""Subprocess helpers.

# Centralizes consistent logging + error handling for subprocess calls.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import sys
import os
import logging
import subprocess

from utils.log_config import extract_error_summary, handle_output, is_debug_logging

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    name: str
    cmd: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandError(RuntimeError):
    """Raised when a child command exits with a non-zero status."""

    def __init__(
        self,
        *,
        name: str,
        cmd: list[str],
        returncode: int,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        self.name = name
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        command = subprocess.list2cmdline(cmd)
        self.command = command
        detail = extract_error_summary(stderr, stdout)
        super().__init__(
            f"Command {name} failed with return code {returncode}"
            + (f": {detail}" if detail else "")
        )


def run_command(
    cmd: list[str | Path],
    name: str,
    cwd: Path | str | None = None,
    *,
    log_output: bool = True,
) -> CommandResult:
    """Run *cmd* and log stdout/stderr similar to other tools.

    # Raises CalledProcessError on failures.
    """
    try:
        # Ensure all command parts are strings (Path objects can be problematic on Windows)
        cmd = [str(c) for c in cmd]

        # Always use the current interpreter (venv) instead of relying on PATH resolving "python"
        if cmd and Path(cmd[0]).name.lower() in {
            "python",
            "python.exe",
            "python3",
            "python3.exe",
        }:
            cmd[0] = sys.executable

        # Force UTF-8 for the child process output
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")

        # Ensure the current venv's Scripts/bin directory is on PATH
        # so that console_scripts entry points (e.g. qc_opendrive) are found
        venv_bin = str(Path(sys.executable).parent)
        if venv_bin not in env.get("PATH", ""):
            env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")

        if is_debug_logging():
            logger.debug("Starting command %s", name)
            logger.debug("Command line: %s", subprocess.list2cmdline(cmd))
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Decode as UTF-8 instead of cp1252
            errors="replace",  # Never crash on undecodable bytes
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        command_result = CommandResult(
            name=name,
            cmd=cmd,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        if log_output:
            handle_output(command_result, name)
        return command_result
    except subprocess.CalledProcessError as e:
        if isinstance(e.cmd, (list, tuple)):
            failed_cmd = [str(part) for part in e.cmd]
        else:
            failed_cmd = [str(e.cmd)]

        failed_result = CommandResult(
            name=name,
            cmd=failed_cmd,
            returncode=e.returncode,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
        )
        if log_output:
            handle_output(failed_result, name)

        raise CommandError(
            name=name,
            cmd=failed_cmd,
            returncode=e.returncode,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
        ) from e
