"""LLM enricher — main entry point.

Usage:
    # Evaluate all assets (no modification)
    python -m metadata_enricher evaluate examples/assets

    # Enrich a single asset's metadata (writes enriched copy)
    python -m metadata_enricher enrich examples/assets/SCEN-95B774BAC0A9

    # Pipeline integration (called by pipeline)
    python -m metadata_enricher enrich --output-path <path> --asset-type <type> <asset_dir>
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .analyzer import analyze_asset
from .enricher import enrich_hdmap, enrich_scenario
from .vocabulary import extract_vocabulary

logger = logging.getLogger(__name__)

OMB_ARTIFACTS = Path("submodules/ontology-management-base/artifacts")


def evaluate(assets_dir: Path) -> dict:
    """Evaluate metadata completeness across all assets and estimate LLM enrichment impact."""
    results = {"assets": {}, "summary": {}}
    asset_folders = sorted(
        [d for d in assets_dir.iterdir() if d.is_dir()],
    )

    for folder in asset_folders:
        meta_dir = folder / "metadata"
        if not meta_dir.exists():
            continue

        for meta_file in sorted(meta_dir.glob("*.json")):
            if meta_file.suffix != ".json" or meta_file.name.endswith(".bjson"):
                continue

            asset_type = meta_file.stem  # "hdmap" or "scenario"
            with open(meta_file) as f:
                metadata = json.load(f)

            # Find the source asset file
            sim_dir = folder / "simulation-data"
            source_file = _find_source_file(sim_dir, folder, asset_type)

            if source_file:
                signals = analyze_asset(source_file)
            else:
                signals = {"file_name": folder.name, "file_type": "unknown"}
                logger.warning("No source file found for %s", folder.name)

            # Load SHACL vocabulary
            shacl_path = OMB_ARTIFACTS / asset_type / f"{asset_type}.shacl.ttl"
            if shacl_path.exists():
                vocabulary = extract_vocabulary(shacl_path)
            else:
                vocabulary = {"enums": {}, "properties": {}}
                logger.warning("SHACL not found: %s", shacl_path)

            # Get existing fields
            prefix = asset_type
            existing = _get_existing_fields(metadata, prefix)

            # Run enrichment
            if asset_type == "scenario":
                enrichment = enrich_scenario(signals, existing, vocabulary)
            else:
                enrichment = enrich_hdmap(signals, existing, vocabulary)

            asset_key = f"{folder.name}/{asset_type}"
            results["assets"][asset_key] = {
                "source_file": str(source_file) if source_file else None,
                "existing_fields": list(existing.keys()),
                "enriched_fields": enrichment["fields"],
                "confidence": enrichment["confidence"],
                "signals_used": {
                    k: v
                    for k, v in signals.items()
                    if k not in ("parameters", "world_positions_sample", "action_types")
                },
            }

    # Build summary
    for asset_type in ["scenario", "hdmap"]:
        type_assets = {
            k: v for k, v in results["assets"].items() if k.endswith(f"/{asset_type}")
        }
        if not type_assets:
            continue

        field_fill_counts: dict[str, int] = {}
        for asset_data in type_assets.values():
            for field in asset_data["enriched_fields"]:
                if asset_data["enriched_fields"][field] is not None:
                    field_fill_counts[field] = field_fill_counts.get(field, 0) + 1

        results["summary"][asset_type] = {
            "total_assets": len(type_assets),
            "fields_enriched": {
                field: f"{count}/{len(type_assets)}"
                for field, count in sorted(field_fill_counts.items())
            },
        }

    return results


def enrich_single(
    asset_dir: Path,
    asset_type: str | None = None,
    output_path: Path | None = None,
    source_dir: Path | None = None,
) -> dict:
    """Enrich metadata for a single asset.

    Returns the enriched metadata dict with new fields merged in.
    """
    meta_dir = asset_dir / "metadata"

    if asset_type is None:
        # Auto-detect
        if (meta_dir / "hdmap.json").exists():
            asset_type = "hdmap"
        elif (meta_dir / "scenario.json").exists():
            asset_type = "scenario"
        else:
            raise FileNotFoundError(f"No metadata found in {meta_dir}")

    meta_file = meta_dir / f"{asset_type}.json"
    with open(meta_file) as f:
        metadata = json.load(f)

    # Find source file — check source_dir first (pipeline passes the original
    # input directory), then fall back to simulation-data/ (post-processed assets)
    source_file = None
    if source_dir:
        source_file = _find_source_file(source_dir, source_dir, asset_type)
    if not source_file:
        sim_dir = asset_dir / "simulation-data"
        source_file = _find_source_file(sim_dir, asset_dir, asset_type)
    signals = analyze_asset(source_file) if source_file else {}

    # Load vocabulary
    shacl_path = OMB_ARTIFACTS / asset_type / f"{asset_type}.shacl.ttl"
    vocabulary = (
        extract_vocabulary(shacl_path)
        if shacl_path.exists()
        else {"enums": {}, "properties": {}}
    )

    existing = _get_existing_fields(metadata, asset_type)

    if asset_type == "scenario":
        enrichment = enrich_scenario(signals, existing, vocabulary)
    else:
        enrichment = enrich_hdmap(signals, existing, vocabulary)

    # Merge enriched fields into metadata
    enriched_metadata = _merge_enrichment(metadata, enrichment["fields"], asset_type)

    # Write output
    if output_path:
        out_file = output_path
    else:
        out_file = meta_dir / f"{asset_type}_enriched.json"

    with open(out_file, "w") as f:
        json.dump(enriched_metadata, f, indent=2, ensure_ascii=False)

    # Write provenance sidecar for downstream consumers (e.g. wizard)
    provenance = _build_provenance(
        enrichment["fields"],
        enrichment["confidence"],
        asset_dir.name,
        asset_type,
    )
    provenance_file = out_file.parent / f"{out_file.stem}_provenance.json"
    with open(provenance_file, "w") as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)

    logger.info(
        "Enriched %d fields for %s → %s (provenance → %s)",
        len(enrichment["fields"]),
        asset_dir.name,
        out_file,
        provenance_file,
    )

    return {
        "enriched_fields": enrichment["fields"],
        "confidence": enrichment["confidence"],
        "output": str(out_file),
    }


def _build_provenance(
    fields: dict,
    confidence: dict[str, str],
    asset_name: str,
    asset_type: str,
    *,
    default_method: str = "rule-based-inference",
    methods: dict[str, str] | None = None,
) -> dict:
    """Build a provenance sidecar describing which fields were enriched and how."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    try:
        tool_version = pkg_version("sl-5-8-asset-tools")
    except PackageNotFoundError:
        tool_version = "0.0.0-dev"

    methods = methods or {}
    field_records = {}
    for field_name, value in fields.items():
        if value is None:
            continue
        field_records[field_name] = {
            "method": methods.get(field_name, default_method),
            "confidence": confidence.get(field_name, "medium"),
        }

    return {
        "assetName": asset_name,
        "assetType": asset_type,
        "tool": {
            "name": "sl-5-8-asset-tools/metadata_enricher",
            "version": tool_version,
        },
        "fields": field_records,
    }


