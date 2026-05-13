# Quick Start

This guide walks through generating your first EVES-003 asset archive.

## 1. Run the Example Pipeline

The fastest way to try the tools:

```bash
make generate opendrive
```

This processes the included OpenDRIVE example and creates an asset archive
under `examples/assets/`.

For OpenSCENARIO:

```bash
make generate openscenario
```

## 2. Process Your Own Files

### Generate an Input Manifest

Place your asset files (simulation data, documentation, media, LICENSE) in a
directory and generate the manifest:

```bash
make init INPUT_DIR=path/to/my-asset
```

This scans the directory and creates an `input_manifest.json` with:

- Simulation data (`.xodr`, `.xosc`, `.zip`, `.7z`) → `isSimulationData`
- Documentation (`.pdf`, `.txt`, `.md`) → `isDocumentation`
- Media (`.jpg`, `.png`, `.svg`) → `isMedia`
- LICENSE files → `isLicense`

Review and edit the manifest if needed, then run the pipeline:

```bash
make generate INPUT_DIR=path/to/my-asset
```

### Custom Output Directory

```bash
make generate INPUT_DIR=path/to/input OUTPUT_DIR=/tmp/my-output
```

## 3. Validate the Output

```bash
make validate
```

This runs SHACL conformance validation on all generated assets.

## 4. Batch Processing

Process all input manifests under `examples/` at once:

```bash
make generate batch
```

HD-map inputs are processed before scenarios so cross-references resolve
correctly.

## 5. Interactive Metadata Review

Use the SD Creation Wizard for human-in-the-loop metadata enrichment:

```bash
WIZARD=true make generate INPUT_DIR=path/to/my-asset
```

Or review already-generated assets:

```bash
make review
```

## Pipeline Module Flags

Skip or enable specific modules at runtime:

```bash
# Skip a module
make generate opendrive PIPELINE_FLAGS="-disable xodr_routing_creator"

# Run only specific modules
make generate opendrive PIPELINE_FLAGS="-enable meta_data_extractor structure_creator"

# Enable GeoJSON 3D preview (disabled by default)
make generate opendrive PIPELINE_FLAGS="-enable vcs_odr-converter"

# List available module IDs
make generate opendrive PIPELINE_FLAGS="-list-modules"
```

## Debug Logging

For verbose output including raw subprocess commands:

```bash
SL58_LOG_MODE=debug make generate opendrive
```
