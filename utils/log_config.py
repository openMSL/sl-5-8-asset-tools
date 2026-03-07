# log_config.py

import logging
from colorlog import ColoredFormatter


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
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(levelname)s - %(name)s - %(message)s",
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

    # 1) The whole stderr as error, if returncode != 0
    if rc != 0:
        # log the return code
        root.error("Command %s exited with return code %d", name, rc)
        # log all stdout as debug, falls du Details brauchst
        if result.stdout:
            root.debug("=== %s stdout ===\n%s", name, result.stdout.rstrip())
        # log stderr as error (rot)
        root.error("=== %s stderr ===\n%s", name, result.stderr.rstrip())
        return

    # 2) If returncode == 0, but stderr is not empty → only warnings
    if result.stderr:
        # split lines and detect keyword "warning"
        for line in result.stderr.splitlines():
            # If the line itself mentions 'warning', treat as warning
            if "warning" in line.lower():
                root.warning("=== %s warning === %s", name, line)
            else:
                # otherwise still log as info or error?
                root.error("=== %s stderr (non-warning) === %s", name, line)

    # 3) Everything that came on stdout remains info (green)
    if result.stdout:
        root.info("=== %s stdout ===\n%s", name, result.stdout.rstrip())