def _find_source_file(sim_dir: Path, asset_dir: Path, asset_type: str) -> Path | None:
    """Find the source simulation file."""
    if sim_dir.exists():
        ext = ".xodr" if asset_type == "hdmap" else ".xosc"
        for f in sim_dir.glob(f"*{ext}"):
            return f

    # Fallback: search input directories
    for pattern in ["**/*.xodr", "**/*.xosc"]:
        ext_match = ".xodr" if asset_type == "hdmap" else ".xosc"
        for f in asset_dir.glob(pattern):
            if f.suffix == ext_match:
                return f

    return None


def _get_existing_fields(metadata: dict, prefix: str) -> dict:
    """Extract already-filled fields from metadata."""
    domain_spec = metadata.get(f"{prefix}:hasDomainSpecification", {})
    filled = {}

    for section_key, section_data in domain_spec.items():
        if section_key.startswith("@"):
            continue
        # Handle list sections (e.g. scenario:hasContent is [Content, Tag])
        items = (
            section_data
            if isinstance(section_data, list)
            else [section_data]
            if isinstance(section_data, dict)
            else []
        )
        for item in items:
            if not isinstance(item, dict):
                continue
            for k, v in item.items():
                if k.startswith("@"):
                    continue
                if v is not None and v != "" and v != [] and v != {}:
                    filled[k] = v

    return filled


