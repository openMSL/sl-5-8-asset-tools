from pathlib import Path
from multiformats import CID
from multiformats.multihash import digest
from PIL import Image
from datetime import datetime
from utils.http import url_from_path
from utils.ids import create_uuid
from utils.http import is_url, download_or_get_file
from utils.json import write_json
from utils.input_manifest import load_input_file
from utils.constants import (
    ENVITED_URL,
    MANIFEST_SCHEMA_VERSION,
    DID_ADRESS,
)

import argparse
import json
import shutil
import logging
import os

logger = logging.getLogger(__name__)


SCHEMA_MANIFEST_VERSION: str = "v2"

CATEGORIES = {
    "isSimulationData": [
        {
            "type": "Asset",
            "extensions": ["xodr", "xosc", "zip", "crg"],
            "folder": "simulation-data",
            "mask": "{name}",
            "role": "isOwner",
        }
    ],
    "isDocumentation": [
        {
            "type": "Document",
            "extensions": ["pdf", "txt", "md"],
            "folder": "documentation",
            "mask": "{name}_{file}",
            "role": "isPublic",
        }
    ],
    "isMedia": [
        {
            "type": "Image",
            "extensions": ["png", "jpeg"],
            "folder": "media",
            "mask": "{name}_impression-{number}",
            "role": "isPublic",
        },
        {
            "type": "Video",
            "extensions": ["mp4"],
            "folder": "media",
            "mask": "{name}",
            "role": "isPublic",
        },
        {
            "type": "3DPreview",
            "extensions": ["json"],
            "folder": "media/3d_preview",
            "mask": "{name}",
            "role": "isPublic",
        },
        {
            "type": "Routing",
            "extensions": ["geojson"],
            "folder": "media",
            "mask": "",
            "role": "isPublic",
        },
    ],
    "isMetadata": [
        {
            "type": "MetaData",
            "extensions": ["json"],
            "folder": "metadata",
            "mask": "domain_metadata",
            "role": "isPublic",
        }
    ],
    "isValidationReport": [
        {
            "type": "Validation",
            "extensions": ["xqar", "txt"],
            "folder": "validation-reports",
            "mask": "",
            "role": "isPublic",
        }
    ],
    "isLicense": [
        {
            "type": "License",
            "extensions": ["", "txt", "md"],
            "folder": "../",
            "mask": "LICENSE",
            "role": "isPublic",
        }
    ],
    "isMiscellaneous": [
        {
            "type": "Service",
            "extensions": ["bjson"],
            "folder": "metadata",
            "mask": "{name}",
            "role": "isRegistered",
        }
    ],
}

ASSET_TYPES = {
    "xodr": {
        "type": "HD-Map",
        "category": "HdMap",
        "classname": "hdmap",
        "link": "hd-map-asset-example",
    },
    "xosc": {
        "type": "Scenario",
        "category": "Scenario",
        "classname": "scenario",
        "link": "scenario-asset-example",
    },
    "zip": {
        "type": "environment-model",
        "category": "environment-model",
        "classname": "environment-model",
        "link": "environment-model-asset-example",
    },
    "crg": {
        "type": "surface-model",
        "category": "surface-model",
        "classname": "surface-model",
        "link": "surface-model-asset-example",
    },
}

MIME_TYPE = {
    "isManifest": {"json": "application/ld+json"},
    "isLicense": {"": "text/html"},
    "isSimulationData": {"": "application/x-{extension}"},
    "isMiscellaneous": {"bjson": "application/json"},
    "isDocumentation": {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "md": "text/markdown",
    },
    "isValidationReport": {"xqar": "application/x-xqar", "txt": "text/plain"},
    "isMetadata": {"json": "application/ld+json"},
    "isMedia": {
        "png": "image/png",
        "geojson": "application/x-geojson",
        "json": "application/json",
        "mp4": "video/mp4",
    },
}


# get data from category and type
def get_data_from_category_type(category: str, type: str) -> dict:
    if category in CATEGORIES:
        found_category = CATEGORIES[category]
        for data in found_category:
            if data["type"] == type:
                return data
    return None


# get data from folder and extension
def get_data_from_folder_extension(folder: str, extension: str) -> tuple[dict, str]:
    for key, category in CATEGORIES.items():
        for data in category:
            if folder in data["folder"]:
                for ext in data["extensions"]:
                    if extension == ext:
                        return data, key
    return None, None


