from pathlib import Path
from zipfile import ZipFile
from utils.log_config import setup_logging
from utils.http import download_or_get_file
from utils.subprocess import run_command
from utils.input_manifest import load_input_file
import argparse
import json
import shutil
import logging

# configure logging once for the entire application
DEBUG = False
setup_logging(logging.DEBUG if DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

asset_types = {"xodr": "hdmap", "xosc": "scenario", "3dmodel": "environment-model"}


# load configurations depending on asset type
def get_configs(config_dir: Path, asset_file: Path) -> list:
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
    for filename in config_files:
        config_file = config_dir / filename
        if not config_file.exists():
            raise FileNotFoundError(f"config file {config_file} not exists")

        with (config_dir / filename).open("r") as file:
            configs.append(json.load(file))

    return configs


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
    if "https:" not in updated_string:
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
            # TODO create folder here or in sub script?
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
    run_command(cmd=script_call, name=script_config["name"], cwd=str(project_root))


# create zip file from folder
def create_zip(output_dir: Path, zip_filename: Path):
    with ZipFile(zip_filename, "w") as zipf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                filename = str(file_path.name)
                if filename == "asset.zip":
                    continue
                file_local = file_path.relative_to(output_dir)
                zipf.write(file_path, file_local)


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
    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir = output_dir.resolve()

    # determine asset type (e.g., ".xodr")
    uploaded_file = Path(args.filename)
    asset_file = get_asset_file(uploaded_file)
    if not asset_file.exists():
        raise FileNotFoundError(f"asset file {asset_file} not exists")
    logger.info(f"asset file {asset_file}")

    # load all configs that are applicable to the asset type
    config_dir = Path(args.config)
    config_dir = config_dir.resolve()
    if not config_dir.is_dir():
        raise FileNotFoundError(f"config path {config_dir} not exists")
    applicable_scripts = get_configs(config_dir, asset_file)

    # create, cleanup output directory for the asset file
    asset_name = asset_file.stem
    if "." in asset_name:
        raise FileNotFoundError(f"File {asset_name} has points in name! Not supported!")

    output_sub_dir = output_dir / asset_name
    if output_sub_dir.exists():
        shutil.rmtree(output_sub_dir)
    output_sub_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"output path {output_sub_dir}")

    # execute each script and collect outputs
    for script_config in applicable_scripts:
        execute_script(script_config, asset_file, output_sub_dir)

    # remove temp folder before
    temp_path = output_sub_dir / "temp"
    shutil.rmtree(temp_path)

    # create a zip file of the output directory
    zip_filename = output_sub_dir / f"asset.zip"
    create_zip(output_sub_dir, zip_filename)


if __name__ == "__main__":
    main()
