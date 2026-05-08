"""HTTP client for the SD Creation Wizard API.

Delegates SHACL parsing and JSON-LD pre-filling to the sd-creation-wizard
TypeScript API (Hono/N3.js) which correctly handles conditional SHACL
constructs (sh:or, sh:and, sh:xone) that the local rdflib-based parser
cannot resolve.

The API is expected to run at ``WIZARD_API_URL`` (default
``http://localhost:3007``) — start it via::

    cd submodules/sd-creation-wizard && pnpm dev:api

The React frontend runs at ``http://localhost:5174`` via::

    cd submodules/sd-creation-wizard && pnpm dev:wizard

Ports are configurable via ``.env`` file or environment variables
(``WIZARD_API_PORT``, ``WIZARD_FRONTEND_PORT``).
"""

from __future__ import annotations

import logging
import os
import signal
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load .env file from project root if it exists."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

_API_PORT = os.environ.get("WIZARD_API_PORT", "3007")
_FRONTEND_PORT = os.environ.get("WIZARD_FRONTEND_PORT", "5174")

DEFAULT_API_URL = f"http://localhost:{_API_PORT}"
DEFAULT_FRONTEND_URL = f"http://localhost:{_FRONTEND_PORT}"
_TIMEOUT = 60  # seconds
_POLL_INTERVAL = 2  # seconds
_BROWSER_WAIT_TIMEOUT = 600  # 10 minutes max for user interaction
_STARTUP_TIMEOUT = 30  # seconds to wait for API to become available
_FRONTEND_STARTUP_TIMEOUT = 30  # seconds for Vite dev server to start
_PID_FILE = Path("/tmp/sd-wizard-api.pid")
_FRONTEND_PID_FILE = Path("/tmp/sd-wizard-frontend.pid")


class WizardAPIError(Exception):
    """Raised when the Wizard API returns a non-success response."""


def convert_and_prefill(
    api_url: str,
    shacl_path: Path,
    jsonld_path: Path,
    timeout: int = _TIMEOUT,
) -> dict:
    """Send SHACL + JSON-LD to the API and return the combined result.

    Calls ``POST /convertAndPrefillFile`` with multipart form data.

    Returns:
        A dict with keys ``shaclModel`` (the converted shape schema
        including ``sh:or`` branches) and ``matchedSubjects`` (a flat
        map of property-URI → current-value extracted from the JSON-LD).

    Raises:
        WizardAPIError: on HTTP 4xx / 5xx or connection failure.
    """
    url = f"{api_url.rstrip('/')}/convertAndPrefillFile"

    try:
        with open(shacl_path, "rb") as shacl_f, open(jsonld_path, "rb") as json_f:
            files = {
                "file": (shacl_path.name, shacl_f, "text/turtle"),
                "jsonFile": (jsonld_path.name, json_f, "application/json"),
            }
            resp = requests.post(url, files=files, timeout=timeout)
    except requests.ConnectionError as exc:
        raise WizardAPIError(
            f"Cannot connect to Wizard API at {api_url}. "
            f"Start it with: cd submodules/sd-creation-wizard && pnpm --filter @sd-creation-wizard/api dev"
        ) from exc
    except requests.Timeout as exc:
        raise WizardAPIError(f"Wizard API request timed out after {timeout}s") from exc
    except OSError as exc:
        raise WizardAPIError(f"Cannot read input file: {exc}") from exc

    if resp.status_code != 200:
        raise WizardAPIError(
            f"Wizard API returned HTTP {resp.status_code}: {resp.text[:500]}"
        )

    return resp.json()


