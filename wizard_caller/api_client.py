"""HTTP client for the SD Creation Wizard API.

Delegates SHACL parsing and JSON-LD pre-filling to the sd-creation-wizard-api
service (Spring Boot) which correctly handles conditional SHACL constructs
(sh:or, sh:and, sh:xone) that the local rdflib-based parser cannot resolve.

The API is expected to run at ``WIZARD_API_URL`` (default
``http://localhost:8080``) — start it via::

    docker compose -f docker-compose.wizard.yml up -d sd-creation-wizard-api
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://localhost:8080"
_TIMEOUT = 60  # seconds


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
            f"Start it with: docker compose -f docker-compose.wizard.yml up -d sd-creation-wizard-api"
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


def is_api_available(api_url: str) -> bool:
    """Check whether the Wizard API is reachable."""
    try:
        resp = requests.get(f"{api_url.rstrip('/')}/getAvailableShapes", timeout=5)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False
