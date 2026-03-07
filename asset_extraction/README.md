# asset_extraction

## Description
Main pipeline entrypoint. It executes configured extractor/creator modules and builds the final `asset.zip`.

## Usage
```bash
python -m asset_extraction.main <uploaded_files.json> -config <config_dir> -out <output_dir>
```

## Arguments
- `filename` (required): Path to the frontend `uploadedFiles.json`.
- `-config` (required): Path to the pipeline/module configuration directory.
- `-out` (required): Output directory where the asset subfolder and archive are created.

## Input
- Uploaded files metadata JSON (`uploadedFiles.json`)
- Configuration directory (for example `./configs`)

## Output
- Asset working folder with generated artifacts
- `asset.zip` inside the asset folder

## Install
```bash
python -m pip install -r asset_extraction/requirements.txt
```
