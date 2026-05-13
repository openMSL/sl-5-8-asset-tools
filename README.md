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
- [openlabel_creator](openlabel_creator/README.md): Creates OpenLABEL JSON from scenario metadata.
- [shacl_combiner](shacl_combiner/README.md): Combines required shacl shapes.
- [llm_enricher](llm_enricher/README.md): Rule-based metadata enrichment for empty fields (disabled by default).
- [wizard_caller](wizard_caller/README.md): SHACL-driven CLI wizard for enriching JSON-LD interactively (disabled via config by default).
- [jsonLD_validator](jsonLD_validator/README.md): Legacy validator (replaced by ontology-management-base in pipeline).
- [qualitychecker_caller](qualitychecker_caller/README.md): Runs ASAM/OpenMSL quality checkers.
- [xodr_routing_creator](xodr_routing_creator/README.md): Generates route and bounding box GeoJSON for georeferenced OpenDRIVE files. Non-georeferenced files are skipped.
- [xodr_to_geojson_caller](xodr_to_geojson_caller/README.md): Pure-Python OpenDRIVE to GeoJSON 3D preview converter (disabled by default; enable via `-enable vcs_odr-converter`).
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

- `path`: output base directory
- `sub_path`: target data subfolder
- `name`: asset filename stem
- `asset_path`: directory containing the input manifest
- `asset_type`: asset domain type (`hdmap`, `scenario`, `environment-model`)

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
make generate opendrive      # OpenDRIVE example  → examples/assets/
make generate openscenario   # OpenSCENARIO example → examples/assets/
```

### Batch Processing

Process all input manifests under the `examples/` directory tree in a single
command.  HD-map inputs are processed before scenarios so cross-references
resolve correctly:

```bash
make generate batch
```

### Selective Module Execution

Individual pipeline modules can be enabled or disabled at runtime using the
`PIPELINE_FLAGS` variable:

```bash
# Skip a specific module
make generate opendrive PIPELINE_FLAGS="-disable xodr_routing_creator"

# Run only specific modules (whitelist)
make generate opendrive PIPELINE_FLAGS="-enable meta_data_extractor structure_creator"

# Enable GeoJSON 3D preview generation (disabled by default)
make generate opendrive PIPELINE_FLAGS="-enable vcs_odr-converter"

# List available module IDs
make generate opendrive PIPELINE_FLAGS="-list-modules"
```

When calling the pipeline directly:

```bash
python -m asset_extraction.main input.json -config configs -out ./out -disable vcs_odr-converter
python -m asset_extraction.main -config configs -list-modules
```

### Run Pipeline for a Custom Input Directory

```bash
make generate INPUT_DIR=path/to/input
```

`OUTPUT_DIR` defaults to `examples/assets/`.
Override explicitly if needed:

```bash
make generate INPUT_DIR=path/to/input OUTPUT_DIR=/tmp/my-output
```

The `INPUT_DIR` must contain an `input_manifest.json`. This is the mode used by downstream asset repositories (e.g. `hd-map-asset-example`) to delegate pipeline execution.

Each input example follows this convention:

- `examples/<source>/<name>/<type>/` — input manifest, simulation data, media, docs, LICENSE
- `examples/assets/` — pipeline-generated EVES-003 assets (gitignored)

By default the pipeline uses concise, stage-oriented logging. To inspect raw
child command lines and full stdout/stderr, set `SL58_LOG_MODE=debug` before
running `make generate ...`.

PowerShell example:

```powershell
$env:SL58_LOG_MODE = "debug"
make generate opendrive
```

## Input Manifest

### Generating a Manifest Automatically

If you don't have an `input_manifest.json` yet, generate one from your files:

```bash
make init INPUT_DIR=path/to/my-asset
```

This scans the directory for simulation data (`.xodr`, `.xosc`, `.zip`, `.7z`),
documentation, media, and license files, then writes an `input_manifest.json`
ready for the pipeline.  Review and edit the generated file if needed, then run:

```bash
make generate INPUT_DIR=path/to/my-asset
```

Use `FORCE=true` to overwrite an existing manifest.

### Manifest Format

The pipeline accepts an `input_manifest.json` (JSON-LD) that describes the asset
files, their categories and access roles.

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

## SD Creation Wizard

The SD Creation Wizard provides a browser-based UI for interactive metadata
enrichment. It parses SHACL ontology shapes into dynamic forms, pre-fills them
with auto-extracted values, and lets users complete any missing fields before
the pipeline continues.

### Prerequisites

- Node.js 20+ and pnpm (installed automatically via corepack)
- Installed automatically by `make setup` (if Node.js is available)

### Interactive Pipeline Usage (Recommended)

The simplest way to use the wizard — just add `WIZARD=true`:

```bash
WIZARD=true make generate INPUT_DIR=examples/ika/SCEN-95B774BAC0A9/hdmap
```

This runs the full pipeline and at the wizard step:

1. Auto-starts the wizard API + frontend (if not already running)
2. Opens your browser with a form pre-filled from extracted metadata
3. Pauses the pipeline until you click **Export**
4. Writes the enriched metadata and continues the pipeline

No separate `make wizard` step needed — everything is automatic.

### Manual Server Management

```bash
make wizard            # start the wizard API + frontend manually
make wizard stop       # stop the wizard servers
make setup wizard      # reinstall wizard dependencies
```

### CLI Mode (Non-Interactive)

Without `WIZARD=true`, the wizard step simply copies JSON-LD unchanged
(disabled by default in config). For terminal-based prompts:

```bash
python -m wizard_caller.main metadata/hdmap.json -shacl temp/hdmap.ttl -enable true -out metadata/hdmap.json
```

### Architecture

| Service  | URL                    | Purpose |
|----------|------------------------|---------|
| API      | <http://localhost:3007> | SHACL parsing, session management |
| Frontend | <http://localhost:5174> | React wizard UI |

Ports are configurable via `.env` (see `.env.example`):

```env
WIZARD_API_PORT=3007
WIZARD_FRONTEND_PORT=5174
```

## Metadata Review

Review existing generated assets interactively.  `make review` runs two phases:

1. **Enrichment** — `llm_enricher` fills empty metadata fields using rule-based inference and records provenance (method + confidence) in `*_provenance.json` files.
2. **Wizard review** — Enriched assets are queued in the SD Creation Wizard for human verification. The wizard pre-fills forms from the existing JSON-LD and highlights inferred values.

Re-zips any assets whose metadata changed after review:

```bash
make review                            # review all assets in examples/assets/
make review REVIEW_DIR=path/to/assets  # review assets in a custom directory
```

### How It Differs from Validate

| Command | Purpose | Automated | Modifies assets |
|---------|---------|-----------|-----------------|
| `make validate` | SHACL schema conformance check | Yes (read-only) | No |
| `make review` | Human metadata review via wizard | Interactive | Yes (re-zips on change) |

Use `validate` to verify structural correctness.  Use `review` to verify
semantic completeness and accuracy with a human in the loop.

## Notes

- For module-specific usage and parameters, see each module README linked above.
