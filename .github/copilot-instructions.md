# sl-5-8-asset-tools — Copilot Instructions

## Project Overview

This repository contains **tools to analyze, transform, and package simulation asset data** into EVES-003 conformant `asset.zip` archives for the ENVITED-X Dataspace / marketplace workflows. It is primarily used by the asset service pipeline in [sl-5-7-asset-services](https://github.com/openMSL/sl-5-7-asset-services).

## Supported Formats

- **ASAM OpenDRIVE** (`.xodr`) → asset type: `hdmap`
- **ASAM OpenSCENARIO XML** (`.xosc`) → asset type: `scenario`
- **3D environment models** (`.zip`, `.7z`) → asset type: `environment-model`

## Repository Structure

### Pipeline Modules (executed in order by `pipeline`)

| Module | Purpose | Enabled | Extensions |
|--------|---------|---------|------------|
| `pipeline/` | Pipeline entrypoint & orchestrator | — | all |
| `metadata_extractor/` | Extracts metadata from asset files (format, content, quantity, georeference) | ✅ | xodr, xosc |
| `jsonld_creator/` | Creates JSON-LD instances from extracted attribute JSON + SHACL ontologies | ✅ | xodr, xosc, 3dmodel |
| `shacl_combiner/` | Combines referenced SHACL shapes into a single `.ttl` file | ✅ | all |
| `wizard/` | SHACL-driven CLI wizard for enriching JSON-LD interactively (disabled via `-enable false` by default) | ✅* | all |
| `jsonld_validator/` | Legacy JSON-LD validator (replaced by ontology-management-base in pipeline) | ❌ | — |
| `quality_checker/` | Runs ASAM/OpenMSL quality checkers, produces `.xqar` + text reports | ✅ | xodr, xosc |
| `geojson_creator/` | Generates GeoJSON road network geometry + bounding box from OpenDRIVE | ✅ | xodr |
| `preview_3d/` | Pure-Python OpenDRIVE → GeoJSON 3D preview converter (reimplements VCS opendriveconverter) | ✅ | xodr |
| `search_indexer/` | Reduces XML to binary JSON (`.bjson`) for search indexing | ✅ | xodr |
| `packager/` | Builds final folder structure, renames files, generates manifest attribute JSON + README | ✅ | all |

### Standalone / Utility Modules

| Module | Purpose |
|--------|---------|
| `utils/` | Shared helpers: logging, subprocess, JSON/RDF I/O, geometry, constants |
| `xodr_calc_box/` | Standalone bounding box calculator for OpenDRIVE files |
| `xodr_trim_to_box/` | Trim OpenDRIVE files to a geographic bounding box |
| `ontology_generator/` | Generate OWL ontologies + SHACL shapes from Excel metadata tables |
| `submodules/ontology-management-base/` | Git submodule: SHACL shapes, OWL ontologies, validation tools |

### Configuration

All pipeline behavior is configured through files in `configs/`:

- **`process.json`** — Defines module execution order, enable/disable flags, and supported file extensions per module
- **`config_<module>.json`** — Per-module configuration with call parameters, input/output paths, and placeholders

#### Supported Config Placeholders

| Placeholder | Expands to |
|-------------|------------|
| `{path}` | Output directory path |
| `{sub_path}` | Target data subfolder (from config `"data folder"`) |
| `{name}` | Asset filename stem (no extension) |
| `{asset_path}` | Full path to asset file |
| `{asset_type}` | Asset type string (`hdmap`, `scenario`, `environment-model`) |

## Setup & Build

Python 3.12+ required.

```bash
make setup
```

All commands are exposed via `make` targets -- run `make help` for the full list.

## Usage

### Run Examples

```bash
make run opendrive
make run openscenario
```

## Pipeline Flow (OpenDRIVE / HD Map)

```
input_manifest.json
  → metadata_extractor     → temp/{name}_extractor.json
  → jsonld_creator           → temp/hdmap.json
  → shacl_combiner           → temp/hdmap.ttl
  → wizard (disabled) → metadata/hdmap.json (interactive SHACL-guided prompts or copy)
  → jsonld_validator_omb     → validation pass/fail
  → qualitychecker (ASAM)    → validation-reports/{name}_asam_cb_xodr.xqar
  → qualitychecker (OpenMSL) → validation-reports/{name}_openmsl_cb_xodr.xqar
  → geojson_creator     → media/roadNetwork.geojson + media/bbox.geojson
  → preview_3d   → media/3d_preview/*.json (road/lane/object GeoJSON)
  → search_indexer             → metadata/{name}.bjson
  → packager         → temp/{name}_structure.json (+ organizes files)
  → jsonld_creator            → manifest.json
  → jsonld_validator_omb     → final validation
  → create asset.zip
```

## Output Asset Structure (EVES-003)

```
<asset_name>/
├── manifest.json
├── README.md
├── simulation-data/          (isOwner)
│   └── {name}.xodr
├── metadata/                 (isPublic / isRegistered)
│   ├── hdmap.json             (domain metadata)
│   └── {name}.bjson          (reduced binary for indexing)
├── media/                    (isPublic)
│   ├── roadNetwork.geojson
│   ├── bbox.geojson
│   ├── {name}_impression-01.png
│   └── 3d_preview/*.json
├── documentation/            (isPublic)
│   └── {name}_documentation.pdf
├── validation-reports/       (isPublic)
│   ├── {name}_asam_cb_xodr.xqar
│   └── {name}_openmsl_cb_xodr.xqar
└── LICENSE
```

## Key Conventions

- **Ontology sources**: ENVITED-X (`https://w3id.org/ascs-ev/envited-x/{schema}/v6`) and GAIA-X base (`ontology-management-base`)
- **JSON-LD metadata** uses typed `@value`/`@type` pairs, `@context` prefixes (`hdmap:`, `manifest:`, `georeference:`, `gx:`)
- **IPFS CIDv1 hashes** (SHA-256, Base32) are computed for each file and stored in the manifest
- **Access roles**: `isOwner` (simulation data), `isPublic` (media, docs, reports), `isRegistered` (services)
- **Quality checkers** require external executables (`qc_opendrive`, `openmsl_qc_opendrive`) to be installed

## Developer Checks

```bash
make help              # Show all available commands
make setup             # Create venv and install all dependencies
make install           # Reinstall all dependencies (dev, QC, OMB)
make lint              # Lint checks (ruff)
make format            # Format Python (ruff)
make check             # Run all checks (format, compile, readme style)
make check format      # Check formatting only
make check py          # Compile-check all Python files
make check readme      # Validate README structure
make validate          # Run SHACL data conformance validation
make generate opendrive     # Run OpenDRIVE example pipeline
make generate openscenario  # Run OpenSCENARIO example pipeline
make clean             # Remove build artifacts and caches
```