def create_session(
    api_url: str,
    shacl_path: Path,
    jsonld_path: Path | None,
    output_path: Path,
    timeout: int = _TIMEOUT,
) -> None:
    """Create a wizard session — hand off files for browser-based editing.

    Calls ``POST /session`` with the SHACL file, optional JSON-LD prefill,
    and the output path where the final JSON-LD should be written.

    Raises:
        WizardAPIError: on HTTP error or connection failure.
    """
    url = f"{api_url.rstrip('/')}/session"

    try:
        with open(shacl_path, "rb") as shacl_f:
            files: dict = {
                "shaclFile": (shacl_path.name, shacl_f, "text/turtle"),
                "outputPath": (None, str(output_path.resolve())),
            }
            jsonld_f = None
            try:
                if jsonld_path and jsonld_path.exists():
                    jsonld_f = open(jsonld_path, "rb")  # noqa: SIM115
                    files["jsonLdFile"] = (
                        jsonld_path.name,
                        jsonld_f,
                        "application/json",
                    )
                resp = requests.post(url, files=files, timeout=timeout)
            finally:
                if jsonld_f:
                    jsonld_f.close()
    except requests.ConnectionError as exc:
        raise WizardAPIError(f"Cannot connect to Wizard API at {api_url}") from exc
    except OSError as exc:
        raise WizardAPIError(f"Cannot read input file: {exc}") from exc

    if resp.status_code != 200:
        raise WizardAPIError(
            f"Session creation failed HTTP {resp.status_code}: {resp.text[:500]}"
        )


def wait_for_export(
    api_url: str,
    timeout: int = _BROWSER_WAIT_TIMEOUT,
) -> bool:
    """Poll the session status until the user exports from the browser.

    Returns True if export completed, False if timed out.
    """
    url = f"{api_url.rstrip('/')}/session/status"
    elapsed = 0

    while elapsed < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("exported"):
                    return True
        except (requests.ConnectionError, requests.Timeout):
            pass

        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    return False


def open_wizard_browser(
    api_url: str,
    frontend_url: str | None = None,
    shacl_path: Path | None = None,
    jsonld_path: Path | None = None,
    output_path: Path | None = None,
) -> bool:
    """Create a session, open the browser, and wait for user to export.

    This is the main entry point for the interactive browser-based wizard.
    The pipeline pauses here until the user completes the form and clicks Export.

    Returns True if export succeeded, False on timeout.
    """
    fe_url = frontend_url or DEFAULT_FRONTEND_URL

    if shacl_path and output_path:
        logger.info("Creating wizard session...")
        create_session(api_url, shacl_path, jsonld_path, output_path)

    logger.info("Opening browser at %s", fe_url)
    webbrowser.open(fe_url)

    logger.info(
        "Waiting for you to complete the wizard in the browser...\n"
        "  → Fill in the form fields and click 'Export JSON-LD' when done.\n"
        "  → The pipeline will continue automatically."
    )

    return wait_for_export(api_url)


def is_api_available(api_url: str) -> bool:
    """Check whether the Wizard API is reachable and has session support."""
    try:
        base = api_url.rstrip("/")
        resp = requests.get(f"{base}/health", timeout=5)
        if resp.status_code != 200:
            return False
        # Verify session endpoint exists
        status = requests.get(f"{base}/session/status", timeout=5)
        return status.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def _find_wizard_dir() -> Path | None:
    """Locate the sd-creation-wizard submodule directory."""
    candidates = [
        Path(__file__).resolve().parent.parent / "submodules" / "sd-creation-wizard",
        Path.cwd() / "submodules" / "sd-creation-wizard",
    ]
    for candidate in candidates:
        if (candidate / "package.json").exists():
            return candidate
    return None


