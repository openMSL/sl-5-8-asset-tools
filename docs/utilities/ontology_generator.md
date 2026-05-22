---
title: ontology_generator
---

# ontology_generator

## Description

Generates ontology (`.owl/.ttl`) and shacl shape files from an Excel metadata table.

## Usage

```bash
python -m ontology_generator.main [-table <Metadata.xlsx>] [-out <ontologies/>] [-url <base_url>]
```

## Arguments

- `-table` (optional, default: `Metadata.xlsx`): Path to the input Excel table.
- `-out`, `--out` (optional, default: `ontologies/`): Output directory for generated files.
- `-url`, `--url` (optional): Base URL embedded in generated ontology references.

## Input

- Excel table containing metadata/schema definitions

## Output

- Generated ontology and shacl files

## Install

```bash
make install  # from repository root
```
