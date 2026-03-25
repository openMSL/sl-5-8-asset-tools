from __future__ import annotations

from pathlib import Path

import logging
import re

logger = logging.getLogger(__name__)


LICENSE_MARKERS = (
    (
        "MPL-2.0",
        (
            "mozilla public license version 2.0",
            "mozilla public license, v. 2.0",
            "mpl-2.0",
        ),
    ),
    (
        "EPL-2.0",
        (
            "eclipse public license - v 2.0",
            "eclipse public license - v. 2.0",
            "eclipse public license 2.0",
            "epl-2.0",
        ),
    ),
    (
        "Apache-2.0",
        (
            "apache license version 2.0",
            "apache license, version 2.0",
            "apache-2.0",
        ),
    ),
    (
        "MIT",
        (
            "mit license",
            "permission is hereby granted, free of charge, to any person obtaining a copy",
        ),
    ),
    (
        "BSD-3-Clause",
        (
            "redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met",
            "neither the name of the",
        ),
    ),
)


def enrich_resource_description(resource_description: dict, asset_file: Path) -> None:
    resource_description.setdefault("gx:resourcePolicy", "allow")

    license_file = _find_license_file(asset_file)
    if license_file is None:
        logger.warning("No sibling LICENSE file found for %s", asset_file.name)
        return

    license_text = license_file.read_text(encoding="utf-8", errors="ignore")

    license_id = _detect_license_identifier(license_text)
    if license_id:
        resource_description.setdefault("gx:license", license_id)
    else:
        logger.warning(
            "Could not determine SPDX license identifier from %s", license_file.name
        )

    copyright_owner = _extract_copyright_owner(license_text)
    if copyright_owner:
        resource_description.setdefault("gx:copyrightOwnedBy", copyright_owner)
    else:
        logger.warning("Could not determine copyright owner from %s", license_file.name)


def _find_license_file(asset_file: Path) -> Path | None:
    candidates = [
        path
        for path in asset_file.parent.iterdir()
        if path.is_file() and path.name.lower().startswith("license")
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda path: (path.name.lower() != "license", len(path.name)))
    return candidates[0]


def _detect_license_identifier(license_text: str) -> str | None:
    normalized = " ".join(license_text.lower().split())
    for license_id, markers in LICENSE_MARKERS:
        if all(marker in normalized for marker in markers):
            return license_id

    for license_id, markers in LICENSE_MARKERS:
        if any(marker in normalized for marker in markers):
            return license_id

    return None


def _extract_copyright_owner(license_text: str) -> str | None:
    for raw_line in license_text.splitlines():
        line = raw_line.strip()
        if not line or not line.lower().startswith("copyright"):
            continue

        owner = re.sub(
            r"^copyright\s*(?:\([cC]\)|[\u00A9])?\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )
        owner = re.sub(
            r"^\d{4}(?:\s*[-,]\s*\d{4})*(?:\s*,\s*)?",
            "",
            owner,
        )
        owner = re.sub(r"\ball rights reserved\.?$", "", owner, flags=re.IGNORECASE)
        owner = owner.strip(" .")
        if owner:
            return owner

    return None
