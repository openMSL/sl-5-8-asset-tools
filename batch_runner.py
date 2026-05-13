"""Batch runner — process multiple assets or review existing ones.

Subcommands
-----------
batch
    Discover all ``input_manifest.json`` files under a directory tree and run
    the full asset-extraction pipeline for each.  HD-map inputs are processed
    before scenario inputs so cross-references resolve correctly.

review
    Enrich and interactively review metadata for existing asset folders via
    the SD Creation Wizard queue UI, then re-zip any assets whose metadata
    changed.

Usage::

    # Batch-process all examples
    python -m batch_runner batch examples/

    # Review existing assets
    python -m batch_runner review examples/assets/
"""

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from utils.cid import compute_file_cid
from utils.log_config import is_debug_logging, setup_logging
from utils.subprocess import run_command, CommandError

setup_logging(logging.DEBUG if is_debug_logging() else logging.INFO)
logger = logging.getLogger(__name__)

# HD-map inputs must be processed before scenario inputs so that cross-
# references (e.g. OpenSCENARIO → OpenDRIVE) resolve correctly.
_TYPE_ORDER = {"hdmap": 0, "scenario": 1}


# ── Batch subcommand ─────────────────────────────────────────────────


def _sort_key(p: Path) -> tuple[int, str]:
    parent = p.parent.name.lower()
    order = _TYPE_ORDER.get(parent, 99)
    return (order, str(p))


def _discover_manifests(root: Path) -> list[Path]:
    """Find all ``input_manifest.json`` files under *root*, sorted hdmap-first."""
    return sorted(root.rglob("input_manifest.json"), key=_sort_key)


def run_batch(
    input_dir: Path,
    config_dir: Path,
    output_dir: Path,
    zip_dir: Path | None = None,
    pipeline_flags: list[str] | None = None,
) -> dict[str, bool]:
    """Run the pipeline for every ``input_manifest.json`` under *input_dir*.

    Returns a dict mapping manifest path → success boolean.
    """
    manifests = _discover_manifests(input_dir)
    if not manifests:
        logger.warning("No input_manifest.json files found under %s", input_dir)
        return {}

    logger.info(
        "Batch: discovered %d input manifest(s) under %s", len(manifests), input_dir
    )

    results: dict[str, bool] = {}
    for idx, manifest in enumerate(manifests, 1):
        label = str(manifest.relative_to(input_dir))
        logger.info("━━ [%d/%d] %s", idx, len(manifests), label)

        cmd = [
            sys.executable,
            "-m",
            "asset_extraction.main",
            str(manifest),
            "-config",
            str(config_dir),
            "-out",
            str(output_dir),
        ]
        if zip_dir:
            cmd += ["-zip-dir", str(zip_dir)]
        if pipeline_flags:
            cmd += pipeline_flags

        try:
            run_command(
                cmd=cmd,
                name=f"pipeline({label})",
                cwd=str(Path(__file__).parent),
                log_output=False,
            )
            results[label] = True
            logger.info("━━ [%d/%d] %s ✓", idx, len(manifests), label)
        except CommandError:
            results[label] = False
            logger.error("━━ [%d/%d] %s ✗", idx, len(manifests), label)

    succeeded = sum(1 for v in results.values() if v)
    failed = len(results) - succeeded
    logger.info(
        "Batch complete: %d succeeded, %d failed out of %d",
        succeeded,
        failed,
        len(results),
    )
    return results


# ── Review subcommand ────────────────────────────────────────────────


def _discover_asset_dirs(root: Path) -> list[Path]:
    """Find asset directories (contain ``manifest.json``) under *root*."""
    dirs = []
    for manifest in sorted(root.rglob("manifest.json")):
        asset_dir = manifest.parent
        # Must have metadata/ to be a valid asset dir
        if (asset_dir / "metadata").is_dir():
            dirs.append(asset_dir)
    return dirs


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_metadata_dir(metadata_dir: Path) -> str:
    """Return a combined hash of all JSON files in a metadata directory."""
    h = hashlib.sha256()
    for json_file in sorted(metadata_dir.glob("*.json")):
        h.update(json_file.name.encode())
        h.update(_hash_file(json_file).encode())
    return h.hexdigest()


