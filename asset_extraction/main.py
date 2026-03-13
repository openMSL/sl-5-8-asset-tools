from pathlib import Path
from zipfile import ZipFile
from time import perf_counter

from utils.log_config import is_debug_logging, setup_logging
from utils.pipeline_reporting import (
    PipelineReporter,
    get_pipeline_name,
    get_stage_label,
    summarize_stage_failure,
    summarize_stage_success,
)
from utils.cid import compute_file_cid
from utils.http import download_or_get_file
from utils.json import write_json
from utils.subprocess import run_command, CommandError
from utils.input_manifest import load_input_file, load_referenced_artifacts
import argparse
import hashlib
import json
import os
import shutil
import logging

# configure logging once for the entire application
setup_logging(logging.DEBUG if is_debug_logging() else logging.INFO)
logger = logging.getLogger(__name__)

asset_types = {"xodr": "hdmap", "xosc": "scenario", "3dmodel": "environment-model"}


# load configurations depending on asset type
def get_configs(config_dir: Path, asset_file: Path) -> tuple[list, dict]:
    """Return (configs, source_filenames) where source_filenames maps index to filename."""
    # get asset extension
    asset_type_extension = get_asset_type_extension(asset_file)

    # load process.json
    process_file = config_dir / "process.json"
    if not process_file.exists():
        raise FileNotFoundError(f"config file {process_file} not exists")
    with process_file.open("r") as file:
        config_process = json.load(file)

    # filter for asset_type
    config_files = []
    for config in config_process.get("config_files", []):
        enabled = config.get("enable", False)
        if enabled is True:
            if "extensions" in config:
                if asset_type_extension in config["extensions"]:
                    config_files.append(config["filename"])
            else:
                config_files.append(config["filename"])

    # load configs
    configs = []
    source_filenames = {}
    for index, filename in enumerate(config_files):
        config_file = config_dir / filename
        if not config_file.exists():
            raise FileNotFoundError(f"config file {config_file} not exists")

        with (config_dir / filename).open("r") as file:
            configs.append(json.load(file))
            source_filenames[index] = filename

    return configs, source_filenames


# replace placeholders in file path
def replace_file_pattern(
    filepath: str,
    path: Path,
    sub_path: Path,
    asset_name: str,
    asset_path: Path,
    asset_type: str,
) -> str:
    updated_string = filepath.replace(r"{path}", str(path))
    updated_string = updated_string.replace(r"{sub_path}", str(sub_path))
    updated_string = updated_string.replace(r"{name}", asset_name)
    updated_string = updated_string.replace(r"{asset_path}", str(asset_path))
    updated_string = updated_string.replace(r"{asset_type}", asset_type)
    if not is_url(Path(updated_string)):
        filename = Path(updated_string)
        filename = filename.as_posix()
        return filename
    else:
        return updated_string


# create params for script calls
def create_script_params(
    script_config: dict, asset_file: Path, output_dir: Path
) -> list:
    # prepare script path
    script_path = Path(script_config["params"]["call"])

    # prepare output path
    if not output_dir.is_absolute():  # is no absolute path
        output_dir = output_dir.resolve()  # convert to absolute
    sub_path = Path(script_config["data folder"])

    # prepare asset name
    asset_name = asset_file.stem  # remove extension
    asset_path = asset_file.parent

    # setup script params
    script_call = []
    script_call.append(script_config["environment type"])

    # disables frozen standard modules so that Python loads them from the hard disk.
    # This can be useful if you are working on the Python interpreter itself or testing changes to the standard modules
    # and do not want to use a frozen version.
    if script_config["environment type"] == "python":
        script_call.append("-X")
        script_call.append("frozen_modules=off")
        script_call.append("-m")  # as module
    script_call.append(script_path)

    asset_type = get_asset_type(get_asset_type_extension(asset_file))

    # input
    if "input" in script_config["params"]:
        for name, value in script_config["params"]["input"].items():
            if name:
                script_call.append(name)
            updated_string = replace_file_pattern(
                value, output_dir, sub_path, asset_name, asset_path, asset_type
            )
            script_call.append(updated_string)
    else:
        script_call.append(asset_file)

    # output
    if "output" in script_config["params"]:
        for name, value in script_config["params"]["output"].items():
            script_call.append(name)
            updated_string = replace_file_pattern(
                value, output_dir, sub_path, asset_name, asset_path, asset_type
            )
            script_call.append(updated_string)
            if not is_url(Path(updated_string)):
                directory = Path(updated_string).parent
                directory.mkdir(parents=True, exist_ok=True)

    # additional parameters
    if "additional" in script_config["params"]:
        for name, value in script_config["params"]["additional"].items():
            script_call.append(name)
            if value:
                updated_string = replace_file_pattern(
                    value, output_dir, sub_path, asset_name, asset_path, asset_type
                )
                script_call.append(updated_string)

    return script_call


