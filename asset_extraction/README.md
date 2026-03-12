# asset_extraction

## Description
Main pipeline entrypoint. It executes configured extractor/creator modules and builds the final `asset.zip`.

## Usage
```bash
python -m asset_extraction.main <input_manifest.json|uploadedFiles.json> -config <config_dir> -out <output_dir>
```

## Arguments
- `filename` (required): Path to `input_manifest.json` or legacy `uploadedFiles.json`.
- `-config` (required): Path to the pipeline/module configuration directory.
- `-out` (required): Output directory where the asset subfolder and archive are created.

## Input
- JSON-LD input manifest (`input_manifest.json`) or legacy uploaded files metadata (`uploadedFiles.json`)
- Configuration directory (for example `./configs`)
- For 3D environment model assets, place the companion `statistic_3dModel.json` next to the uploaded `.zip`/`.7z` archive.

## Output
- Asset working folder with generated artifacts
- `asset.zip` inside the asset folder

## Install
```bash
make install  # from repository root
```
