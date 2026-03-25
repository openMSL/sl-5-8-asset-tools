# asset_extraction

## Description

Main pipeline entrypoint. It executes configured extractor/creator modules, builds a temporary `asset.zip`, computes its CID, and renames the final archive to `<CID>.zip`.

## Usage

```bash
python -m asset_extraction.main <input_manifest.json> -config <config_dir> -out <output_dir> [-zip-dir <archive_dir>]
```

## Arguments

- `filename` (required): Path to `input_manifest.json`.
- `-config` (required): Path to the pipeline/module configuration directory.
- `-out` (required): Output directory where the asset subfolder and archive are created.
- `-zip-dir` (optional): Directory where the temporary `asset.zip` is written and then renamed to `<CID>.zip`. Defaults to `-out`.

## Input

- JSON-LD input manifest (`input_manifest.json`)
- Configuration directory (for example `./configs`)
- For 3D environment model assets, place the companion `statistic_3dModel.json` next to the uploaded `.zip`/`.7z` archive.

## Output

- Asset working folder with generated artifacts
- CID-named archive (`<CID>.zip`) in `-zip-dir` or, by default, in `-out`

## Install

```bash
make install  # from repository root
```