# get file data from category
def get_file_data_from_category(file: Path) -> dict:
    extension = file.suffix.lstrip(".")  # Get file extension without the dot
    folder = file.parent.name

    data, key = get_data_from_folder_extension(folder, extension)
    if data:
        data["category"] = key
        return data

    return None


# get file data
def get_file_data(user_data, filename: Path) -> dict:
    for file in user_data:
        if file["filename"] == filename:
            return file
    return None


# get mime typ
def get_mime_type(category: str, extension: str) -> str:
    if category in MIME_TYPE:
        cat_data = MIME_TYPE[category]
        if extension in cat_data:
            mime_type_str = cat_data[extension]
        elif "" in cat_data:
            mime_type_str = cat_data[""]
        else:
            return None

        mime_type_str = mime_type_str.replace(r"{extension}", extension)
        return mime_type_str

    return None


# create and fill file_data element
def create_file_data(
    filename: Path, abs_data_path: Path, data_type: str, role: str, asset_info: dict
):
    file_data = {}
    file_data["manifest:hasAccessRole"] = "manifest:" + role
    file_data["manifest:hasCategory"] = "manifest:" + data_type
    file_meta_data = dict()
    file_data["manifest:hasFileMetadata"] = file_meta_data
    if is_url(filename):
        file_meta_data["manifest:filePath"] = url_from_path(filename)
        file_meta_data["manifest:mimeType"] = get_mime_type(data_type, "")
    else:
        relative_path = filename.relative_to(abs_data_path)

        if os.path.exists(filename) and data_type != "isManifest":
            file_meta_data["manifest:fileSize"] = os.path.getsize(filename.as_posix())
            creation_ts = filename.stat().st_ctime
            creation_dt = datetime.fromtimestamp(creation_ts)
            formatted_creation_data = creation_dt.isoformat(timespec="seconds")

            if data_type == "isSimulationData":
                if asset_info and "recordingTime" in asset_info:
                    formatted_creation_data = asset_info["recordingTime"]
                file_meta_data["manifest:timestamp"] = formatted_creation_data
            else:
                file_meta_data["manifest:timestamp"] = formatted_creation_data
            # create IPFS CIDv1 identifier
            with open(filename, "rb") as f:
                data = f.read()
            # create Multihash (SHA-256)
            mh = digest(data, "sha2-256")
            # create CIDv1 with code "raw"
            cid = CID("base32", 1, "raw", bytes(mh))
            # convert in Base32 coded string
            cid_str = cid.encode("base32")
            file_meta_data["manifest:cid"] = cid_str
            file_meta_data["manifest:filePath"] = "ipfs://" + cid_str

            if data_type == "isMedia" and filename.suffix.lstrip(".") == "png":
                img = Image.open(filename)
                width, height = img.size
                dimesion_group = {}
                dimesion_group["manifest:unit"] = "pixels"
                dimesion_group["manifest:width"] = str(width)
                dimesion_group["manifest:height"] = str(height)
                file_meta_data["manifest:hasDimensions"] = dimesion_group
        else:
            file_meta_data["manifest:filePath"] = "./" + relative_path.as_posix()

        file_meta_data["manifest:mimeType"] = get_mime_type(
            data_type, relative_path.suffix.lstrip(".")
        )

    return file_data


# regrister asset
def register_asset(
    data: dict,
    filename: Path,
    abs_data_path: Path,
    category: str,
    role: str,
    data_type=None,
):
    files = []
    files.append(create_file_data(filename, abs_data_path, category, role, None))
    if data_type:
        if data_type in data:
            data[data_type].extend(files)
        else:
            data[data_type] = files
    else:
        data.clear()
        data.update(files[0])


# register folder
def register_folder(
    data: list,
    user_data: dict,
    path: Path,
    abs_data_path: Path,
    asset_data: dict,
    asset_info: dict,
):
    if not path.exists():
        return

    for filename in path.rglob("*"):
        if filename.is_dir():
            continue

        file_data = get_file_data_from_category(filename)  # add from scripts
        if not file_data:
            continue

        category = file_data["category"]
        role = file_data["role"]

        # add to json data
        file_entry = create_file_data(
            filename, abs_data_path, category, role, asset_info
        )
        if category == "isMetadata":
            file_entry["manifest:iri"] = asset_info["did"]
            file_entry["skos:note"] = (
                f"This is the domain metadata for a {asset_data['type']}."
            )
            file_entry["sh:conformsTo"] = [
                f"{ENVITED_URL}{asset_data['classname']}/{SCHEMA_MANIFEST_VERSION}/ontology"
            ]

        data.append(file_entry)


