---
title: structure_creator
---

# structure_creator

## Description

Builds the asset folder/file structure from frontend metadata and creates a manifest attribute JSON for downstream JSON-LD generation.

## Usage

```bash
python -m structure_creator.main <input_manifest.json> -out <structure.json> -path <asset_dir> -asset_json <asset_instance.json> -asset_extractor <extractor.json>
```

## Arguments

- `filename` (required): Path to `input_manifest.json`.
- `-out` (required): Output JSON file for generated manifest structure data.
- `-path` (required): Target asset directory used for copy/organization.
- `-asset_json` (required): Asset JSON-LD file path (used for DID update).
- `-asset_extractor` (required): Extractor JSON path (used for metadata enrichment).

## Input

- Frontend metadata JSON
- Existing generated metadata files

## Output

- Organized asset folder structure
- Structure JSON for manifest creation

## Install

```bash
make install  # from repository root
```
