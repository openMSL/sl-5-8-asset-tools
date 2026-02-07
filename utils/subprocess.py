"""Subprocess helpers.

# Centralizes consistent logging + error handling for subprocess calls.
"""

from __future__ import annotations

from pathlib import Path
import logging
import subprocess

from utils.log_config import handle_output


logger = logging.getLogger(__name__)


def run_command(cmd: list[str], name: str, cwd: Path | None = None) -> None:
    """Run *cmd* and log stdout/stderr similar to other tools.

    # Raises CalledProcessError on failures.
    """
    try:
        logger.info(">>>    start command %s", name)
        logger.info(cmd)
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        handle_output(result, name)
        logger.info("   <<< end command %s", name)
    except subprocess.CalledProcessError as e:
        logger.error(f"!!!!!!!!!!!! Command {name} failed with return code {e.returncode}")        
        handle_output(e, name)
        exit(1)
