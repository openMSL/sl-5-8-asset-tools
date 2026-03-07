# meta_data_extractor

## Description
Extracts metadata from supported asset files and writes an attribute JSON used by `jsonLD_creator`.

Supported formats:
- ASAM OpenDRIVE (`.xodr`)
- ASAM OpenSCENARIO XML (`.xosc`)
- 3D environment model data

## Usage
```bash
python -m meta_data_extractor.main <asset_file> -out <output.json> [-u]
```

## Arguments
- `filename` (required): Input asset file.
- `-out`, `--output` (required): Output metadata attribute JSON.
- `-u`, `--user_input` (optional): Enables interactive prompts for non-extractable attributes.

## Input
- Asset file

## Output
- Metadata attribute JSON

## Install
```bash
python -m pip install -r meta_data_extractor/requirements.txt
```