# Combine parameters and call sub script
def execute_script(script_config: dict, asset_file: Path, output_dir: Path):

    # create script parameters
    script_call = create_script_params(script_config, asset_file, output_dir)

    # run sub script
    project_root = Path(__file__).parent.parent
    return run_command(
        cmd=script_call,
        name=script_config["name"],
        cwd=str(project_root),
        log_output=False,
    )


def _format_reference(ref: dict) -> dict:
    """Format a referenced artifact link from input manifest JSON-LD
    to match the output manifest format used by jsonLD_creator."""
    cat = ref.get("hasCategory", ref.get("manifest:hasCategory", {}))
    role = ref.get("hasAccessRole", ref.get("manifest:hasAccessRole", {}))
    meta = ref.get("hasFileMetadata", ref.get("manifest:hasFileMetadata", {}))

    cat_id = cat.get("@id", "") if isinstance(cat, dict) else str(cat)
    role_id = role.get("@id", "") if isinstance(role, dict) else str(role)

    out_meta = {"@type": "manifest:FileMetadata"}
    for key in ("filePath", "manifest:filePath"):
        if key in meta:
            val = meta[key]
            out_meta["filePath"] = (
                val.get("@value", val) if isinstance(val, dict) else val
            )
            break
    for key in ("mimeType", "manifest:mimeType"):
        if key in meta:
            out_meta["mimeType"] = meta[key]
            break
    for key in ("cid", "manifest:cid"):
        if key in meta:
            out_meta["cid"] = meta[key]
            break
    for key in ("filename", "manifest:filename"):
        if key in meta:
            out_meta["filename"] = meta[key]
            break

    return {
        "@type": "manifest:Link",
        "hasAccessRole": {"@type": "manifest:AccessRole", "@id": role_id},
        "hasCategory": {"@type": "manifest:Category", "@id": cat_id},
        "manifest:hasFileMetadata": out_meta,
    }


# create zip file from folder
def create_zip(output_dir: Path, zip_filename: Path):
    # Use a fixed timestamp for all entries so the archive is deterministic.
    source_mtime = os.environ.get("SL58_SOURCE_MTIME")
    if source_mtime:
        from datetime import datetime

        dt = datetime.fromtimestamp(int(source_mtime))
        fixed_date_time = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    else:
        fixed_date_time = None

    with ZipFile(zip_filename, "w") as zipf:
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file():
                file_local = file_path.relative_to(output_dir)
                if fixed_date_time:
                    from zipfile import ZipInfo

                    info = ZipInfo(file_local.as_posix(), date_time=fixed_date_time)
                    info.compress_type = zipf.compression
                    zipf.writestr(info, file_path.read_bytes())
                else:
                    zipf.write(file_path, file_local)


def compute_input_hash(input_dir: Path) -> str:
    """Compute a stable SHA-256 hash over all input files (sorted by name)."""
    sha = hashlib.sha256()
    for path in sorted(input_dir.rglob("*")):
        if path.is_file():
            sha.update(path.name.encode("utf-8"))
            sha.update(path.read_bytes())
    return sha.hexdigest()


# get asset type extension
def get_asset_type_extension(asset_file: Path) -> str:
    asset_type = asset_file.suffix.lstrip(".")  # Get file extension without the dot
    if asset_type == "zip" or asset_type == "7z":
        asset_type = "3dmodel"
    return asset_type


# get asset type
def get_asset_type(asset_type: Path) -> str:
    if asset_type in asset_types:
        return asset_types[asset_type]

    raise FileNotFoundError(f"asset type not found {asset_type}")


# Return the first filename where type == "Asset" or raise if not found
def get_asset_filename(json_path: Path) -> Path:
    data = load_input_file(json_path)

    for entry in data:
        if entry.get("type") == "Asset":
            filename = entry.get("filename")
            if not isinstance(filename, str) or not filename:
                raise ValueError("Asset entry found but 'filename' is missing/invalid")
            return Path(filename)

    raise ValueError("No entry with type == 'Asset' found")


# get asset file from frontend json
def get_asset_file(uploadedFile: Path) -> Path:
    # get from xml
    asset_file = get_asset_filename(uploadedFile)

    return download_or_get_file(asset_file, uploadedFile.parent)