def _create_zip(output_dir: Path, zip_path: Path) -> None:
    """Create a deterministic zip archive of *output_dir*."""
    source_mtime = os.environ.get("SL58_SOURCE_MTIME")
    if source_mtime:
        from datetime import datetime

        dt = datetime.fromtimestamp(int(source_mtime))
        fixed_date_time = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    else:
        fixed_date_time = None

    with ZipFile(zip_path, "w") as zipf:
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file():
                file_local = file_path.relative_to(output_dir)
                if fixed_date_time:
                    info = ZipInfo(file_local.as_posix(), date_time=fixed_date_time)
                    info.compress_type = zipf.compression
                    zipf.writestr(info, file_path.read_bytes())
                else:
                    zipf.write(file_path, file_local)


def _rezip_asset(asset_dir: Path, zip_dir: Path) -> Path | None:
    """Re-create the CID.zip for a single asset directory.

    Returns the new zip path, or None on error.
    """
    temp_zip = zip_dir / "asset.zip"
    if temp_zip.exists():
        temp_zip.unlink()

    _create_zip(asset_dir, temp_zip)
    archive_cid = compute_file_cid(temp_zip)
    zip_filename = zip_dir / f"{archive_cid}.zip"

    if zip_filename.exists():
        zip_filename.unlink()
    temp_zip.replace(zip_filename)

    logger.info("Re-zipped %s → %s", asset_dir.name, zip_filename.name)
    return zip_filename


def run_review(
    assets_dir: Path,
    config_dir: Path,
    zip_dir: Path | None = None,
) -> dict[str, str]:
    """Enrich, review, and optionally re-zip assets under *assets_dir*.

    Returns a dict mapping asset name → status (enriched/unchanged/error).
    """
    asset_dirs = _discover_asset_dirs(assets_dir)
    if not asset_dirs:
        logger.warning("No asset directories found under %s", assets_dir)
        return {}

    effective_zip_dir = zip_dir or assets_dir
    logger.info("Review: discovered %d asset(s) under %s", len(asset_dirs), assets_dir)

    # Snapshot metadata hashes before enrichment
    pre_hashes: dict[str, str] = {}
    for asset_dir in asset_dirs:
        meta_dir = asset_dir / "metadata"
        pre_hashes[asset_dir.name] = _hash_metadata_dir(meta_dir)

    # Phase 1: Enrich all assets
    logger.info("Phase 1: Enriching metadata for %d assets...", len(asset_dirs))
    for idx, asset_dir in enumerate(asset_dirs, 1):
        logger.info("  [%d/%d] Enriching %s", idx, len(asset_dirs), asset_dir.name)
        _enrich_asset(asset_dir, config_dir)

    # Phase 2: Wizard review (queue mode)
    logger.info("Phase 2: Opening wizard for interactive review...")
    _run_wizard_queue(asset_dirs, config_dir)

    # Phase 3: Detect changes and re-zip
    logger.info("Phase 3: Checking for changes and re-zipping...")
    results: dict[str, str] = {}
    for asset_dir in asset_dirs:
        meta_dir = asset_dir / "metadata"
        post_hash = _hash_metadata_dir(meta_dir)

        if post_hash != pre_hashes[asset_dir.name]:
            logger.info("  %s: metadata changed — re-zipping", asset_dir.name)
            new_zip = _rezip_asset(asset_dir, effective_zip_dir)
            results[asset_dir.name] = (
                f"updated → {new_zip.name}" if new_zip else "error"
            )
        else:
            logger.info("  %s: unchanged", asset_dir.name)
            results[asset_dir.name] = "unchanged"

    changed = sum(1 for v in results.values() if v.startswith("updated"))
    logger.info(
        "Review complete: %d changed, %d unchanged out of %d",
        changed,
        len(results) - changed,
        len(results),
    )
    return results