def _start_api(wizard_dir: Path) -> bool:
    """Start the wizard API in the background. Returns True if successful."""
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True  # already running
        except (OSError, ValueError):
            _PID_FILE.unlink(missing_ok=True)

    logger.info("Starting wizard API server...")
    api_dir = wizard_dir / "apps" / "api"
    tsx = shutil.which("tsx") or str(api_dir / "node_modules" / ".bin" / "tsx")

    proc = subprocess.Popen(
        [tsx, "src/index.ts"],
        cwd=str(api_dir),
        stdin=subprocess.DEVNULL,
        stdout=open("/tmp/sd-wizard-api.log", "w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _PID_FILE.write_text(str(proc.pid))
    _PID_FILE.chmod(0o600)

    # Wait for API to become available
    for _ in range(int(_STARTUP_TIMEOUT / 2)):
        time.sleep(2)
        if is_api_available(DEFAULT_API_URL):
            logger.info("Wizard API started (PID %d)", proc.pid)
            return True

    logger.error("Wizard API failed to start within %ds", _STARTUP_TIMEOUT)
    return False


def _start_frontend(wizard_dir: Path) -> bool:
    """Start the React/Vite frontend dev server in the background."""
    if _FRONTEND_PID_FILE.exists():
        try:
            pid = int(_FRONTEND_PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True  # already running
        except (OSError, ValueError):
            _FRONTEND_PID_FILE.unlink(missing_ok=True)

    logger.info("Starting wizard frontend...")
    wizard_app_dir = wizard_dir / "apps" / "wizard"
    pnpm = shutil.which("pnpm") or "pnpm"

    proc = subprocess.Popen(
        [pnpm, "vite", "--port", _FRONTEND_PORT],
        cwd=str(wizard_app_dir),
        stdin=subprocess.DEVNULL,
        stdout=open("/tmp/sd-wizard-frontend.log", "w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _FRONTEND_PID_FILE.write_text(str(proc.pid))
    _FRONTEND_PID_FILE.chmod(0o600)

    # Wait for frontend to become available (Vite starts quickly)
    for _ in range(int(_FRONTEND_STARTUP_TIMEOUT / 2)):
        time.sleep(2)
        try:
            resp = requests.get(DEFAULT_FRONTEND_URL, timeout=3)
            if resp.status_code == 200:
                logger.info("Wizard frontend started (PID %d)", proc.pid)
                return True
        except (requests.ConnectionError, requests.Timeout):
            continue

    logger.error(
        "Wizard frontend failed to start within %ds", _FRONTEND_STARTUP_TIMEOUT
    )
    return False


def _graceful_kill(pid: int, label: str) -> None:
    """Terminate a process gracefully: SIGTERM first, SIGKILL after 3s."""
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(6):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except OSError:
                logger.info("Stopped stale %s (PID %d)", label, pid)
                return
        # Still alive after 3s — force kill
        os.kill(pid, signal.SIGKILL)
        logger.info("Force-killed stale %s (PID %d)", label, pid)
    except OSError:
        pass


def ensure_wizard_running(api_url: str | None = None) -> str | None:
    """Ensure the wizard API (and frontend) are running. Auto-starts if needed.

    Returns the API URL if successful, None if unable to start.
    """
    url = api_url or DEFAULT_API_URL

    if is_api_available(url):
        return url

    # Kill stale wizard processes if PID files exist but health check failed
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            _graceful_kill(pid, "wizard API")
        except (OSError, ValueError):
            pass
        _PID_FILE.unlink(missing_ok=True)

    if _FRONTEND_PID_FILE.exists():
        try:
            pid = int(_FRONTEND_PID_FILE.read_text().strip())
            _graceful_kill(pid, "wizard frontend")
        except (OSError, ValueError):
            pass
        _FRONTEND_PID_FILE.unlink(missing_ok=True)

    wizard_dir = _find_wizard_dir()
    if not wizard_dir:
        logger.warning("Cannot find sd-creation-wizard submodule — cannot auto-start")
        return None

    if not shutil.which("node"):
        logger.warning("Node.js not found — cannot auto-start wizard")
        return None

    # Ensure dependencies are installed
    if not (wizard_dir / "node_modules").exists():
        logger.info("Installing wizard dependencies...")
        subprocess.run(
            ["pnpm", "install"],
            cwd=str(wizard_dir),
            capture_output=True,
            check=False,
        )

    if not (wizard_dir / "packages" / "shacl-core" / "dist").exists():
        logger.info("Building shacl-core...")
        subprocess.run(
            ["pnpm", "--filter", "@sd-creation-wizard/shacl-core", "build"],
            cwd=str(wizard_dir),
            capture_output=True,
            check=False,
        )

    if not _start_api(wizard_dir):
        return None

    if not _start_frontend(wizard_dir):
        logger.warning(
            "Wizard frontend failed to start — browser may show a blank page. "
            "The API is still available for CLI usage."
        )

    return url
