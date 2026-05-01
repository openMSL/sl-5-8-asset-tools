"""Schema decoder: loads XSD schemas and decodes XML files into typed dicts.

Wraps the ``xmlschema`` library with:
- Auto-detection of format and version from file content
- Schema caching (compile once, reuse)
- Lax validation to tolerate non-conformant real-world files
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import xmlschema
from lxml import etree

logger = logging.getLogger(__name__)

# XSD sources shipped in OMB or installed packages
_OMB_ROOT = (
    Path(__file__).resolve().parents[2] / "submodules" / "ontology-management-base"
)
_QC_OPENDRIVE = Path(__file__).resolve().parents[2] / ".venv" / "lib"

_SCHEMA_CATALOG: dict[tuple[str, str], Path] = {
    # OpenSCENARIO — OMB ships v1.3.1
    ("openscenario", "1.3"): _OMB_ROOT
    / "imports"
    / "OpenScenario"
    / "OpenSCENARIO.xsd",
    ("openscenario", "1.2"): _OMB_ROOT
    / "imports"
    / "OpenScenario"
    / "OpenSCENARIO.xsd",
    ("openscenario", "1.1"): _OMB_ROOT
    / "imports"
    / "OpenScenario"
    / "OpenSCENARIO.xsd",
    ("openscenario", "1.0"): _OMB_ROOT
    / "imports"
    / "OpenScenario"
    / "OpenSCENARIO.xsd",
    # OpenDRIVE — OMB 1.8 XSD uses XSD 1.1 features (xs:alternative) not supported
    # by xmlschema. Use the qc_opendrive 1.7 schema which covers all structural elements.
    ("opendrive", "1.8"): Path("__opendrive_fallback__"),
    ("opendrive", "1.7"): Path("__opendrive_fallback__"),
    ("opendrive", "1.6"): Path("__opendrive_fallback__"),
    ("opendrive", "1.5"): Path("__opendrive_fallback__"),
    ("opendrive", "1.4"): Path("__opendrive_fallback__"),
}


def _find_opendrive_xsd() -> Path:
    """Locate the OpenDRIVE 1.7 XSD from qc_opendrive package."""
    try:
        import qc_opendrive

        pkg_dir = Path(qc_opendrive.__file__).parent
        xsd = pkg_dir / "schema" / "1.7.0" / "opendrive_17_core.xsd"
        if xsd.exists():
            return xsd
    except ImportError:
        pass

    # Fallback: search in venv
    venv_root = Path(__file__).resolve().parents[2] / ".venv"
    for xsd in venv_root.rglob("opendrive_17_core.xsd"):
        return xsd

    raise FileNotFoundError(
        "Cannot find OpenDRIVE 1.7 XSD. Install qc_opendrive or ensure "
        "the schema is available in the venv."
    )


class SchemaDecoder:
    """Decodes XML files into typed Python dicts using their XSD schema."""

    def decode(self, file: Path) -> tuple[dict[str, Any], list]:
        """Decode an XML file into a typed dict.

        Returns:
            (data_dict, validation_errors) — data is always returned even with
            errors (lax mode).
        """
        fmt, version = self._detect_format_version(file)
        schema = self._load_schema(fmt, version)
        data, errors = schema.decode(str(file), validation="lax")
        if errors:
            logger.debug(
                "Schema decode produced %d lax validation errors for %s",
                len(errors),
                file.name,
            )
        return data, errors

    def decode_to_dict(self, file: Path) -> dict[str, Any]:
        """Convenience: decode and return only the data dict."""
        data, _ = self.decode(file)
        return data

    def _detect_format_version(self, file: Path) -> tuple[str, str]:
        """Quick-parse file header to determine format and version.

        Only reads the first few KB — does not parse the entire file.
        """
        # Read enough to get the root element and header
        with open(file, "rb") as f:
            # Use iterparse to get just the first few elements
            context = etree.iterparse(f, events=("start",))
            root_tag = None
            rev_major = "1"
            rev_minor = "0"

            for event, elem in context:
                if root_tag is None:
                    root_tag = elem.tag
                    # OpenDRIVE has version in root <header> child
                    if root_tag.lower().replace("opendrive", "") == "":
                        # It's OpenDRIVE — get version from <header> element
                        pass

                if elem.tag == "FileHeader":
                    # OpenSCENARIO
                    rev_major = elem.get("revMajor", "1")
                    rev_minor = elem.get("revMinor", "0")
                    break
                elif elem.tag == "header":
                    # OpenDRIVE
                    rev_major = elem.get("revMajor", "1")
                    rev_minor = elem.get("revMinor", "0")
                    break

        # Determine format from root tag
        if root_tag and "scenario" in root_tag.lower():
            fmt = "openscenario"
        elif root_tag and "opendrive" in root_tag.lower():
            fmt = "opendrive"
        elif file.suffix.lower() == ".xosc":
            fmt = "openscenario"
        elif file.suffix.lower() == ".xodr":
            fmt = "opendrive"
        else:
            raise ValueError(
                f"Cannot determine format for {file.name} (root tag: {root_tag})"
            )

        version = f"{rev_major}.{rev_minor}"
        logger.debug("Detected %s v%s for %s", fmt, version, file.name)
        return fmt, version

    @staticmethod
    @lru_cache(maxsize=8)
    def _load_schema(fmt: str, version: str) -> xmlschema.XMLSchema:
        """Load and cache the compiled XSD schema for a format+version pair."""
        # Find best matching schema — try exact major.minor, then major only
        major = version.split(".")[0]
        key = (fmt, version)
        if key not in _SCHEMA_CATALOG:
            key = (fmt, major + ".0")
        if key not in _SCHEMA_CATALOG:
            # Fall back to latest known version for this format
            candidates = [k for k in _SCHEMA_CATALOG if k[0] == fmt]
            if not candidates:
                raise ValueError(f"No XSD schema available for format '{fmt}'")
            key = sorted(candidates, reverse=True)[0]

        xsd_path = _SCHEMA_CATALOG[key]

        # Handle OpenDRIVE fallback (dynamic lookup)
        if str(xsd_path) == "__opendrive_fallback__":
            xsd_path = _find_opendrive_xsd()

        if not xsd_path.exists():
            raise FileNotFoundError(
                f"XSD schema not found at {xsd_path} — is the OMB submodule initialized?"
            )

        logger.info("Loading XSD schema: %s", xsd_path.name)
        return xmlschema.XMLSchema(str(xsd_path))
