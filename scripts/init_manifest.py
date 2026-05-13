"""Generate an ``input_manifest.json`` from the files in a directory.

Scans a directory for simulation data, documentation, media, and license
files, then writes a valid EVES-003 input manifest (JSON-LD) that the
asset-extraction pipeline can consume directly.

Usage::

    python -m scripts.init_manifest path/to/my-asset
    python -m scripts.init_manifest path/to/my-asset --access-role isPublic
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONTEXT = [
    "https://w3id.org/ascs-ev/envited-x/manifest/v5/",
    "https://w3id.org/ascs-ev/envited-x/envited-x/v3/",
]

# ── File classification ──────────────────────────────────────────────

_SIM_DATA_EXTENSIONS = {
    ".xodr": "application/xml",
    ".xosc": "application/xml",
    ".zip": "application/zip",
    ".7z": "application/x-7z-compressed",
}

_DOC_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".html", ".rst"}
_MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".svg", ".gif", ".mp4", ".webm"}
_LICENSE_NAMES = {"license", "license.txt", "license.md"}
_LICENSE_MIME = "text/plain"

_MIME_OVERRIDES = {
    ".xodr": "application/xml",
    ".xosc": "application/xml",
    ".geojson": "application/geo+json",
    ".jsonld": "application/ld+json",
}


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _classify_file(path: Path) -> tuple[str, str] | None:
    """Return (category, mimeType) for a file, or None to skip it."""
    name_lower = path.name.lower()
    ext = path.suffix.lower()

    if name_lower in _LICENSE_NAMES:
        return "license", _LICENSE_MIME

    if name_lower == "input_manifest.json":
        return None

    if ext in _SIM_DATA_EXTENSIONS:
        return "isSimulationData", _SIM_DATA_EXTENSIONS[ext]

    if ext in _DOC_EXTENSIONS:
        return "isDocumentation", _guess_mime(path)

    if ext in _MEDIA_EXTENSIONS:
        return "isMedia", _guess_mime(path)

    # JSON companion files (e.g. statistic_3dModel.json, openlabel)
    if ext == ".json":
        return "isMedia", "application/json"

    return None


# ── Manifest generation ──────────────────────────────────────────────


def scan_directory(input_dir: Path) -> list[dict[str, Any]]:
    """Scan *input_dir* and return classified file entries.

    Each entry is ``{"path": relative_name, "category": ..., "mime": ...}``.
    Only top-level files are included (no recursion).
    """
    entries: list[dict[str, Any]] = []
    for child in sorted(input_dir.iterdir()):
        if child.is_dir() or child.name.startswith("."):
            continue
        result = _classify_file(child)
        if result is None:
            logger.debug("Skipping unrecognized file: %s", child.name)
            continue
        category, mime = result
        entries.append({"path": child.name, "category": category, "mime": mime})
    return entries


def build_manifest(
    entries: list[dict[str, Any]],
    *,
    access_role: str = "isOwner",
) -> dict[str, Any]:
    """Build an input_manifest.json dict from classified file entries."""
    artifacts: list[dict] = []
    license_link: dict | None = None

    for entry in entries:
        link: dict[str, Any] = {
            "@type": "Link",
            "hasCategory": f"envited-x:{entry['category']}",
            "hasAccessRole": f"envited-x:{access_role}",
            "hasFileMetadata": {
                "@type": "FileMetadata",
                "filePath": entry["path"],
                "mimeType": entry["mime"],
            },
        }

        if entry["category"] == "license":
            link["hasCategory"] = "envited-x:isLicense"
            link["hasAccessRole"] = "envited-x:isPublic"
            license_link = link
        else:
            artifacts.append(link)

    manifest: dict[str, Any] = {
        "@context": CONTEXT,
        "@id": "did:key:placeholder",
        "@type": "envited-x:Manifest",
    }

    if artifacts:
        manifest["hasArtifacts"] = artifacts

    if license_link:
        manifest["hasLicense"] = license_link

    return manifest


def generate_manifest(
    input_dir: Path,
    *,
    output: Path | None = None,
    access_role: str = "isOwner",
    force: bool = False,
) -> Path:
    """Scan *input_dir*, build a manifest, and write it.

    Returns the path of the written manifest file.
    """
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {input_dir}")

    out_path = output or (input_dir / "input_manifest.json")
    if out_path.exists() and not force:
        raise FileExistsError(f"{out_path} already exists. Use --force to overwrite.")

    entries = scan_directory(input_dir)

    sim_data = [e for e in entries if e["category"] == "isSimulationData"]
    if not sim_data:
        raise ValueError(
            f"No simulation data files found in {input_dir}. "
            f"Expected: {', '.join(_SIM_DATA_EXTENSIONS)}"
        )

    manifest = build_manifest(entries, access_role=access_role)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(manifest, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Wrote %s (%d artifact(s))", out_path, len(entries))
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="init_manifest",
        description=(
            "Generate an input_manifest.json by scanning a directory for "
            "simulation data, documentation, media, and license files."
        ),
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing asset files to package.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: INPUT_DIR/input_manifest.json).",
    )
    parser.add_argument(
        "--access-role",
        default="isOwner",
        choices=["isOwner", "isPublic", "isRegistered"],
        help="Default access role for artifacts (default: isOwner).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing input_manifest.json.",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    try:
        path = generate_manifest(
            args.input_dir,
            output=args.output,
            access_role=args.access_role,
            force=args.force,
        )
        print(f"Created {path}")
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