def _enrich_asset(asset_dir: Path, config_dir: Path) -> None:
    """Run llm_enricher on a single asset directory."""
    # Detect asset type from metadata
    meta_dir = asset_dir / "metadata"
    asset_type = None
    for candidate in ("hdmap", "scenario", "environment-model"):
        if (meta_dir / f"{candidate}.json").exists():
            asset_type = candidate
            break

    if not asset_type:
        logger.warning(
            "Cannot detect asset type for %s — skipping enrichment", asset_dir.name
        )
        return

    cmd = [
        sys.executable,
        "-m",
        "llm_enricher.main",
        "enrich",
        str(asset_dir),
        "--asset-type",
        asset_type,
        "--output-path",
        str(meta_dir / f"{asset_type}.json"),
    ]
    try:
        run_command(
            cmd=cmd,
            name=f"enrich({asset_dir.name})",
            cwd=str(Path(__file__).parent),
            log_output=False,
        )
    except CommandError:
        logger.warning("Enrichment failed for %s — continuing", asset_dir.name)


def _run_wizard_queue(asset_dirs: list[Path], config_dir: Path) -> None:
    """Open the wizard with a queue of all assets for interactive review.

    Falls back to per-asset wizard if queue API is not available.
    """
    if not os.environ.get("WIZARD_ENABLED", "").lower() == "true":
        logger.info(
            "Wizard not enabled (set WIZARD=true) — skipping interactive review"
        )
        return

    from wizard_caller.api_client import (
        WizardAPIError,
        ensure_wizard_running,
        open_wizard_browser,
    )

    api_url = os.environ.get("WIZARD_API_URL") or "http://localhost:3007"
    resolved_url = ensure_wizard_running(api_url)
    if not resolved_url:
        logger.warning("Wizard API not available — skipping interactive review")
        return

    # Try queue mode first (POST /session/queue)
    if _try_queue_mode(resolved_url, asset_dirs, config_dir):
        return

    # Fallback: process one at a time
    logger.info("Queue API not available — falling back to per-asset wizard")
    for idx, asset_dir in enumerate(asset_dirs, 1):
        meta_dir = asset_dir / "metadata"
        asset_type = _detect_asset_type(meta_dir)
        if not asset_type:
            continue

        shacl_path = (
            Path("submodules/ontology-management-base/artifacts")
            / asset_type
            / f"{asset_type}.shacl.ttl"
        )
        jsonld_path = meta_dir / f"{asset_type}.json"
        provenance_path = meta_dir / f"{asset_type}_provenance.json"

        if not shacl_path.exists() or not jsonld_path.exists():
            continue

        logger.info("  [%d/%d] Reviewing %s", idx, len(asset_dirs), asset_dir.name)
        try:
            open_wizard_browser(
                api_url=resolved_url,
                shacl_path=shacl_path,
                jsonld_path=jsonld_path,
                output_path=jsonld_path,
                provenance_path=provenance_path if provenance_path.exists() else None,
                asset_name=asset_dir.name,
            )
        except WizardAPIError as exc:
            logger.warning("Wizard failed for %s: %s", asset_dir.name, exc)


