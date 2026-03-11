"""Resolve external asset references in an input_manifest.json.

Reads a scenario's input_manifest.json, finds hasReferencedArtifacts entries
with placeholder values (__*__), and replaces them with actual values from a
referenced asset's output manifest.json.

Usage:
    python scripts/resolve_references.py \
        examples/OpenSCENARIO/input/input_manifest.json \
        --ref-manifest examples/OpenDRIVE/output/*/manifest.json
"""

import argparse
import json
import sys
from pathlib import Path


def find_sim_data_entry(manifest: dict) -> dict | None:
    """Find the first isSimulationData artifact in a manifest."""
    for key in ("manifest:hasArtifacts", "hasArtifacts"):
        artifacts = manifest.get(key, [])
        if not isinstance(artifacts, list):
            artifacts = [artifacts]
        for art in artifacts:
            cat = art.get("hasCategory", art.get("manifest:hasCategory", {}))
            cat_id = cat.get("@id", "") if isinstance(cat, dict) else str(cat)
            if "isSimulationData" in cat_id or "SimulationData" in cat_id:
                return art
    return None


def get_file_metadata(link: dict) -> dict:
    """Extract FileMetadata from a Link node."""
    return link.get("hasFileMetadata", link.get("manifest:hasFileMetadata", {}))


def main():
    parser = argparse.ArgumentParser(description="Resolve external asset references")
    parser.add_argument("manifest", help="Path to the scenario input_manifest.json")
    parser.add_argument(
        "--ref-manifest",
        required=True,
        help="Path to the referenced asset's output manifest.json",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    ref_manifest_path = Path(args.ref_manifest)

    if not manifest_path.exists():
        print(f"[ERR] Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    if not ref_manifest_path.exists():
        print(
            f"[ERR] Reference manifest not found: {ref_manifest_path}", file=sys.stderr
        )
        sys.exit(1)

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    with ref_manifest_path.open("r", encoding="utf-8") as f:
        ref_manifest = json.load(f)

    # Extract reference values from the referenced asset's manifest
    ref_sim = find_sim_data_entry(ref_manifest)
    if not ref_sim:
        print("[ERR] No simulation data entry in reference manifest", file=sys.stderr)
        sys.exit(1)

    ref_meta = get_file_metadata(ref_sim)
    ref_path = ref_meta.get("filePath", ref_meta.get("manifest:filePath", ""))
    ref_cid = ref_meta.get("cid", ref_meta.get("manifest:cid", ""))

    if isinstance(ref_path, dict):
        ref_path = ref_path.get("@value", "")

    # Resolve placeholders in hasReferencedArtifacts
    refs = manifest.get(
        "hasReferencedArtifacts", manifest.get("manifest:hasReferencedArtifacts", [])
    )
    if not isinstance(refs, list):
        refs = [refs]

    replaced = False
    for ref in refs:
        meta = get_file_metadata(ref)
        fp = meta.get("filePath", meta.get("manifest:filePath", ""))
        cid = meta.get("cid", meta.get("manifest:cid", ""))

        if isinstance(fp, str) and fp.startswith("__") and fp.endswith("__"):
            key = "filePath" if "filePath" in meta else "manifest:filePath"
            meta[key] = ref_path
            replaced = True
        if isinstance(cid, str) and cid.startswith("__") and cid.endswith("__"):
            key = "cid" if "cid" in meta else "manifest:cid"
            meta[key] = ref_cid
            replaced = True

    if replaced:
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"[OK] Resolved references in {manifest_path}")
    else:
        print(f"[INFO] No placeholders to resolve in {manifest_path}")


if __name__ == "__main__":
    main()
