from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from utils.constants import GITHUB_URL, GITHUB_RAW_URL, ENVITEDX_URL, GAIAX_ONTOLOGY_PART, SHACL_FOLDER_NAME

import re
import logging
import requests

logger = logging.getLogger(__name__)

def download_or_get_file(filename : Path, out_path: Path) -> Path:
    """get filename, if url download file first and get local filename"""

    if is_url(filename):
        filename = Path(download_file(normalize_url(str(filename)), out_path, filename.name))

    filename = filename.resolve()
    return filename

def is_url(url: Path) -> bool:
    """Return True if the given string/path looks like a URL."""

    url = url_from_path(url)
    parsed = urlparse(url)
    # A URL usually has a scheme (e.g. “http”, “https”) and a “netloc” (e.g. “www.example.com”)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)

def url_from_path(path: Path) -> str:
    s = path.as_posix()
    # from 'http:/example.com' to 'http://example.com'
    s = re.sub(
        r'^(?P<scheme>https?):/+',
        lambda m: f"{m.group('scheme')}://",
        s,
        flags=re.IGNORECASE
    )
    return s

def github_to_raw(url: str) -> str:
    """Convert GitHub blob URL to raw URL if needed."""

    org_url = url
    if "github.com" in url and "/blob/" in url:
        url = url.replace(GITHUB_URL, GITHUB_RAW_URL).replace("/blob/", "/")
    
    # old
    old_url = org_url.strip()
    p = urlparse(old_url)

    # Already raw
    if p.netloc == "raw.githubusercontent.com":
        old_url = old_url

    if p.netloc != "github.com":
        old_url = old_url  # Not GitHub; leave as-is

    parts = [x for x in p.path.split("/") if x]
    # Expect: org, repo, "blob", ref, ...path
    if len(parts) >= 5 and parts[2] == "blob":
        org, repo, ref = parts[0], parts[1], parts[3]
        file_path = "/".join(parts[4:])
        old_url = f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{file_path}"
    
    if old_url != url:
        print("not equal")
    
    return url


def normalize_url(url: str) -> str:
    """Normalize known URL patterns to a downloadable URL."""

    url = url.strip().replace("\\", "/")  # Fix Windows separators
    # Ensure scheme has exactly '://'
    url = re.sub(r"^(https?):/+", r"\1://", url)
    return url

def get_url_for_download(url: str) -> str:
    """replace url with raw.githubusercontent.com"""
    
    is_gaiax_ontology = True if str(url).startswith(ENVITEDX_URL) else False
    if is_gaiax_ontology:
        # Break the old URL into components
        parsed = urlparse(url)
        # Split the path into individual segments (empty parts are removed)
        segments = [seg for seg in parsed.path.split("/") if seg]
        
        if segments:
            name = segments[0]
            # Create the new URL: new server, /main/, then the extracted name
            new_url = f"{GITHUB_RAW_URL}{GAIAX_ONTOLOGY_PART}/main/{name}/{name}_shacl.ttl"
            return new_url
    else:
        # If no path segments were found, return the new server
        return url.replace('#', '.ttl')

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
    """Download SHACL file from URL into local shacls folder if missing."""
    
    filename = f"{shacl_name}_shacl.ttl"
    local_filepath = Path(f"{SHACL_FOLDER_NAME}/{filename}")

    if not local_filepath.exists():
        url = f"{url_path}{filename}" if str(url_path).startswith(ENVITEDX_URL) else url_path
        response = requests.get(url, timeout=30)
        if not response:
            raise RuntimeError(f"No shacl files found in url: {url}")

        Path(SHACL_FOLDER_NAME).mkdir(parents=True, exist_ok=True)
        local_filepath.write_bytes(response.content)

    return local_filepath
