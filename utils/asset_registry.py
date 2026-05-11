"""Asset registry — cross-reference state shared between pipeline runs.

After each pipeline run completes, the registry records the asset's CID,
manifest path, and simulation-data file path.  Before a subsequent run
injects ``hasReferencedArtifacts``, it can look up ``__*__`` placeholders
and resolve them to real values from a previously-generated asset.

The registry is stored as ``.asset_registry.json`` in the output directory
so that batch and single-asset runs share the same state transparently.

Registry schema::

    {
      "<filename_stem>": {
        "hdmap": {
          "cid": "bafkrei...",
          "manifest_path": "MyRoad/manifest.json",
          "sim_data_path": "simulation-data/MyRoad.xodr"
        },
        "scenario": {
          "cid": "bafkrei...",
          "manifest_path": "MyRoad_scenario/manifest.json",
          "sim_data_path": "simulation-data/MyRoad.xosc"
        }
      }
    }

Placeholder mapping::

    __OPENDRIVE_ASSET_CID__  → hdmap entry["cid"]
    __OPENDRIVE_ASSET_PATH__ → hdmap entry["sim_data_path"]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REGISTRY_FILENAME = ".asset_registry.json"

# Maps placeholder tokens to registry entry keys.
_PLACEHOLDER_MAP: dict[str, tuple[str, str]] = {
    # (asset_type, entry_key)
    "__OPENDRIVE_ASSET_CID__": ("hdmap", "cid"),
    "__OPENDRIVE_ASSET_PATH__": ("hdmap", "sim_data_path"),
}

# Nested type: stem → asset_type → entry
RegistryType = dict[str, dict[str, dict[str, str]]]


def _registry_path(output_dir: Path) -> Path:
    return output_dir / REGISTRY_FILENAME


def load_registry(output_dir: Path) -> RegistryType:
    """Load the registry from *output_dir*, returning an empty dict if absent."""
    path = _registry_path(output_dir)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read asset registry %s: %s", path, exc)
        return {}


def save_registry(output_dir: Path, registry: RegistryType) -> None:
    """Atomically write the registry to *output_dir*."""
    path = _registry_path(output_dir)
    payload = json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Failed to write asset registry %s: %s", path, exc)
        tmp.unlink(missing_ok=True)


def register_asset(
    output_dir: Path,
    *,
    stem: str,
    asset_type: str,
    cid: str,
    manifest_path: str,
    sim_data_path: str,
) -> None:
    """Record a completed asset in the registry."""
    registry = load_registry(output_dir)
    registry.setdefault(stem, {})[asset_type] = {
        "cid": cid,
        "manifest_path": manifest_path,
        "sim_data_path": sim_data_path,
    }
    save_registry(output_dir, registry)
    logger.debug("Registered asset %s (type=%s, cid=%s)", stem, asset_type, cid)


def has_collision(output_dir: Path, stem: str, asset_type: str) -> bool:
    """Return True if a different asset type already occupies *stem*."""
    registry = load_registry(output_dir)
    entry = registry.get(stem, {})
    return bool(entry) and asset_type not in entry


def resolve_placeholders(
    refs: list[dict[str, Any]],
    output_dir: Path,
    *,
    current_stem: str | None = None,
) -> list[dict[str, Any]]:
    """Resolve ``__*__`` placeholders in referenced-artifact link dicts.

    Looks up the registry in *output_dir* and substitutes placeholder
    values with actual CID / path values from previously-generated assets.

    When *current_stem* is given, the resolver prefers a registry entry
    whose stem matches (e.g. scenario ``Foo.xosc`` resolves against
    hdmap ``Foo``).  Falls back to the first entry of the required type.

    Returns the (mutated) *refs* list for convenience.
    """
    registry = load_registry(output_dir)
    if not registry:
        return refs

    def _pick(asset_type: str) -> dict[str, str] | None:
        # Prefer same-stem entry
        if current_stem and current_stem in registry:
            entry = registry[current_stem].get(asset_type)
            if entry:
                return entry
        # Fall back to first entry of that type
        for stem_entries in registry.values():
            if asset_type in stem_entries:
                return stem_entries[asset_type]
        return None

    for ref in refs:
        meta = ref.get("hasFileMetadata", ref.get("manifest:hasFileMetadata", {}))

        for field in ("filePath", "manifest:filePath"):
            val = meta.get(field)
            if isinstance(val, str) and val in _PLACEHOLDER_MAP:
                asset_type, key = _PLACEHOLDER_MAP[val]
                entry = _pick(asset_type)
                if entry:
                    meta[field] = entry[key]
                    logger.info("Resolved %s → %s", val, meta[field])

        for field in ("cid", "manifest:cid"):
            val = meta.get(field)
            if isinstance(val, str) and val in _PLACEHOLDER_MAP:
                asset_type, key = _PLACEHOLDER_MAP[val]
                entry = _pick(asset_type)
                if entry:
                    meta[field] = entry[key]
                    logger.info("Resolved %s → %s", val, meta[field])

    return refs
