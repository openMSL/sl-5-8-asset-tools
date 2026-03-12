from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from utils.constants import (
    GITHUB_URL,
    GITHUB_RAW_URL,
    ENVITED_URL,
    SHACL_FOLDER_NAME,
    SHACLE_NAME,
)

import re
import logging
import requests

logger = logging.getLogger(__name__)

# Resolve OMB artifacts relative to this file's location
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OMB_ARTIFACTS = _PROJECT_ROOT / "submodules" / "ontology-management-base" / "artifacts"


def download_or_get_file(filename: Path, out_path: Path) -> Path:
    """get filename, if url download file first and get local filename"""

    if is_url(filename):
        filename = Path(
            download_file(normalize_url(str(filename)), out_path, filename.name)
        )

    filename = filename.resolve()
    return filename


def is_url(url: Path) -> bool:
    """Return True if the given string/path looks like a URL."""

    url = url_from_path(url)
    parsed = urlparse(url)
    # A URL usually has a scheme (e.g. “http”, “https”) and a “netloc” (e.g. “www.example.com”)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def url_from_path(path: Path) -> str:
    s = path.as_posix()
    # from 'http:/example.com' to 'http://example.com'
    s = re.sub(
        r"^(?P<scheme>https?):/+",
        lambda m: f"{m.group('scheme')}://",
        s,
        flags=re.IGNORECASE,
    )
    return s


def github_to_raw(url: str) -> str:
    """Convert GitHub blob URL to raw URL if needed."""

    if "github.com" in url and "/blob/" in url:
        url = url.replace(GITHUB_URL, GITHUB_RAW_URL).replace("/blob/", "/")

    return url


def normalize_url(url: str) -> str:
    """Normalize known URL patterns to a downloadable URL."""

    url = url.strip().replace("\\", "/")  # Fix Windows separators
    # Ensure scheme has exactly '://'
    url = re.sub(r"^(https?):/+", r"\1://", url)
    return url


def get_url_for_download(url: str) -> str:
    """replace url with raw.githubusercontent.com"""

    if not url.startswith(ENVITED_URL):
        # If no path segments were found, return the new server
        return url.replace("#", ".ttl")
    else:
        return url


def download_file(url_path: str, out_path: Path, filename: str) -> Path:
    """Download file from url to out_path."""

    url_path = github_to_raw(url_path)
    with requests.get(url_path, stream=True, timeout=30) as r:
        r.raise_for_status()
        out_path.mkdir(parents=True, exist_ok=True)
        filepath = out_path / filename
        with filepath.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return filepath


def download_shacl(url_path: str, shacl_name: str) -> Path:
    """Resolve a SHACL file from local OMB artifacts or download as fallback."""

    # 1. Try local OMB artifacts (domain shapes)
    omb_shacl = OMB_ARTIFACTS / shacl_name / f"{shacl_name}{SHACLE_NAME}"
    if omb_shacl.exists():
        logger.info(f"Using local OMB artifact: {omb_shacl}")
        return omb_shacl

    # 2. Try local OMB imports (W3C vocabularies like sh, rdf, owl)
    omb_import = OMB_ARTIFACTS.parent / "imports" / shacl_name / f"{shacl_name}.owl.ttl"
    if omb_import.exists():
        logger.info(f"Using local OMB import: {omb_import}")
        return omb_import

    # 3. Try local cache (from a previous download)
    filename = f"{shacl_name}{SHACLE_NAME}"
    local_path = _PROJECT_ROOT / SHACL_FOLDER_NAME
    local_filepath = local_path / filename

    if local_filepath.exists():
        return local_filepath

    # 4. Fallback: download from remote URL
    logger.warning(
        f"SHACL '{shacl_name}' not found in OMB artifacts, downloading from {url_path}"
    )
    if not url_path.endswith("ttl"):
        url_path = url_path + "shapes"

    resp = requests.get(
        url_path,
        headers={
            "Accept": "text/turtle",
            "User-Agent": "python-requests (envited-x downloader)",
        },
        allow_redirects=True,
        timeout=30,
    )
    resp.raise_for_status()
    local_path.mkdir(parents=True, exist_ok=True)
    with local_filepath.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    return local_filepath
