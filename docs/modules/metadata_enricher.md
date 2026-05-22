---
title: metadata_enricher
---

# metadata_enricher

## Description

Rule-based metadata enrichment for empty fields in generated JSON-LD.
Analyzes asset content and SHACL vocabulary to infer missing values
with confidence tracking. Records provenance (method + confidence) in
a companion `*_provenance.json` file.

Disabled by default in the pipeline (`process.json`). Used by
`make review` for metadata quality improvement before human verification.

## Usage

```bash
# Evaluate metadata completeness across all assets (read-only)
python -m metadata_enricher evaluate examples/assets

# Enrich a single asset's metadata
python -m metadata_enricher enrich examples/assets/StraightRoad_NCAP_Roadmarks
```

## Arguments

- `evaluate <assets_dir>`: Analyze completeness without modification.
- `enrich <asset_dir>`: Fill empty metadata fields and write enriched copy.
- `--output-path`: Override output file path.
- `--asset-type`: Asset type (`hdmap`, `scenario`).
- `--source-dir`: Source directory for context analysis.

## Input

- Asset directory with `metadata/<type>.json` (JSON-LD)
- SHACL ontology shapes from `submodules/ontology-management-base/artifacts`

## Output

- Enriched `metadata/<type>.json`
- `metadata/<type>_provenance.json` with per-field method and confidence

## Install

```bash
make install  # from repository root
```