def _try_queue_mode(api_url: str, asset_dirs: list[Path], config_dir: Path) -> bool:
    """Attempt to use the batch queue API. Returns True if successful."""
    import requests
    import webbrowser

    queue_url = f"{api_url.rstrip('/')}/session/queue"

    sessions = []
    for asset_dir in asset_dirs:
        meta_dir = asset_dir / "metadata"
        asset_type = _detect_asset_type(meta_dir)
        if not asset_type:
            continue

        shacl_path = (
            Path("submodules/ontology-management-base/artifacts")
            / asset_type
            / f"{asset_type}.shacl.ttl"
        )
        jsonld_path = meta_dir / f"{asset_type}.json"
        provenance_path = meta_dir / f"{asset_type}_provenance.json"

        if not shacl_path.exists() or not jsonld_path.exists():
            continue

        session_data: dict = {
            "assetName": asset_dir.name,
            "assetType": asset_type,
            "outputPath": str(jsonld_path.resolve()),
        }

        # Read file contents for the queue payload
        session_data["shaclContent"] = shacl_path.read_text(encoding="utf-8")
        session_data["jsonLdContent"] = jsonld_path.read_text(encoding="utf-8")
        if provenance_path.exists():
            session_data["provenanceContent"] = provenance_path.read_text(
                encoding="utf-8"
            )

        sessions.append(session_data)

    if not sessions:
        return False

    try:
        resp = requests.post(queue_url, json={"sessions": sessions}, timeout=30)
        if resp.status_code != 200:
            logger.debug("Queue API returned %d — not available", resp.status_code)
            return False
    except (requests.ConnectionError, requests.Timeout):
        return False

    logger.info("Created wizard queue with %d sessions", len(sessions))

    frontend_url = os.environ.get("WIZARD_FRONTEND_URL") or "http://localhost:5174"
    webbrowser.open(frontend_url)

    logger.info(
        "Waiting for you to review all assets in the browser...\n"
        "  → Review each asset and click 'Export' or 'Next' to proceed.\n"
        "  → The pipeline will continue when all assets are reviewed."
    )

    # Poll queue status
    status_url = f"{api_url.rstrip('/')}/session/queue/status"
    import time

    timeout = 3600  # 1 hour for batch review
    elapsed = 0
    poll_interval = 3

    while elapsed < timeout:
        try:
            resp = requests.get(status_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("allExported"):
                    logger.info("All %d assets reviewed ✓", len(sessions))
                    return True
                current = data.get("current", 0) + 1
                total = data.get("total", len(sessions))
                completed = data.get("completed", 0)
                logger.debug(
                    "Queue progress: %d/%d (completed: %d)", current, total, completed
                )
        except (requests.ConnectionError, requests.Timeout):
            pass

        time.sleep(poll_interval)
        elapsed += poll_interval

    logger.warning("Wizard queue timed out after %ds", timeout)
    return True  # Still consider it done — user may have exported some


def _detect_asset_type(meta_dir: Path) -> str | None:
    """Detect asset type from files in metadata directory."""
    for candidate in ("hdmap", "scenario", "environment-model"):
        if (meta_dir / f"{candidate}.json").exists():
            return candidate
    return None


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="batch_runner",
        description="Batch-process or review multiple assets",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # batch subcommand
    batch_parser = subparsers.add_parser(
        "batch",
        help="Run pipeline for all input manifests under a directory",
    )
    batch_parser.add_argument(
        "input_dir",
        type=str,
        help="Root directory to search for input_manifest.json files",
    )
    batch_parser.add_argument(
        "-config",
        type=str,
        default="configs",
        help="Config directory (default: configs)",
    )
    batch_parser.add_argument(
        "-out",
        type=str,
        default="examples/assets",
        help="Output directory for generated assets",
    )
    batch_parser.add_argument(
        "-zip-dir",
        type=str,
        default=None,
        help="Output directory for CID.zip archives (default: same as -out)",
    )
    batch_parser.add_argument(
        "pipeline_flags",
        nargs="*",
        default=[],
        help="Additional flags passed to asset_extraction.main",
    )

    # review subcommand
    review_parser = subparsers.add_parser(
        "review",
        help="Enrich and review existing assets via wizard",
    )
    review_parser.add_argument(
        "assets_dir",
        type=str,
        help="Directory containing generated asset folders",
    )
    review_parser.add_argument(
        "-config",
        type=str,
        default="configs",
        help="Config directory (default: configs)",
    )
    review_parser.add_argument(
        "-zip-dir",
        type=str,
        default=None,
        help="Output directory for re-generated CID.zip archives",
    )

    args = parser.parse_args()

    if args.command == "batch":
        results = run_batch(
            input_dir=Path(args.input_dir).resolve(),
            config_dir=Path(args.config).resolve(),
            output_dir=Path(args.out).resolve(),
            zip_dir=Path(args.zip_dir).resolve() if args.zip_dir else None,
            pipeline_flags=args.pipeline_flags or None,
        )
        if any(not v for v in results.values()):
            sys.exit(1)

    elif args.command == "review":
        results = run_review(
            assets_dir=Path(args.assets_dir).resolve(),
            config_dir=Path(args.config).resolve(),
            zip_dir=Path(args.zip_dir).resolve() if args.zip_dir else None,
        )


if __name__ == "__main__":
    main()