def _merge_enrichment(metadata: dict, enriched_fields: dict, prefix: str) -> dict:
    """Merge enriched fields into the metadata JSON-LD structure."""
    import copy

    result = copy.deepcopy(metadata)
    domain_spec = result.get(f"{prefix}:hasDomainSpecification", {})

    # Field → section mapping
    content_fields = {
        "abstractionLevel",
        "aim",
        "controllers",
        "country",
        "criticalityFactors",
        "customCommands",
        "entityTypes",
        "movementDescription",
        "scenarioCategory",
        "sunAzimuth",
        "timeDate",
        "usedStandardFunctions",
        "weatherSummary",
        "roadTypes",
        "laneTypes",
        "levelOfDetail",
        "trafficDirection",
    }
    quantity_fields = {
        "numberTrafficObjects",
        "permanentTrafficObjects",
        "temporaryTrafficObjects",
    }
    data_source_fields = {
        "sourceType",
        "sourceDescription",
        "calibration",
        "measurementSystem",
        "usedDataSources",
    }
    quality_fields = {
        "accuracyLaneModel2d",
        "accuracyLaneModelHeight",
        "accuracyObjects",
        "accuracySignals",
        "precision",
        "rangeOfModeling",
    }

    section_map = {
        f"{prefix}:hasContent": content_fields,
        f"{prefix}:hasQuantity": quantity_fields,
        f"{prefix}:hasDataSource": data_source_fields,
        f"{prefix}:hasQuality": quality_fields,
    }

    for section_key, field_set in section_map.items():
        raw_section = domain_spec.get(section_key, {})

        # Handle list sections (e.g. scenario:hasContent can be a union list)
        is_list = isinstance(raw_section, list)
        if is_list:
            # Find the primary content dict (matching the domain @type)
            target_type = f"{prefix}:Content" if "Content" in section_key else None
            section = None
            for item in raw_section:
                if isinstance(item, dict):
                    if target_type and item.get("@type") == target_type:
                        section = item
                        break
            if section is None and raw_section:
                section = raw_section[0] if isinstance(raw_section[0], dict) else {}
            if section is None:
                section = {}
        elif isinstance(raw_section, dict):
            section = raw_section
        else:
            continue

        has_new_fields = False
        for field_name, value in enriched_fields.items():
            if field_name in field_set and value is not None:
                section[field_name] = value
                has_new_fields = True

        if has_new_fields:
            if section_key not in domain_spec:
                # Derive @type from section key (e.g. hdmap:hasDataSource → hdmap:DataSource)
                type_name = section_key.split(":")[1].replace("has", "")
                section["@type"] = f"{prefix}:{type_name}"
                domain_spec[section_key] = section
            elif not is_list:
                # For dict sections, write back (list items are mutated in-place)
                domain_spec[section_key] = section

    # Normalize legacy formatType ("ASAM OpenSCENARIO" → XML/DSL based on version)
    _normalize_format_type(domain_spec, prefix)

    return result


def _normalize_format_type(domain_spec: dict, prefix: str) -> None:
    """Normalize legacy 'ASAM OpenSCENARIO' formatType to XML or DSL variant.

    Since January 2024, ASAM split the standard into 'ASAM OpenSCENARIO XML'
    (v1.x) and 'ASAM OpenSCENARIO DSL' (v2.x). Infers the correct suffix
    from the version field when the generic name is found.
    """
    format_section = domain_spec.get(f"{prefix}:hasFormat")
    if not isinstance(format_section, dict):
        return

    format_type = format_section.get("formatType", "")
    if format_type != "ASAM OpenSCENARIO":
        return

    version = str(format_section.get("version", ""))
    major = version.split(".")[0] if version else ""

    if major.isdigit() and int(major) >= 2:
        format_section["formatType"] = "ASAM OpenSCENARIO DSL"
    else:
        # Default to XML for v1.x or when version is unclear
        format_section["formatType"] = "ASAM OpenSCENARIO XML"

    logger.info(
        "Normalized formatType: 'ASAM OpenSCENARIO' → '%s' (version %s)",
        format_section["formatType"],
        version or "unknown",
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    parser = argparse.ArgumentParser(
        description="LLM-based metadata enrichment for simulation assets"
    )
    sub = parser.add_subparsers(dest="command")

    eval_p = sub.add_parser("evaluate", help="Evaluate metadata completeness")
    eval_p.add_argument("assets_dir", type=Path, help="Path to assets directory")

    enrich_p = sub.add_parser("enrich", help="Enrich a single asset")
    enrich_p.add_argument("asset_dir", type=Path, help="Path to asset directory")
    enrich_p.add_argument("--asset-type", choices=["hdmap", "scenario"])
    enrich_p.add_argument("--output-path", type=Path)
    enrich_p.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing the original source file (pipeline mode)",
    )

    args = parser.parse_args()

    if args.command == "evaluate":
        results = evaluate(args.assets_dir)
        report_path = args.assets_dir / "enrichment_evaluation.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(json.dumps(results["summary"], indent=2))
        print(f"\nFull report: {report_path}")
    elif args.command == "enrich":
        result = enrich_single(
            args.asset_dir, args.asset_type, args.output_path, args.source_dir
        )
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
