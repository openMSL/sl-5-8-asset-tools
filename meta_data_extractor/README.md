# meta_data_extractor

## Description
Extracts metadata from supported asset files and writes an attribute JSON used by `jsonLD_creator`.

Supported formats:
- ASAM OpenDRIVE (`.xodr`)
- ASAM OpenSCENARIO XML (`.xosc`)
- 3D environment model statistics (`statistic_3dModel.json`) when called with `-format 3dmodel`

## Usage
```bash
python -m meta_data_extractor.main <asset_file> -out <output.json> [-u] [-format <name>]
```

## Arguments
- `filename` (required): Input asset file.
- `-out`, `--output` (required): Output metadata attribute JSON.
- `-u`, `--user_input` (optional): Enables interactive prompts for non-extractable attributes.
- `-format` (optional): Explicit extractor override. Use `3dmodel` for `statistic_3dModel.json`.

## Input
- Asset file

## Output
- Metadata attribute JSON

## Install
```bash
make install  # from repository root
```