# fill mask element
def fill_mask(filename: Path, file_data: dict, index: int) -> Path:
    return file_data["mask"]


# create filename
def create_filename(
    filename: Path, asset_name: Path, file_data: dict, index: int
) -> Path:
    basename = str(filename.stem)  # Name without extension

    mask = fill_mask(filename, file_data, index)

    if "{name}" in mask and "{file}" in mask:
        common_prefix = os.path.commonprefix([basename, asset_name])
        basename = basename[len(common_prefix) :].lstrip("_- ")
    mask = mask.replace(r"{name}", asset_name)
    mask = mask.replace(r"{file}", basename)

    basename = mask.replace(r"{number}", str(index).zfill(2))
    extension = filename.suffix

    filename_new = f"{basename}{extension}"
    return Path(filename_new)


# Helper function to safely retrieve nested keys from a dictionary.
# :param d: The dictionary to extract the value from.
# :param keys: A list of keys representing the path to the desired value.
# :param default: The value to return if a key in the path does not exist.
# :return: The value found at the end of the key path, or default if any key is missing.
def safe_get(data: dict, keys: str, default=None) -> dict:
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError):
            return default
    return data


# get name and description from domainMetadata.json file
def get_name_description_from_domainMetadata(filename, type):
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    name = safe_get(data, [f"{type}:hasResourceDescription", "gx:name"])
    if not name:
        logger.error(
            f"name : {type}:hasResourceDescription -> gx:name not exists in {filename}"
        )

    description = safe_get(data, [f"{type}:hasResourceDescription", "gx:description"])
    if not description:
        logger.error(
            f"description: {type}:hasResourceDescription -> gx:description not exists in {filename}"
        )

    return name, description


# get asset name and extension from user data
def get_asset(user_data: dict) -> tuple[str, str]:
    for file in user_data:
        if file["category"] == "isSimulationData" and file["type"] == "Asset":
            asset_name = Path(file["filename"])
            asset_extension = asset_name.suffix.lstrip(".")
            asset_name = asset_name.stem
            return asset_name, asset_extension
    return None, None


# get asset info (did, recordingTime)
def get_asset_info(asset_json: Path, asset_extractor: Path) -> dict:

    # load asset json
    if not asset_json.is_absolute():
        asset_json = asset_json.resolve()
    if not asset_json.exists():
        raise FileNotFoundError(f"asset file {asset_json} not exists")
    with open(asset_json, "r") as file:
        asset_json_data = json.load(file)
    asset_info = {}
    asset_info["did"] = asset_json_data["@id"]  # to get did

    # load asset extractor data
    if not asset_extractor.is_absolute():
        asset_extractor = asset_extractor.resolve()
    if not asset_extractor.exists():
        raise FileNotFoundError(f"asset file {asset_extractor} not exists")

    with open(asset_extractor, "r") as file:
        asset_extractor_data = json.load(file)

    if "recordingTime" in asset_extractor_data:
        asset_info["recordingTime"] = asset_extractor_data[
            "recordingTime"
        ]  # to get recordingTime

    return asset_info


