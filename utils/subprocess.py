"""Subprocess helpers.

# Centralizes consistent logging + error handling for subprocess calls.
"""

from __future__ import annotations
from pathlib import Path
from utils.log_config import handle_output

import sys
import os
import logging
import subprocess

logger = logging.getLogger(__name__)


def run_command(
    cmd: list[str | Path], name: str, cwd: Path | str | None = None
) -> None:
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

        logger.info(">>>    start command %s", name)
        logger.info(cmd)
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
        handle_output(result, name)
        logger.info("   <<< end command %s", name)
    except subprocess.CalledProcessError as e:
        logger.error(
            f"!!!!!!!!!!!! Command {name} failed with return code {e.returncode}"
        )
        handle_output(e, name)
        raise Exception(f"Command {name}")