def main():
    # parse arguments
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="extracted from asset and user infos all extractor/creator scripts are called to create an asset archive.",
    )
    parser.add_argument(
        "filename",
        type=str,
        help="filename of input_manifest.json or uploadedFiles.json",
    )
    parser.add_argument(
        "-config", type=str, required=True, help="config path for sub tools."
    )
    parser.add_argument(
        "-out", type=str, required=True, help="output path for asset archive."
    )
    parser.add_argument(
        "-zip-dir",
        type=str,
        default="",
        help="optional output directory for the generated archive",
    )
    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir = output_dir.resolve()
    zip_dir = Path(args.zip_dir).resolve() if args.zip_dir else output_dir
    zip_dir.mkdir(parents=True, exist_ok=True)

    # determine asset type (e.g., ".xodr")
    uploaded_file = Path(args.filename)
    asset_file = get_asset_file(uploaded_file)
    if not asset_file.exists():
        raise FileNotFoundError(f"asset file {asset_file} not exists")

    # load all configs that are applicable to the asset type
    config_dir = Path(args.config)
    config_dir = config_dir.resolve()
    if not config_dir.is_dir():
        raise FileNotFoundError(f"config path {config_dir} not exists")
    applicable_scripts, source_filenames = get_configs(config_dir, asset_file)

    # create, cleanup output directory for the asset file
    asset_name = asset_file.stem
    if "." in asset_name:
        raise FileNotFoundError(f"File {asset_name} has points in name! Not supported!")

    output_sub_dir = output_dir / asset_name
    if output_sub_dir.exists():
        shutil.rmtree(output_sub_dir)
    output_sub_dir.mkdir(parents=True, exist_ok=True)

    # Deterministic mode (opt-in): hash all input files so subprocesses
    # derive reproducible UUIDs and use the source file's modification
    # time instead of "now" for generated-file timestamps.
    # Enable with SL58_DETERMINISTIC=1.
    if os.environ.get("SL58_DETERMINISTIC") == "1":
        input_hash = compute_input_hash(asset_file.parent)
        source_mtime = str(int(asset_file.stat().st_mtime))
        os.environ["SL58_INPUT_HASH"] = input_hash
        os.environ["SL58_SOURCE_MTIME"] = source_mtime
        logger.debug(
            "Deterministic mode: input_hash=%s, source_mtime=%s",
            input_hash,
            source_mtime,
        )
    else:
        os.environ.pop("SL58_INPUT_HASH", None)
        os.environ.pop("SL58_SOURCE_MTIME", None)

    project_root = Path(__file__).parent.parent
    pipeline_reporter = PipelineReporter(
        pipeline_name=get_pipeline_name(asset_file),
        total_stages=len(applicable_scripts),
        input_file=asset_file,
        output_dir=output_sub_dir,
        project_root=project_root,
    )
    pipeline_reporter.start_pipeline()

    # execute each script and collect outputs
    pipeline_started_at = perf_counter()
    for stage_index, script_config in enumerate(applicable_scripts, start=1):
        source_file = source_filenames.get(stage_index - 1, "")
        stage_label = get_stage_label(script_config, source_file)
        pipeline_reporter.start_stage(stage_index, stage_label)
        stage_started_at = perf_counter()

        try:
            result = execute_script(script_config, asset_file, output_sub_dir)
        except CommandError as exc:
            summary = summarize_stage_failure(
                script_config,
                exc.cmd,
                exc,
                project_root=project_root,
                source_filename=source_file,
            )
            pipeline_reporter.finish_stage(
                stage_index,
                stage_label,
                perf_counter() - stage_started_at,
                summary,
            )
            raise SystemExit(1) from None

        summary = summarize_stage_success(
            script_config,
            result.cmd,
            result,
            project_root=project_root,
            source_filename=source_file,
        )
        pipeline_reporter.finish_stage(
            stage_index,
            stage_label,
            perf_counter() - stage_started_at,
            summary,
        )

    # inject referenced artifacts from input manifest into output manifest
    refs = load_referenced_artifacts(uploaded_file)
    manifest_path = output_sub_dir / "manifest.json"
    if refs and manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["manifest:hasReferencedArtifacts"] = [
            _format_reference(ref) for ref in refs
        ]
        write_json(manifest_path, manifest, indentValue=2, trailing_newline=True)
        logger.info(f"Injected {len(refs)} referenced artifact(s) into manifest")

    # remove temp folder before
    temp_path = output_sub_dir / "temp"
    if temp_path.exists():
        shutil.rmtree(temp_path)

    # create a temporary archive, compute its CID, then rename it
    temp_zip_path = zip_dir / "asset.zip"
    if temp_zip_path.exists():
        temp_zip_path.unlink()
    create_zip(output_sub_dir, temp_zip_path)
    archive_cid = compute_file_cid(temp_zip_path)
    zip_filename = zip_dir / f"{archive_cid}.zip"
    if zip_filename.exists():
        zip_filename.unlink()
    temp_zip_path.replace(zip_filename)
    archive_display = zip_filename
    logger.info("[DONE ] Archive: %s", archive_display)
    pipeline_reporter.finish_pipeline(perf_counter() - pipeline_started_at)


if __name__ == "__main__":
    main()