def main():
    #  parse arguments
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="the folder structure is completed from the user info and a metadata table is created for the manifest",
    )
    parser.add_argument(
        "filename", help="filename of input_manifest.json or uploadedFiles.json."
    )
    parser.add_argument("-out", required=True, help="json file for manifest.")
    parser.add_argument("-path", required=True, help="path to copy/parse data.")
    parser.add_argument(
        "-asset_json",
        required=True,
        help="filename to final asset json. Required for DID",
    )
    parser.add_argument(
        "-asset_extractor",
        required=True,
        help="filename to temp asset json. Required for recording Time",
    )
    args = parser.parse_args()

    user_input_file = Path(args.filename)
    data_path = Path(args.path)
    filename_out = Path(args.out)

    if not user_input_file.is_absolute():
        user_input_file = user_input_file.resolve()
    if not user_input_file.exists():
        raise FileNotFoundError(f"json file {user_input_file} not exists")

    if not data_path.is_absolute():
        data_path = data_path.resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"data path {data_path} not exists")

    # read json (supports both input_manifest.json and legacy uploadedFiles.json)
    user_data = load_input_file(user_input_file)

    manifest_uuid = create_uuid()

    # get asset info (uuid, recordingTime)
    asset_json = Path(args.asset_json)
    asset_info = get_asset_info(asset_json, Path(args.asset_extractor))

    # initialize asset_name
    asset_name, asset_extension = get_asset(user_data)
    if not asset_name or not asset_extension:
        raise FileNotFoundError(f"no asset found in {file}")

    if asset_extension in ASSET_TYPES:
        asset_data = ASSET_TYPES[asset_extension]

    # copy files
    upload_folder = user_input_file.parent
    indexImage = 1
    license_data = None
    license_dest = None
    for file in user_data:
        filename = Path(file["filename"])

        # resolve relative paths against the upload folder
        if not filename.is_absolute():
            filename = upload_folder / filename

        # get cat, type data
        category = file["category"]
        typ = file["type"]
        cat_type_data = get_data_from_category_type(category, typ)
        if not cat_type_data:
            raise ValueError(f"type {typ} not found in category {category}")

        filename = download_or_get_file(filename, filename_out.parent)

        # get dest name
        dest_name = filename.name
        dest_name = create_filename(
            Path(dest_name), asset_name, cat_type_data, indexImage
        )
        if category == "isMedia" and typ == "Image":
            indexImage = indexImage + 1  # increase image index for image mask

        # destination filename
        dest = Path(data_path / cat_type_data["folder"])
        if not dest.exists():
            dest.mkdir(parents=True, exist_ok=True)
        dest = dest / dest_name
        dest = dest.resolve()
        # source filename
        source = upload_folder / filename
        source = source.resolve()
        # copy
        shutil.copy(source, dest)

        if category == "isLicense":
            license_data = file
            license_dest = dest

    # create json file for jsonLD creator
    data = {}
    data["did"] = DID_ADRESS + manifest_uuid
    data["shacl_schema"] = "Manifest"
    data["shacl_url"] = f"{ENVITED_URL}manifest/{MANIFEST_SCHEMA_VERSION}"
    data_group = []
    data["manifest:hasArtifacts"] = data_group
    for sub_folder in data_path.iterdir():
        relative_path = str(sub_folder.relative_to(data_path))
        if relative_path == "temp":
            continue
        register_folder(
            data_group, user_data, sub_folder, data_path, asset_data, asset_info
        )

    # register license
    if license_data is not None:
        licence_group = {}
        data["manifest:hasLicense"] = licence_group
        license_path = license_dest if license_dest else Path(license_data["filename"])
        license_base = data_path.parent if license_dest else data_path
        register_asset(
            licence_group,
            license_path,
            license_base,
            "isLicense",
            "isPublic",
        )

    # register manifest
    manifest_group = {}
    data["manifest:hasManifestReference"] = manifest_group
    register_asset(
        manifest_group,
        data_path / "manifest.json",
        data_path,
        "isManifest",
        "isPublic",
    )

    path = filename_out.parent
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    # create readme
    if asset_extension in ASSET_TYPES:
        classname = ASSET_TYPES[asset_extension]["classname"]
        domainMetadata = filename_out.parent.parent / f"metadata/{classname}.json"
        name, description = get_name_description_from_domainMetadata(
            domainMetadata, classname.lower()
        )
        if name and description:
            readme_file = filename_out.parent.parent / "README.md"
            readme_file.write_text(
                f"# {name}\n\n{description}\n\n"
                f"This asset conforms to [EVES-003]"
                f"(https://ascs-ev.github.io/EVES/EVES-003/eves-003.html).\n",
                encoding="utf-8",
            )

    # write metadata json
    write_json(filename_out, data)

    # replace with uuid in json
    asset_content = asset_json.read_text(encoding="utf-8")
    asset_content = asset_content.replace("Manifest:uuid", f"Manifest:{manifest_uuid}")
    asset_json.write_text(asset_content, encoding="utf-8")


if __name__ == "__main__":
    main()
