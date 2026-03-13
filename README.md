# Asset Tools

## Overview

This repository contains tools to analyze, transform, and package asset data into CID-named `.zip` archives for marketplace workflows (for example Envited Marketplace).

The tools are primarily used by the asset service pipeline in:

- <https://github.com/openMSL/sl-5-7-asset-services>

## Supported Formats

- ASAM OpenDRIVE (`.xodr`)
- ASAM OpenSCENARIO XML (`.xosc`)
- 3D environment model archives (`.zip`, `.7z`) with a companion `statistic_3dModel.json` metadata file in the same input folder

## Pipeline Modules

The following modules are used in the asset archive pipeline.

- [asset_extraction](asset_extraction/README.md): Pipeline entrypoint and orchestrator.
- [meta_data_extractor](meta_data_extractor/README.md): Extracts metadata from asset files.
- [jsonLD_creator](jsonLD_creator/README.md): Creates JSON-LD from attribute JSON.
- [shacl_combiner](shacl_combiner/README.md): Combines required shacl shapes.
- [wizard_caller](wizard_caller/README.md): SHACL-driven CLI wizard for enriching JSON-LD interactively (disabled via config by default).
- [jsonLD_validator](jsonLD_validator/README.md): Legacy validator (replaced by ontology-management-base in pipeline).
- [qualitychecker_caller](qualitychecker_caller/README.md): Runs ASAM/OpenMSL quality checkers.
- [xodr_routing_creator](xodr_routing_creator/README.md): Generates route and bounding box geometry.
- [xodr_to_geojson_caller](xodr_to_geojson_caller/README.md): Pure-Python OpenDRIVE to GeoJSON 3D preview converter.
- [asset_reducer](asset_reducer/README.md): Reduces XML asset data for search indexing.
- [structure_creator](structure_creator/README.md): Builds final archive structure and manifest input.

## Additional Modules

- [utils](utils/README.md): Shared helper modules.
- [xodr_calc_box](xodr_calc_box/README.md): Bounding box calculation helper.
- [xodr_trim_to_box](xodr_trim_to_box/README.md): Trim OpenDRIVE by bounding box.
- [ontologie_creator](ontologie_creator/README.md): Generate ontology/shacl from Excel table.

## Process Diagram

![AssetExtractor process](AssetExtractor_process.png)

## Configuration

Pipeline behavior is configured through files in [`configs/`](configs).

There are two configuration types:

1. `process.json`

- Defines module order and activation flags.
- Each item contains:
  - `enable`: activate/deactivate module
  - `filename`: module config filename
  - `extensions`: supported asset extensions

1. Module-specific config (for example `config_meta_data_extractor.json`)

- Defines concrete call parameters for a module.
- Core fields:
  - `name`
  - `environment type`
  - `data folder`
  - `params` (`call`, `input`, `output`, `additional`)

Supported placeholders:

- `path`: path of input file
- `sub_path`: target data subfolder
- `name`: asset filename stem
- `asset_path`: full asset path
- `asset_type`: asset extension

Example:

```json
{
  "name": "xodr_routing_creator",
  "environment type": "python",
  "data folder": "media",
  "params": {
    "call": "xodr_routing_creator.main",
    "output": {
      "-out": "{path}/{sub_path}/roadNetwork.geojson"
    },
    "additional": {
      "-box": "{path}/{sub_path}/bbox.geojson"
    }
  }
}
```

## Build

Python 3.12+ is required.

```bash
git clone https://github.com/openMSL/sl-5-8-asset-tools.git
cd sl-5-8-asset-tools
make setup
```

All dependencies are managed via `pyproject.toml` and installed automatically by `make setup`.
When run from a git checkout, `make setup` also initializes and updates the configured git submodules automatically. Cloning with `--recurse-submodules` still works, but is no longer required.

On Windows, run `make` from Git Bash or another POSIX `sh`-compatible shell.

Run `make help` for the full list of available commands.

## Usage

### Run Example Pipelines

Two ready-to-run examples are included under `examples/`:

```bash
make generate opendrive      # OpenDRIVE example  → examples/OpenDRIVE/output/ + examples/OpenDRIVE/<CID>.zip
make generate openscenario   # OpenSCENARIO example → examples/OpenSCENARIO/output/ + examples/OpenSCENARIO/<CID>.zip
```

Each example follows the `input/` → `output/` convention:

- `examples/<name>/input/` — input manifest, simulation data, media, docs, LICENSE
- `examples/<name>/output/` — pipeline-generated EVES-003 asset (gitignored)

By default the pipeline uses concise, stage-oriented logging. To inspect raw
child command lines and full stdout/stderr, set `SL58_LOG_MODE=debug` before
running `make generate ...`.

PowerShell example:

```powershell
$env:SL58_LOG_MODE = "debug"
make generate opendrive
```

## Input Manifest

The pipeline accepts an `input_manifest.json` (JSON-LD) that describes the asset
files, their categories and access roles.  A legacy `uploadedFiles.json` array
format is also supported for backward compatibility.

Minimal `input_manifest.json` example:

```json
{
  "@context": [
    "https://w3id.org/ascs-ev/envited-x/manifest/v5/",
    { "envited-x": "https://w3id.org/ascs-ev/envited-x/envited-x/v3/" }
  ],
  "@id": "did:key:z6Mk...",
  "@type": "envited-x:Manifest",
  "hasArtifacts": [
    {
      "@type": "Link",
      "hasCategory": { "@id": "envited-x:isSimulationData" },
      "hasAccessRole": { "@id": "envited-x:isOwner" },
      "hasFileMetadata": {
        "@type": "FileMetadata",
        "filePath": "my-road.xodr",
        "mimeType": "application/xml"
      }
    }
  ],
  "hasLicense": {
    "@type": "Link",
    "hasCategory": { "@id": "envited-x:isLicense" },
    "hasAccessRole": { "@id": "envited-x:isPublic" },
    "hasFileMetadata": {
      "@type": "FileMetadata",
      "filePath": "LICENSE",
      "mimeType": "text/plain"
    }
  }
}
```

Supported categories:

- `isSimulationData`, `isDocumentation`, `isMedia`, `isMetadata`
- `isValidationReport`, `isLicense`, `isMiscellaneous`

## Notes

- On Linux, `qualitychecker_caller` may require additional runtime libraries for `TextReport`.
- For module-specific usage and parameters, see each module README linked above.
